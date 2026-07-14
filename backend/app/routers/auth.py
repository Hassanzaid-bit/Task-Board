import sqlalchemy as sa
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncConnection

from ..db import get_conn
from ..deps import get_current_user
from ..models import LoginIn, RegisterIn, TokenOut, UserOut
from ..ratelimit import limiter
from ..schema import users
from ..security import create_access_token, hash_password, verify_password

router = APIRouter(prefix="/api/v1", tags=["auth"])


@router.post("/auth/register", response_model=TokenOut, status_code=201)
@limiter.limit("10/minute")
async def register(
    request: Request, body: RegisterIn, conn: AsyncConnection = Depends(get_conn)
) -> TokenOut:
    try:
        result = await conn.execute(
            sa.insert(users)
            .values(
                email=body.email.lower(),
                display_name=body.display_name,
                password_hash=hash_password(body.password),
            )
            .returning(users.c.id, users.c.email, users.c.display_name)
        )
    except IntegrityError:
        raise HTTPException(
            status_code=409, detail="An account with this email already exists"
        ) from None
    row = result.mappings().one()
    return TokenOut(access_token=create_access_token(row["id"]), user=UserOut(**row))


@router.post("/auth/login", response_model=TokenOut)
@limiter.limit("10/minute")
async def login(
    request: Request, body: LoginIn, conn: AsyncConnection = Depends(get_conn)
) -> TokenOut:
    row = (
        await conn.execute(sa.select(users).where(users.c.email == body.email.lower()))
    ).mappings().first()
    # Same error for unknown email and wrong password — don't leak which emails exist.
    if row is None or not verify_password(body.password, row["password_hash"]):
        raise HTTPException(status_code=401, detail="Invalid email or password")
    user = UserOut(id=row["id"], email=row["email"], display_name=row["display_name"])
    return TokenOut(access_token=create_access_token(user.id), user=user)


@router.get("/auth/me", response_model=UserOut)
async def me(user: dict = Depends(get_current_user)) -> UserOut:
    return UserOut(**{k: user[k] for k in ("id", "email", "display_name")})


@router.get("/users", response_model=list[UserOut])
async def list_users(
    user: dict = Depends(get_current_user), conn: AsyncConnection = Depends(get_conn)
) -> list[UserOut]:
    """All users, for the assignee picker."""
    query = sa.select(users.c.id, users.c.email, users.c.display_name).order_by(
        users.c.display_name
    )
    rows = (await conn.execute(query)).mappings().all()
    return [UserOut(**r) for r in rows]
