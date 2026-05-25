"""Content router — calendar view, published posts, and content generation trigger."""
from __future__ import annotations

import logging
from datetime import date, datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy import and_, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from api.deps import get_current_user, get_db
from models.content import ContentDraft
from models.user import User

log = logging.getLogger(__name__)
router = APIRouter()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _week_bounds(week_offset: int = 0) -> tuple[date, date]:
    """Return the Monday and Sunday of the ISO week offset from today."""
    today = datetime.now(timezone.utc).date()
    # isoweekday: Mon=1 … Sun=7
    monday = today - timedelta(days=today.isoweekday() - 1) + timedelta(weeks=week_offset)
    sunday = monday + timedelta(days=6)
    return monday, sunday


def _draft_to_dict(draft: ContentDraft, full: bool = False) -> Dict[str, Any]:
    """Serialize a ContentDraft to a plain dict."""
    data: Dict[str, Any] = {
        "id": str(draft.id),
        "type": draft.type,
        "platform": draft.platform,
        "caption": draft.caption[:100] if not full else draft.caption,
        "image_url": draft.image_url,
        "status": draft.status,
        "scheduled_at": draft.scheduled_at.isoformat() if draft.scheduled_at else None,
    }
    if full:
        data.update(
            {
                "hashtags": draft.hashtags or [],
                "listing_id": str(draft.listing_id) if draft.listing_id else None,
                "approval_notes": draft.approval_notes,
                "buffer_post_id": draft.buffer_post_id,
                "engagement_data": draft.engagement_data,
                "published_at": draft.published_at.isoformat() if draft.published_at else None,
                "created_at": draft.created_at.isoformat(),
                "updated_at": draft.updated_at.isoformat() if draft.updated_at else None,
            }
        )
    return data


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.get("/calendar")
async def get_content_calendar(
    week_offset: int = Query(0, description="0 = current week, -1 = last week, 1 = next week"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Dict[str, Any]:
    """Return all content drafts for a given ISO week, grouped by weekday (0=Mon)."""
    monday, sunday = _week_bounds(week_offset)

    # Build datetime boundaries (inclusive, UTC midnight-to-midnight)
    week_start_dt = datetime(monday.year, monday.month, monday.day, tzinfo=timezone.utc)
    week_end_dt = datetime(sunday.year, sunday.month, sunday.day, 23, 59, 59, tzinfo=timezone.utc)

    result = await db.execute(
        select(ContentDraft).where(
            and_(
                ContentDraft.user_id == current_user.id,
                ContentDraft.scheduled_at >= week_start_dt,
                ContentDraft.scheduled_at <= week_end_dt,
                or_(
                    ContentDraft.status.in_(["approved", "scheduled", "published"]),
                    ContentDraft.status == "draft",
                ),
            )
        ).order_by(ContentDraft.scheduled_at.asc())
    )
    drafts = result.scalars().all()

    # Group by weekday number (0=Mon … 6=Sun)
    posts: Dict[str, List[Dict[str, Any]]] = {str(i): [] for i in range(7)}
    for draft in drafts:
        if draft.scheduled_at:
            # Convert to local weekday index; Monday = 0
            day_idx = draft.scheduled_at.weekday()
            posts[str(day_idx)].append(_draft_to_dict(draft))

    return {
        "week_start": monday.isoformat(),
        "week_end": sunday.isoformat(),
        "posts": posts,
    }


@router.get("/published")
async def get_published_content(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> List[Dict[str, Any]]:
    """Return the last 30 published content drafts, newest first."""
    result = await db.execute(
        select(ContentDraft).where(
            and_(
                ContentDraft.user_id == current_user.id,
                ContentDraft.status == "published",
            )
        ).order_by(ContentDraft.published_at.desc().nullslast()).limit(30)
    )
    drafts = result.scalars().all()
    return [_draft_to_dict(draft, full=True) for draft in drafts]


@router.post("/generate-week")
async def generate_week(
    current_user: User = Depends(get_current_user),
) -> Dict[str, Any]:
    """Trigger the MarketingAgent to generate a full week of content drafts."""
    try:
        from workers.tasks import run_marketing_week

        task = run_marketing_week.delay(str(current_user.id))
        log.info("content.generate_week.triggered", user_id=str(current_user.id), task_id=task.id)
        return {"status": "triggered", "task_id": task.id}
    except Exception as exc:
        log.error("content.generate_week.failed", user_id=str(current_user.id), error=str(exc))
        # Return a response even if Celery is unavailable (dev mode)
        return {"status": "triggered", "task_id": "unavailable", "error": str(exc)}
