"""Listings CRUD router."""
from __future__ import annotations

import logging
import uuid
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, status
from pydantic import BaseModel, Field
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from api.deps import get_current_user, get_db
from models.listing import Listing
from models.user import User

log = logging.getLogger(__name__)
router = APIRouter()


# ---------------------------------------------------------------------------
# Pydantic schemas
# ---------------------------------------------------------------------------

class ListingCreate(BaseModel):
    name: str
    address: str = ""
    property_type: str = "condo"
    tenure: str = "freehold"
    developer: Optional[str] = None
    price_min: Optional[float] = None
    price_max: Optional[float] = None
    price_psf: Optional[float] = None
    bedrooms: Optional[int] = None
    bathrooms: Optional[int] = None
    land_area: Optional[float] = None
    built_up: Optional[float] = None
    facilities: List[str] = Field(default_factory=list)
    nearby_amenities: Dict[str, Any] = Field(default_factory=dict)
    selling_points: List[str] = Field(default_factory=list)
    target_buyer: Optional[str] = None
    investment_potential: Optional[str] = None
    payment_scheme: Optional[str] = None
    promotions: Optional[str] = None
    available_units: Optional[int] = None


class ListingUpdate(BaseModel):
    name: Optional[str] = None
    address: Optional[str] = None
    property_type: Optional[str] = None
    tenure: Optional[str] = None
    developer: Optional[str] = None
    price_min: Optional[float] = None
    price_max: Optional[float] = None
    price_psf: Optional[float] = None
    bedrooms: Optional[int] = None
    bathrooms: Optional[int] = None
    land_area: Optional[float] = None
    built_up: Optional[float] = None
    facilities: Optional[List[str]] = None
    nearby_amenities: Optional[Dict[str, Any]] = None
    selling_points: Optional[List[str]] = None
    target_buyer: Optional[str] = None
    investment_potential: Optional[str] = None
    payment_scheme: Optional[str] = None
    promotions: Optional[str] = None
    available_units: Optional[int] = None
    status: Optional[str] = None


class ListingResponse(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    name: str
    address: str
    property_type: str
    tenure: str
    developer: Optional[str]
    price_min: Optional[float]
    price_max: Optional[float]
    price_psf: Optional[float]
    bedrooms: Optional[int]
    bathrooms: Optional[int]
    land_area: Optional[float]
    built_up: Optional[float]
    floor_plan_urls: List[Any]
    photo_urls: List[Any]
    brochure_url: Optional[str]
    video_url: Optional[str]
    facilities: List[Any]
    nearby_amenities: Dict[str, Any]
    selling_points: List[Any]
    target_buyer: Optional[str]
    investment_potential: Optional[str]
    payment_scheme: Optional[str]
    promotions: Optional[str]
    available_units: Optional[int]
    status: str
    kb_indexed: bool

    class Config:
        from_attributes = True


class PaginatedListings(BaseModel):
    items: List[ListingResponse]
    total: int
    page: int
    page_size: int


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.get("/", response_model=PaginatedListings)
async def list_listings(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    status_filter: Optional[str] = Query(None, alias="status"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> PaginatedListings:
    """List all listings for the authenticated user (paginated)."""
    q = select(Listing).where(Listing.user_id == current_user.id)
    if status_filter:
        q = q.where(Listing.status == status_filter)
    q = q.order_by(Listing.created_at.desc())

    # Count
    from sqlalchemy import func, select as sa_select
    count_q = sa_select(func.count()).select_from(
        q.subquery()
    )
    total = (await db.execute(count_q)).scalar() or 0

    # Page
    q = q.offset((page - 1) * page_size).limit(page_size)
    rows = (await db.execute(q)).scalars().all()

    return PaginatedListings(
        items=[ListingResponse.model_validate(r) for r in rows],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.post("/", response_model=ListingResponse, status_code=status.HTTP_201_CREATED)
async def create_listing(
    body: ListingCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ListingResponse:
    """Create a new listing and trigger background indexing + research tasks."""
    listing = Listing(
        user_id=current_user.id,
        **body.model_dump(exclude_none=False),
    )
    db.add(listing)
    await db.flush()  # get the generated id before commit
    listing_id = str(listing.id)
    await db.commit()
    await db.refresh(listing)

    # Dispatch background tasks
    try:
        from workers.tasks import index_listing_to_kb, run_property_research
        index_listing_to_kb.delay(listing_id)
        run_property_research.delay(listing_id)
        log.info("listing.created", listing_id=listing_id, tasks_dispatched=True)
    except Exception as exc:
        log.warning("listing.task_dispatch_failed", listing_id=listing_id, error=str(exc))

    return ListingResponse.model_validate(listing)


@router.get("/{listing_id}", response_model=ListingResponse)
async def get_listing(
    listing_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ListingResponse:
    """Get a single listing by ID."""
    listing = await _get_or_404(db, listing_id, current_user.id)
    return ListingResponse.model_validate(listing)


@router.put("/{listing_id}", response_model=ListingResponse)
async def update_listing(
    listing_id: uuid.UUID,
    body: ListingUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ListingResponse:
    """Update listing fields."""
    listing = await _get_or_404(db, listing_id, current_user.id)

    updates = body.model_dump(exclude_none=True)
    for key, value in updates.items():
        setattr(listing, key, value)

    # If price/content changed, re-queue indexing
    content_keys = {"name", "address", "selling_points", "facilities", "nearby_amenities"}
    if content_keys.intersection(updates.keys()):
        listing.kb_indexed = False
        try:
            from workers.tasks import index_listing_to_kb
            index_listing_to_kb.delay(str(listing.id))
        except Exception as exc:
            log.warning("listing.reindex_failed", listing_id=str(listing_id), error=str(exc))

    await db.commit()
    await db.refresh(listing)
    return ListingResponse.model_validate(listing)


@router.delete("/{listing_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_listing(
    listing_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    """Soft-delete a listing (set status to 'withdrawn')."""
    listing = await _get_or_404(db, listing_id, current_user.id)
    listing.status = "withdrawn"
    await db.commit()
    log.info("listing.withdrawn", listing_id=str(listing_id))


@router.post("/{listing_id}/upload")
async def upload_listing_files(
    listing_id: uuid.UUID,
    files: List[UploadFile] = File(...),
    file_type: str = Query("photo", enum=["photo", "floor_plan", "brochure", "video"]),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Dict[str, Any]:
    """Upload floor plans, photos, or other documents to S3 and attach URLs to listing."""
    listing = await _get_or_404(db, listing_id, current_user.id)

    from tools.s3 import StorageTool
    storage = StorageTool()
    uploaded_urls = []

    for file in files:
        file_bytes = await file.read()
        key = f"listings/{listing_id}/{file_type}/{file.filename}"
        url = await storage.upload_file(
            file_bytes=file_bytes,
            key=key,
            content_type=file.content_type,
        )
        uploaded_urls.append(url)

    # Append URLs to the appropriate list field
    if file_type == "photo":
        listing.photo_urls = (listing.photo_urls or []) + uploaded_urls
    elif file_type == "floor_plan":
        listing.floor_plan_urls = (listing.floor_plan_urls or []) + uploaded_urls
    elif file_type == "brochure" and uploaded_urls:
        listing.brochure_url = uploaded_urls[0]
    elif file_type == "video" and uploaded_urls:
        listing.video_url = uploaded_urls[0]

    await db.commit()
    log.info(
        "listing.files_uploaded",
        listing_id=str(listing_id),
        file_type=file_type,
        count=len(uploaded_urls),
    )
    return {"uploaded": uploaded_urls, "file_type": file_type}


@router.post("/{listing_id}/mark-sold", response_model=ListingResponse)
async def mark_listing_sold(
    listing_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ListingResponse:
    """Mark a listing as sold and update the knowledge base."""
    listing = await _get_or_404(db, listing_id, current_user.id)
    listing.status = "sold"
    listing.kb_indexed = False  # Trigger re-index with updated status
    await db.commit()
    await db.refresh(listing)

    try:
        from workers.tasks import index_listing_to_kb
        index_listing_to_kb.delay(str(listing.id))
    except Exception as exc:
        log.warning("listing.sold_reindex_failed", listing_id=str(listing_id), error=str(exc))

    log.info("listing.marked_sold", listing_id=str(listing_id))
    return ListingResponse.model_validate(listing)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

async def _get_or_404(
    db: AsyncSession,
    listing_id: uuid.UUID,
    user_id: uuid.UUID,
) -> Listing:
    """Fetch a listing belonging to *user_id* or raise 404."""
    result = await db.execute(
        select(Listing).where(
            Listing.id == listing_id,
            Listing.user_id == user_id,
        )
    )
    listing = result.scalar_one_or_none()
    if not listing:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Listing {listing_id} not found",
        )
    return listing
