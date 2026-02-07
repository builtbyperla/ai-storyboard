"""
Shared database helper module for image generation tasks and cache.
Provides consistent database access for both MCP server and chat backend.
"""

import os
import json
from typing import Optional, List, Dict, Any
import sqlalchemy
from sqlalchemy import String, Integer, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from core.app_config import DatabaseConfig

# SQLAlchemy Base
class Base(DeclarativeBase):
    def to_dict(self) -> Dict[str, Any]:
        """Convert model instance to dictionary."""
        return {c.name: getattr(self, c.name) for c in self.__table__.columns}

    @classmethod
    def get_cols(cls, *names):
        return [cls.__table__.c[n] for n in names]

# SQLAlchemy ORM Models
class ImageCache(Base):
    """Cached image generations"""
    __tablename__ = 'image_cache'

    image_id: Mapped[str] = mapped_column(Text, primary_key=True)
    path: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    image_style: Mapped[str] = mapped_column(Text, nullable=False)
    timestamp: Mapped[int] = mapped_column(Integer, nullable=False)

class ImageRequest(Base):
    """Requests to generate images"""
    __tablename__ = 'image_requests'

    task_id: Mapped[str] = mapped_column(Text, primary_key=True)
    status: Mapped[str] = mapped_column(Text, nullable=False)
    timestamp: Mapped[int] = mapped_column(Integer, nullable=False)
    context: Mapped[str] = mapped_column(Text, nullable=False)  # {prompt, style}
    image_id: Mapped[Optional[str]] = mapped_column(Text, nullable=True, default=None)

class Message(Base):
    """User and AI messages in user-assistant format for Claude"""
    __tablename__ = 'messages'

    message_id: Mapped[str] = mapped_column(Text, primary_key=True)
    msg_str: Mapped[str] = mapped_column(Text, nullable=False)
    timestamp: Mapped[int] = mapped_column(Integer, nullable=False)
    state_snapshot: Mapped[str] = mapped_column(Text, nullable=True)

class RecallEntry(Base):
    """Constantly updated table for memory management system"""
    __tablename__ = 'recall_entries'

    entry_id: Mapped[str] = mapped_column(Text, primary_key=True)
    recall_str: Mapped[str] = mapped_column(Text, nullable=False)
    entry_type: Mapped[str] = mapped_column(Text, nullable=False)  # User transcript, tool response, agent response
    timestamp: Mapped[int] = mapped_column(Integer, nullable=False)
    sequence_num: Mapped[Optional[int]] = mapped_column(Integer, autoincrement=True)
    has_embedding: Mapped[bool] = mapped_column(Integer, nullable=False, default=0)
    needs_embedding: Mapped[bool] = mapped_column(Integer, nullable=False, default=1)

class UserSession(Base):
    """Session numbers incremented at every startup (used for unique keys)"""
    __tablename__ = 'sessions'
    session_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    timestamp: Mapped[int] = mapped_column(Integer, nullable=False)

# Explicit list of all models - add new models here to include them in the database
ALL_MODELS = [
    ImageCache,
    ImageRequest,
    Message,
    RecallEntry,
    UserSession
]

class DBCore:
    """Low-level database primitives: schema, helpers, and initialization."""

    # Database engine and session setup
    engine = create_async_engine(f"sqlite+aiosqlite:///{DatabaseConfig.DB_PATH}", echo=False)
    async_session_maker = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    # ========== Helper methods for flexible querying ==========

    @staticmethod
    async def select(
        model: type[Base],
        cols: Optional[List[str]] = None,
        where=None,
        order_desc: bool = False
    ):
        """
        Low-level query helper, auto-ordered by timestamp.

        Args:
            model: The SQLAlchemy model class
            cols: Optional list of column names. If None, selects all columns.
            where: Optional SQLAlchemy filter expression (e.g., Model.col == value)
            order_desc: If True, orders by timestamp descending; if False (default), orders ascending

        Returns:
            List of model instances (if cols=None) or Row objects (if cols specified)
        """
        async with DBCore.async_session_maker() as session:
            # Partial columns or full model
            if cols:
                col_objs = model.get_cols(*cols)
                stmt = sqlalchemy.select(*col_objs)
            else:
                stmt = sqlalchemy.select(model)

            # Apply filter
            if where is not None:
                stmt = stmt.where(where)

            # Auto-order by timestamp if model has it
            if hasattr(model, 'timestamp'):
                if order_desc:
                    stmt = stmt.order_by(sqlalchemy.desc(model.timestamp))
                else:
                    stmt = stmt.order_by(sqlalchemy.asc(model.timestamp))

            result = await session.execute(stmt)

            # Return model instances directly when selecting full models
            # Return Row objects when selecting specific columns
            return result.scalars().all() if not cols else result.all()

    @staticmethod
    async def select_dicts(
        model: type[Base],
        cols: Optional[List[str]] = None,
        where=None,
        order_desc: bool = False
    ) -> List[Dict[str, Any]]:
        """
        Query helper that returns dicts, with optional partial column selection.

        Args:
            model: The SQLAlchemy model class
            cols: Optional list of column names. If None, returns all columns as dicts.
            where: Optional SQLAlchemy filter expression
            order_desc: If True, orders by timestamp descending; if False (default), orders ascending

        Returns:
            List of dicts
        """
        results = await DBCore.select(model, cols, where, order_desc)

        if cols:
            # Partial columns: Row objects with _mapping
            return [dict(row._mapping) for row in results]
        else:
            # Full models: model instances with .to_dict()
            return [m.to_dict() for m in results]

    # ========== Database initialization ==========

    @staticmethod
    async def setup(clear_db=False):
        """Ensure database directory and tables exist. Idempotent - safe to call multiple times."""
        os.makedirs(DatabaseConfig.DB_DIR, exist_ok=True)

        # Delete existing DB for fresh start (for testing/demo purposes)
        if clear_db and os.path.exists(DatabaseConfig.DB_PATH):
            os.remove(DatabaseConfig.DB_PATH)

        # Create all tables from ALL_MODELS list
        async with DBCore.engine.begin() as conn:
            for model in ALL_MODELS:
                await conn.run_sync(model.__table__.create, checkfirst=True)