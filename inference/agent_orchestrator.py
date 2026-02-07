import asyncio
from collections import OrderedDict
from core.constants import InputSourceType as Source
from typing import Callable
from core.utils.time_utils import get_current_timestamp
    
class AgentOrchestrator:
    """
    Simple orchestrator which manages a queue for running the agent inference for
    all our user and app event handlers. This ensures inference events run
    sequentially, not concurrently.

    Uses an ordered dict for our queue object to avoid duplicates since our
    app and user event handlers manage their own buffers.
    """
    USER_EVENT_KEYS = frozenset([Source.CHAT, Source.AUDIO])

    def __init__(self):
        self.handler_map = {} # Source -> HandlerInfo
        self.pending_dict = OrderedDict()  # Track what sources are waiting for turn
        self._last_user_event = None # Timestamp

        self.queue_event = asyncio.Event() # Notifies if item has joined queue
        self._task = None # Infinite queue loop event
    
    def _ensure_started(self):
        if self._task is None:
            self._task = asyncio.create_task(self._queue_loop())

    def register(self, src: Source, callback: Callable):
        # Register callback info for a given event type
        self._ensure_started()

        # Add handler to map
        info = HandlerInfo(callback)
        self.handler_map[src] = info
        return info
    
    def join_queue(self, src: Source):
        self._ensure_started()

        # Mark user event and add event to pending queue
        if self._is_user_event(src):
            self._last_user_event = get_current_timestamp()
        self.pending_dict[src] = None

        # Inform queue loop
        self.queue_event.set()

    async def _queue_loop(self):
        while True:
            # Wait for queue events
            await self.queue_event.wait()
            self.queue_event.clear()
            while len(self.pending_dict) > 0:
                # Pop off first item in queue and call its handler
                current_src, _ = self.pending_dict.popitem(last=False)
                handler_info = self.handler_map.get(current_src)
                await handler_info.run_callback()

    def check_for_user_events(self, timestamp: int):
        # Checks if user events are pending or have occurred since given timestamp
        past_event = self._user_event_since_timestamp(timestamp)
        curr_event = self.has_user_events_pending()
        return (past_event or curr_event)

    def has_user_events_pending(self):
        # Checks if any user event sources are currently pending in queue
        for src in self.pending_dict:
            if self._is_user_event(src):
                return True
        return False

    def _is_user_event(self, src: Source):
        # Checks if event source is a user event
        return (src in AgentOrchestrator.USER_EVENT_KEYS)

    def _user_event_since_timestamp(self, timestamp: int):
        # Checks if a user event has occurred since given timestamp
        if not self._last_user_event:
            return False
        return (timestamp < self._last_user_event)


# Passthrough object for orchestrator + event handlers
class HandlerInfo:
    def __init__(self, callback):
        self._inference_ready_callback = callback
    
    async def run_callback(self):
        await self._inference_ready_callback()

agent_orchestrator = AgentOrchestrator()
