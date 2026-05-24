"""Image generation node — creates or selects images for social media posts."""
from __future__ import annotations

import logging
import os
from typing import Optional

import anthropic

from backend.agents.state import MarketingState
from backend.config.settings import settings
from backend.knowledge.kb_writer import KBWriter

logger = logging.getLogger(__name__)

_client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
_kb = KBWriter()


# ---------------------------------------------------------------------------
# Image type classification
# ---------------------------------------------------------------------------

_IMAGE_TYPE_MAP = {
    "listing_spotlight": "listing_photo",
    "property_tour": "listing_photo",
    "market_tip": "stat_card",
    "market_update": "stat_card",
    "stat_reveal": "stat_card",
    "area_highlight": "infographic",
    "local_area": "infographic",
    "testimonial": "text_card",
    "personal_brand": "text_card",
    "investment_tip": "stat_card",
}


def _classify_image_type(content_type: str, caption: str) -> str:
    """Determine the best image type for the post."""
    content_lower = content_type.lower()

    # Direct mapping
    for key, img_type in _IMAGE_TYPE_MAP.items():
        if key in content_lower:
            return img_type

    # Fallback: scan caption for clues
    caption_lower = caption.lower()
    if any(word in caption_lower for word in ["bedroom", "bathroom", "sqft", "psf", "unit", "floor"]):
        return "listing_photo"
    if any(word in caption_lower for word in ["%", "price", "index", "trend", "market"]):
        return "stat_card"

    return "listing_photo"  # safe default


# ---------------------------------------------------------------------------
# Generation functions
# ---------------------------------------------------------------------------

def _get_listing_photos_from_kb(user_id: str, listing_id: Optional[str], topic: str) -> Optional[str]:
    """Try to retrieve an existing property photo URL from KB/DB."""
    logger.info("KB photo lookup stub: user=%s listing=%s", user_id, listing_id)
    # In production: query the Listing model from DB for photo_urls[0]
    # Return None if not found so we fall through to generation
    return None


def _generate_with_dalle3(prompt: str) -> Optional[str]:
    """Generate an image using DALL-E 3 via OpenAI API."""
    logger.info("DALL-E 3: generating image")
    try:
        from openai import OpenAI
        openai_client = OpenAI(api_key=settings.openai_api_key)
        response = openai_client.images.generate(
            model="dall-e-3",
            prompt=prompt,
            size="1024x1024",
            quality="standard",
            n=1,
        )
        url = response.data[0].url if response.data else None
        logger.info("DALL-E 3: generated image url=%s", url[:60] if url else "None")
        return url
    except Exception as exc:
        logger.error("DALL-E 3 generation failed: %s", exc)
        return None


def _generate_with_ideogram(prompt: str) -> Optional[str]:
    """Generate a stat card image using Ideogram API (better text rendering)."""
    logger.info("Ideogram: generating stat card")
    try:
        import httpx

        api_key = settings.ideogram_api_key
        if not api_key:
            raise ValueError("IDEOGRAM_API_KEY not set")

        payload = {
            "image_request": {
                "prompt": prompt,
                "aspect_ratio": "ASPECT_1_1",
                "model": "V_2",
                "magic_prompt_option": "AUTO",
            }
        }

        with httpx.Client(timeout=60) as http:
            resp = http.post(
                "https://api.ideogram.ai/generate",
                headers={"Api-Key": api_key, "Content-Type": "application/json"},
                json=payload,
            )
            resp.raise_for_status()
            data = resp.json()
            images = data.get("data", [])
            if images:
                url = images[0].get("url")
                logger.info("Ideogram: generated image url=%s", str(url)[:60] if url else "None")
                return url

        return None
    except Exception as exc:
        logger.error("Ideogram generation failed: %s", exc)
        return None


def _upload_to_s3(image_url: str, user_id: str, filename: str) -> Optional[str]:
    """Download an image from URL and upload to S3/R2, return the permanent URL."""
    logger.info("S3 upload stub: user=%s filename=%s", user_id, filename)
    try:
        import httpx
        import boto3

        # Download image
        with httpx.Client(timeout=30) as http:
            img_resp = http.get(image_url)
            img_resp.raise_for_status()
            image_bytes = img_resp.content

        # Upload to S3
        s3 = boto3.client(
            "s3",
            region_name=settings.s3_region,
            aws_access_key_id=settings.aws_access_key_id,
            aws_secret_access_key=settings.aws_secret_access_key,
            endpoint_url=settings.s3_endpoint_url or None,
        )
        key = f"content/{user_id}/{filename}"
        s3.put_object(
            Bucket=settings.s3_bucket_name,
            Key=key,
            Body=image_bytes,
            ContentType="image/jpeg",
        )
        permanent_url = f"https://{settings.s3_bucket_name}.s3.{settings.s3_region}.amazonaws.com/{key}"
        logger.info("S3 upload complete: %s", permanent_url)
        return permanent_url
    except Exception as exc:
        logger.error("S3 upload failed: %s", exc)
        return image_url  # Return original URL as fallback


def _build_dalle_prompt(image_type: str, caption: str, topic: str, platform: str) -> str:
    """Build a DALL-E prompt for a photorealistic property image."""
    base = (
        "Professional real estate photography, high quality, well-lit, modern aesthetic. "
        "No text overlays. No watermarks. "
    )
    if image_type == "listing_photo":
        return (
            f"{base}Exterior or interior architectural photo of a modern residential property. "
            f"Clean lines, attractive landscaping if exterior, stylish interior if inside. "
            f"Context: {topic or 'luxury residential property'}. "
            f"Shot for {platform} social media."
        )
    elif image_type == "infographic":
        return (
            f"{base}Beautiful aerial or street-level photo of an urban neighbourhood with parks, "
            f"cafes, and modern amenities. Vibrant community feel. "
            f"Context: {topic or 'desirable residential area'}."
        )
    else:
        return (
            f"{base}Modern, clean property-related lifestyle photo. "
            f"Bright, aspirational, suitable for real estate social media. Topic: {topic}."
        )


def _build_ideogram_prompt(caption: str, topic: str, platform: str) -> str:
    """Build an Ideogram prompt for a text-forward stat card."""
    return (
        f"Clean, modern real estate infographic card. "
        f"Minimalist design with bold typography. "
        f"Colour palette: deep navy blue and gold accents on white background. "
        f"Property/market statistic visual. "
        f"Topic: {topic or 'property market insight'}. "
        f"Professional, suitable for {platform}. "
        f"Include a subtle property icon or chart element. "
        f"No specific numbers or text — just the design layout and style."
    )


# ---------------------------------------------------------------------------
# Node
# ---------------------------------------------------------------------------

def image_gen_node(state: MarketingState) -> dict:
    """Select or generate an appropriate image for the current social post.

    Logic:
    - listing posts → try KB/DB for existing photo, else DALL-E 3
    - stat cards (with text) → Ideogram (better text rendering)
    - area/infographic → DALL-E 3
    Upload result to S3 and return permanent URL.
    """
    user_id = state.get("user_id", "")
    listing_id = state.get("listing_id")
    current_post = state.get("current_post", {})
    caption = state.get("caption", "")

    platform = current_post.get("platform", "instagram")
    content_type = current_post.get("content_type", "listing_spotlight")
    topic = current_post.get("topic", "")
    post_listing_id = current_post.get("listing_id") or listing_id

    # ------------------------------------------------------------------
    # Determine image type
    # ------------------------------------------------------------------
    image_type = _classify_image_type(content_type=content_type, caption=caption)
    logger.info("image_gen_node: content_type=%s → image_type=%s", content_type, image_type)

    image_url: Optional[str] = None

    # ------------------------------------------------------------------
    # Try existing listing photos first (for listing content)
    # ------------------------------------------------------------------
    if image_type == "listing_photo" and post_listing_id:
        image_url = _get_listing_photos_from_kb(
            user_id=user_id,
            listing_id=post_listing_id,
            topic=topic,
        )

    # ------------------------------------------------------------------
    # Generate image if none found
    # ------------------------------------------------------------------
    if not image_url:
        if image_type == "stat_card":
            # Ideogram for text-heavy stat cards
            prompt = _build_ideogram_prompt(caption=caption, topic=topic, platform=platform)
            image_url = _generate_with_ideogram(prompt=prompt)

            # Fallback to DALL-E 3 if Ideogram unavailable
            if not image_url:
                logger.info("image_gen_node: Ideogram unavailable, falling back to DALL-E 3")
                prompt = _build_dalle_prompt(
                    image_type="listing_photo",
                    caption=caption,
                    topic=topic,
                    platform=platform,
                )
                image_url = _generate_with_dalle3(prompt=prompt)

        else:
            # DALL-E 3 for photorealistic and infographic content
            prompt = _build_dalle_prompt(
                image_type=image_type,
                caption=caption,
                topic=topic,
                platform=platform,
            )
            image_url = _generate_with_dalle3(prompt=prompt)

    # ------------------------------------------------------------------
    # Upload to S3 for permanent storage
    # ------------------------------------------------------------------
    if image_url and image_url.startswith("http"):
        import time
        timestamp = str(int(time.time()))
        filename = f"{content_type}_{timestamp}.jpg"
        permanent_url = _upload_to_s3(
            image_url=image_url,
            user_id=user_id,
            filename=filename,
        )
        image_url = permanent_url or image_url

    # Final fallback: return empty string (scheduler can handle missing image)
    if not image_url:
        logger.warning("image_gen_node: no image generated, returning empty URL")
        image_url = ""

    summary = (
        f"[Image Gen] Type: {image_type}. Method: {'existing_photo' if 'listing' in image_type else 'generated'}. "
        f"URL: {(image_url[:60] + '...') if len(image_url) > 60 else image_url}"
    )

    return {
        "image_url": image_url,
        "messages": [{"role": "assistant", "content": summary}],
    }
