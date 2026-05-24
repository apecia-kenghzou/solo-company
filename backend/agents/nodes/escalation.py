"""Escalation node — notifies the human owner about hot leads requiring attention."""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Optional

import anthropic

from backend.agents.state import FrontDeskState
from backend.config.settings import settings

logger = logging.getLogger(__name__)

_client = anthropic.Anthropic(api_key=settings.anthropic_api_key)


# ---------------------------------------------------------------------------
# Stubs for notification and DB operations
# ---------------------------------------------------------------------------

def _send_push_notification(user_id: str, title: str, body: str) -> None:
    """Stub — sends push notification to owner's device."""
    logger.info("PushNotif stub: user=%s title=%s", user_id, title)
    # In production: calls FCM or APNS via backend notification service


def _send_email_notification(user_id: str, subject: str, html_body: str) -> None:
    """Stub — emails escalation brief to owner."""
    logger.info("Email notif stub: user=%s subject=%s", user_id, subject)
    # In production: calls Gmail tool or SendGrid


def _update_lead_temperature(lead_id: Optional[str], temperature: str) -> None:
    """Stub — updates lead.temperature in DB."""
    logger.info("DB stub: update lead %s temperature=%s", lead_id, temperature)


def _update_lead_status(lead_id: Optional[str], status: str) -> None:
    """Stub — updates lead.status in DB (only if not already at a higher status)."""
    logger.info("DB stub: update lead %s status=%s", lead_id, status)


def _log_escalation_event(lead_id: Optional[str], user_id: str, reason: str, brief: str) -> None:
    """Stub — persists escalation event to DB for audit trail."""
    logger.info("DB stub: log escalation for lead %s user %s", lead_id, user_id)


# ---------------------------------------------------------------------------
# Node
# ---------------------------------------------------------------------------

def escalation_node(state: FrontDeskState) -> dict:
    """Compile a context brief and notify the owner about a hot lead.

    This node fires when state["escalate"] == True.

    Steps:
    1. Compile a concise brief: lead info, conversation summary, escalation reason.
    2. Use Claude to generate suggested talking points for the owner.
    3. Send push notification + email with the brief.
    4. Update lead temperature to 'hot' and status to 'hot' in DB.
    5. Log the escalation event.
    """
    if not state.get("escalate"):
        # Safety guard — should not be called unless escalate is True
        return {"messages": [{"role": "assistant", "content": "[Escalation] Not triggered (escalate=False)."}]}

    user_id = state.get("user_id", "")
    lead_id = state.get("lead_id")
    lead_data = state.get("lead_data", {})
    escalation_reason = state.get("escalation_reason", "Hot lead signal detected.")
    inbound = state.get("inbound_message", "")
    draft_reply = state.get("draft_reply", "")
    listing_id = state.get("listing_id")
    channel = state.get("channel", "unknown")

    lead_name = lead_data.get("name") or "Unknown Lead"
    lead_email = lead_data.get("email", "N/A")
    lead_phone = lead_data.get("phone", "N/A")
    budget = f"{lead_data.get('budget_min', '?')} - {lead_data.get('budget_max', '?')}"
    timeline = lead_data.get("timeline", "Not specified")
    urgency = lead_data.get("urgency", "unknown")
    property_interest = lead_data.get("property_interest", "Not specified")

    # ------------------------------------------------------------------
    # Build context summary for Claude
    # ------------------------------------------------------------------
    conversation_history = lead_data.get("conversation_history", [])
    if isinstance(conversation_history, list):
        recent_exchanges = conversation_history[-6:]  # last 3 exchanges
        history_text = "\n".join(
            f"{e.get('role', '?').upper()}: {e.get('content', '')}"
            for e in recent_exchanges
        )
    else:
        history_text = "No conversation history available."

    # ------------------------------------------------------------------
    # Generate talking points with Claude
    # ------------------------------------------------------------------
    talking_points_prompt = (
        f"A real estate lead requires immediate human follow-up. "
        f"Generate 3-5 concise, actionable talking points for the agent to use when contacting this lead.\n\n"
        f"Lead: {lead_name}\n"
        f"Property interest: {property_interest}\n"
        f"Budget: {budget}\n"
        f"Timeline: {timeline}\n"
        f"Urgency: {urgency}\n"
        f"Channel: {channel}\n"
        f"Escalation reason: {escalation_reason}\n\n"
        f"Latest message from lead:\n{inbound}\n\n"
        f"Recent conversation:\n{history_text}"
    )

    talking_points = ""
    try:
        tp_response = _client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=512,
            system=(
                "You are a senior real estate sales coach. "
                "Generate practical, specific talking points to help the agent convert this lead. "
                "Format as a numbered list. Be direct and actionable."
            ),
            messages=[{"role": "user", "content": talking_points_prompt}],
        )
        talking_points = tp_response.content[0].text.strip() if tp_response.content else ""
    except Exception as exc:
        logger.error("escalation_node: Claude talking points failed: %s", exc)
        talking_points = (
            "1. Reference their specific property interest and budget directly.\n"
            "2. Acknowledge urgency and offer to move quickly.\n"
            "3. Propose a viewing or call today/tomorrow.\n"
            "4. Have relevant listing details ready.\n"
            "5. Listen first — understand their timeline before pitching."
        )

    # ------------------------------------------------------------------
    # Assemble escalation brief
    # ------------------------------------------------------------------
    now_str = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    brief_text = f"""
ESCALATION BRIEF — {now_str}
{'=' * 50}

LEAD INFORMATION
----------------
Name:           {lead_name}
Email:          {lead_email}
Phone:          {lead_phone}
Channel:        {channel}
Urgency:        {urgency}

PROPERTY INTEREST
-----------------
Interest:       {property_interest}
Budget:         {budget}
Timeline:       {timeline}
Listing ID:     {listing_id or 'N/A'}

ESCALATION TRIGGER
------------------
Reason:         {escalation_reason}

LATEST MESSAGE FROM LEAD
------------------------
{inbound}

RECENT CONVERSATION
-------------------
{history_text}

SUGGESTED TALKING POINTS
-------------------------
{talking_points}

{'=' * 50}
Action required: Contact this lead ASAP on {lead_phone or lead_email}.
""".strip()

    # ------------------------------------------------------------------
    # Send notifications
    # ------------------------------------------------------------------
    notif_title = f"Hot Lead Alert: {lead_name}"
    notif_body = f"Reason: {escalation_reason}. Budget: {budget}. Contact: {lead_phone or lead_email}."

    _send_push_notification(user_id=user_id, title=notif_title, body=notif_body)
    _send_email_notification(
        user_id=user_id,
        subject=f"[Hot Lead] {lead_name} — Action Required",
        html_body=f"<pre>{brief_text}</pre>",
    )

    # ------------------------------------------------------------------
    # Update lead in DB
    # ------------------------------------------------------------------
    _update_lead_temperature(lead_id=lead_id, temperature="hot")
    _update_lead_status(lead_id=lead_id, status="hot")
    _log_escalation_event(
        lead_id=lead_id,
        user_id=user_id,
        reason=escalation_reason,
        brief=brief_text,
    )

    logger.info(
        "escalation_node: escalated lead %s for user %s — reason: %s",
        lead_id, user_id, escalation_reason,
    )

    summary = (
        f"[Escalation] Brief compiled and sent for lead '{lead_name}'. "
        f"Lead temperature set to 'hot'. "
        f"Reason: {escalation_reason}"
    )

    return {
        "escalation_reason": escalation_reason,
        "messages": [{"role": "assistant", "content": summary}],
    }
