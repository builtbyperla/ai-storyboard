from typing import List, Dict, Any, Optional
from core.event_manager import event_manager
from db_ops.app import AppDB
from core.vector_db import vector_db
from core.app_config import EmbeddingConfig
from core.logger_config import logger
from inference.providers.openai_client import openai_client
from db_ops.memory import MemoryDB


class EmbeddingEngine:
    async def get_unprocessed_entries(self) -> List[Dict[str, Any]]:
        """Get all recall entries that don't have embeddings yet."""
        return await MemoryDB.get_unprocessed_recall_entries()

    async def update_embeddings_in_db(self):
        """Process all unprocessed entries and update their embeddings in the database."""
        unprocessed = await self.get_unprocessed_entries()

        if not unprocessed:
            return

        # Extract messages and IDs
        msgs = [entry['recall_str'] for entry in unprocessed]
        entry_ids = [entry['entry_id'] for entry in unprocessed]

        # Get embeddings from OpenAI
        embeddings = await self.create_embeddings(msgs)
        logger.info(f'Generated {len(embeddings)} embeddings')

        # Save to VectorDB and mark as processed in SQLite
        await self.save_embeddings(entry_ids, embeddings)

        count = await vector_db.count()
        logger.info(f'Number of embeddings in vector db: {count}')

    async def save_embeddings(
        self,
        entry_ids: List[str],
        embeddings: List[List[float]]
    ):
        """Save embeddings to VectorDB and mark entries as processed in SQLite."""
        # Add to VectorDB collection
        await vector_db.add(ids=entry_ids, embeddings=embeddings)

        # Mark entries as having embeddings in SQLite
        await MemoryDB.mark_recall_entries_as_embedded(entry_ids)

    @staticmethod
    async def create_embeddings(msgs: List[str]) -> List[List[float]]:
        """Get embeddings from OpenAI API."""
        response = await openai_client.embeddings.create(
            input=msgs,
            model=EmbeddingConfig.OPENAI_EMBEDDING_MODEL
        )
        embeddings = [item.embedding for item in response.data]
        return embeddings