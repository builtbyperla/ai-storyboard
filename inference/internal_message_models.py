from anthropic.types import ToolUseBlock as AnthropicToolUseBlock
from anthropic.types import ThinkingBlock as AnthropicThinkingBlock
from anthropic.types import Message as AnthropicMessage
from common.models import ToolResult
from dataclasses import dataclass

class ClaudeTemplates:
    """
    Template dicts for formatting messages & blocks in format expected from Claude
    """
    def user_msg_template():
        return {'role':'user', 'content': None}

    def assistant_msg_template():
        return {'role':'assistant', 'content': None}

    def text_content_block_template():
        return {'type': 'text', 'text': None}

    def tool_request_template():
        return {'type': 'tool_use', 'name' : None, 'input': None}

    def tool_result_template():
        return {'type': 'tool_result', 'content' : None}

    def thinking_template():
        return {'type': 'thinking', 'thinking': None}

class MessagingBaseClass:
    """Base class for all message and block types with standardized formatting methods."""

    def get_message_for_recall(self):
        """Return simplified format for recall_entries table (memory/retrieval system)."""
        raise Exception("get_message_for_recall() not implemented yet")

    def get_message_for_llm(self):
        """Return full format for Claude API (includes IDs, signatures, etc.)."""
        raise Exception("get_message_for_llm() not implemented yet")

    def get_message_for_db(self):
        """Return storage format for messages table (excludes IDs/signatures to save tokens)."""
        raise Exception("get_message_for_db() not implemented yet")

class AppBlockBaseClass(MessagingBaseClass):
    """Base class for content blocks (text, tool_use, thinking) within messages."""
    pass

class AppMessageBaseClass(MessagingBaseClass):
    """Base class for complete messages (user messages, assistant responses, tool results)."""
    def add_text(self, text):
        pass

class TextBlock(AppBlockBaseClass):
    """Internal representation of a text content block from Claude responses."""

    def __init__(self, text: str):
        self.text = text

    def get_message_for_db(self):
        """Returns text block dict (type + text content)."""
        block = ClaudeTemplates.text_content_block_template()
        block['text'] = self.text
        return block

    def get_message_for_llm(self):
        """Same format as DB (no additional fields needed)."""
        return self.get_message_for_db()

    def get_message_for_recall(self):
        """Returns raw text string for simple recall/search."""
        return self.text

class ThinkingBlock(AppBlockBaseClass):
    """Internal representation of extended thinking content blocks (Claude's reasoning process)."""

    def __init__(self, block: AnthropicThinkingBlock):
        self.thinking_str = block.thinking
        self.signature = block.signature

    def get_message_for_db(self):
        """Excluded from DB storage to save space. Returns None."""
        return None

    def get_message_for_llm(self):
        """Returns thinking block dict (type, thinking content, signature)."""
        block = ClaudeTemplates.thinking_template()
        block['thinking'] = self.thinking_str
        block['signature'] = self.signature
        return block

    def get_message_for_recall(self):
        """Excluded from recall system (not needed for memory retrieval). Returns None."""
        return None

class MessageFromUser(AppMessageBaseClass):
    """User message containing one or more text strings."""

    def __init__(self, messages: list[str]):
        """
        Args:
            messages: List of text strings. Single string returns as plain string,
                     multiple as list of text blocks.
        """
        self.messages = messages

    def format_content(self):
        """Format content based on number of messages: string for 1, list of blocks for multiple."""
        if len(self.messages) == 0:
            return ""
        if len(self.messages) == 1:
            return self.messages[0]
        blocks = []
        for msg in self.messages:
            block = ClaudeTemplates.text_content_block_template()
            block['text'] = msg
            blocks.append(block)
        return blocks

    def get_message_for_db(self):
        """Returns user message dict (role + content)."""
        user_msg_wrapper = ClaudeTemplates.user_msg_template()
        user_msg_wrapper['content'] = self.format_content()
        return user_msg_wrapper

    def get_message_for_llm(self):
        """Same format as DB."""
        return self.get_message_for_db()

    def get_message_for_recall(self):
        """Same format as DB."""
        return self.get_message_for_db()

    def add_text(self, text: str):
        self.messages.append(text)

class MessageFromApp(AppMessageBaseClass):
    """For constructing internal messages from the app to Claude for things like tool use"""

    def __init__(self, blocks: list[AppBlockBaseClass]):
        """
        Args:
            blocks: List of content blocks (TextBlock, ResponseFromTool, etc.) to include in this message.
        """
        self.blocks = blocks

    def get_message_for_db(self):
        """Returns user message with content blocks."""
        wrapper = ClaudeTemplates.user_msg_template()
        content_blocks = [block.get_message_for_db() for block in self.blocks]
        wrapper['content'] = content_blocks
        return wrapper

    def get_message_for_llm(self):
        """Returns user message with content blocks."""
        wrapper = ClaudeTemplates.user_msg_template()
        content_blocks = [block.get_message_for_llm() for block in self.blocks]
        wrapper['content'] = content_blocks
        return wrapper

    def get_message_for_recall(self):
        """Returns list of blocks for recall."""
        return [block.get_message_for_recall() for block in self.blocks]
    
    def add_text(self, text: str):
        block = TextBlock(text)
        self.blocks.append(block)
    
class ResponseFromTool(AppBlockBaseClass):
    """Tool result message to send back to Claude (formatted as user message with tool_result blocks)."""

    def __init__(self, tool_result: ToolResult):
        """
        Args:
            tool_response: Dict containing tool result with tool_use_id, content, and is_error fields.
        """
        self.tool_use_id = tool_result.tool_use_id
        self.tool_name = tool_result.tool_name
        self.result = tool_result.result  # Raw for recall DB
        self.result_str = tool_result.deserialize_result()  # Serialized for Claude
        self.is_error = tool_result.is_error
        self.tool_input = tool_result.tool_input
    
    def get_message_for_db(self):
        wrapper = ClaudeTemplates.tool_result_template()
        wrapper['content'] = self.result_str  # Use pre-serialized string
        wrapper['tool_use_id'] = self.tool_use_id  # Store ID for history reload
        wrapper['is_error'] = self.is_error  # Separate field, not nested in content
        return wrapper

    def get_message_for_llm(self):
        return self.get_message_for_db()  # Same format for both

    def get_message_for_recall(self):
        # Minimal format for recall - tool name and status
        # Tool input is typically redundant with agent's text response
        recall_data = {
            'tool': self.tool_name,
            'status': 'error' if self.is_error else 'success'
        }
        
        # Special case: Include task_id and prompt for image generation requests
        # so agent can search for and reference specific images later
        if self.tool_name == 'image_generation-request_image':
            if self.result and isinstance(self.result, dict) and 'image_request_id' in self.result:
                recall_data['image_request_id'] = self.result['image_request_id']
            if self.tool_input and isinstance(self.tool_input, dict):
                if 'prompt' in self.tool_input:
                    recall_data['prompt'] = self.tool_input['prompt']
                if 'label' in self.tool_input:
                    recall_data['label'] = self.tool_input['label']
        
        return recall_data

class ToolRequestFromAI(AppBlockBaseClass):
    """Tool use block from Claude (tool call request)."""

    def __init__(self, block: AnthropicToolUseBlock):
        self.name = block.name
        self.input = block.input
        self.id = block.id

    def get_message_for_db(self):
        """Returns tool_use block dict (type, name, input, id)."""
        block = ClaudeTemplates.tool_request_template()
        block['name'] = self.name
        block['input'] = self.input
        block['id'] = self.id
        return block

    def get_message_for_llm(self):
        """Returns same format as DB (ID included)."""
        return self.get_message_for_db()

    def get_message_for_recall(self):
        """Includes ID for matching with tool results in recall."""
        return {
            'tool': self.name,
            'id': self.id,
            'input': self.input
        }

class ResponseFromAI(AppMessageBaseClass):
    '''Internal representation of LLM response'''
    def __init__(self, response: AnthropicMessage = None):
        self._raw_response = None
        self._stop_reason = ""

        self._text_messages: list[str] = []  # Simple strings for convenience
        self._tool_requests: list[ToolRequestFromAI] = [] # For easy tool calling
        self._ordered_blocks: list[AppBlockBaseClass] = [] # For sending back in proper order

        self._load_response(response)
    
    def _load_response(self, response: AnthropicMessage):
        if response is None:
            return

        self._raw_response = response
        self._stop_reason = response.stop_reason

        # Load flattened blocks from agent response
        text_msgs, tool_reqs, ordered_blocks = self._split_blocks(response)
        self._text_messages = text_msgs  # Simple strings for convenience
        self._tool_requests = tool_reqs # Tool blocks in internal msg fmt
        self._ordered_blocks = ordered_blocks # For sending back to LLM
    
    def _split_blocks(self, response: AnthropicMessage):
        text_messages = []
        tool_requests = []
        ordered_blocks = []  # Block objects preserving Claude's ordering

        for block in response.content:
            block_type = block.type
            if block_type == 'text':
                text = block.text
                text_block = TextBlock(text)
                text_messages.append(text)  # Store as string
                ordered_blocks.append(text_block)  # Store as object
            elif block_type == 'tool_use':
                tool_request = ToolRequestFromAI(block)
                tool_requests.append(tool_request)
                ordered_blocks.append(tool_request)
            elif block_type == 'thinking':
                thinking_block = ThinkingBlock(block)
                ordered_blocks.append(thinking_block)

        return (text_messages, tool_requests, ordered_blocks)

    def get_stop_reason(self):
        return self._stop_reason

    def get_tool_requests(self):
        return self._tool_requests
    
    def get_text_messages(self):
        return self._text_messages

    def get_message_for_db(self) -> dict:
        '''Returns assistant message for DB storage - excludes IDs and thinking blocks'''
        wrapper = ClaudeTemplates.assistant_msg_template()
        blocks = []
        for block in self._ordered_blocks:
            block_for_db = block.get_message_for_db()
            if block_for_db is not None:
                blocks.append(block_for_db)
        wrapper['content'] = blocks
        return wrapper

    def get_message_for_llm(self) -> dict:
        '''Returns assistant message for LLM - includes IDs, optionally includes thinking blocks'''
        wrapper = ClaudeTemplates.assistant_msg_template()
        blocks = []
        for block in self._ordered_blocks:
            block_for_llm = block.get_message_for_llm()
            if block_for_llm is not None:
                blocks.append(block_for_llm)
        wrapper['content'] = blocks
        return wrapper

    def get_message_for_recall(self):
        '''Returns just the text content for recall/memory'''
        return '\n'.join(self._text_messages)

    def add_text(self, text: str):
        block = TextBlock(text)
        self._ordered_blocks.append(block)
        self._text_messages.append(text)

