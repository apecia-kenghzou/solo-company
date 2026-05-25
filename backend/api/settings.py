"""Settings router — company profile, business rules, integrations, and channel config."""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Literal, Optional

from fastapi import APIRouter, Depends, HTTPException, UploadFile, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from api.deps import get_current_user, get_db
from models.user import User

log = logging.getLogger(__name__)
router = APIRouter()


# ---------------------------------------------------------------------------
# Pydantic schemas
# ---------------------------------------------------------------------------

class CompanyProfileResponse(BaseModel):
    company_name: Optional[str] = None
    tagline: Optional[str] = None
    owner_name: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    office_address: Optional[str] = None
    license_number: Optional[str] = None
    brand_voice: Optional[str] = None
    instagram_url: Optional[str] = None
    facebook_url: Optional[str] = None
    tiktok_url: Optional[str] = None
    linkedin_url: Optional[str] = None
    logo_url: Optional[str] = None


class CompanyProfileRequest(BaseModel):
    company_name: Optional[str] = None
    tagline: Optional[str] = None
    owner_name: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    office_address: Optional[str] = None
    license_number: Optional[str] = None
    brand_voice: Optional[str] = None
    instagram_url: Optional[str] = None
    facebook_url: Optional[str] = None
    tiktok_url: Optional[str] = None
    linkedin_url: Optional[str] = None
    logo_url: Optional[str] = None


class BusinessRulesResponse(BaseModel):
    always_ask: Optional[List[str]] = None
    never_promise: Optional[List[str]] = None
    escalate_triggers: Optional[List[str]] = None
    follow_up_sequences: Optional[Dict[str, Any]] = None
    preferred_channel: Optional[str] = "whatsapp"
    viewing_hours: Optional[Dict[str, Any]] = None
    compliance_notes: Optional[str] = None


class BusinessRulesRequest(BaseModel):
    always_ask: Optional[List[str]] = None
    never_promise: Optional[List[str]] = None
    escalate_triggers: Optional[List[str]] = None
    follow_up_sequences: Optional[Dict[str, Any]] = None
    preferred_channel: Optional[str] = None
    viewing_hours: Optional[Dict[str, Any]] = None
    compliance_notes: Optional[str] = None


class WhatsAppConfigRequest(BaseModel):
    phone_number_id: str
    display_number: str


class VerticalRequest(BaseModel):
    vertical: Literal["real_estate", "consultant", "recruiter"]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _deep_merge(base: Dict[str, Any], override: Dict[str, Any]) -> Dict[str, Any]:
    """Merge override into base, returning a new dict. Only non-None values override."""
    result = dict(base)
    for key, value in override.items():
        if value is not None:
            if isinstance(value, dict) and isinstance(result.get(key), dict):
                result[key] = _deep_merge(result[key], value)
            else:
                result[key] = value
    return result


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.get("/company", response_model=CompanyProfileResponse)
async def get_company_profile(
    current_user: User = Depends(get_current_user),
) -> CompanyProfileResponse:
    """Return the current user's company profile."""
    profile = current_user.company_profile or {}
    return CompanyProfileResponse(**profile)


@router.put("/company", response_model=CompanyProfileResponse)
async def update_company_profile(
    body: CompanyProfileRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> CompanyProfileResponse:
    """Merge the provided fields into the user's company profile."""
    from models.base import AsyncSessionLocal
    from sqlalchemy import select

    existing = dict(current_user.company_profile or {})
    updates = body.model_dump(exclude_none=True)
    merged = _deep_merge(existing, updates)

    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(User).where(User.id == current_user.id)
        )
        user = result.scalar_one_or_none()
        if not user:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

        user.company_profile = merged

        if "company_name" in updates:
            user.company_name = updates["company_name"]

        await session.commit()

    return CompanyProfileResponse(**merged)


@router.post("/logo")
async def upload_logo(
    file: UploadFile,
    current_user: User = Depends(get_current_user),
) -> Dict[str, str]:
    """Upload a logo image and store the URL in the user's company profile."""
    if not file.content_type or not file.content_type.startswith("image/"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="File must be an image (content_type must start with 'image/')",
        )

    # Determine extension from content_type or filename
    ext = "jpg"
    if file.filename and "." in file.filename:
        ext = file.filename.rsplit(".", 1)[-1].lower()
    elif file.content_type:
        ct_map = {
            "image/jpeg": "jpg",
            "image/png": "png",
            "image/gif": "gif",
            "image/webp": "webp",
            "image/svg+xml": "svg",
        }
        ext = ct_map.get(file.content_type, "jpg")

    key = f"users/{current_user.id}/logo.{ext}"
    file_bytes = await file.read()

    from tools.s3 import StorageTool
    storage = StorageTool()
    logo_url = await storage.upload_file(file_bytes, key, content_type=file.content_type)

    # Persist to company_profile
    from models.base import AsyncSessionLocal
    from sqlalchemy import select

    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(User).where(User.id == current_user.id)
        )
        user = result.scalar_one_or_none()
        if not user:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

        profile = dict(user.company_profile or {})
        profile["logo_url"] = logo_url
        user.company_profile = profile
        await session.commit()

    log.info("settings.logo_uploaded", user_id=str(current_user.id), url=logo_url)
    return {"logo_url": logo_url}


@router.get("/business-rules", response_model=BusinessRulesResponse)
async def get_business_rules(
    current_user: User = Depends(get_current_user),
) -> BusinessRulesResponse:
    """Return the current user's business rules."""
    rules = current_user.business_rules or {}
    return BusinessRulesResponse(**rules)


@router.put("/business-rules", response_model=BusinessRulesResponse)
async def update_business_rules(
    body: BusinessRulesRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> BusinessRulesResponse:
    """Merge the provided fields into the user's business rules."""
    from models.base import AsyncSessionLocal
    from sqlalchemy import select

    existing = dict(current_user.business_rules or {})
    updates = body.model_dump(exclude_none=True)
    merged = _deep_merge(existing, updates)

    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(User).where(User.id == current_user.id)
        )
        user = result.scalar_one_or_none()
        if not user:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

        user.business_rules = merged
        await session.commit()

    return BusinessRulesResponse(**merged)


@router.get("/integrations")
async def get_integrations(
    current_user: User = Depends(get_current_user),
) -> Dict[str, Any]:
    """Return integration connection status for the current user."""
    return {
        "gmail": {
            "connected": bool(current_user.gmail_address),
            "email": current_user.gmail_address,
        },
        "whatsapp": {
            "connected": bool(current_user.whatsapp_phone_number_id),
            "phone_number_id": current_user.whatsapp_phone_number_id,
            "display_number": current_user.whatsapp_display_number,
        },
        "google_calendar": {
            "connected": False,
            "note": "Connect via Gmail OAuth flow",
        },
    }


@router.put("/whatsapp")
async def update_whatsapp_config(
    body: WhatsAppConfigRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Dict[str, Any]:
    """Save WhatsApp Business phone number configuration."""
    from models.base import AsyncSessionLocal
    from sqlalchemy import select

    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(User).where(User.id == current_user.id)
        )
        user = result.scalar_one_or_none()
        if not user:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

        user.whatsapp_phone_number_id = body.phone_number_id
        user.whatsapp_display_number = body.display_number
        await session.commit()

    log.info(
        "settings.whatsapp_updated",
        user_id=str(current_user.id),
        phone_number_id=body.phone_number_id,
    )
    return {
        "status": "ok",
        "phone_number_id": body.phone_number_id,
        "display_number": body.display_number,
    }


@router.put("/vertical")
async def update_vertical(
    body: VerticalRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Dict[str, Any]:
    """Update the user's vertical (industry config)."""
    from models.base import AsyncSessionLocal
    from sqlalchemy import select

    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(User).where(User.id == current_user.id)
        )
        user = result.scalar_one_or_none()
        if not user:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

        user.vertical = body.vertical
        await session.commit()

    log.info("settings.vertical_updated", user_id=str(current_user.id), vertical=body.vertical)
    return {"vertical": body.vertical}
