"""Content models — drafted social posts and recorded agent actions."""
from __future__ import annotations

import uuid
from typing import Any, Dict, List, Optional
import datetime

from sqlalchemy import JSON, DateTime, ForeignKey, String, Text, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from models.base import Base, TimestampMixin


class ContentDraft(Base, TimestampMixin):
    """A piece of content drafted by the MarketingAgent, pending approval."""

    __tablename__ = "content_drafts"

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
    )

    # Content metadata
    type: Mapped[str] = mapped_column(
        String(64), nullable=False
    )  # instagram_post / facebook_post / whatsapp_broadcast / email_newsletter / reel_script
    platform: Mapped[str] = mapped_column(String(64), nullable=False)
    caption: Mapped[str] = mapped_column(Text, nullable=False, default="")
    image_url: Mapped[Optional[str]] = mapped_column(String(2048), nullable=True)
    hashtags: Mapped[List[Any]] = mapped_column(JSON, nullable=False, default=list)

    # Scheduling
    scheduled_at: Mapped[Optional[datetime.datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True, index=True
    )
    published_at: Mapped[Optional[datetime.datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # Approval workflow
    status: Mapped[str] = mapped_column(
        String(32), nullable=False, default="draft", index=True
    )  # draft / pending_approval / approved / scheduled / published / rejected
    approval_notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Buffer integration
    buffer_post_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    # Analytics
    engagement_data: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON, nullable=True)

    def __repr__(self) -> str:
        return f"<ContentDraft id={self.id} type={self.type} status={self.status}>"


class AgentAction(Base, TimestampMixin):
    """Audit log of every action taken by an agent."""

    __tablename__ = "agent_actions"

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

    agent_name: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    action_type: Mapped[str] = mapped_column(String(128), nullable=False)

    input_data: Mapped[Dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    output_data: Mapped[Dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)

    status: Mapped[str] = mapped_column(
        String(32), nullable=False, default="pending_approval", index=True
    )  # success / failed / pending_approval
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    def __repr__(self) -> str:
        return (
            f"<AgentAction id={self.id} agent={self.agent_name} "
            f"type={self.action_type} status={self.status}>"
        )
