"""KBWriter — structures domain knowledge and writes it to Pinecone."""
from __future__ import annotations

import hashlib
import logging
from datetime import datetime, timezone
from typing import Optional

from knowledge.pinecone_store import PineconeStore

logger = logging.getLogger(__name__)


def _short_hash(text: str, length: int = 8) -> str:
    return hashlib.md5(text.encode()).hexdigest()[:length]


class KBWriter:
    """High-level interface for writing domain knowledge into Pinecone."""

    def _store(self, user_id: str) -> PineconeStore:
        return PineconeStore(namespace=user_id)

    # ------------------------------------------------------------------
    # Company Profile
    # ------------------------------------------------------------------

    async def write_company_profile(self, user_id: str, profile: dict) -> None:
        """Chunk the company profile into searchable pieces and upsert each."""
        store = self._store(user_id)

        chunks = []

        # Identity
        name = profile.get("name", "")
        owner = profile.get("owner_name", "")
        license_no = profile.get("license_number", "")
        if name or owner:
            chunks.append(
                {
                    "id": f"{user_id}_company_identity",
                    "text": (
                        f"Company name: {name}. "
                        f"Owner: {owner}. "
                        f"License number: {license_no}."
                    ),
                    "metadata": {"type": "company_profile", "field": "identity", "user_id": user_id},
                }
            )

        # Brand voice
        voice = profile.get("brand_voice", "")
        if voice:
            chunks.append(
                {
                    "id": f"{user_id}_company_voice",
                    "text": f"Brand voice and communication style: {voice}",
                    "metadata": {"type": "company_profile", "field": "brand_voice", "user_id": user_id},
                }
            )

        # Credentials / specialisations
        credentials = profile.get("credentials", "")
        specialisations = profile.get("specialisations", "")
        if credentials or specialisations:
            chunks.append(
                {
                    "id": f"{user_id}_company_credentials",
                    "text": (
                        f"Credentials: {credentials}. "
                        f"Specialisations: {specialisations}."
                    ),
                    "metadata": {"type": "company_profile", "field": "credentials", "user_id": user_id},
                }
            )

        # Contact information
        contact = profile.get("contact_number", "")
        address = profile.get("office_address", "")
        social = profile.get("social_handles", "")
        if contact or address:
            chunks.append(
                {
                    "id": f"{user_id}_company_contact",
                    "text": (
                        f"Contact number: {contact}. "
                        f"Office address: {address}. "
                        f"Social handles: {social}."
                    ),
                    "metadata": {"type": "company_profile", "field": "contact", "user_id": user_id},
                }
            )

        # Business rules
        rules = profile.get("business_rules", "")
        if rules:
            chunks.append(
                {
                    "id": f"{user_id}_company_rules",
                    "text": f"Business rules and compliance notes: {rules}",
                    "metadata": {"type": "company_profile", "field": "business_rules", "user_id": user_id},
                }
            )

        if chunks:
            await store.upsert_batch(chunks)
            logger.info("Written %d company profile chunks for user %s", len(chunks), user_id)

    # ------------------------------------------------------------------
    # Listing
    # ------------------------------------------------------------------

    async def write_listing(self, user_id: str, listing: dict) -> None:
        """Create multiple KB entries for a property listing."""
        store = self._store(user_id)
        listing_id = listing.get("id", _short_hash(listing.get("name", "listing")))

        chunks = []

        # Overview
        chunks.append(
            {
                "id": f"{user_id}_listing_{listing_id}_overview",
                "text": (
                    f"Listing: {listing.get('name', '')} at {listing.get('address', '')}. "
                    f"Type: {listing.get('property_type', '')}. "
                    f"Tenure: {listing.get('tenure', '')}. "
                    f"Developer: {listing.get('developer', '')}."
                ),
                "metadata": {
                    "type": "listing",
                    "listing_id": listing_id,
                    "field": "overview",
                    "user_id": user_id,
                },
            }
        )

        # Pricing
        chunks.append(
            {
                "id": f"{user_id}_listing_{listing_id}_pricing",
                "text": (
                    f"Price range: {listing.get('price_min', '')} - {listing.get('price_max', '')}. "
                    f"Price per sqft: {listing.get('price_psf', '')}."
                ),
                "metadata": {
                    "type": "listing",
                    "listing_id": listing_id,
                    "field": "pricing",
                    "user_id": user_id,
                },
            }
        )

        # Features
        chunks.append(
            {
                "id": f"{user_id}_listing_{listing_id}_features",
                "text": (
                    f"Bedrooms: {listing.get('bedrooms', '')}. "
                    f"Bathrooms: {listing.get('bathrooms', '')}. "
                    f"Built-up: {listing.get('built_up', '')} sqft. "
                    f"Land area: {listing.get('land_area', '')} sqft. "
                    f"Target buyer: {listing.get('target_buyer', '')}."
                ),
                "metadata": {
                    "type": "listing",
                    "listing_id": listing_id,
                    "field": "features",
                    "user_id": user_id,
                },
            }
        )

        # Facilities
        facilities = listing.get("facilities", [])
        if facilities:
            fac_text = ", ".join(facilities) if isinstance(facilities, list) else str(facilities)
            chunks.append(
                {
                    "id": f"{user_id}_listing_{listing_id}_facilities",
                    "text": f"Facilities at {listing.get('name', 'this listing')}: {fac_text}.",
                    "metadata": {
                        "type": "listing",
                        "listing_id": listing_id,
                        "field": "facilities",
                        "user_id": user_id,
                    },
                }
            )

        # Selling points
        selling_points = listing.get("selling_points", [])
        if selling_points:
            sp_text = "; ".join(selling_points) if isinstance(selling_points, list) else str(selling_points)
            chunks.append(
                {
                    "id": f"{user_id}_listing_{listing_id}_selling_points",
                    "text": f"Key selling points for {listing.get('name', 'this listing')}: {sp_text}.",
                    "metadata": {
                        "type": "listing",
                        "listing_id": listing_id,
                        "field": "selling_points",
                        "user_id": user_id,
                    },
                }
            )

        # Nearby amenities
        amenities = listing.get("nearby_amenities", [])
        if amenities:
            am_text = ", ".join(amenities) if isinstance(amenities, list) else str(amenities)
            chunks.append(
                {
                    "id": f"{user_id}_listing_{listing_id}_amenities",
                    "text": f"Nearby amenities for {listing.get('name', 'this listing')}: {am_text}.",
                    "metadata": {
                        "type": "listing",
                        "listing_id": listing_id,
                        "field": "amenities",
                        "user_id": user_id,
                    },
                }
            )

        # Investment potential
        investment = listing.get("investment_potential", "")
        if investment:
            chunks.append(
                {
                    "id": f"{user_id}_listing_{listing_id}_investment",
                    "text": f"Investment potential for {listing.get('name', 'this listing')}: {investment}",
                    "metadata": {
                        "type": "listing",
                        "listing_id": listing_id,
                        "field": "investment",
                        "user_id": user_id,
                    },
                }
            )

        await store.upsert_batch(chunks)
        logger.info(
            "Written %d listing chunks for listing %s, user %s", len(chunks), listing_id, user_id
        )

    # ------------------------------------------------------------------
    # Market Report
    # ------------------------------------------------------------------

    async def write_market_report(self, user_id: str, report: dict) -> None:
        """Store weekly market intelligence as vectors."""
        store = self._store(user_id)
        report_date = report.get("date", datetime.now(timezone.utc).strftime("%Y-%m-%d"))
        report_id = f"{user_id}_market_{report_date}"

        content = report.get("content", "")
        if not content:
            # Try assembling from sub-fields
            sections = []
            for key in ("price_trend", "new_launches", "demand_insights", "agent_talking_points", "summary"):
                val = report.get(key, "")
                if val:
                    sections.append(f"{key.replace('_', ' ').title()}: {val}")
            content = " | ".join(sections) if sections else str(report)

        await store.upsert(
            doc_id=report_id,
            text=content,
            metadata={
                "type": "market_report",
                "date": report_date,
                "user_id": user_id,
            },
        )
        logger.info("Written market report for user %s on %s", user_id, report_date)

    # ------------------------------------------------------------------
    # Social Trends
    # ------------------------------------------------------------------

    async def write_social_trends(self, user_id: str, trends: list[dict]) -> None:
        """Store social trend data as vectors."""
        store = self._store(user_id)
        chunks = []
        for i, trend in enumerate(trends):
            trend_text = trend.get("text", "")
            if not trend_text:
                parts = []
                for key, val in trend.items():
                    if key not in ("id", "user_id") and val:
                        parts.append(f"{key}: {val}")
                trend_text = "; ".join(parts) if parts else str(trend)

            trend_id = trend.get("id", f"{user_id}_trend_{i}_{_short_hash(trend_text)}")
            chunks.append(
                {
                    "id": trend_id,
                    "text": trend_text,
                    "metadata": {
                        "type": "social_trend",
                        "platform": trend.get("platform", ""),
                        "date": trend.get("date", ""),
                        "user_id": user_id,
                    },
                }
            )

        if chunks:
            await store.upsert_batch(chunks)
            logger.info("Written %d social trends for user %s", len(chunks), user_id)

    # ------------------------------------------------------------------
    # Objection Handling
    # ------------------------------------------------------------------

    async def write_objection_answer(
        self, user_id: str, objection: str, answer: str
    ) -> None:
        """Store a pre-approved objection/answer pair."""
        store = self._store(user_id)
        doc_id = f"{user_id}_objection_{_short_hash(objection)}"
        await store.upsert(
            doc_id=doc_id,
            text=f"Objection: {objection}\nAnswer: {answer}",
            metadata={
                "type": "objection",
                "objection": objection,
                "user_id": user_id,
            },
        )
        logger.info("Written objection answer for user %s", user_id)

    # ------------------------------------------------------------------
    # Lead Insight
    # ------------------------------------------------------------------

    async def write_lead_insight(
        self, user_id: str, lead_id: str, insight: str
    ) -> None:
        """Store an insight about a lead or buyer profile."""
        store = self._store(user_id)
        doc_id = f"{user_id}_lead_{lead_id}_{_short_hash(insight)}"
        await store.upsert(
            doc_id=doc_id,
            text=insight,
            metadata={
                "type": "lead_insight",
                "lead_id": lead_id,
                "user_id": user_id,
            },
        )
        logger.info("Written lead insight for lead %s, user %s", lead_id, user_id)

    # ------------------------------------------------------------------
    # Convenience wrappers used by Celery tasks
    # ------------------------------------------------------------------

    async def index_listing(self, listing) -> None:
        """Index a SQLAlchemy Listing ORM object into the KB.

        Converts the ORM object to a dict and delegates to ``write_listing``.
        Requires the listing to have a non-null ``user_id`` attribute.
        """
        listing_dict = {
            "id": str(listing.id),
            "name": listing.name or "",
            "address": listing.address or "",
            "property_type": listing.property_type or "",
            "tenure": listing.tenure or "",
            "developer": listing.developer or "",
            "price_min": str(listing.price_min) if listing.price_min else "",
            "price_max": str(listing.price_max) if listing.price_max else "",
            "price_psf": str(listing.price_psf) if listing.price_psf else "",
            "bedrooms": listing.bedrooms,
            "bathrooms": listing.bathrooms,
            "built_up": str(listing.built_up) if listing.built_up else "",
            "land_area": str(listing.land_area) if listing.land_area else "",
            "facilities": listing.facilities or [],
            "selling_points": listing.selling_points or [],
            "nearby_amenities": listing.nearby_amenities or {},
            "target_buyer": listing.target_buyer or "",
            "investment_potential": listing.investment_potential or "",
        }
        await self.write_listing(user_id=str(listing.user_id), listing=listing_dict)

    async def index_document(
        self,
        doc_id: str,
        text: str,
        metadata: dict,
        namespace: str = "default",
    ) -> None:
        """Index an arbitrary text document into a named namespace.

        Args:
            doc_id: Unique identifier for the document vector.
            text: Text content to embed.
            metadata: Metadata dict stored alongside the vector.
            namespace: Pinecone namespace to upsert into.
        """
        from knowledge.pinecone_store import PineconeStore

        store = PineconeStore(namespace=namespace)
        await store.upsert(doc_id=doc_id, text=text, metadata=metadata)
        logger.info("Indexed document '%s' into namespace '%s'", doc_id, namespace)

    # ------------------------------------------------------------------
    # Query
    # ------------------------------------------------------------------

    async def query_kb(
        self,
        user_id: str,
        query: str,
        kb_type: Optional[str] = None,
        top_k: int = 5,
    ) -> str:
        """Query KB and return a formatted context string for LLM injection.

        Returns a numbered list of relevant facts.
        """
        store = self._store(user_id)
        filter_dict = {"type": {"$eq": kb_type}} if kb_type else None

        try:
            results = await store.query(query_text=query, top_k=top_k, filter=filter_dict)
        except Exception as exc:
            logger.error("KB query failed: %s", exc)
            return ""

        if not results:
            return ""

        lines = []
        for i, result in enumerate(results, start=1):
            text = result.get("text", "").strip()
            if text:
                lines.append(f"{i}. {text}")

        return "\n".join(lines)
