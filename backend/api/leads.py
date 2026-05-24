"""Leads CRUD router."""
from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from api.deps import get_current_user, get_db
from models.lead import Lead
from models.user import User

log = logging.getLogger(__name__)
router = APIRouter()


# ---------------------------------------------------------------------------
# Pydantic schemas
# ---------------------------------------------------------------------------

class LeadCreate(BaseModel):
    name: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    source: str = "website"
    listing_id: Optional[uuid.UUID] = None
    budget_min: Optional[float] = None
    budget_max: Optional[float] = None
    timeline: Optional[str] = None
    pre_approved: Optional[bool] = None
    property_type_interest: Optional[str] = None
    preferred_area: Optional[str] = None
    notes: Optional[str] = None
    temperature: str = "cold"


class LeadUpdate(BaseModel):
    name: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    status: Optional[str] = None
    temperature: Optional[str] = None
    budget_min: Optional[float] = None
    budget_max: Optional[float] = None
    timeline: Optional[str] = None
    pre_approved: Optional[bool] = None
    property_type_interest: Optional[str] = None
    preferred_area: Optional[str] = None
    notes: Optional[str] = None
    listing_id: Optional[uuid.UUID] = None
    next_follow_up_at: Optional[datetime] = None


class MessageAdd(BaseModel):
    role: str = Field(..., description="user | assistant | agent")
    content: str


class EscalateRequest(BaseModel):
    reason: Optional[str] = None


class LeadResponse(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    listing_id: Optional[uuid.UUID]
    name: Optional[str]
    email: Optional[str]
    phone: Optional[str]
    source: str
    status: str
    budget_min: Optional[float]
    budget_max: Optional[float]
    timeline: Optional[str]
    pre_approved: Optional[bool]
    property_type_interest: Optional[str]
    preferred_area: Optional[str]
    notes: Optional[str]
    conversation_history: List[Any]
    last_contacted_at: Optional[datetime]
    next_follow_up_at: Optional[datetime]
    follow_up_count: int
    temperature: str
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class PaginatedLeads(BaseModel):
    items: List[LeadResponse]
    total: int
    page: int
    page_size: int


class LeadStats(BaseModel):
    total: int
    by_status: Dict[str, int]
    by_temperature: Dict[str, int]


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.get("/stats", response_model=LeadStats)
async def get_lead_stats(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> LeadStats:
    """Return lead counts grouped by status and temperature for dashboard cards."""
    # Status counts
    status_rows = (await db.execute(
        select(Lead.status, func.count().label("cnt"))
        .where(Lead.user_id == current_user.id)
        .group_by(Lead.status)
    )).all()

    # Temperature counts
    temp_rows = (await db.execute(
        select(Lead.temperature, func.count().label("cnt"))
        .where(Lead.user_id == current_user.id)
        .group_by(Lead.temperature)
    )).all()

    total = sum(r.cnt for r in status_rows)

    return LeadStats(
        total=total,
        by_status={r.status: r.cnt for r in status_rows},
        by_temperature={r.temperature: r.cnt for r in temp_rows},
    )


@router.get("/", response_model=PaginatedLeads)
async def list_leads(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    status_filter: Optional[str] = Query(None, alias="status"),
    listing_id: Optional[uuid.UUID] = Query(None),
    temperature: Optional[str] = Query(None),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> PaginatedLeads:
    """List leads for the authenticated user with optional filters."""
    q = select(Lead).where(Lead.user_id == current_user.id)

    if status_filter:
        q = q.where(Lead.status == status_filter)
    if listing_id:
        q = q.where(Lead.listing_id == listing_id)
    if temperature:
        q = q.where(Lead.temperature == temperature)

    q = q.order_by(Lead.created_at.desc())

    # Count
    count_q = select(func.count()).select_from(q.subquery())
    total = (await db.execute(count_q)).scalar() or 0

    # Page
    q = q.offset((page - 1) * page_size).limit(page_size)
    rows = (await db.execute(q)).scalars().all()

    return PaginatedLeads(
        items=[LeadResponse.model_validate(r) for r in rows],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.post("/", response_model=LeadResponse, status_code=status.HTTP_201_CREATED)
async def create_lead(
    body: LeadCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> LeadResponse:
    """Create a lead manually (e.g. from the dashboard)."""
    lead = Lead(
        user_id=current_user.id,
        **body.model_dump(exclude_none=False),
    )
    db.add(lead)
    await db.commit()
    await db.refresh(lead)
    log.info("lead.created", lead_id=str(lead.id), source=lead.source)
    return LeadResponse.model_validate(lead)


@router.get("/{lead_id}", response_model=LeadResponse)
async def get_lead(
    lead_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> LeadResponse:
    """Get a single lead including full conversation history."""
    lead = await _get_or_404(db, lead_id, current_user.id)
    return LeadResponse.model_validate(lead)


@router.put("/{lead_id}", response_model=LeadResponse)
async def update_lead(
    lead_id: uuid.UUID,
    body: LeadUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> LeadResponse:
    """Update lead status, notes, or qualification fields."""
    lead = await _get_or_404(db, lead_id, current_user.id)
    updates = body.model_dump(exclude_none=True)
    for key, value in updates.items():
        setattr(lead, key, value)

    await db.commit()
    await db.refresh(lead)
    return LeadResponse.model_validate(lead)


@router.post("/{lead_id}/message", response_model=LeadResponse)
async def add_message(
    lead_id: uuid.UUID,
    body: MessageAdd,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> LeadResponse:
    """Append a message to the lead's conversation history."""
    lead = await _get_or_404(db, lead_id, current_user.id)

    history = list(lead.conversation_history or [])
    history.append(
        {
            "role": body.role,
            "content": body.content,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    )
    lead.conversation_history = history
    lead.last_contacted_at = datetime.now(timezone.utc)

    await db.commit()
    await db.refresh(lead)
    return LeadResponse.model_validate(lead)


@router.post("/{lead_id}/escalate")
async def escalate_lead(
    lead_id: uuid.UUID,
    body: EscalateRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Dict[str, Any]:
    """Mark a lead as requiring urgent owner attention and send an alert.

    Updates lead status to 'hot' and appends an escalation note to
    conversation history. Sends a WhatsApp or email alert to the owner.
    """
    lead = await _get_or_404(db, lead_id, current_user.id)

    # Update lead
    lead.temperature = "hot"
    history = list(lead.conversation_history or [])
    history.append(
        {
            "role": "system",
            "content": f"[ESCALATED] Reason: {body.reason or 'No reason provided'}",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    )
    lead.conversation_history = history

    await db.commit()

    # Alert the owner
    alert_sent = False
    try:
        from tools.whatsapp import WhatsAppTool
        from models.user import User as UserModel
        from sqlalchemy import select as sa_select

        result = await db.execute(sa_select(UserModel).where(UserModel.id == current_user.id))
        owner = result.scalar_one_or_none()

        if owner and owner.company_profile:
            owner_phone = owner.company_profile.get("contact_number")
            if owner_phone:
                wa = WhatsAppTool()
                await wa.send_text(
                    to=owner_phone,
                    body=(
                        f"[ESCALATION] Lead {lead.name or lead.phone or lead_id} "
                        f"needs urgent attention!\n"
                        f"Reason: {body.reason or 'Not specified'}\n"
                        f"Status: {lead.status} | Temp: {lead.temperature}"
                    ),
                )
                alert_sent = True
    except Exception as exc:
        log.warning("escalate.alert_failed", lead_id=str(lead_id), error=str(exc))

    log.info("lead.escalated", lead_id=str(lead_id), alert_sent=alert_sent)
    return {"escalated": True, "lead_id": str(lead_id), "alert_sent": alert_sent}


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

async def _get_or_404(
    db: AsyncSession,
    lead_id: uuid.UUID,
    user_id: uuid.UUID,
) -> Lead:
    result = await db.execute(
        select(Lead).where(Lead.id == lead_id, Lead.user_id == user_id)
    )
    lead = result.scalar_one_or_none()
    if not lead:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Lead {lead_id} not found",
        )
    return lead
