"""Approvals router — review, approve, reject, or request changes on ContentDraft records."""
from __future__ import annotations

import logging
import uuid
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from api.deps import get_current_user, get_db
from models.content import ContentDraft
from models.listing import Listing
from models.user import User

log = logging.getLogger(__name__)
router = APIRouter()


# ---------------------------------------------------------------------------
# Pydantic schemas
# ---------------------------------------------------------------------------

class NotesRequest(BaseModel):
    notes: str


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

async def _get_draft_or_404(
    db: AsyncSession,
    draft_id: uuid.UUID,
    user_id: uuid.UUID,
) -> ContentDraft:
    result = await db.execute(
        select(ContentDraft).where(
            ContentDraft.id == draft_id,
            ContentDraft.user_id == user_id,
        )
    )
    draft = result.scalar_one_or_none()
    if not draft:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"ContentDraft {draft_id} not found",
        )
    return draft


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.get("")
async def list_pending_approvals(
    type: Optional[str] = Query(None, description="Filter by content type"),
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Dict[str, Any]:
    """List ContentDraft records pending approval, oldest first."""
    q = select(ContentDraft).where(
        and_(
            ContentDraft.user_id == current_user.id,
            ContentDraft.status == "pending_approval",
        )
    )

    if type:
        q = q.where(ContentDraft.type == type)

    q = q.order_by(ContentDraft.created_at.asc())

    # Count
    count_q = select(func.count()).select_from(q.subquery())
    total = (await db.execute(count_q)).scalar() or 0

    # Paginate
    q = q.offset((page - 1) * per_page).limit(per_page)
    drafts = (await db.execute(q)).scalars().all()

    # Collect listing names
    listing_ids = {d.listing_id for d in drafts if d.listing_id}
    listing_names: Dict[Any, str] = {}
    if listing_ids:
        rows = (await db.execute(
            select(Listing.id, Listing.name).where(Listing.id.in_(listing_ids))
        )).all()
        listing_names = {row.id: row.name for row in rows}

    items = [
        {
            "id": str(d.id),
            "type": d.type,
            "platform": d.platform,
            "caption": d.caption,
            "image_url": d.image_url,
            "hashtags": d.hashtags or [],
            "listing_id": str(d.listing_id) if d.listing_id else None,
            "listing_name": listing_names.get(d.listing_id) if d.listing_id else None,
            "scheduled_at": d.scheduled_at.isoformat() if d.scheduled_at else None,
            "created_at": d.created_at.isoformat(),
        }
        for d in drafts
    ]

    return {
        "items": items,
        "total": total,
        "page": page,
        "per_page": per_page,
    }


@router.post("/{draft_id}/approve")
async def approve_draft(
    draft_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Dict[str, Any]:
    """Approve a pending content draft."""
    draft = await _get_draft_or_404(db, draft_id, current_user.id)

    draft.status = "approved"
    if draft.scheduled_at:
        draft.status = "scheduled"

    await db.commit()
    log.info("approvals.approved", draft_id=str(draft_id), user_id=str(current_user.id))
    return {"status": "approved", "id": str(draft_id)}


@router.post("/{draft_id}/reject")
async def reject_draft(
    draft_id: uuid.UUID,
    body: NotesRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Dict[str, Any]:
    """Reject a pending content draft with notes."""
    draft = await _get_draft_or_404(db, draft_id, current_user.id)

    draft.status = "rejected"
    draft.approval_notes = body.notes

    await db.commit()
    log.info("approvals.rejected", draft_id=str(draft_id), user_id=str(current_user.id))
    return {"status": "rejected"}


@router.post("/{draft_id}/request-changes")
async def request_changes(
    draft_id: uuid.UUID,
    body: NotesRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Dict[str, Any]:
    """Send a draft back to agent for revision with notes."""
    draft = await _get_draft_or_404(db, draft_id, current_user.id)

    draft.status = "draft"
    draft.approval_notes = body.notes

    await db.commit()
    log.info("approvals.revision_requested", draft_id=str(draft_id), user_id=str(current_user.id))
    return {"status": "revision_requested"}
