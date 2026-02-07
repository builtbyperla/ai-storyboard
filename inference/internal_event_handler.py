from inference.agent_orchestrator import agent_orchestrator as orchestrator
from inference.user_event_handlers import BaseEventHandler
from core.utils.time_utils import get_current_timestamp
from core.constants import InputSourceType
from core.event_manager import event_manager
from enum import Enum
import asyncio

class EventTypes(Enum):
    IMAGES_COMPLETE = 'images_complete'

class AppEventHandler(BaseEventHandler):
    """ Handler for triggering manual inference outside of user-agent loop
        (for background tasks like image generation)
    """
    msg_template = '<internal_app_message>{}</internal_app_message>'

    def __init__(self):
        super().__init__(InputSourceType.APP_EVENT)
        self.flags = {et : False for et in EventTypes}
        self._last_image_timestamp = None
        self._loop_task = None

    async def start_event_loop(self):
        """Start the background event loop that listens for image batch completion"""
        self._loop_task = asyncio.create_task(self._event_loop())

    async def _event_loop(self):
        """Background loop that awaits image_batch_completed events"""
        while True:
            await event_manager.image_batch_completed.wait()
            self.on_image_completed()
            event_manager.image_batch_completed.clear()

    def on_image_completed(self):
        # Record image completion event + timestamp and
        # then join orchestrator queue
        self._ensure_registered()
        self.flags[EventTypes.IMAGES_COMPLETE] = True
        self._last_image_timestamp = get_current_timestamp()
        orchestrator.join_queue(self.src)
    
    async def on_handler_turn(self):
        # Skip inference for image events if the following happened:
        # - there were user events between batch completion and now
        # - there are currently pending user events in the orchestrator queue
        # Reasoning: Recent image gen statuses are included in state info at
        #            every inference. This avoids duplicate work.
        if self.flags[EventTypes.IMAGES_COMPLETE]:
            if not orchestrator.check_for_user_events(self._last_image_timestamp):
                msg = AppEventHandler.msg_template.format('Image batch completed')
                self.messages.append(msg)

        # Pop messages and send to inference if any
        if len(self.messages) > 0:
            await super().on_handler_turn()

        # Reset event flags for next turn
        self.reset_flags()
    
    def reset_flags(self):
        self.flags = {et : False for et in EventTypes}

app_event_handler = AppEventHandler()