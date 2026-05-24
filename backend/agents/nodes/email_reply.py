"""Email reply node — drafts and optionally sends replies to inbound leads."""
from __future__ import annotations

import logging
from typing import Optional

import anthropic

from backend.agents.state import FrontDeskState
from backend.config.settings import settings
from backend.knowledge.kb_writer import KBWriter

logger = logging.getLogger(__name__)

_client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
_kb = KBWriter()


def _get_listing_context(user_id: str, listing_id: Optional[str], lead_data: dict) -> str:
    """Build a context query string from available lead data."""
    parts = []
    if listing_id:
        parts.append(f"listing {listing_id}")
    if lead_data.get("property_interest"):
        parts.append(lead_data["property_interest"])
    if not parts:
        parts.append("property listing details")
    return " ".join(parts)


def _send_via_gmail(to_email: str, subject: str, body: str) -> bool:
    """Stub for Gmail send — real implementation wires to Gmail API tool."""
    logger.info("Gmail send stub: to=%s subject=%s", to_email, subject)
    # In production this calls backend.tools.gmail_tool.send_email(...)
    return True


def _save_content_draft(user_id: str, lead_id: Optional[str], reply: str) -> str:
    """Stub for saving a pending-approval ContentDraft to DB."""
    logger.info("ContentDraft stub: user=%s lead=%s", user_id, lead_id)
    # In production this calls the ORM ContentDraft model and saves to DB
    return "draft_placeholder_id"


def email_reply_node(state: FrontDeskState) -> dict:
    """Draft and (conditionally) send an email reply to an inbound lead.

    - Spam messages are dropped immediately with no reply.
    - Hot/warm leads get a draft saved for human approval.
    - Cold inquiries are sent automatically via Gmail.
    """
    classification = state.get("classification", "inquiry")
    user_id = state.get("user_id", "")
    lead_id = state.get("lead_id")
    listing_id = state.get("listing_id")
    lead_data = state.get("lead_data", {})
    inbound = state.get("inbound_message", "")

    # ------------------------------------------------------------------
    # Early exit for spam
    # ------------------------------------------------------------------
    if classification == "spam":
        logger.info("email_reply_node: classification=spam, skipping reply")
        return {
            "draft_reply": "",
            "reply_sent": False,
            "escalate": False,
            "messages": [{"role": "assistant", "content": "[Email Reply] Skipped — message classified as spam."}],
        }

    # ------------------------------------------------------------------
    # Retrieve KB context
    # ------------------------------------------------------------------
    context_query = _get_listing_context(user_id, listing_id, lead_data)
    kb_context = ""
    try:
        import asyncio
        kb_context = asyncio.run(_kb.query_kb(user_id=user_id, query=context_query, top_k=6))
    except Exception as exc:
        logger.warning("email_reply_node: KB query failed: %s", exc)
        kb_context = state.get("kb_context", "")

    # ------------------------------------------------------------------
    # Retrieve brand voice
    # ------------------------------------------------------------------
    brand_voice = ""
    try:
        import asyncio
        brand_voice = asyncio.run(_kb.query_kb(user_id=user_id, query="brand voice communication style", kb_type="company_profile", top_k=2))
    except Exception:
        pass

    # ------------------------------------------------------------------
    # Build system prompt
    # ------------------------------------------------------------------
    lead_name = lead_data.get("name") or "the enquirer"
    urgency = lead_data.get("urgency", "low")

    system_prompt = (
        "You are a professional real estate assistant drafting an email reply on behalf of a real estate agent.\n\n"
        "BRAND VOICE:\n"
        f"{brand_voice or 'Warm, professional, and knowledgeable. Use clear language and avoid jargon.'}\n\n"
        "PROPERTY / LISTING CONTEXT:\n"
        f"{kb_context or 'No specific listing context available.'}\n\n"
        "GUIDELINES:\n"
        "- Address the lead by name if available.\n"
        "- Answer their specific question or inquiry directly.\n"
        "- Highlight 1-2 relevant property features if they mentioned a property.\n"
        "- Include a clear CTA (e.g. 'I'd love to arrange a viewing' or 'Reply to this email to learn more').\n"
        "- Keep the email concise — 3-5 short paragraphs maximum.\n"
        "- Do NOT include a subject line — only the email body.\n"
        "- Sign off with the agent's name if available in the brand context, otherwise use 'Your Property Consultant'."
    )

    user_message = (
        f"Draft a warm, professional email reply to the following inbound inquiry.\n\n"
        f"Lead name: {lead_name}\n"
        f"Urgency: {urgency}\n"
        f"Classification: {classification}\n"
        f"Their message:\n{inbound}"
    )

    # ------------------------------------------------------------------
    # Generate draft with Claude
    # ------------------------------------------------------------------
    draft_reply = ""
    try:
        response = _client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=1024,
            system=system_prompt,
            messages=[{"role": "user", "content": user_message}],
        )
        draft_reply = response.content[0].text.strip() if response.content else ""
    except Exception as exc:
        logger.error("email_reply_node: Claude call failed: %s", exc)
        draft_reply = (
            f"Dear {lead_name},\n\n"
            "Thank you for your inquiry. We'll be in touch shortly with more information.\n\n"
            "Best regards,\nYour Property Consultant"
        )

    # ------------------------------------------------------------------
    # Decide: auto-send vs. save for approval
    # ------------------------------------------------------------------
    is_warm_or_hot = urgency in ("medium", "high") or classification in ("inquiry",)
    reply_sent = False
    draft_id = None
    approval_required = False

    if is_warm_or_hot:
        # Save for human approval
        approval_required = True
        draft_id = _save_content_draft(user_id=user_id, lead_id=lead_id, reply=draft_reply)
        logger.info("email_reply_node: draft saved for approval (id=%s)", draft_id)
    else:
        # Auto-send cold inquiry
        to_email = lead_data.get("email", "")
        if to_email:
            reply_sent = _send_via_gmail(
                to_email=to_email,
                subject="Re: Your Property Inquiry",
                body=draft_reply,
            )
        else:
            logger.warning("email_reply_node: no email address to send to")

    summary = (
        f"[Email Reply] Draft created for lead '{lead_name}'. "
        f"Approval required: {approval_required}. Sent: {reply_sent}."
    )

    return {
        "kb_context": kb_context,
        "draft_reply": draft_reply,
        "reply_sent": reply_sent,
        "escalate": False,
        "escalation_reason": "",
        "messages": [{"role": "assistant", "content": summary}],
    }
