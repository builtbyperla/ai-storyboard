from core.websocket_manager import SocketNames, socket_manager
from core.logger_config import logger
from enum import Enum

# Command constants
UPDATE_USER_TRANSCRIPT_COMMAND = 'update_user_transcript'
SHOW_AGENT_THINKING_COMMAND = 'show_agent_thinking'
UPDATE_AGENT_THINKING_COMMAND = 'update_agent_thinking'
START_AGENT_RESPONSE_COMMAND = 'start_agent_response'
UPDATE_AGENT_RESPONSE_COMMAND = 'update_agent_response'
INDICATOR_COMMAND = 'update_ai_status'
PLAY_NOTIFICATION_SOUND_COMMAND = 'play_notification_sound'
END_AGENT_MESSAGE_COMMAND = 'end_agent_message'
NOTIFY_TRANSCRIPTS_FLUSHED_COMMAND = 'notify_transcripts_flushed'
NOTIFY_CHAT_FLUSHED_COMMAND = 'notify_chat_flushed'

class IndicatorState(Enum):
    IDLE = 'idle'
    THINKING = 'thinking'
    RESPONDING = 'responding'

class MsgStreamerUI:
    async def update_user_text_box(user_msg: str):
        """Sends a command to the frontend to update the user transcript text box"""
        payload = {
            'command': UPDATE_USER_TRANSCRIPT_COMMAND,
            'params': {'text': user_msg}
        }
        await socket_manager.send_message(SocketNames.BRIDGE, payload)

    async def show_agent_thinking():
        """Sends a command to the frontend to show the thinking indicator"""
        payload = {
            'command': SHOW_AGENT_THINKING_COMMAND
        }
        await socket_manager.send_message(SocketNames.BRIDGE, payload)

    async def update_agent_thinking(text: str):
        """Sends a command to the frontend to append text to the thinking accumulator"""
        payload = {
            'command': UPDATE_AGENT_THINKING_COMMAND,
            'params': {'text': text}
        }
        await socket_manager.send_message(SocketNames.BRIDGE, payload)

    async def start_agent_response():
        """Sends a command to the frontend to clear response text and hide thinking"""
        payload = {
            'command': START_AGENT_RESPONSE_COMMAND
        }
        logger.debug("Sending start agent response")
        await socket_manager.send_message(SocketNames.BRIDGE, payload)

    async def update_agent_response(text: str):
        """Sends a command to the frontend to append text to the response accumulator"""
        payload = {
            'command': UPDATE_AGENT_RESPONSE_COMMAND,
            'params': {'text': text}
        }
        await socket_manager.send_message(SocketNames.BRIDGE, payload)

    async def play_notification_sound():
        """Sends a command to the frontend to play the notification sound"""
        payload = {
            'command': PLAY_NOTIFICATION_SOUND_COMMAND
        }
        await socket_manager.send_message(SocketNames.BRIDGE, payload)

    async def end_agent_message():
        """Sends a command to the frontend to end agent message (style it sage green and play notification sound)"""
        payload = {
            'command': END_AGENT_MESSAGE_COMMAND
        }
        await socket_manager.send_message(SocketNames.BRIDGE, payload)

    async def notify_transcripts_flushed():
        """Sends a command to the frontend to trigger the flush indicator flash (mauve flash for 1 second)

        Note: The indicator is only visible when audio is active (isListening=true).
        When audio is off, the indicator is hidden automatically.
        """
        payload = {
            'command': NOTIFY_TRANSCRIPTS_FLUSHED_COMMAND
        }
        await socket_manager.send_message(SocketNames.BRIDGE, payload)

    async def notify_chat_flushed():
        """Sends a command to the frontend to trigger the chat flush indicator flash (mauve flash for 1 second)"""
        payload = {
            'command': NOTIFY_CHAT_FLUSHED_COMMAND
        }
        await socket_manager.send_message(SocketNames.BRIDGE, payload)
