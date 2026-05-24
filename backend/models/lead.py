"""Lead model — a prospect / contact in the pipeline."""
from __future__ import annotations

import uuid
from typing import Any, Dict, List, Optional
import datetime

from sqlalchemy import JSON, Boolean, DateTime, ForeignKey, Numeric, String, Text, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from models.base import Base, TimestampMixin


class Lead(Base, TimestampMixin):
    """A prospect who has expressed interest through any channel."""

    __tablename__ = "leads"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        server_default=text("gen_random_uuid()"),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    listing_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("listings.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    # Contact info
    name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    email: Mapped[Optional[str]] = mapped_column(String(320), nullable=True)
    phone: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)

    # Origin
    source: Mapped[str] = mapped_column(
        String(64), nullable=False, default="website"
    )  # email / whatsapp / website / referral

    # Pipeline position
    status: Mapped[str] = mapped_column(
        String(64), nullable=False, default="new", index=True
    )  # new / warm / hot / viewing_scheduled / offer / closed / lost

    # Qualification
    budget_min: Mapped[Optional[float]] = mapped_column(Numeric(12, 2), nullable=True)
    budget_max: Mapped[Optional[float]] = mapped_column(Numeric(12, 2), nullable=True)
    timeline: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    pre_approved: Mapped[Optional[bool]] = mapped_column(Boolean, nullable=True)
    property_type_interest: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    preferred_area: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Conversation
    conversation_history: Mapped[List[Any]] = mapped_column(
        JSON, nullable=False, default=list
    )  # list of {role, content, timestamp}

    # Follow-up scheduling
    last_contacted_at: Mapped[Optional[datetime.datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    next_follow_up_at: Mapped[Optional[datetime.datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True, index=True
    )
    follow_up_count: Mapped[int] = mapped_column(nullable=False, default=0)

    # Temperature score
    temperature: Mapped[str] = mapped_column(
        String(16), nullable=False, default="cold"
    )  # cold / warm / hot

    def __repr__(self) -> str:
        return (
            f"<Lead id={self.id} name={self.name!r} status={self.status} "
            f"temperature={self.temperature}>"
        )
