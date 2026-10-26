from collections.abc import AsyncGenerator
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

from app.core.config import settings


# SQLAlchemy 2.0 Declarative Base
class Base(DeclarativeBase):
    pass


# SQLAlchemy 2.0 Async Engine with asyncpg
engine_kwargs = {
    "echo": False,
    "future": True,
    "pool_pre_ping": True,
}

if "asyncpg" in settings.DATABASE_URL:
    engine_kwargs["connect_args"] = {
        "timeout": 2.0,
        "command_timeout": 5.0,
    }

engine: AsyncEngine = create_async_engine(
    settings.DATABASE_URL,
    **engine_kwargs,
)

# Async Sessionmaker
async_session_maker: async_sessionmaker[AsyncSession] = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
)


# FastAPI Database Session Dependency
async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with async_session_maker() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def init_db() -> None:
    """Initialize database tables."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
