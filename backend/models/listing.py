"""Listing model — a property or service offering."""
from __future__ import annotations

import uuid
from typing import Any, Dict, List, Optional

from sqlalchemy import JSON, Boolean, ForeignKey, Numeric, String, Text, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from models.base import Base, TimestampMixin


class Listing(Base, TimestampMixin):
    """Represents a property listing (real estate vertical) or equivalent
    for other verticals (service offering, role brief, etc.)."""

    __tablename__ = "listings"

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

    # Core details
    name: Mapped[str] = mapped_column(String(512), nullable=False)
    address: Mapped[str] = mapped_column(String(1024), nullable=False, default="")

    # Property classification
    property_type: Mapped[str] = mapped_column(
        String(64), nullable=False, default="condo"
    )  # condo / landed / commercial
    tenure: Mapped[str] = mapped_column(
        String(64), nullable=False, default="freehold"
    )  # freehold / leasehold
    developer: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    # Pricing
    price_min: Mapped[Optional[float]] = mapped_column(
        Numeric(12, 2), nullable=True
    )
    price_max: Mapped[Optional[float]] = mapped_column(
        Numeric(12, 2), nullable=True
    )
    price_psf: Mapped[Optional[float]] = mapped_column(
        Numeric(10, 2), nullable=True
    )

    # Physical specs
    bedrooms: Mapped[Optional[int]] = mapped_column(nullable=True)
    bathrooms: Mapped[Optional[int]] = mapped_column(nullable=True)
    land_area: Mapped[Optional[float]] = mapped_column(Numeric(10, 2), nullable=True)
    built_up: Mapped[Optional[float]] = mapped_column(Numeric(10, 2), nullable=True)

    # Media
    floor_plan_urls: Mapped[List[Any]] = mapped_column(JSON, nullable=False, default=list)
    photo_urls: Mapped[List[Any]] = mapped_column(JSON, nullable=False, default=list)
    brochure_url: Mapped[Optional[str]] = mapped_column(String(2048), nullable=True)
    video_url: Mapped[Optional[str]] = mapped_column(String(2048), nullable=True)

    # Features & selling info
    facilities: Mapped[List[Any]] = mapped_column(JSON, nullable=False, default=list)
    nearby_amenities: Mapped[Dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    selling_points: Mapped[List[Any]] = mapped_column(JSON, nullable=False, default=list)
    target_buyer: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    investment_potential: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    payment_scheme: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    promotions: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    available_units: Mapped[Optional[int]] = mapped_column(nullable=True)

    # Lifecycle
    status: Mapped[str] = mapped_column(
        String(32), nullable=False, default="active"
    )  # active / sold / withdrawn

    # Knowledge base flag
    kb_indexed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    def __repr__(self) -> str:
        return f"<Listing id={self.id} name={self.name!r} status={self.status}>"
