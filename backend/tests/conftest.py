"""Test setup: the API tests run against a real (SQLite) database file,
exercising actual SQL — schema, constraints, and queries — not mocks.
"""

import os

# Must be set before any app module is imported (engine is created at import time).
os.environ["DATABASE_URL"] = "sqlite+aiosqlite:///./test.db"

import pytest_asyncio  # noqa: E402
from httpx import ASGITransport, AsyncClient  # noqa: E402

from app.db import engine  # noqa: E402
from app.main import app  # noqa: E402
from app.ratelimit import limiter  # noqa: E402
from app.schema import metadata  # noqa: E402

limiter.enabled = False


@pytest_asyncio.fixture
async def client():
    async with engine.begin() as conn:
        await conn.run_sync(metadata.drop_all)
        await conn.run_sync(metadata.create_all)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


@pytest_asyncio.fixture
async def alice(client: AsyncClient) -> dict:
    """Registers a fresh user; returns their auth headers and user record."""
    resp = await client.post(
        "/api/v1/auth/register",
        json={"email": "alice@example.com", "display_name": "Alice", "password": "secret-pass-1"},
    )
    assert resp.status_code == 201, resp.text
    data = resp.json()
    return {
        "headers": {"Authorization": f"Bearer {data['access_token']}"},
        "user": data["user"],
    }
