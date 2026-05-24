"""Health check router — reports DB, Redis, and Pinecone connectivity."""
from __future__ import annotations

import logging
from typing import Any, Dict

from fastapi import APIRouter

log = logging.getLogger(__name__)

router = APIRouter(tags=["health"])


@router.get("/health", summary="System health check")
async def health_check() -> Dict[str, Any]:
    """Return the health status of all backend dependencies.

    Checks:
    - PostgreSQL: simple SELECT 1
    - Redis: PING command
    - Pinecone: describe_index_stats (non-blocking, degraded if unavailable)
    """
    status: Dict[str, Any] = {
        "status": "ok",
        "version": "0.1.0",
        "dependencies": {},
    }

    # --- PostgreSQL ---
    try:
        from models.base import AsyncSessionLocal
        from sqlalchemy import text

        async with AsyncSessionLocal() as session:
            await session.execute(text("SELECT 1"))
        status["dependencies"]["postgres"] = "ok"
    except Exception as exc:
        log.error("health.postgres_fail", error=str(exc))
        status["dependencies"]["postgres"] = f"error: {exc}"
        status["status"] = "degraded"

    # --- Redis ---
    try:
        import redis.asyncio as aioredis
        from config.settings import settings

        r = aioredis.from_url(settings.redis_url)
        pong = await r.ping()
        await r.aclose()
        status["dependencies"]["redis"] = "ok" if pong else "no_pong"
    except Exception as exc:
        log.error("health.redis_fail", error=str(exc))
        status["dependencies"]["redis"] = f"error: {exc}"
        status["status"] = "degraded"

    # --- Pinecone ---
    try:
        from knowledge.pinecone_store import get_pinecone_index

        index = get_pinecone_index()
        stats = index.describe_index_stats()
        status["dependencies"]["pinecone"] = {
            "status": "ok",
            "total_vector_count": stats.get("total_vector_count", 0),
        }
    except Exception as exc:
        log.warning("health.pinecone_skipped", reason=str(exc))
        status["dependencies"]["pinecone"] = f"unavailable: {exc}"
        # Pinecone being down is degraded but not critical for basic ops

    return status
