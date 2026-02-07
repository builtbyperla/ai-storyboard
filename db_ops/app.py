import json
from typing import Optional, List, Dict, Any
from sqlalchemy import select, and_
from typing import List, Dict
import sqlalchemy
from core.db_core import (
    DBCore,
    ImageCache,
    ImageRequest,
    Message,
    RecallEntry,
    UserSession,
)
from core.utils.time_utils import get_current_timestamp
from core.unique_id_manager import id_manager
from inference.internal_message_models import MessageFromUser, MessageFromApp, ResponseFromAI
from core.constants import InputSourceType

class AppDB(DBCore):
    """Application-level database orchestration for complex multi-table operations."""

    # ========== GET methods (simple reads) ==========

    @staticmethod
    async def get_session() -> int:
        # Session ID auto increments and we send it back
        ts = get_current_timestamp()
        async with DBCore.async_session_maker() as session:
            us = UserSession()
            us.timestamp = ts
            session.add(us)
            await session.flush()
            await session.commit()
            return us.session_id

    @staticmethod
    async def get_image_cache() -> List[Dict[str, Any]]:
        """Retrieve all image cache entries."""
        return await DBCore.select_dicts(ImageCache)

    # ========== INSERT methods (batch operations with ID generation) ==========

    @staticmethod
    async def insert_messages_batch(messages: List[tuple[str, int, str]]) -> None:
        """Insert multiple messages in a single transaction.

        Args:
            messages: List of tuples (msg_str, timestamp, snapshot_str_or_none)
        """
        async with DBCore.async_session_maker() as session:
            for msg_str, timestamp, snapshot in messages:
                msg_id = id_manager.get_message_id()
                message = Message(
                    message_id=msg_id,
                    msg_str=msg_str,
                    timestamp=timestamp,
                    state_snapshot=snapshot
                )
                session.add(message)
            await session.commit()

    @staticmethod
    async def insert_recall_entries_batch(
        entries: List[tuple[str, str, int]], skip_embeddings_set=set()
    ) -> None:
        """Insert multiple recall entries in a single transaction.

        Args:
            entries: List of tuples (recall_str, entry_type, timestamp)
        """
        async with DBCore.async_session_maker() as session:
            for index, (recall_str, entry_type, timestamp) in enumerate(entries):
                entry = RecallEntry(
                    entry_id=id_manager.get_recall_id(),
                    recall_str=recall_str,
                    entry_type=entry_type,
                    timestamp=timestamp,
                    needs_embedding=(index not in skip_embeddings_set)
                )
                session.add(entry)
            await session.commit()

    @staticmethod
    async def insert_image_cache(
        image_id: str,
        path: str,
        description: str,
        image_style: str,
        timestamp: int,
    ) -> None:
        """Insert an image cache entry."""
        async with DBCore.async_session_maker() as session:
            cache_entry = ImageCache(
                image_id=image_id,
                path=path,
                description=description,
                image_style=image_style,
                timestamp=timestamp
            )
            session.add(cache_entry)
            await session.commit()

    @staticmethod
    async def insert_image_request(
        task_id: str,
        status: str,
        timestamp: int,
        context: str,
        image_id: Optional[str] = None,
    ) -> None:
        """Insert an image request."""
        async with DBCore.async_session_maker() as session:
            request = ImageRequest(
                task_id=task_id,
                status=status,
                timestamp=timestamp,
                context=context,
                image_id=image_id
            )
            session.add(request)
            await session.commit()

    # ========== UPDATE methods ==========

    @staticmethod
    async def update_image_request(task_id: str, status: str, image_id: str) -> None:
        """Update status and image_id for an existing image request."""
        async with DBCore.async_session_maker() as session:
            stmt = (
                sqlalchemy.update(ImageRequest)
                .where(ImageRequest.task_id == task_id)
                .values(status=status, image_id=image_id)
            )
            await session.execute(stmt)
            await session.commit()

    # ========== SAVE methods (complex multi-table orchestration) ==========

    @staticmethod
    async def save_messages_from_user(messages: list[str], source: InputSourceType, state_snapshot: dict = None) -> None:
        """Save user messages to both messages and recall_entries tables.

        Args:
            messages: List of user message strings
            source: InputSourceType value ('chat' or 'audio')
            state_snapshot: Optional canvas state snapshot dict
        """
        timestamp = get_current_timestamp()

        # Create message using internal model
        user_msg = MessageFromUser(messages)

        # Save to messages table (single insert)
        msg_dict = user_msg.get_message_for_db()
        msg_str = json.dumps(msg_dict)
        snapshot_str = json.dumps(state_snapshot) if state_snapshot else None
        message_batch = [(msg_str, timestamp, snapshot_str)]
        await AppDB.insert_messages_batch(message_batch)

        # Save to recall_entries table (batch insert if multiple)
        entry_type = (
            'user_chat_message'
            if source == InputSourceType.CHAT
            else 'user_audio_transcript'
        )
        recall_entries = [(msg, entry_type, timestamp) for msg in messages]
        await AppDB.insert_recall_entries_batch(recall_entries)

    @staticmethod
    async def save_ai_response(ai_response: ResponseFromAI) -> None:
        """Save AI response to both messages and recall_entries tables.

        Args:
            ai_response: ResponseFromAI object
        """
        timestamp = get_current_timestamp()

        # Save to messages table (excludes thinking blocks)
        msg_dict = ai_response.get_message_for_db()
        msg_str = json.dumps(msg_dict)
        message_batch = [(msg_str, timestamp, None)]
        await AppDB.insert_messages_batch(message_batch)

        # Save to recall_entries table (only text content)
        text_content = ai_response.get_message_for_recall()
        if text_content:
            recall_entries = [(text_content, 'agent_response', timestamp)]
            await AppDB.insert_recall_entries_batch(recall_entries)

    @staticmethod
    async def save_tool_responses(tool_blocks: list, timestamps: list[str]) -> None:
        """Save tool responses to both recall_entries and messages tables.

        Args:
            tool_blocks: List of ResponseFromTool objects
            timestamps: List of timestamps for each tool call
        """
        # Batch insert recall entries with actual tool call timestamps
        recall_entries = []
        semantic_query_indices = set()
        for i, (tool_resp, timestamp) in enumerate(zip(tool_blocks, timestamps)):
            recall_data = tool_resp.get_message_for_recall()
            recall_str = json.dumps(recall_data)
            recall_entries.append((recall_str, 'tool_use', timestamp))

            if tool_resp.tool_name == 'semantic_search':
                semantic_query_indices.add(i)

        # Add entry to recall table, skip embedding generation if semantic search
        # to avoid recursive results
        await AppDB.insert_recall_entries_batch(recall_entries, semantic_query_indices)

        # Save MessageFromApp to LLM messages table
        timestamp = get_current_timestamp()
        app_msg = MessageFromApp(tool_blocks)
        msg_dict = app_msg.get_message_for_db()
        msg_str = json.dumps(msg_dict)
        message_batch = [(msg_str, timestamp, None)]
        await AppDB.insert_messages_batch(message_batch)
