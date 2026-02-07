from handlers.ui_messaging import MsgStreamerUI as msg_ui
from db_ops.app import AppDB
from handlers.user_interface import UserInterfaceHandler
from core.user_config_manager import user_config_manager
from core.utils.time_utils import get_current_timestamp, get_reference_timestamp
from core.utils.schema_utils import inline_refs
from core.logger_config import logger
from inference.providers.anthropic_client import anthropic_client
from anthropic.types import MessageParam
from anthropic import AsyncMessageStreamManager
from core.constants import InputSourceType
from core.app_config import ClaudeConfig
from core.event_manager import event_manager
from agent_tools.mcp_client import get_global_mcp_client
from handlers.image_generation import image_orchestrator
from core.memory_worker import memory_worker
from common.models import ToolResult, ImageRequest
from inference.prompt_builder import PromptBuilder
from db_ops.agent import AgentDB
from core.app_config import AppConfig
from datetime import timedelta
import asyncio
import json
from inference.internal_message_models import (
    MessageFromUser,
    MessageFromApp,
    ResponseFromTool,
    ResponseFromAI,
    TextBlock,
)

CACHE_CONTROL_FLAG = {
    'cache_control' : {'type' : 'ephemeral'}
}

class StreamHandler:
    '''
        Handles Claude stream events for the inference engine.
        Streams response + thinking to the frontend and ignores everything else,
        then it returns the final message.
    '''

    @staticmethod
    async def process_stream(stream: AsyncMessageStreamManager, stream_thinking=False) -> str:
        '''
            Handles operations that should be triggered for streamed events.
            Returns final message
        '''
        async for event in stream:
            # Start block
            if event.type == "content_block_start":
                block_type = event.content_block.type
                if block_type == "thinking":
                    await msg_ui.show_agent_thinking()
                elif block_type == "text":
                    await msg_ui.start_agent_response()
                elif block_type == 'tool_use':
                    # Display thinking icon for tool use blocks so it doesn't look
                    # like the agent hangs while the full block is streamed
                    await msg_ui.show_agent_thinking()

            # Block delta
            elif event.type == "content_block_delta":
                delta_type = event.delta.type

                # Extract the actual text chunk based on delta type
                if delta_type == "thinking_delta" and stream_thinking:
                    await msg_ui.update_agent_thinking(event.delta.thinking)
                elif delta_type == "text_delta":
                    await msg_ui.update_agent_response(event.delta.text)

        final_message = await stream.get_final_message()
        return final_message

class AgentInferenceEngine:
    '''
        Core inference engine for the AI agent.
    '''
    def __init__(self):
        self._cached_tool_schemas = None

    async def run_inference(self, messages: list[str], source: InputSourceType) -> None:
        """ Starting point for agent inference, prepares message history, injects
            state information, and calls _run_inference_until_end_turn() to handle
            tool loops until the LLM indicates end of turn.
        """
        # Input mode shows a flashing icon to represent message buffer being flushed
        await self._notify_ui_buffers_flushed(source)
        await msg_ui.show_agent_thinking()

        # Get all previous messages and current state info
        cutoff_time = get_reference_timestamp(AppConfig.DEFAULT_TIMERANGE_MS)
        msg_history_for_llm = await AgentDB.recent_messages_for_state(cutoff_time)
        state_snapshot = await UserInterfaceHandler.get_board_state()

        # Save user message to DB with state snapshot
        await AppDB.save_messages_from_user(messages, source, state_snapshot)

        # Inject state into current message blocks
        state_str = await self._get_state_snapshot(source)
        messages.append(state_str)

        # Append current message to messages for LLM
        user_msg_obj = MessageFromUser(messages)
        msg_to_llm = user_msg_obj.get_message_for_llm()
        msg_history_for_llm.append(msg_to_llm)

        # Call inner loop
        await self._run_inference_until_end_turn(msg_history_for_llm)

        # Signal that inference is complete
        await event_manager.notify_inference_completed()

    async def _run_inference_until_end_turn(self, message_history: list[dict]):
        """Inner loop that handles tool calls until end_turn."""
        # Initial call to LLM
        ai_response = await self._call_claude(message_history)

        # Buffer our current messages for inner loop stability
        loop_messages = message_history.copy()

        # Inform image orchestrator of new batch group (for async image gen callbacks)
        image_orchestrator.start_batch()        

        # Keep processing tool calls until end turn
        while ai_response.get_stop_reason() != 'end_turn':
            # Display thinking icon between calls
            await msg_ui.show_agent_thinking()

            # Tool calls
            if ai_response.get_stop_reason() == "tool_use":
                # Save AI response to DB (save at every call, not while streaming)
                await AppDB.save_ai_response(ai_response)

                # Add assistant message to loop history (for LLM)
                loop_messages.append(ai_response.get_message_for_llm())

                # Execute all tool calls and capture timestamps
                tool_requests = ai_response.get_tool_requests()
                tool_blocks = []
                tool_timestampss = []
                for tool_req in tool_requests:
                    tool_name = tool_req.name
                    tool_input = tool_req.input
                    tool_id = tool_req.id
                    tool_timestamps = get_current_timestamp()
                    tool_result = await self._call_tool(tool_name, tool_input, tool_id)
                    tool_blocks.append(ResponseFromTool(tool_result))
                    tool_timestampss.append(tool_timestamps)

                # Save tool blocks to both recall and messages tables
                await AppDB.save_tool_responses(tool_blocks, tool_timestampss)

                # Create MessageFromApp with all tool results for LLM
                msg_to_llm = MessageFromApp(tool_blocks).get_message_for_llm()
                loop_messages.append(msg_to_llm)

                # Call LLM again
                ai_response = await self._call_claude(loop_messages)

            # Max tokens
            elif ai_response.get_stop_reason() == "max_tokens":
                raise Exception('Max tokens limit breached')

            # Unknown stop reason
            else:
                raise Exception(f'Unknown stop reason: {ai_response.get_stop_reason()}')

        # Save final response after loop completes
        await AppDB.save_ai_response(ai_response)

        # End agent message (style sage green and play notification sound)
        await msg_ui.end_agent_message()

    async def _call_claude(self, message_history: list[MessageParam]) -> ResponseFromAI:
        '''
            Calls Anthropic API for text inference with streaming enabled.
        '''
        try:
            # Get model and token configuration
            selected_model = user_config_manager.get_agent_model()
            token_config = ClaudeConfig.MODEL_TOKEN_CONFIG[selected_model]

            # Get prompt (add cache control)
            prompt = PromptBuilder.build_prompt()
            prompt_block = TextBlock(prompt).get_message_for_llm()
            prompt_block.update(CACHE_CONTROL_FLAG)

            # Set up streaming parameters
            stream_params = {
                "model": selected_model,
                "max_tokens": token_config["max_tokens"],
                "messages": message_history,
                "tools": await self._get_tool_schemas(),
                "system" : [prompt_block]
            }
            if user_config_manager.get_agent_thinking():
                stream_params["thinking"] = {
                    "type": "enabled",
                    "budget_tokens": token_config["thinking_budget_tokens"]
                }

            # Call Claude finally
            async with anthropic_client.messages.stream(**stream_params) as stream:
                final_message = await StreamHandler.process_stream(stream)
                return ResponseFromAI(final_message)

        except Exception as e:
            logger.error(f"[_call_claude] ERROR: {type(e).__name__}: {e}")
            import traceback
            traceback.print_exc()
            raise

    async def _call_tool(self, tool_name: str, tool_input: dict, tool_id: str) -> ToolResult:
        try:
            # Get the initialized global MCP client
            mcp_client = await get_global_mcp_client()
            response = await mcp_client.call_tool(tool_name, tool_input)
            data = response.data
            
            # Convert Pydantic models to dict for JSON serialization
            if hasattr(data, 'model_dump'):
                data = data.model_dump()
            elif hasattr(data, 'dict'):
                data = data.dict()
                
            is_error = False
        except:
            is_error = True
            data = None
            
        tool_result = ToolResult(
            tool_name=tool_name,
            tool_use_id=tool_id,
            is_error=is_error,
            result=data,
            tool_input=tool_input
        )
        return tool_result

    async def _get_tool_schemas(self):
        if self._cached_tool_schemas is not None:
            return self._cached_tool_schemas

        # Get tools from MCP client
        mcp_client = await get_global_mcp_client()
        mcp_tools = await mcp_client.list_tools()

        # Convert MCP tools to Anthropic format
        tools = []
        for tool in mcp_tools:
            # Inline all $ref and $defs to make schema Claude-compatible
            schema = inline_refs(tool.inputSchema)

            tools.append({
                "name": tool.name,
                "description": tool.description,
                "input_schema": schema
            })

        # Add prompt caching to last tool
        if len(tools) > 0:
            tools[-1].update(CACHE_CONTROL_FLAG)
        
        self._cached_tool_schemas = tools

        return tools
    
    async def _notify_ui_buffers_flushed(self, source: InputSourceType):
        # Inform UI the buffers are being flushed
        if source == InputSourceType.AUDIO:
            asyncio.create_task(msg_ui.notify_transcripts_flushed())
        elif source == InputSourceType.CHAT:
            asyncio.create_task(msg_ui.notify_chat_flushed())

    async def _get_state_snapshot(self, source: InputSourceType) -> str:
        # Get storyboard UI state
        board_state = await UserInterfaceHandler.get_board_state()

        # Get recent image requests with filtered columns [task_id, status, image_id]
        image_request_statuses = await AgentDB.recent_image_requests_for_state(
            AppConfig.REQUEST_STATE_WINDOW_MS)
        
        # Get image style prompt from user config
        image_style_prompt = user_config_manager.get_image_style_prompt()

        # Add in long-term memory context
        memory_str = ''
        memory = memory_worker.get_longterm_memory()
        if memory:
            memory_str = f'<long-term-memory-context>{memory}</long-term-memory-context>'

        # Assemble state snapshot
        state = f"""
            <app_state>
                <current_input_mode>{source}</current_input_mode>
                <board_state>
                    {json.dumps(board_state)}
                </board_state>
                <recent_image_request_statuses>
                    {json.dumps(image_request_statuses)}
                </recent_image_request_statuses>
                <image_generation_style>
                The default image style at the time of this message is as follows:
                    <style>{image_style_prompt}</style>
                </image_generation_style>
                {memory_str}
            </app_state>
        """
        return state


agent_inference_engine = AgentInferenceEngine()