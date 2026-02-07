
from inference.agent_inference_engine import agent_inference_engine
from inference.agent_orchestrator import agent_orchestrator as orchestrator
from core.constants import InputSourceType
from core.logger_config import logger
import asyncio
import traceback

'''
    Wrappers for managing user events from chat and audio to be sent
    to inference engine.
'''

class BaseEventHandler:
    def __init__(self, src: InputSourceType):
        self.messages = [] # message buffer
        self._handler_info = None # pass-through object from orchestrator if needed
        self.src = src # event type
    
    def _ensure_registered(self):
        # Registers handler with agent orchestrator
        if self._handler_info is None:
            self._handler_info = orchestrator.register(self.src, self.on_handler_turn)

    def on_new_messages(self, messages: list[str]):
        # Update message buffer and join orchestrator queue
        self._ensure_registered()
        self.messages.extend(messages)
        orchestrator.join_queue(self.src)

    async def on_handler_turn(self):
        # Inference callback for when it's this handler's turn in orchestrator queue
        try:
            # Pop current messages and send to inference engine
            current_messages = self.messages.copy()
            self.messages = []
            await agent_inference_engine.run_inference(current_messages, self.src)
        except Exception as e:
            logger.error(f'Error in [{self.src}] handler: {str(e)}')

class ChatHandler(BaseEventHandler):
    def __init__(self):
        super().__init__(InputSourceType.CHAT)

class AudioHandler(BaseEventHandler):
    def __init__(self):
        super().__init__(InputSourceType.AUDIO)

chat_handler = ChatHandler()
audio_handler = AudioHandler()