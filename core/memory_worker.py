from inference.memory_summary_engine import MemorySummaryEngine
from core.app_config import MemoryConfig
from db_ops.memory import MemoryDB
from core.event_manager import event_manager
from core.utils.time_utils import get_reference_timestamp
from core.logger_config import logger
import asyncio
import time

class MemoryWorker:
    """
    Periodically updates long-term memory at fixed intervals so long
    as there are new user events. Calls MemoryEngine to generate a
    new summary based on new messages since last update.
    """
    def __init__(self):
        self._longterm_memory = None
        self._last_longterm_update_timestamp = 0

    async def start_loop(self):
        await self.update_longterm_memory_loop()

    async def update_longterm_memory_loop(self):
        while True:
            # Clear the event before so we can reload long-term memory
            # if we start with a non-empty DB
            event_manager.inform_memory_manager.clear()
            try:
                # Fetch all entries since last processed message
                entries = await MemoryDB.get_recall_entries_for_summary(
                    self._last_longterm_update_timestamp)

                # Process the entries
                memory = await MemorySummaryEngine.refresh_longterm_memory(
                    self._longterm_memory,
                    entries
                )

                # Store long term memory and get timestamp to use for later iterations
                if memory:
                    self._longterm_memory = memory
                    self._last_longterm_update_timestamp = max(
                        entry['timestamp'] for entry in entries
                    )
                    logger.info(f'Long-term memory: {memory}')
            except Exception as e:
                # Watermark unchanged - will retry these messages next cycle
                logger.error(f'error: could not update long-term memory; {str(e)}')

            # Wait for refresh cycle and inference events
            await asyncio.sleep(MemoryConfig.LONGTERM_MEMORY_REFRESH_SEC)
            await event_manager.inform_memory_manager.wait()

    def get_longterm_memory(self):
        return self._longterm_memory

memory_worker = MemoryWorker()
