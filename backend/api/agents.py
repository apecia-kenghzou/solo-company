"""Agent management and approval router."""
from __future__ import annotations

import logging
import uuid
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from api.deps import get_current_user, get_db
from models.content import AgentAction, ContentDraft
from models.user import User

# ContentDraft is imported for use in the status endpoint pending-approval count.

log = logging.getLogger(__name__)
router = APIRouter()


# ---------------------------------------------------------------------------
# Pydantic schemas
# ---------------------------------------------------------------------------

class AgentStatusResponse(BaseModel):
    agent_statuses: Dict[str, Any]
    pending_approvals: int


class AgentActionResponse(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    agent_name: str
    action_type: str
    input_data: Dict[str, Any]
    output_data: Dict[str, Any]
    status: str
    error_message: Optional[str]
    created_at: Any
    updated_at: Any

    class Config:
        from_attributes = True


class ContentDraftResponse(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    listing_id: Optional[uuid.UUID]
    type: str
    platform: str
    caption: str
    image_url: Optional[str]
    hashtags: List[Any]
    scheduled_at: Optional[Any]
    published_at: Optional[Any]
    status: str
    approval_notes: Optional[str]
    buffer_post_id: Optional[str]
    engagement_data: Optional[Dict[str, Any]]
    created_at: Any
    updated_at: Any

    class Config:
        from_attributes = True


class PaginatedActions(BaseModel):
    items: List[AgentActionResponse]
    total: int
    page: int
    page_size: int


class TriggerMarketingRequest(BaseModel):
    listing_id: Optional[uuid.UUID] = None
    content_types: Optional[List[str]] = None
    platforms: Optional[List[str]] = None


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.get("/status", response_model=AgentStatusResponse)
async def get_agent_status(
    current_user: User = Depends(get_current_user),
) -> AgentStatusResponse:
    """Return current agent run statuses from Redis.

    Reads the latest briefing and trend scan statuses stored by Celery tasks
    plus counts pending content approvals.
    """
    import json
    from datetime import datetime, timezone
    from config.settings import settings

    agent_statuses: Dict[str, Any] = {}

    try:
        import redis
        r = redis.from_url(settings.redis_url, decode_responses=True)
        today_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        week_str = datetime.now(timezone.utc).strftime("%Y-W%W")

        # Morning briefing
        briefing_raw = r.get(f"briefing:{current_user.id}:{today_str}")
        if briefing_raw:
            briefing = json.loads(briefing_raw)
            agent_statuses["briefing_agent"] = {
                "status": "completed",
                "generated_at": briefing.get("generated_at"),
                "leads_to_follow_up": len(briefing.get("leads_to_follow_up", [])),
            }
        else:
            agent_statuses["briefing_agent"] = {"status": "not_run_today"}

        # Social trends
        tiktok_raw = r.get(f"trends:tiktok:{today_str}")
        agent_statuses["social_trend_agent"] = {
            "status": "completed" if tiktok_raw else "not_run_today",
            "tiktok_results": len(json.loads(tiktok_raw)) if tiktok_raw else 0,
        }

        # Market report
        market_raw = r.get(f"market_report:{week_str}")
        agent_statuses["research_agent"] = {
            "status": "completed" if market_raw else "not_run_this_week",
        }

        r.close()
    except Exception as exc:
        log.warning("agents.status_redis_failed", error=str(exc))
        agent_statuses["redis"] = f"unavailable: {exc}"

    # Pending approvals count
    from models.base import AsyncSessionLocal
    async with AsyncSessionLocal() as session:
        pending = (await session.execute(
            select(func.count()).select_from(ContentDraft).where(
                and_(
                    ContentDraft.user_id == current_user.id,
                    ContentDraft.status == "pending_approval",
                )
            )
        )).scalar() or 0

    return AgentStatusResponse(
        agent_statuses=agent_statuses,
        pending_approvals=pending,
    )


@router.post("/trigger/research/{listing_id}")
async def trigger_research(
    listing_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Dict[str, Any]:
    """Manually trigger property research for a specific listing."""
    from models.listing import Listing

    result = await db.execute(
        select(Listing).where(
            Listing.id == listing_id,
            Listing.user_id == current_user.id,
        )
    )
    listing = result.scalar_one_or_none()
    if not listing:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Listing {listing_id} not found",
        )

    try:
        from workers.tasks import run_property_research
        task = run_property_research.delay(str(listing_id))
        log.info("agents.research_triggered", listing_id=str(listing_id), task_id=task.id)
        return {"status": "queued", "task_id": task.id, "listing_id": str(listing_id)}
    except Exception as exc:
        log.error("agents.research_trigger_failed", error=str(exc))
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Failed to queue research task: {exc}",
        )


@router.post("/trigger/marketing")
async def trigger_marketing(
    body: TriggerMarketingRequest,
    current_user: User = Depends(get_current_user),
) -> Dict[str, Any]:
    """Manually trigger marketing content generation for the current user.

    Dispatches a task that will use the MarketingAgent (M4) to generate
    content drafts for the specified platforms.
    """
    # MarketingAgent graph will be implemented in M4.
    # For now we return a queued response and log the intent.
    log.info(
        "agents.marketing_triggered",
        user_id=str(current_user.id),
        listing_id=str(body.listing_id) if body.listing_id else None,
        platforms=body.platforms,
    )

    # Placeholder task dispatch — real agent graph wired in M4
    return {
        "status": "queued",
        "user_id": str(current_user.id),
        "listing_id": str(body.listing_id) if body.listing_id else None,
        "platforms": body.platforms or ["instagram", "facebook"],
        "note": "MarketingAgent will be fully wired in Milestone 4",
    }


@router.post("/trigger/briefing")
async def trigger_briefing(
    current_user: User = Depends(get_current_user),
) -> Dict[str, Any]:
    """Manually generate the morning briefing for the current user."""
    try:
        from workers.tasks import generate_morning_briefing
        task = generate_morning_briefing.delay(str(current_user.id))
        log.info("agents.briefing_triggered", user_id=str(current_user.id), task_id=task.id)
        return {
            "status": "queued",
            "task_id": task.id,
            "user_id": str(current_user.id),
        }
    except Exception as exc:
        log.error("agents.briefing_trigger_failed", error=str(exc))
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Failed to queue briefing task: {exc}",
        )


@router.get("/actions", response_model=PaginatedActions)
async def list_agent_actions(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    agent_name: Optional[str] = Query(None),
    action_status: Optional[str] = Query(None, alias="status"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> PaginatedActions:
    """List recent agent actions (audit log) for the current user."""
    q = select(AgentAction).where(AgentAction.user_id == current_user.id)

    if agent_name:
        q = q.where(AgentAction.agent_name == agent_name)
    if action_status:
        q = q.where(AgentAction.status == action_status)

    q = q.order_by(AgentAction.created_at.desc())

    count_q = select(func.count()).select_from(q.subquery())
    total = (await db.execute(count_q)).scalar() or 0

    q = q.offset((page - 1) * page_size).limit(page_size)
    rows = (await db.execute(q)).scalars().all()

    return PaginatedActions(
        items=[AgentActionResponse.model_validate(r) for r in rows],
        total=total,
        page=page,
        page_size=page_size,
    )


