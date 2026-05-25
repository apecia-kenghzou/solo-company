"""Solo Agent OS — FastAPI application entrypoint."""
from __future__ import annotations

import os
from contextlib import asynccontextmanager
from typing import AsyncGenerator

import sentry_sdk
import socketio
import structlog
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from config.settings import settings

# ---------------------------------------------------------------------------
# Structured logging
# ---------------------------------------------------------------------------
structlog.configure(
    processors=[
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.dev.ConsoleRenderer(),
    ],
    wrapper_class=structlog.make_filtering_bound_logger(20),
    context_class=dict,
    logger_factory=structlog.PrintLoggerFactory(),
)

log = structlog.get_logger(__name__)

# ---------------------------------------------------------------------------
# Sentry (optional)
# ---------------------------------------------------------------------------
_sentry_dsn = os.getenv("SENTRY_DSN", "")
if _sentry_dsn:
    sentry_sdk.init(
        dsn=_sentry_dsn,
        environment=settings.app_env,
        traces_sample_rate=0.1,
    )
    log.info("sentry.init", dsn=_sentry_dsn[:30] + "...")

# ---------------------------------------------------------------------------
# Socket.IO
# ---------------------------------------------------------------------------
sio = socketio.AsyncServer(
    async_mode="asgi",
    cors_allowed_origins=settings.frontend_url,
    logger=False,
    engineio_logger=False,
)


@sio.event
async def connect(sid: str, environ: dict) -> None:
    log.info("socketio.connect", sid=sid)


@sio.event
async def disconnect(sid: str) -> None:
    log.info("socketio.disconnect", sid=sid)


# ---------------------------------------------------------------------------
# Lifespan
# ---------------------------------------------------------------------------
@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Startup and shutdown logic."""
    log.info("startup.begin", env=settings.app_env)

    # --- Database init ---
    try:
        from models.base import init_db
        await init_db()
        log.info("startup.db_ready")
    except Exception as exc:  # pragma: no cover
        log.error("startup.db_error", error=str(exc))

    # --- Pinecone ---
    try:
        from knowledge.pinecone_store import init_pinecone
        init_pinecone()
        log.info("startup.pinecone_ready")
    except Exception as exc:  # pragma: no cover
        log.warning("startup.pinecone_skipped", reason=str(exc))

    # --- Object storage (MinIO / Garage / S3) ---
    # ensure_bucket() is a no-op if the bucket already exists; safe on every boot.
    try:
        from tools.s3 import storage
        await storage.ensure_bucket()
        log.info(
            "startup.storage_ready",
            provider=settings.s3_provider,
            bucket=settings.s3_bucket_name,
        )
    except Exception as exc:  # pragma: no cover
        log.warning("startup.storage_skipped", reason=str(exc))

    log.info("startup.complete", version="0.1.0")
    yield

    log.info("shutdown.begin")


# ---------------------------------------------------------------------------
# FastAPI app
# ---------------------------------------------------------------------------
app = FastAPI(
    title="Solo Agent OS",
    version="0.1.0",
    description="An Autonomous Business Brain for the One-Person Company",
    lifespan=lifespan,
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.frontend_url],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------------------------------------------------------------------
# Routers
# ---------------------------------------------------------------------------
from api.health import router as health_router
from api.leads import router as leads_router
from api.listings import router as listings_router
from api.agents import router as agents_router
from api.webhooks import router as webhooks_router

app.include_router(health_router, prefix="/api")
app.include_router(leads_router, prefix="/api/leads", tags=["leads"])
app.include_router(listings_router, prefix="/api/listings", tags=["listings"])
app.include_router(agents_router, prefix="/api/agents", tags=["agents"])
app.include_router(webhooks_router, prefix="/api/webhooks", tags=["webhooks"])


# ---------------------------------------------------------------------------
# Root health check (short-form)
# ---------------------------------------------------------------------------
@app.get("/health", tags=["health"])
async def health_check() -> dict:
    return {"status": "ok", "version": "0.1.0"}


# ---------------------------------------------------------------------------
# Mount Socket.IO ASGI app at /ws
# ---------------------------------------------------------------------------
socket_app = socketio.ASGIApp(sio, other_asgi_app=app)

# Expose as top-level for uvicorn: `uvicorn main:socket_app`
# (Keep `app` as the plain FastAPI object for testing)
