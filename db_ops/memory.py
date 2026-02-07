from typing import Optional, List, Dict, Any
from sqlalchemy import select, and_
from typing import List, Dict
import sqlalchemy
from core.db_core import (
    DBCore,
    RecallEntry,
)

class MemoryDB:
    """
    Database methods related to agent memory and embedding vectors
    """
    @staticmethod
    async def get_recall_entries_for_summary(
        cutoff_timestamp: int
    ) -> List[Dict[str, Any]]:
        """Get recall entries after the cutoff timestamp for summarization."""
        async with DBCore.async_session_maker() as session:
            stmt = (
                select(RecallEntry)
                .where(RecallEntry.timestamp > cutoff_timestamp)
                .order_by(RecallEntry.timestamp, RecallEntry.sequence_num)
            )
            result = await session.execute(stmt)
            entries = result.scalars().all()
            return [entry.to_dict() for entry in entries]

    @staticmethod
    async def get_unprocessed_recall_entries() -> List[Dict[str, Any]]:
        """Get all recall entries that don't have embeddings yet."""
        conditions = [RecallEntry.has_embedding == 0, RecallEntry.needs_embedding == 1]
        where = sqlalchemy.and_(*conditions) if conditions else None
        return await DBCore.select_dicts(RecallEntry, where=where)

    @staticmethod
    async def mark_recall_entries_as_embedded(entry_ids: List[str]) -> None:
        """Mark recall entries as having embeddings."""
        async with DBCore.async_session_maker() as session:
            stmt = (
                sqlalchemy.update(RecallEntry)
                .where(RecallEntry.entry_id.in_(entry_ids))
                .values(has_embedding=1)
            )
            await session.execute(stmt)
            await session.commit()