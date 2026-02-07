from core.event_manager import event_manager
from inference.embedding_engine import EmbeddingEngine

class EmbeddingWorker:
    """
        Background task which has embedding engine update all
        pending embeddings and insert them into the vector DB
        whenever inference is completed (when update_embeddings event is set)
    """
    def __init__(self):
        self.engine = EmbeddingEngine()
    
    async def start_loop(self):
        while True:
            # Wait to be triggered by a complete inference loop
            await event_manager.update_embeddings.wait()
            event_manager.update_embeddings.clear()
            await self.engine.update_embeddings_in_db()

embedding_worker = EmbeddingWorker()
