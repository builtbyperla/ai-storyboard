import asyncio

class EventManager:
    """
    App-wide async event manager so different modules can inform each
    other of events without messing with callbacks or circular imports
    """
    def __init__(self):
        self.user_config_changed = asyncio.Event()
        self.image_batch_completed = asyncio.Event()
        self.inform_memory_manager = asyncio.Event()
        self.update_embeddings = asyncio.Event()
        self.audio_stopped = asyncio.Event()

    async def notify_inference_completed(self):
        self.inform_memory_manager.set()
        self.update_embeddings.set()

    async def notify_config_changed(self):
        self.user_config_changed

# Global signal instances
event_manager = EventManager()
