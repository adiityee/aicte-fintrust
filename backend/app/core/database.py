from collections.abc import AsyncGenerator
import json
import logging
import os
import sys
import uuid
from typing import Any, Optional

from sqlalchemy import CHAR, Text, text
from sqlalchemy.dialects.postgresql import JSONB as PG_JSONB, UUID as PG_UUID
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.types import TypeDecorator

from app.core.config import settings

logger = logging.getLogger("fintrust.database")


# SQLAlchemy 2.0 Declarative Base
class Base(DeclarativeBase):
    pass


# ---------------------------------------------------------------------------
# Cross-Platform Types (PostgreSQL & SQLite Compatible)
# ---------------------------------------------------------------------------

class CompatibleUUID(TypeDecorator):
    """
    Platform-independent UUID type.
    Uses PostgreSQL's native UUID type if available, otherwise CHAR(36) for SQLite.
    """
    impl = CHAR
    cache_ok = True

    def load_dialect_impl(self, dialect):
        if dialect.name == "postgresql":
            return dialect.type_descriptor(PG_UUID(as_uuid=True))
        return dialect.type_descriptor(CHAR(36))

    def process_bind_param(self, value, dialect):
        if value is None:
            return value
        if dialect.name == "postgresql":
            return str(value)
        if isinstance(value, uuid.UUID):
            return str(value)
        return str(uuid.UUID(str(value)))

    def process_result_value(self, value, dialect):
        if value is None:
            return value
        if isinstance(value, uuid.UUID):
            return value
        return uuid.UUID(str(value))


class CompatibleJSON(TypeDecorator):
    """
    Platform-independent JSON type.
    Uses PostgreSQL's native JSONB if available, otherwise Text storing JSON string for SQLite.
    """
    impl = Text
    cache_ok = True

    def load_dialect_impl(self, dialect):
        if dialect.name == "postgresql":
            return dialect.type_descriptor(PG_JSONB())
        return dialect.type_descriptor(Text())

    def process_bind_param(self, value, dialect):
        if value is None:
            return value
        if dialect.name == "postgresql":
            return value
        return json.dumps(value)

    def process_result_value(self, value, dialect):
        if value is None:
            return value
        if dialect.name == "postgresql":
            return value
        if isinstance(value, str):
            try:
                return json.loads(value)
            except Exception:
                return value
        return value


# ---------------------------------------------------------------------------
# Dynamic Engine Configuration with Graceful SQLite Fallback
# ---------------------------------------------------------------------------

# Resolve unified local SQLite database path: ./fintrust.db
BACKEND_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
SQLITE_DB_PATH = os.path.join(BACKEND_DIR, "fintrust.db").replace("\\", "/")
FALLBACK_SQLITE_URL = f"sqlite+aiosqlite:///{SQLITE_DB_PATH}"


def get_configured_database_url() -> str:
    """Returns configured DATABASE_URL, defaulting to SQLite if empty."""
    url = os.getenv("DATABASE_URL", settings.DATABASE_URL)
    if not url or url.strip() == "":
        return FALLBACK_SQLITE_URL
    return url


def create_engine_instance(db_url: str) -> AsyncEngine:
    """Creates an AsyncEngine instance with appropriate connect args."""
    kwargs: dict[str, Any] = {
        "echo": False,
        "future": True,
    }
    if "asyncpg" in db_url:
        kwargs["connect_args"] = {
            "timeout": 1.5,
            "command_timeout": 3.0,
        }
        kwargs["pool_pre_ping"] = True
    elif "sqlite" in db_url:
        kwargs["connect_args"] = {"check_same_thread": False}
    return create_async_engine(db_url, **kwargs)


current_database_url = get_configured_database_url()
engine: AsyncEngine = create_engine_instance(current_database_url)

# Async Sessionmaker
async_session_maker: async_sessionmaker[AsyncSession] = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
)


def switch_to_sqlite() -> None:
    """Switches the active global engine and session maker to local SQLite database."""
    global engine, async_session_maker, current_database_url
    if "sqlite" in current_database_url:
        return
    current_database_url = FALLBACK_SQLITE_URL
    engine = create_engine_instance(FALLBACK_SQLITE_URL)
    async_session_maker.configure(bind=engine)


async def init_db() -> None:
    """
    Initialize database tables.
    If PostgreSQL fails or is unreachable, automatically falls back to local SQLite.
    """
    global engine, async_session_maker, current_database_url
    try:
        async with engine.begin() as conn:
            # Connectivity probe
            await conn.execute(text("SELECT 1"))
            await conn.run_sync(Base.metadata.create_all)
        print(f"[FinTrust DB] Initialized tables on: {engine.url}")
    except Exception as exc:
        if "sqlite" not in str(engine.url):
            print(f"[FinTrust DB] PostgreSQL connection failed ({exc}). Switching to local SQLite fallback: {FALLBACK_SQLITE_URL}")
            switch_to_sqlite()
            async with engine.begin() as conn:
                await conn.run_sync(Base.metadata.create_all)
            print(f"[FinTrust DB] Initialized fallback SQLite tables on: {engine.url}")
        else:
            raise


# FastAPI Database Session Dependency
async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """
    FastAPI dependency yielding an async database session.
    Automatically catches PostgreSQL disconnects and falls back to SQLite.
    """
    global engine, async_session_maker, current_database_url
    try:
        async with async_session_maker() as session:
            # Connectivity probe if on PostgreSQL
            if "postgresql" in str(engine.url):
                await session.execute(text("SELECT 1"))
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise
            finally:
                await session.close()
    except Exception as exc:
        if "postgresql" in str(engine.url):
            print(f"[FinTrust DB] Connection failed on request ({exc}). Switching to SQLite fallback...")
            switch_to_sqlite()
            async with engine.begin() as conn:
                await conn.run_sync(Base.metadata.create_all)
            async with async_session_maker() as session:
                try:
                    yield session
                    await session.commit()
                except Exception:
                    await session.rollback()
                    raise
                finally:
                    await session.close()
        else:
            raise
