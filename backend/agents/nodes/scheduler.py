"""Scheduler node — schedules approved content to Buffer or Meta Graph API."""
from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Optional

from backend.agents.state import MarketingState
from backend.config.settings import settings

logger = logging.getLogger(__name__)

# Optimal posting times per platform (local time — assume UTC for MVP)
_OPTIMAL_TIMES: dict[str, list[str]] = {
    "instagram": ["09:00", "12:00", "19:00"],
    "facebook": ["10:00", "15:00"],
    "whatsapp": ["09:00", "18:00"],
    "linkedin": ["08:00", "12:00", "17:00"],
}

# Platforms supported by Buffer
_BUFFER_PLATFORMS = {"instagram", "facebook", "linkedin", "twitter"}
# Platforms scheduled directly via Meta Graph API
_META_PLATFORMS = {"instagram", "facebook"}


# ---------------------------------------------------------------------------
# Buffer API helpers
# ---------------------------------------------------------------------------

def _schedule_via_buffer(
    platform: str,
    caption: str,
    hashtags: list[str],
    image_url: Optional[str],
    scheduled_at: str,
    user_id: str,
) -> Optional[str]:
    """Schedule a post via Buffer API. Returns buffer_post_id or None."""
    logger.info("Buffer schedule: platform=%s scheduled_at=%s", platform, scheduled_at)
    try:
        import httpx

        access_token = settings.buffer_access_token
        if not access_token:
            raise ValueError("BUFFER_ACCESS_TOKEN not set")

        # Combine caption and hashtags
        hashtag_text = " ".join(hashtags)
        full_text = f"{caption}\n\n{hashtag_text}".strip() if hashtags else caption

        # Build post payload
        payload: dict = {
            "text": full_text,
            "scheduled_at": scheduled_at,  # ISO 8601
        }

        if image_url:
            payload["media"] = {"photo": image_url}

        # Buffer v1 API — profile_id needed (stored per user in production)
        # For MVP: use a stub profile_id
        profile_id = f"buffer_profile_{platform}_{user_id}"

        with httpx.Client(timeout=30) as http:
            resp = http.post(
                f"https://api.bufferapp.com/1/updates/create.json",
                headers={"Authorization": f"Bearer {access_token}"},
                data={
                    "profile_ids[]": profile_id,
                    "text": full_text,
                    "scheduled_at": scheduled_at,
                    **({"media[photo]": image_url} if image_url else {}),
                },
            )
            resp.raise_for_status()
            data = resp.json()
            updates = data.get("updates", [{}])
            post_id = updates[0].get("id") if updates else None
            logger.info("Buffer scheduled: post_id=%s", post_id)
            return str(post_id) if post_id else "buffer_stub_id"

    except Exception as exc:
        logger.error("Buffer scheduling failed: %s", exc)
        return None


def _schedule_via_meta(
    platform: str,
    caption: str,
    hashtags: list[str],
    image_url: Optional[str],
    scheduled_at: str,
) -> Optional[str]:
    """Schedule a post directly via Meta Graph API. Returns post ID or None."""
    logger.info("Meta Graph API schedule: platform=%s scheduled_at=%s", platform, scheduled_at)
    try:
        import httpx
        from datetime import datetime

        access_token = settings.meta_access_token
        if not access_token:
            raise ValueError("META_ACCESS_TOKEN not set")

        # Convert ISO to Unix timestamp
        scheduled_dt = datetime.fromisoformat(scheduled_at.replace("Z", "+00:00"))
        scheduled_unix = int(scheduled_dt.timestamp())

        hashtag_text = " ".join(hashtags)
        full_message = f"{caption}\n\n{hashtag_text}".strip() if hashtags else caption

        with httpx.Client(timeout=30) as http:
            if platform == "instagram":
                ig_user_id = settings.meta_ig_user_id
                if not ig_user_id:
                    raise ValueError("META_IG_USER_ID not set")

                # Step 1: Create media container
                container_payload = {
                    "caption": full_message,
                    "access_token": access_token,
                }
                if image_url:
                    container_payload["image_url"] = image_url
                    container_payload["media_type"] = "IMAGE"
                else:
                    container_payload["media_type"] = "IMAGE"

                container_resp = http.post(
                    f"https://graph.facebook.com/v18.0/{ig_user_id}/media",
                    data=container_payload,
                )
                container_resp.raise_for_status()
                container_id = container_resp.json().get("id")

                if not container_id:
                    raise ValueError("No container ID returned from Meta")

                # Step 2: Publish (scheduled)
                publish_resp = http.post(
                    f"https://graph.facebook.com/v18.0/{ig_user_id}/media_publish",
                    data={
                        "creation_id": container_id,
                        "access_token": access_token,
                        "published": "false",
                        "scheduled_publish_time": str(scheduled_unix),
                    },
                )
                publish_resp.raise_for_status()
                post_id = publish_resp.json().get("id")
                logger.info("Meta IG scheduled: post_id=%s", post_id)
                return str(post_id) if post_id else "meta_ig_stub_id"

            elif platform == "facebook":
                page_id = settings.meta_page_id
                if not page_id:
                    raise ValueError("META_PAGE_ID not set")

                fb_payload = {
                    "message": full_message,
                    "scheduled_publish_time": str(scheduled_unix),
                    "published": "false",
                    "access_token": access_token,
                }
                if image_url:
                    fb_payload["url"] = image_url
                    endpoint = f"https://graph.facebook.com/v18.0/{page_id}/photos"
                else:
                    endpoint = f"https://graph.facebook.com/v18.0/{page_id}/feed"

                fb_resp = http.post(endpoint, data=fb_payload)
                fb_resp.raise_for_status()
                post_id = fb_resp.json().get("id") or fb_resp.json().get("post_id")
                logger.info("Meta FB scheduled: post_id=%s", post_id)
                return str(post_id) if post_id else "meta_fb_stub_id"

        return None

    except Exception as exc:
        logger.error("Meta Graph API scheduling failed: %s", exc)
        return None


def _update_content_draft_db(
    draft_id: Optional[str],
    status: str,
    scheduled_at: Optional[str],
    buffer_post_id: Optional[str],
) -> None:
    """Stub — updates ContentDraft record in DB."""
    logger.info(
        "DB stub: update ContentDraft id=%s status=%s scheduled_at=%s buffer_id=%s",
        draft_id, status, scheduled_at, buffer_post_id,
    )
    # In production: async SQLAlchemy ORM update on ContentDraft model


def _resolve_scheduled_at(current_post: dict, platform: str) -> str:
    """Use the post's scheduled_at if set, else pick next optimal time."""
    scheduled_at = current_post.get("scheduled_at", "")
    if scheduled_at:
        return scheduled_at

    # Pick next optimal slot: today at first available time
    now = datetime.now(timezone.utc)
    optimal_times = _OPTIMAL_TIMES.get(platform, ["09:00"])

    # Find the next future optimal time today
    for time_str in optimal_times:
        hour, minute = map(int, time_str.split(":"))
        candidate = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
        if candidate > now:
            return candidate.strftime("%Y-%m-%dT%H:%M:%SZ")

    # All times today have passed — schedule for tomorrow at first optimal time
    tomorrow = now + __import__("datetime").timedelta(days=1)
    first_time = optimal_times[0]
    hour, minute = map(int, first_time.split(":"))
    scheduled = tomorrow.replace(hour=hour, minute=minute, second=0, microsecond=0)
    return scheduled.strftime("%Y-%m-%dT%H:%M:%SZ")


# ---------------------------------------------------------------------------
# Node
# ---------------------------------------------------------------------------

def scheduler_node(state: MarketingState) -> dict:
    """Schedule an approved content draft to Buffer or Meta Graph API.

    Routing:
    - Instagram/Facebook: try Meta Graph API first, fall back to Buffer
    - LinkedIn/Twitter: Buffer
    - WhatsApp: direct send stub (WhatsApp Business API doesn't support scheduling)

    Updates ContentDraft.status to 'scheduled' and sets scheduled_at + buffer_post_id.
    """
    user_id = state.get("user_id", "")
    draft_id = state.get("draft_id")
    current_post = state.get("current_post", {})
    caption = state.get("caption", "")
    hashtags = state.get("hashtags", [])
    image_url = state.get("image_url") or ""

    platform = current_post.get("platform", "instagram").lower()

    # ------------------------------------------------------------------
    # Determine scheduled time
    # ------------------------------------------------------------------
    scheduled_at = _resolve_scheduled_at(current_post=current_post, platform=platform)

    logger.info(
        "scheduler_node: platform=%s scheduled_at=%s draft_id=%s",
        platform, scheduled_at, draft_id,
    )

    # ------------------------------------------------------------------
    # Validate we have content to post
    # ------------------------------------------------------------------
    if not caption:
        logger.warning("scheduler_node: no caption available, skipping schedule")
        return {
            "scheduled": False,
            "messages": [{"role": "assistant", "content": "[Scheduler] Skipped — no caption available."}],
        }

    # ------------------------------------------------------------------
    # WhatsApp: direct send (no scheduling API)
    # ------------------------------------------------------------------
    if platform == "whatsapp":
        logger.info("scheduler_node: WhatsApp uses direct send, not scheduling API")
        _update_content_draft_db(
            draft_id=draft_id,
            status="scheduled",
            scheduled_at=scheduled_at,
            buffer_post_id=None,
        )
        return {
            "scheduled": True,
            "messages": [{"role": "assistant", "content": f"[Scheduler] WhatsApp post queued for {scheduled_at}."}],
        }

    # ------------------------------------------------------------------
    # Meta Graph API platforms (Instagram / Facebook)
    # ------------------------------------------------------------------
    buffer_post_id: Optional[str] = None
    post_id: Optional[str] = None

    if platform in _META_PLATFORMS:
        post_id = _schedule_via_meta(
            platform=platform,
            caption=caption,
            hashtags=hashtags,
            image_url=image_url or None,
            scheduled_at=scheduled_at,
        )

    # ------------------------------------------------------------------
    # Buffer fallback (or primary for LinkedIn/Twitter)
    # ------------------------------------------------------------------
    if not post_id:
        buffer_post_id = _schedule_via_buffer(
            platform=platform,
            caption=caption,
            hashtags=hashtags,
            image_url=image_url or None,
            scheduled_at=scheduled_at,
            user_id=user_id,
        )
        if not buffer_post_id:
            logger.error("scheduler_node: both Meta and Buffer scheduling failed for %s", platform)
            return {
                "scheduled": False,
                "messages": [{"role": "assistant", "content": f"[Scheduler] Failed to schedule on {platform}. Both Meta and Buffer APIs unavailable."}],
            }
    else:
        buffer_post_id = post_id

    # ------------------------------------------------------------------
    # Update DB
    # ------------------------------------------------------------------
    _update_content_draft_db(
        draft_id=draft_id,
        status="scheduled",
        scheduled_at=scheduled_at,
        buffer_post_id=buffer_post_id,
    )

    summary = (
        f"[Scheduler] Post scheduled on {platform.upper()} for {scheduled_at}. "
        f"Post ID: {buffer_post_id}. Draft ID: {draft_id}."
    )

    return {
        "scheduled": True,
        "messages": [{"role": "assistant", "content": summary}],
    }
