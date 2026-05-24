"""Strategist node — builds a weekly 5-post social media content calendar."""
from __future__ import annotations

import json
import logging
from datetime import datetime, timedelta, timezone
from typing import Optional

import anthropic

from backend.agents.state import MarketingState
from backend.config.settings import settings
from backend.knowledge.kb_writer import KBWriter

logger = logging.getLogger(__name__)

_client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
_kb = KBWriter()

# Optimal posting times per platform
_OPTIMAL_TIMES: dict[str, list[str]] = {
    "instagram": ["09:00", "12:00", "19:00"],
    "facebook": ["10:00", "15:00"],
    "whatsapp": ["09:00", "18:00"],
    "linkedin": ["08:00", "12:00", "17:00"],
}

_CONTENT_PLAN_SCHEMA = {
    "name": "create_content_plan",
    "description": "Create a structured 5-post weekly content plan for a real estate agent.",
    "input_schema": {
        "type": "object",
        "properties": {
            "posts": {
                "type": "array",
                "minItems": 5,
                "maxItems": 5,
                "items": {
                    "type": "object",
                    "properties": {
                        "post_number": {"type": "integer"},
                        "content_type": {
                            "type": "string",
                            "enum": [
                                "listing_spotlight",
                                "market_tip",
                                "local_area",
                                "personal_brand",
                                "testimonial",
                                "market_update",
                                "investment_tip",
                                "property_tour",
                            ],
                        },
                        "platform": {
                            "type": "string",
                            "enum": ["instagram", "facebook", "whatsapp", "linkedin"],
                        },
                        "topic": {
                            "type": "string",
                            "description": "Specific topic or angle for this post.",
                        },
                        "listing_id": {
                            "type": "string",
                            "description": "Listing ID if this is a listing spotlight post.",
                        },
                        "posting_day": {
                            "type": "string",
                            "enum": ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"],
                        },
                        "posting_time": {
                            "type": "string",
                            "description": "Optimal posting time in HH:MM 24h format.",
                        },
                        "rationale": {
                            "type": "string",
                            "description": "Why this post at this time.",
                        },
                    },
                    "required": ["post_number", "content_type", "platform", "topic", "posting_day", "posting_time"],
                },
            }
        },
        "required": ["posts"],
    },
}


def _get_next_weekday_date(day_name: str) -> str:
    """Return the next occurrence of a day name as YYYY-MM-DD."""
    days = {"Monday": 0, "Tuesday": 1, "Wednesday": 2, "Thursday": 3,
            "Friday": 4, "Saturday": 5, "Sunday": 6}
    today = datetime.now(timezone.utc)
    target = days.get(day_name, 0)
    days_ahead = (target - today.weekday()) % 7
    if days_ahead == 0:
        days_ahead = 7  # Schedule for next week if today
    scheduled = today + timedelta(days=days_ahead)
    return scheduled.strftime("%Y-%m-%d")


def strategist_node(state: MarketingState) -> dict:
    """Plan a 5-post weekly content calendar based on listings and trends.

    Content mix (weekly):
    - 2 listing spotlights (different listings where available)
    - 1-2 market tips (based on current market report)
    - 1 local area post
    - 1 personal brand / testimonial post

    For each post: determines platform, content type, optimal posting time.
    """
    user_id = state.get("user_id", "")
    listing_id = state.get("listing_id")
    trend_data = state.get("trend_data", [])

    # ------------------------------------------------------------------
    # Gather context from KB
    # ------------------------------------------------------------------
    kb_parts = []
    active_listings: list[dict] = []
    try:
        import asyncio

        # Get all active listings
        listings_ctx = asyncio.run(_kb.query_kb(
            user_id=user_id,
            query="property listing for sale available",
            kb_type="listing",
            top_k=8,
        ))
        if listings_ctx:
            kb_parts.append(f"ACTIVE LISTINGS:\n{listings_ctx}")

        # Market report context
        market_ctx = asyncio.run(_kb.query_kb(
            user_id=user_id,
            query="property market trends price insights this week",
            kb_type="market_report",
            top_k=3,
        ))
        if market_ctx:
            kb_parts.append(f"CURRENT MARKET DATA:\n{market_ctx}")

        # Social trends
        trend_ctx = asyncio.run(_kb.query_kb(
            user_id=user_id,
            query="viral hooks content angles trending formats",
            kb_type="social_trend",
            top_k=4,
        ))
        if trend_ctx:
            kb_parts.append(f"CURRENT TRENDS:\n{trend_ctx}")

        # Brand voice
        voice_ctx = asyncio.run(_kb.query_kb(
            user_id=user_id,
            query="brand voice communication style target audience",
            kb_type="company_profile",
            top_k=2,
        ))
        if voice_ctx:
            kb_parts.append(f"BRAND CONTEXT:\n{voice_ctx}")

    except Exception as exc:
        logger.warning("strategist_node: KB query failed: %s", exc)

    # Add trend_data from state if available
    if trend_data:
        top_trends = trend_data[:3]
        trend_summary = "; ".join(
            str(t.get("text", t.get("hook", t.get("content_type", ""))))
            for t in top_trends
        )
        kb_parts.append(f"TREND DATA FROM RESEARCH:\n{trend_summary}")

    kb_context = "\n\n".join(kb_parts) if kb_parts else "No context loaded."

    # ------------------------------------------------------------------
    # Generate content plan with Claude tool_use
    # ------------------------------------------------------------------
    week_start = datetime.now(timezone.utc).strftime("%B %d, %Y")

    system_prompt = (
        "You are a senior real estate marketing strategist. "
        "Create a smart, balanced weekly content calendar that builds the agent's brand, "
        "showcases listings, and provides genuine value to their audience. "
        "Consider platform strengths, audience behaviour, and the current market context."
    )

    user_prompt = (
        f"Create a 5-post weekly content calendar for the week starting {week_start}.\n\n"
        f"REQUIREMENTS:\n"
        f"- Exactly 2 listing spotlight posts (use different listings if available)\n"
        f"- At least 1 market tips/insights post (use current market data)\n"
        f"- 1 local area post (neighbourhood, amenities, lifestyle)\n"
        f"- 1 personal brand or testimonial post\n"
        f"- Spread across multiple platforms (don't put all on Instagram)\n"
        f"- Space posts out across the week (Mon-Sat)\n"
        f"- Use optimal posting times for each platform\n\n"
        f"CONTEXT:\n{kb_context}\n\n"
        f"For listing posts, reference the listing IDs from the context. "
        f"For topic, be specific — use actual property names, prices, locations from context."
    )

    content_plan: list[dict] = []
    try:
        plan_response = _client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=2048,
            system=system_prompt,
            messages=[{"role": "user", "content": user_prompt}],
            tools=[_CONTENT_PLAN_SCHEMA],
            tool_choice={"type": "tool", "name": "create_content_plan"},
        )

        tool_block = next(
            (b for b in plan_response.content if b.type == "tool_use"),
            None,
        )
        if tool_block:
            plan_data: dict = tool_block.input
            raw_posts = plan_data.get("posts", [])
            for post in raw_posts:
                # Add scheduled datetime
                day_name = post.get("posting_day", "Monday")
                posting_time = post.get("posting_time", "09:00")
                scheduled_date = _get_next_weekday_date(day_name)
                post["scheduled_date"] = scheduled_date
                post["scheduled_at"] = f"{scheduled_date}T{posting_time}:00Z"
                content_plan.append(post)

    except Exception as exc:
        logger.error("strategist_node: Claude plan generation failed: %s", exc)

    # ------------------------------------------------------------------
    # Fallback: build default plan if Claude failed
    # ------------------------------------------------------------------
    if not content_plan:
        logger.warning("strategist_node: using fallback content plan")
        default_posts = [
            {"post_number": 1, "content_type": "listing_spotlight", "platform": "instagram",
             "topic": "Property listing showcase — key features and highlights",
             "listing_id": listing_id or "", "posting_day": "Monday", "posting_time": "09:00"},
            {"post_number": 2, "content_type": "market_tip", "platform": "facebook",
             "topic": "This week's property market insight — what buyers should know",
             "listing_id": "", "posting_day": "Tuesday", "posting_time": "10:00"},
            {"post_number": 3, "content_type": "listing_spotlight", "platform": "instagram",
             "topic": "Second listing showcase — investment opportunity",
             "listing_id": "", "posting_day": "Wednesday", "posting_time": "12:00"},
            {"post_number": 4, "content_type": "local_area", "platform": "instagram",
             "topic": "Why this neighbourhood is becoming the most desirable in the city",
             "listing_id": "", "posting_day": "Thursday", "posting_time": "09:00"},
            {"post_number": 5, "content_type": "personal_brand", "platform": "linkedin",
             "topic": "What I've learned helping buyers find their dream home this year",
             "listing_id": "", "posting_day": "Saturday", "posting_time": "10:00"},
        ]
        for post in default_posts:
            day_name = post["posting_day"]
            posting_time = post["posting_time"]
            scheduled_date = _get_next_weekday_date(day_name)
            post["scheduled_date"] = scheduled_date
            post["scheduled_at"] = f"{scheduled_date}T{posting_time}:00Z"
            content_plan.append(post)

    summary = (
        f"[Strategist] Content plan created: {len(content_plan)} posts scheduled "
        f"for week of {week_start}. "
        f"Platforms: {', '.join(set(p.get('platform', '') for p in content_plan))}."
    )

    return {
        "content_plan": content_plan,
        "current_post": content_plan[0] if content_plan else {},
        "messages": [{"role": "assistant", "content": summary}],
    }
