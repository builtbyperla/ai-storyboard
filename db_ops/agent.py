from core.db_core import DBCore, ImageCache
from db_ops.app import AppDB
from typing import Optional, List, Dict, Any
from sqlalchemy import select, and_
import sqlalchemy
from typing import Annotated, Optional
from core.db_core import (
    ImageRequest,
    Message,
    RecallEntry
)
import json
from datetime import datetime

class AgentDB(DBCore):
    """ Database orchestration for agent queries. Changing these affects the
        data, state, query results, etc. that the agent receives.
    """
    
    # ============================================================================
    # INTERFACE METHODS - Called by MCP tools / agent
    # ============================================================================
    
    @staticmethod
    async def query_image_cache(image_ids: list[str], include_style: bool = False) -> List[Dict[str, Any]]:
        """Query image cache for specific image IDs with optional style.
        
        Args:
            image_ids: List of image IDs to fetch
            include_style: If True, include 'style' in returned dict alongside id and description
        
        Returns:
            List of dicts with {id, description} or {id, description, style} sorted by recency (newest first)
        """
        if not image_ids:
            return []
        
        cols = ["image_id", "description"]
        if include_style:
            cols.append("image_style")
        
        where = ImageCache.image_id.in_(image_ids)
        return await DBCore.select_dicts(
            ImageCache, cols=cols, where=where, order_desc=True
        )

    @staticmethod
    async def fetch_image_statuses(task_ids: List[str]) -> List[Dict[str, Any]]:
        """Get image request statuses for specified task IDs, ordered by timestamp ascending."""
        where = ImageRequest.task_id.in_(task_ids) if task_ids else None
        return await DBCore.select_dicts(
            ImageRequest,
            cols=['task_id', 'status', 'image_id'],
            where=where,
            order_desc=False
        )
    
    # ============================================================================
    # INTERNAL METHODS - Called by inference engine and handlers
    # ============================================================================
    
    @staticmethod
    async def recent_messages_for_state(cutoff_timestamp: Optional[int] = None) -> List[Dict[str, Any]]:
        """Get messages, optionally filtered by timestamp.
        Ensures tool_use/tool_result pairs aren't broken at message boundaries.

        Used by inference engine for state.
        
        NOTE: This contains some fuzzy adjustments when clipping messages since tool results need a tool_request
            block matching it. Otherwise we get errors.

        Args:
            cutoff_timestamp: Only return messages with timestamp > cutoff_timestamp
        
        Returns:
            List of message dicts ordered by timestamp ascending. May return empty list if no messages exist.
        """
        # Get messages from after cutoff timestamp or all by default
        # Messages are ordered ascending by timestamp (oldest first, newest last)
        if cutoff_timestamp is not None:
            where = Message.timestamp > cutoff_timestamp
            rows = await DBCore.select(Message, where=where)
        else:
            rows = await DBCore.select(Message)
        
        rows = [json.loads(row.msg_str) for row in rows]

        # Drop first (oldest) message if it has orphaned tool_result
        # since it's missing the assistant tool_use that came before the cutoff
        if len(rows) > 0 and AgentDB._has_tool_result(rows[0]):
            rows.pop(0)
        return rows

    @staticmethod
    async def fetch_recall_entries_for_semantic(entry_ids: list[str], window_size_ms):
        """
        Get deduplicated RecallEntry records for matched entries with context windows.

        For each matched entry_id, grabs entries within its time window. Collects all
        entries from all windows into a set to deduplicate, then returns ordered by timestamp.

        Used by semantic search tool.
        """
        async with DBCore.async_session_maker() as session:
            # Get the target entries with their timestamps
            result = await session.execute(
                select(RecallEntry).where(RecallEntry.entry_id.in_(entry_ids))
            )
            target_entries = result.scalars().all()
            
            if not target_entries:
                return []
            
            # Collect entries from each window into a dict (deduplicate by entry_id)
            entries_dict = {}
            
            for target_entry in target_entries:
                min_time = target_entry.timestamp - window_size_ms
                max_time = target_entry.timestamp + window_size_ms
                
                # Query entries within this specific window
                result = await session.execute(
                    select(RecallEntry)
                    .where(
                        and_(
                            RecallEntry.timestamp >= min_time,
                            RecallEntry.timestamp <= max_time
                        )
                    )
                )
                window_entries = result.scalars().all()
                
                # Add to dict (automatically deduplicates by entry_id)
                for entry in window_entries:
                    if entry.entry_id not in entries_dict:
                        entries_dict[entry.entry_id] = {
                            'recall_str': entry.recall_str,
                            'entry_type': entry.entry_type,
                            'timestamp': entry.timestamp,
                            'entry_id': entry.entry_id,
                            'sequence_num': entry.sequence_num
                        }
            
            # Sort by timestamp and sequence_num, then return
            deduplicated = sorted(
                entries_dict.values(),
                key=lambda x: (x['timestamp'], x['sequence_num'])
            )
            
            # Add human-readable time and remove fields only needed for sorting
            for entry in deduplicated:
                # Convert ms timestamp to day month format with 24 hour time
                dt = datetime.fromtimestamp(entry['timestamp'] / 1000)
                entry['time'] = dt.strftime('%b %d %H:%M')
                
                # Parse JSON strings back to their original types
                try:
                    entry['recall_str'] = json.loads(entry['recall_str'])
                except (json.JSONDecodeError, TypeError):
                    # If it's not JSON, keep as-is (plain string)
                    pass
                
                del entry['sequence_num']
                del entry['entry_id']
                del entry['timestamp']
            
            return deduplicated
        
    @staticmethod
    def _has_tool_result(msg: dict):
        if msg.get('role') != 'user':
            return False
        content = str(msg.get('content', []))
        if 'tool_result' in content:
            return True
        return False
    
    @staticmethod
    async def recent_image_requests_for_state(cutoff_timestamp: int) -> List[Dict[str, Any]]:
        """Get recent image requests within a time window with filtered columns.
           Used by the inference engine for state snapshot.

        Args:
            cutoff_timestamp: Only return entries with timestamp > cutoff_timestamp

        Returns:
            List of dicts with [task_id, status, image_id], ordered by timestamp ascending
        """
        where = ImageRequest.timestamp > cutoff_timestamp
        return await DBCore.select_dicts(
            ImageRequest,
            cols=['task_id', 'status', 'image_id'],
            where=where,
            order_desc=False
        )

    @staticmethod
    async def cached_images_for_state(cutoff_timestamp: int) -> List[Dict[str, Any]]:
        """Get image cache entries within a time window.
           Used by the inference engine for state snapshot.

        Args:
            cutoff_timestamp: Only return entries with timestamp > cutoff_timestamp

        Returns:
            List of dicts with [image_id, description], ordered by timestamp descending (most recent first)
        """
        async with DBCore.async_session_maker() as session:
            stmt = (
                sqlalchemy.select(
                    ImageCache.image_id
                )
                .where(ImageCache.timestamp > cutoff_timestamp)
                .order_by(ImageCache.timestamp.desc())
            )
            result = await session.execute(stmt)
            return [
                {"image_id": row[0], "description": row[1]}
                for row in result.all()
            ]
