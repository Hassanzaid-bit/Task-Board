from collections.abc import AsyncIterator

from sqlalchemy.ext.asyncio import AsyncConnection, AsyncEngine, create_async_engine

from . import config
from .schema import metadata

engine: AsyncEngine = create_async_engine(config.DATABASE_URL)


async def init_db() -> None:
    async with engine.begin() as conn:
        await conn.run_sync(metadata.create_all)


async def get_conn() -> AsyncIterator[AsyncConnection]:
    """One transaction per request: commits on success, rolls back on error."""
    async with engine.begin() as conn:
        yield conn
