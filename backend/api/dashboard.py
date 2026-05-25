"""Dashboard router — stats, overdue leads, and agent action feed."""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends
from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from api.deps import get_current_user, get_db
from models.content import AgentAction, ContentDraft
from models.lead import Lead
from models.listing import Listing
from models.user import User

log = logging.getLogger(__name__)
router = APIRouter()


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.get("/stats")
async def get_dashboard_stats(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Dict[str, int]:
    """Return the four stat-card counts for the current user."""
    now = datetime.now(timezone.utc)
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)

    # New leads today
    new_leads_today = (await db.execute(
        select(func.count()).select_from(Lead).where(
            and_(
                Lead.user_id == current_user.id,
                Lead.created_at >= today_start,
            )
        )
    )).scalar() or 0

    # Pending content approvals
    pending_approvals = (await db.execute(
        select(func.count()).select_from(ContentDraft).where(
            and_(
                ContentDraft.user_id == current_user.id,
                ContentDraft.status == "pending_approval",
            )
        )
    )).scalar() or 0

    # Active listings
    active_listings = (await db.execute(
        select(func.count()).select_from(Listing).where(
            and_(
                Listing.user_id == current_user.id,
                Listing.status == "active",
            )
        )
    )).scalar() or 0

    # Hot leads not closed/lost
    hot_leads = (await db.execute(
        select(func.count()).select_from(Lead).where(
            and_(
                Lead.user_id == current_user.id,
                Lead.temperature == "hot",
                Lead.status.notin_(["closed", "lost"]),
            )
        )
    )).scalar() or 0

    return {
        "new_leads_today": new_leads_today,
        "pending_approvals": pending_approvals,
        "active_listings": active_listings,
        "hot_leads": hot_leads,
    }


@router.get("/overdue-leads")
async def get_overdue_leads(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> List[Dict[str, Any]]:
    """Return leads whose next_follow_up_at is in the past and are not closed/lost."""
    now = datetime.now(timezone.utc)

    result = await db.execute(
        select(Lead).where(
            and_(
                Lead.user_id == current_user.id,
                Lead.next_follow_up_at <= now,
                Lead.status.notin_(["closed", "lost", "offer"]),
            )
        ).order_by(Lead.next_follow_up_at.asc()).limit(20)
    )
    leads = result.scalars().all()

    # Collect listing IDs for a bulk join
    listing_ids = {lead.listing_id for lead in leads if lead.listing_id}
    listing_names: Dict[Any, str] = {}
    if listing_ids:
        listing_rows = (await db.execute(
            select(Listing.id, Listing.name).where(Listing.id.in_(listing_ids))
        )).all()
        listing_names = {row.id: row.name for row in listing_rows}

    def _iso(dt: Optional[datetime]) -> Optional[str]:
        return dt.isoformat() if dt else None

    return [
        {
            "id": str(lead.id),
            "name": lead.name,
            "phone": lead.phone,
            "email": lead.email,
            "status": lead.status,
            "temperature": lead.temperature,
            "property_type_interest": lead.property_type_interest,
            "last_contacted_at": _iso(lead.last_contacted_at),
            "next_follow_up_at": _iso(lead.next_follow_up_at),
            "listing_name": listing_names.get(lead.listing_id) if lead.listing_id else None,
        }
        for lead in leads
    ]


@router.get("/agent-actions")
async def get_agent_actions(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> List[Dict[str, Any]]:
    """Return the last 50 agent actions for the current user, newest first."""
    result = await db.execute(
        select(AgentAction).where(
            AgentAction.user_id == current_user.id
        ).order_by(AgentAction.created_at.desc()).limit(50)
    )
    actions = result.scalars().all()

    return [
        {
            "id": str(action.id),
            "agent_name": action.agent_name,
            "action_type": action.action_type,
            "status": action.status,
            "created_at": action.created_at.isoformat(),
            "output_data": str(action.output_data)[:200] if action.output_data else None,
        }
        for action in actions
    ]
