import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi.errors import RateLimitExceeded

from .db import init_db
from .ratelimit import limiter
from .routers import auth, projects, tasks, ws

logger = logging.getLogger("taskboard")


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Retry because the db container can accept TCP before it's ready to serve.
    for attempt in range(10):
        try:
            await init_db()
            break
        except Exception:
            if attempt == 9:
                raise
            logger.warning("Database not ready, retrying...")
            await asyncio.sleep(2)
    yield


app = FastAPI(title="Task Board API", lifespan=lifespan)
app.state.limiter = limiter

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Consistent error shape across the API: {"detail": {"code": ..., "message": ...}}
_ERROR_CODES = {401: "unauthorized", 404: "not_found", 409: "conflict", 422: "invalid_input"}


@app.exception_handler(HTTPException)
async def http_error_handler(request: Request, exc: HTTPException):
    return JSONResponse(
        status_code=exc.status_code,
        headers=getattr(exc, "headers", None),
        content={
            "detail": {
                "code": _ERROR_CODES.get(exc.status_code, "error"),
                "message": exc.detail if isinstance(exc.detail, str) else str(exc.detail),
            }
        },
    )


@app.exception_handler(RequestValidationError)
async def validation_error_handler(request: Request, exc: RequestValidationError):
    return JSONResponse(
        status_code=422,
        content={
            "detail": {
                "code": "validation_error",
                "message": "Request validation failed",
                "errors": [
                    {"field": ".".join(str(p) for p in e["loc"][1:]), "message": e["msg"]}
                    for e in exc.errors()
                ],
            }
        },
    )


@app.exception_handler(RateLimitExceeded)
async def rate_limit_handler(request: Request, exc: RateLimitExceeded):
    return JSONResponse(
        status_code=429,
        content={
            "detail": {
                "code": "rate_limited",
                "message": f"Too many requests: {exc.detail}. Try again shortly.",
            }
        },
    )


@app.get("/api/v1/health")
async def health() -> dict:
    return {"status": "ok"}


app.include_router(auth.router)
app.include_router(projects.router)
app.include_router(tasks.router)
app.include_router(ws.router)
