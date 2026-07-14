import sqlalchemy as sa
from fastapi import Depends, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncConnection

from .db import get_conn
from .schema import users
from .security import decode_access_token


def _extract_bearer_token(request: Request) -> str:
    auth = request.headers.get("Authorization", "")
    scheme, _, token = auth.partition(" ")
    if scheme.lower() != "bearer" or not token:
        raise HTTPException(status_code=401, detail="Missing or malformed Authorization header")
    return token


async def get_current_user(
    request: Request, conn: AsyncConnection = Depends(get_conn)
) -> dict:
    """Resolves the JWT to a user row; 401 on any failure."""
    user_id = decode_access_token(_extract_bearer_token(request))
    if user_id is None:
        raise HTTPException(status_code=401, detail="Invalid or expired token")
    row = (
        await conn.execute(sa.select(users).where(users.c.id == user_id))
    ).mappings().first()
    if row is None:
        raise HTTPException(status_code=401, detail="User no longer exists")
    return dict(row)
