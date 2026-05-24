"""Chat node — conversational WhatsApp agent for ongoing lead conversations."""
from __future__ import annotations

import json
import logging
from typing import Optional

import anthropic

from backend.agents.state import FrontDeskState
from backend.config.settings import settings
from backend.knowledge.kb_writer import KBWriter

logger = logging.getLogger(__name__)

_client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
_kb = KBWriter()

# Signals that indicate a hot lead ready for human escalation
_ESCALATION_KEYWORDS = [
    "want to buy", "ready to buy", "make an offer", "serious buyer",
    "how do i purchase", "what is the process to buy", "i want to proceed",
    "deposit", "loan pre-approval", "can we sign", "finalize",
    "very interested", "when can we close", "i'll take it",
    "too slow", "not helpful", "waste of time", "speak to manager",
    "call me now", "urgent", "need to decide today", "deadline",
]

_VIEWING_KEYWORDS = [
    "can i view", "viewing", "show me", "visit", "walk through",
    "see the unit", "inspect", "when can i see", "schedule a visit",
    "arrange viewing", "book a viewing",
]

_DETECT_SIGNALS_TOOL = {
    "name": "detect_conversation_signals",
    "description": "Analyse the latest lead message to detect viewing interest and escalation signals.",
    "input_schema": {
        "type": "object",
        "properties": {
            "viewing_interest": {
                "type": "boolean",
                "description": "True if the lead has expressed interest in viewing the property.",
            },
            "escalate": {
                "type": "boolean",
                "description": "True if the lead shows hot buyer signals (offer intent, urgency, frustration, or request for immediate human contact).",
            },
            "escalation_reason": {
                "type": "string",
                "description": "Short explanation of why escalation is needed (if escalate=true).",
            },
            "suggested_viewing_times": {
                "type": "array",
                "items": {"type": "string"},
                "description": "2-3 suggested viewing time slots if viewing_interest=true (e.g. 'Saturday 10am', 'Sunday 2pm').",
            },
        },
        "required": ["viewing_interest", "escalate"],
    },
}


def _load_conversation_history(lead_data: dict) -> list[dict]:
    """Extract conversation history from lead_data, handling various formats."""
    history = lead_data.get("conversation_history", [])
    if isinstance(history, str):
        try:
            history = json.loads(history)
        except json.JSONDecodeError:
            history = []
    return history if isinstance(history, list) else []


def _update_conversation_history(lead_id: Optional[str], user_msg: str, assistant_msg: str) -> None:
    """Stub — appends exchange to lead.conversation_history in DB."""
    logger.info(
        "DB stub: update conversation history for lead %s (user=%d chars, assistant=%d chars)",
        lead_id, len(user_msg), len(assistant_msg),
    )
    # In production: async DB update via SQLAlchemy ORM Lead model


def _keyword_check(text: str, keywords: list[str]) -> bool:
    """Simple keyword presence check (case-insensitive)."""
    lower = text.lower()
    return any(kw in lower for kw in keywords)


def chat_node(state: FrontDeskState) -> dict:
    """Conversational agent for ongoing WhatsApp lead conversations.

    Responsibilities:
    - Query KB for listing details, market data, and objection handling.
    - Maintain conversation context from lead history.
    - Detect escalation signals (offer intent, frustration, urgency).
    - Detect viewing interest and generate suggested time slots.
    - Respond naturally using Claude with full KB context.
    """
    user_id = state.get("user_id", "")
    lead_id = state.get("lead_id")
    listing_id = state.get("listing_id")
    lead_data = state.get("lead_data", {})
    inbound = state.get("inbound_message", "")

    lead_name = lead_data.get("name") or "the lead"
    property_interest = lead_data.get("property_interest", "")

    # ------------------------------------------------------------------
    # Quick keyword pre-checks (avoids unnecessary LLM calls for clear cases)
    # ------------------------------------------------------------------
    quick_escalate = _keyword_check(inbound, _ESCALATION_KEYWORDS)
    quick_viewing = _keyword_check(inbound, _VIEWING_KEYWORDS)

    # ------------------------------------------------------------------
    # Build KB context
    # ------------------------------------------------------------------
    kb_parts = []
    try:
        import asyncio

        # Listing / property details
        listing_query = f"{property_interest} {listing_id or ''}".strip() or "property listing"
        listing_ctx = asyncio.run(_kb.query_kb(user_id=user_id, query=listing_query, kb_type="listing", top_k=5))
        if listing_ctx:
            kb_parts.append(f"LISTING DETAILS:\n{listing_ctx}")

        # Market data
        market_ctx = asyncio.run(_kb.query_kb(user_id=user_id, query="property market trends pricing", kb_type="market_report", top_k=2))
        if market_ctx:
            kb_parts.append(f"MARKET DATA:\n{market_ctx}")

        # Objection handling
        obj_ctx = asyncio.run(_kb.query_kb(user_id=user_id, query=inbound, kb_type="objection", top_k=3))
        if obj_ctx:
            kb_parts.append(f"OBJECTION HANDLING:\n{obj_ctx}")

        # Brand voice
        voice_ctx = asyncio.run(_kb.query_kb(user_id=user_id, query="brand voice style", kb_type="company_profile", top_k=1))
        if voice_ctx:
            kb_parts.append(f"COMMUNICATION STYLE:\n{voice_ctx}")

    except Exception as exc:
        logger.warning("chat_node: KB query failed: %s", exc)

    kb_context = "\n\n".join(kb_parts) if kb_parts else state.get("kb_context", "")

    # ------------------------------------------------------------------
    # Load conversation history
    # ------------------------------------------------------------------
    history = _load_conversation_history(lead_data)
    # Build Claude message list from history
    claude_messages: list[dict] = []
    for entry in history[-10:]:  # cap at last 10 exchanges to stay within context
        role = entry.get("role", "user")
        content = entry.get("content", "")
        if role in ("user", "assistant") and content:
            claude_messages.append({"role": role, "content": content})

    # Append current inbound
    claude_messages.append({"role": "user", "content": inbound})

    # ------------------------------------------------------------------
    # System prompt
    # ------------------------------------------------------------------
    system_prompt = (
        "You are a knowledgeable, warm real estate consultant having a WhatsApp conversation. "
        "Your role is to answer questions, handle objections, build rapport, and guide the lead toward a viewing.\n\n"
        "GUIDELINES:\n"
        "- Keep replies concise for WhatsApp — 2-5 sentences typically.\n"
        "- Use the lead's name occasionally but not in every message.\n"
        "- Be honest — don't promise things you can't confirm.\n"
        "- If they're interested in viewing, offer 2-3 specific time slots.\n"
        "- If they raise an objection, address it directly using the objection handling context.\n"
        "- Never send a wall of text — use line breaks if needed.\n\n"
        f"KNOWLEDGE BASE CONTEXT:\n{kb_context or 'No specific context loaded.'}"
    )

    # ------------------------------------------------------------------
    # Generate reply with Claude
    # ------------------------------------------------------------------
    reply_text = ""
    try:
        response = _client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=768,
            system=system_prompt,
            messages=claude_messages,
        )
        reply_text = response.content[0].text.strip() if response.content else ""
    except Exception as exc:
        logger.error("chat_node: Claude reply generation failed: %s", exc)
        reply_text = "Thanks for your message! Let me get back to you with more details shortly."

    # ------------------------------------------------------------------
    # Signal detection via Claude tool_use
    # ------------------------------------------------------------------
    escalate = quick_escalate
    escalation_reason = ""
    viewing_interest = quick_viewing
    suggested_times: list[str] = []

    try:
        signal_response = _client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=512,
            system=(
                "You are an assistant that analyses real estate lead messages to detect "
                "buying intent signals, escalation triggers, and viewing interest."
            ),
            messages=[
                {
                    "role": "user",
                    "content": (
                        f"Lead name: {lead_name}\n"
                        f"Their latest message:\n{inbound}\n\n"
                        f"Conversation context (last exchange):\n"
                        f"{claude_messages[-3].get('content', '') if len(claude_messages) >= 3 else 'N/A'}"
                    ),
                }
            ],
            tools=[_DETECT_SIGNALS_TOOL],
            tool_choice={"type": "tool", "name": "detect_conversation_signals"},
        )

        tool_block = next(
            (b for b in signal_response.content if b.type == "tool_use"),
            None,
        )
        if tool_block:
            signals: dict = tool_block.input
            escalate = signals.get("escalate", escalate)
            escalation_reason = signals.get("escalation_reason", "")
            viewing_interest = signals.get("viewing_interest", viewing_interest)
            suggested_times = signals.get("suggested_viewing_times", [])

    except Exception as exc:
        logger.warning("chat_node: signal detection failed: %s", exc)

    # ------------------------------------------------------------------
    # Update conversation history in DB
    # ------------------------------------------------------------------
    _update_conversation_history(
        lead_id=lead_id,
        user_msg=inbound,
        assistant_msg=reply_text,
    )

    # Append viewing times to reply if viewing interest detected and times available
    if viewing_interest and suggested_times and not quick_viewing:
        times_str = "\n".join(f"• {t}" for t in suggested_times[:3])
        reply_text = f"{reply_text}\n\nI have the following slots available:\n{times_str}\n\nWhich works best for you?"

    summary = (
        f"[Chat] Reply drafted for {lead_name}. "
        f"Escalate: {escalate}. Viewing interest: {viewing_interest}. "
        f"Reason: {escalation_reason or 'N/A'}."
    )

    return {
        "kb_context": kb_context,
        "draft_reply": reply_text,
        "reply_sent": False,  # Sending is handled by a separate send step
        "escalate": escalate,
        "escalation_reason": escalation_reason,
        "viewing_booked": False,
        "messages": [{"role": "assistant", "content": summary}],
    }
