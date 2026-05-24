"""WhatsApp follow-up node — sends time-based nurture sequences to leads."""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Optional

import anthropic

from backend.agents.state import FrontDeskState
from backend.config.settings import settings
from backend.knowledge.kb_writer import KBWriter

logger = logging.getLogger(__name__)

_client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
_kb = KBWriter()

# Follow-up day templates drive the prompt context
_FOLLOWUP_TEMPLATES = {
    1: {
        "tone": "warm and welcoming",
        "goal": "introduce yourself and reference their specific property interest to start the relationship",
        "instruction": (
            "This is a Day 1 follow-up. The lead just reached out. "
            "Warm intro, reference their property interest specifically. "
            "Keep it short — 2-3 sentences. End with an open question."
        ),
    },
    3: {
        "tone": "helpful and informative",
        "goal": "add genuine value with a market insight or property highlight relevant to their interest",
        "instruction": (
            "This is a Day 3 follow-up. The lead hasn't responded or needs nurturing. "
            "Share one interesting market insight or a standout feature of the property. "
            "Position yourself as a knowledgeable advisor. 3-4 sentences max."
        ),
    },
    7: {
        "tone": "friendly and conversational",
        "goal": "soft check-in with a genuine question to re-engage",
        "instruction": (
            "This is a Day 7 follow-up. Soft check-in. "
            "Acknowledge that they might be busy. Ask a specific question about their timeline or requirements. "
            "2-3 sentences. No hard sell."
        ),
    },
    30: {
        "tone": "long-term relationship building",
        "goal": "stay top of mind with new content or a market update",
        "instruction": (
            "This is a Day 30 long-term nurture. The lead has gone quiet. "
            "Share something genuinely new — a new listing, market development, or useful property tip. "
            "Keep it brief. Remind them you're available when they're ready."
        ),
    },
}

_DEFAULT_TEMPLATE = {
    "tone": "friendly and professional",
    "goal": "maintain engagement and provide value",
    "instruction": "Send a friendly check-in message that adds value. 2-3 sentences.",
}


def _send_whatsapp(phone: str, message: str) -> bool:
    """Stub for WhatsApp send — real implementation calls 360dialog API."""
    logger.info("WhatsApp send stub: to=%s msg_len=%d", phone, len(message))
    # In production: calls backend.tools.whatsapp_tool.send_message(phone, message)
    return True


def _update_lead_next_followup(lead_id: str, next_at: datetime) -> None:
    """Stub — updates lead.next_follow_up_at in DB."""
    logger.info("DB stub: update lead %s next_follow_up_at=%s", lead_id, next_at.isoformat())
    # In production: async DB update via SQLAlchemy


def _get_follow_up_count(lead_data: dict) -> int:
    """Extract follow_up_count from lead_data, defaulting to 0."""
    try:
        return int(lead_data.get("follow_up_count", 0))
    except (TypeError, ValueError):
        return 0


def _resolve_template_day(follow_up_count: int) -> dict:
    """Map follow-up count to the appropriate template."""
    if follow_up_count == 0:
        return _FOLLOWUP_TEMPLATES[1]
    elif follow_up_count <= 2:
        return _FOLLOWUP_TEMPLATES[3]
    elif follow_up_count <= 5:
        return _FOLLOWUP_TEMPLATES[7]
    else:
        return _FOLLOWUP_TEMPLATES[30]


def whatsapp_followup_node(state: FrontDeskState) -> dict:
    """Send a personalised WhatsApp follow-up message to a lead.

    Determines follow-up stage from lead_data.follow_up_count:
      0       → Day 1 warm intro
      1-2     → Day 3 value-add
      3-5     → Day 7 soft check-in
      6+      → Day 30 long-term nurture
    """
    user_id = state.get("user_id", "")
    lead_id = state.get("lead_id")
    lead_data = state.get("lead_data", {})
    listing_id = state.get("listing_id")

    lead_name = lead_data.get("name") or "there"
    phone = lead_data.get("phone", "")
    property_interest = lead_data.get("property_interest", "property options")
    follow_up_count = _get_follow_up_count(lead_data)

    # ------------------------------------------------------------------
    # Determine follow-up stage
    # ------------------------------------------------------------------
    template = _resolve_template_day(follow_up_count)

    # ------------------------------------------------------------------
    # Fetch KB context for personalisation
    # ------------------------------------------------------------------
    kb_context = ""
    try:
        import asyncio
        query = f"{property_interest} market insights"
        kb_context = asyncio.run(_kb.query_kb(user_id=user_id, query=query, top_k=4))
    except Exception as exc:
        logger.warning("whatsapp_followup_node: KB query failed: %s", exc)

    # ------------------------------------------------------------------
    # Generate personalised message with Claude
    # ------------------------------------------------------------------
    system_prompt = (
        "You are a real estate agent sending a personalised WhatsApp follow-up message. "
        "Write naturally as if you're texting — conversational, warm, no corporate stiffness. "
        "No hashtags. No emojis unless the tone calls for it. "
        "Keep messages SHORT. WhatsApp messages should be 1-4 sentences maximum.\n\n"
        f"RELEVANT CONTEXT:\n{kb_context or 'No specific context available.'}"
    )

    user_prompt = (
        f"Write a WhatsApp follow-up message.\n\n"
        f"Lead name: {lead_name}\n"
        f"Property interest: {property_interest}\n"
        f"Budget: {lead_data.get('budget_min', 'unknown')} - {lead_data.get('budget_max', 'unknown')}\n"
        f"Timeline: {lead_data.get('timeline', 'not specified')}\n"
        f"Follow-up number: {follow_up_count + 1}\n\n"
        f"TONE: {template['tone']}\n"
        f"GOAL: {template['goal']}\n\n"
        f"INSTRUCTIONS: {template['instruction']}"
    )

    message_text = ""
    try:
        response = _client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=512,
            system=system_prompt,
            messages=[{"role": "user", "content": user_prompt}],
        )
        message_text = response.content[0].text.strip() if response.content else ""
    except Exception as exc:
        logger.error("whatsapp_followup_node: Claude call failed: %s", exc)
        message_text = f"Hi {lead_name}, just checking in on your property search. Let me know if I can help!"

    # ------------------------------------------------------------------
    # Send message
    # ------------------------------------------------------------------
    sent = False
    if phone and message_text:
        sent = _send_whatsapp(phone=phone, message=message_text)
    else:
        logger.warning("whatsapp_followup_node: missing phone or message, skipping send")

    # ------------------------------------------------------------------
    # Schedule next follow-up
    # ------------------------------------------------------------------
    now = datetime.now(timezone.utc)
    # Next follow-up intervals: day 1 → +2d, day 3 → +4d, day 7 → +23d, day 30 → +30d
    next_intervals = {0: 2, 1: 4, 2: 4, 3: 23, 4: 23}
    days_until_next = next_intervals.get(follow_up_count, 30)
    next_follow_up = now + timedelta(days=days_until_next)

    if lead_id:
        _update_lead_next_followup(lead_id=lead_id, next_at=next_follow_up)

    summary = (
        f"[WhatsApp Follow-up #{follow_up_count + 1}] "
        f"Sent to {lead_name} ({phone or 'no phone'}). "
        f"Message sent: {sent}. "
        f"Next follow-up scheduled: {next_follow_up.strftime('%Y-%m-%d')}."
    )

    return {
        "follow_up_scheduled": True,
        "draft_reply": message_text,
        "reply_sent": sent,
        "messages": [{"role": "assistant", "content": summary}],
    }
