"""User model."""
from __future__ import annotations

import uuid
from typing import Any, Dict, Optional

from sqlalchemy import JSON, Boolean, String, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from models.base import Base, TimestampMixin


class User(Base, TimestampMixin):
    """Platform user — one record per solo professional."""

    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        server_default=text("gen_random_uuid()"),
    )

    # External auth (Clerk)
    clerk_id: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)

    email: Mapped[str] = mapped_column(String(320), unique=True, nullable=False)
    full_name: Mapped[str] = mapped_column(String(255), nullable=False, default="")

    # Vertical determines which YAML config drives agent behaviour
    vertical: Mapped[str] = mapped_column(String(64), nullable=False, default="real_estate")

    company_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    # Full onboarding questionnaire answers stored as JSON
    company_profile: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON, nullable=True)

    # Persisted business rules extracted during onboarding
    business_rules: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON, nullable=True)

    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    # WhatsApp Business — phone_number_id from Meta Cloud API metadata
    # Used to route inbound webhooks to the correct user.
    # Format: the numeric ID shown in Meta Business Manager, e.g. "123456789012345"
    whatsapp_phone_number_id: Mapped[Optional[str]] = mapped_column(
        String(64), nullable=True, index=True, unique=True
    )
    # The display number shown to leads (E.164 format, e.g. "+60123456789")
    whatsapp_display_number: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)

    # Gmail — the OAuth-connected address used for Push/Sub routing
    gmail_address: Mapped[Optional[str]] = mapped_column(
        String(320), nullable=True, index=True
    )

    # Billing
    stripe_customer_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    plan: Mapped[str] = mapped_column(String(64), nullable=False, default="starter")

    def __repr__(self) -> str:
        return f"<User id={self.id} email={self.email} vertical={self.vertical}>"
