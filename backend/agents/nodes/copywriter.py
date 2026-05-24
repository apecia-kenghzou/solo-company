"""Copywriter node — generates platform-specific social media copy for listings."""
from __future__ import annotations

import logging

import anthropic

from backend.agents.state import MarketingState
from backend.config.settings import settings
from backend.knowledge.kb_writer import KBWriter

logger = logging.getLogger(__name__)

_client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
_kb = KBWriter()


# ---------------------------------------------------------------------------
# Platform-specific copy guidelines
# ---------------------------------------------------------------------------

_PLATFORM_GUIDELINES: dict[str, dict] = {
    "instagram": {
        "tone": "visually compelling, aspirational, scroll-stopping",
        "structure": (
            "Line 1 (hook): One powerful sentence to stop the scroll — make it emotional or surprising.\n"
            "Lines 2-6 (body): Tell the story. Use short punchy lines. Line breaks for readability.\n"
            "Line 7-8 (CTA): Clear action. 'DM for details', 'Link in bio', 'Comment YES to learn more'.\n"
            "Hashtags: 15-25 hashtags in the first comment or below (will be provided separately)."
        ),
        "length": "150-300 words for caption body",
        "hashtag_count": "20-25",
        "notes": "Use emojis sparingly but effectively. No corporate speak. First line must stand alone.",
    },
    "facebook": {
        "tone": "informative, warm, community-focused",
        "structure": (
            "Opening: A question or interesting fact (1-2 sentences).\n"
            "Body: 2-3 paragraphs with property details, area benefits, and investment angle.\n"
            "CTA: Direct call to action (call/message/book viewing).\n"
            "Link preview: Ensure key info appears before any links."
        ),
        "length": "150-400 words",
        "hashtag_count": "3-5",
        "notes": "Facebook users read more. Include specifics like price, location, and key features. Good for informative storytelling.",
    },
    "whatsapp": {
        "tone": "personal, direct, conversational",
        "structure": (
            "Opening: Personal greeting (Hi [name] or Hi all)\n"
            "Body: 2-3 short paragraphs — what's new, why it matters, one key detail.\n"
            "CTA: Clear single action — 'Reply for more info', 'Call me on [number]'.\n"
            "No hashtags. No emojis overload. Feels like a personal message."
        ),
        "length": "80-150 words",
        "hashtag_count": "0",
        "notes": "This is a WhatsApp broadcast — must feel personal, not like advertising. Use 'I' not 'we'. Clear simple CTA.",
    },
    "linkedin": {
        "tone": "thought leadership, professional, insightful",
        "structure": (
            "Hook: Bold opening statement or counterintuitive insight.\n"
            "Body: 3-5 short paragraphs sharing expertise, data, or perspective.\n"
            "Lesson: What's the takeaway for property investors / buyers?\n"
            "CTA: Soft — 'Thoughts?', 'What's your experience?', or 'DM me if you want to explore'."
        ),
        "length": "200-400 words",
        "hashtag_count": "3-5",
        "notes": "Share expert perspective, not just listings. Use data and personal experience. Connect property to business/investment angle.",
    },
}

_DEFAULT_PLATFORM = _PLATFORM_GUIDELINES["instagram"]


def copywriter_node(state: MarketingState) -> dict:
    """Write platform-specific social media copy for a content post.

    Uses the current_post dict to determine platform and content type,
    queries KB for relevant context, and generates caption + hashtags.
    """
    user_id = state.get("user_id", "")
    listing_id = state.get("listing_id")
    current_post = state.get("current_post", {})
    trend_data = state.get("trend_data", [])

    platform = current_post.get("platform", "instagram").lower()
    content_type = current_post.get("content_type", "listing_spotlight")
    topic = current_post.get("topic", "")
    notes = current_post.get("notes", "")
    post_listing_id = current_post.get("listing_id") or listing_id

    platform_guide = _PLATFORM_GUIDELINES.get(platform, _DEFAULT_PLATFORM)

    # ------------------------------------------------------------------
    # Build KB context
    # ------------------------------------------------------------------
    kb_parts = []
    try:
        import asyncio

        # Listing details
        if post_listing_id or topic:
            listing_query = f"{topic or ''} {post_listing_id or ''}".strip() or "property listing"
            listing_ctx = asyncio.run(_kb.query_kb(user_id=user_id, query=listing_query, kb_type="listing", top_k=5))
            if listing_ctx:
                kb_parts.append(f"LISTING DETAILS:\n{listing_ctx}")

        # Market context
        market_ctx = asyncio.run(_kb.query_kb(user_id=user_id, query="property market trends investment", kb_type="market_report", top_k=2))
        if market_ctx:
            kb_parts.append(f"MARKET CONTEXT:\n{market_ctx}")

        # Brand voice
        voice_ctx = asyncio.run(_kb.query_kb(user_id=user_id, query="brand voice tone communication style", kb_type="company_profile", top_k=2))
        if voice_ctx:
            kb_parts.append(f"BRAND VOICE:\n{voice_ctx}")

        # Trend hooks for inspiration
        trend_ctx = asyncio.run(_kb.query_kb(user_id=user_id, query=f"{platform} viral hooks content angles", kb_type="social_trend", top_k=3))
        if trend_ctx:
            kb_parts.append(f"CURRENT TRENDS & HOOKS:\n{trend_ctx}")

    except Exception as exc:
        logger.warning("copywriter_node: KB query failed: %s", exc)

    kb_context = "\n\n".join(kb_parts) if kb_parts else "No specific context loaded."

    # ------------------------------------------------------------------
    # Build system and user prompts
    # ------------------------------------------------------------------
    system_prompt = (
        f"You are an expert real estate social media copywriter specialising in {platform} content. "
        f"You write copy that converts — it stops the scroll, builds desire, and drives action.\n\n"
        f"PLATFORM: {platform.upper()}\n"
        f"TONE: {platform_guide['tone']}\n"
        f"STRUCTURE GUIDE:\n{platform_guide['structure']}\n"
        f"TARGET LENGTH: {platform_guide['length']}\n"
        f"NOTES: {platform_guide['notes']}"
    )

    # Format trend data if available
    trend_inspiration = ""
    if trend_data:
        top_hooks = [t.get("hook", "") for t in trend_data[:3] if t.get("hook")]
        if top_hooks:
            trend_inspiration = "TRENDING HOOKS FOR INSPIRATION:\n" + "\n".join(f"• {h}" for h in top_hooks)

    user_prompt = (
        f"Write {platform.upper()} copy for this post.\n\n"
        f"Content type: {content_type}\n"
        f"Topic/Focus: {topic or 'property listing'}\n"
        f"Additional notes: {notes or 'None'}\n\n"
        f"KNOWLEDGE BASE CONTEXT:\n{kb_context}\n\n"
        f"{trend_inspiration}\n\n"
        f"Output ONLY:\n"
        f"1. The caption (no label needed)\n"
        f"2. Then on a new line: HASHTAGS: followed by the hashtags space-separated\n\n"
        f"Do not include any other text or labels."
    )

    # ------------------------------------------------------------------
    # Generate copy with Claude
    # ------------------------------------------------------------------
    caption = ""
    hashtags: list[str] = []

    try:
        response = _client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=1024,
            system=system_prompt,
            messages=[{"role": "user", "content": user_prompt}],
        )
        raw_output = response.content[0].text.strip() if response.content else ""

        # Parse caption and hashtags
        if "HASHTAGS:" in raw_output:
            parts = raw_output.split("HASHTAGS:", 1)
            caption = parts[0].strip()
            hashtag_line = parts[1].strip()
            # Parse hashtags — handle both space and newline separated
            hashtags = [
                tag.strip().lstrip("#")
                for tag in hashtag_line.replace("\n", " ").split()
                if tag.strip()
            ]
            # Re-add # prefix
            hashtags = [f"#{h}" if not h.startswith("#") else h for h in hashtags]
        else:
            # No hashtag separator — treat full output as caption
            caption = raw_output
            hashtags = []

    except Exception as exc:
        logger.error("copywriter_node: Claude copy generation failed: %s", exc)
        caption = (
            f"Discover your dream property today.\n\n"
            f"{topic or 'Premium properties available for serious buyers.'}\n\n"
            f"DM us to learn more."
        )
        hashtags = ["#realestate", "#property", "#dreamhome", "#propertyforsale", "#realestatetips"]

    # ------------------------------------------------------------------
    # Enforce platform hashtag count limits
    # ------------------------------------------------------------------
    max_hashtags = int(platform_guide["hashtag_count"].split("-")[-1]) if "-" in platform_guide["hashtag_count"] else int(platform_guide["hashtag_count"])
    hashtags = hashtags[:max_hashtags]

    # WhatsApp: strip all hashtags
    if platform == "whatsapp":
        hashtags = []

    summary = (
        f"[Copywriter] {platform.upper()} copy generated for '{content_type}'. "
        f"Caption: {len(caption)} chars. Hashtags: {len(hashtags)}."
    )

    return {
        "caption": caption,
        "hashtags": hashtags,
        "messages": [{"role": "assistant", "content": summary}],
    }
