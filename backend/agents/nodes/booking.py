"""Booking node — schedules property viewings via Google Calendar."""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Optional

import anthropic

from backend.agents.state import FrontDeskState
from backend.config.settings import settings

logger = logging.getLogger(__name__)

_client = anthropic.Anthropic(api_key=settings.anthropic_api_key)


# ---------------------------------------------------------------------------
# Tool stubs (replaced by real CalendarTool integration in production)
# ---------------------------------------------------------------------------

def _get_available_slots(user_id: str, days_ahead: int = 7) -> list[dict]:
    """Stub — returns mock available viewing slots from Google Calendar."""
    logger.info("CalendarTool stub: get_available_slots user=%s days=%d", user_id, days_ahead)
    now = datetime.now(timezone.utc)
    slots = []
    # Generate mock slots: 10am and 2pm on the next 4 weekdays
    offset = 1
    while len(slots) < 6:
        candidate = now + timedelta(days=offset)
        # Skip weekends (5=Sat, 6=Sun)
        if candidate.weekday() < 5:
            slots.append({
                "start": candidate.replace(hour=10, minute=0, second=0, microsecond=0).isoformat(),
                "label": candidate.strftime("%A %d %b") + " at 10:00 AM",
            })
            slots.append({
                "start": candidate.replace(hour=14, minute=0, second=0, microsecond=0).isoformat(),
                "label": candidate.strftime("%A %d %b") + " at 2:00 PM",
            })
        offset += 1
        if offset > 30:
            break
    return slots[:6]


def _create_calendar_event(
    user_id: str,
    lead_name: str,
    lead_phone: str,
    listing_name: str,
    slot_start: str,
    listing_address: str,
) -> Optional[str]:
    """Stub — creates a Google Calendar event and returns the event ID."""
    logger.info(
        "CalendarTool stub: create_event user=%s lead=%s slot=%s",
        user_id, lead_name, slot_start,
    )
    # In production: calls backend.tools.calendar_tool.create_event(...)
    return f"evt_{lead_name.replace(' ', '_').lower()}_{slot_start[:10]}"


def _send_whatsapp(phone: str, message: str) -> bool:
    """Stub for WhatsApp confirmation send."""
    logger.info("WhatsApp stub: send to %s", phone)
    return True


def _update_lead_status(lead_id: Optional[str], status: str) -> None:
    """Stub — updates lead.status in DB."""
    logger.info("DB stub: update lead %s status=%s", lead_id, status)


# ---------------------------------------------------------------------------
# Node
# ---------------------------------------------------------------------------

def booking_node(state: FrontDeskState) -> dict:
    """Schedule a property viewing for a lead who has expressed interest.

    Flow:
    1. Fetch available calendar slots.
    2. Use Claude to compose a natural availability message.
    3. Send slot options to lead via WhatsApp.
    4. When a slot is confirmed (simulated here), create Calendar event.
    5. Send confirmation message.
    6. Update lead status to 'viewing_scheduled'.
    """
    user_id = state.get("user_id", "")
    lead_id = state.get("lead_id")
    lead_data = state.get("lead_data", {})
    listing_id = state.get("listing_id")
    draft_reply = state.get("draft_reply", "")

    lead_name = lead_data.get("name") or "there"
    phone = lead_data.get("phone", "")
    property_interest = lead_data.get("property_interest", "the property")

    # ------------------------------------------------------------------
    # Get available slots
    # ------------------------------------------------------------------
    available_slots = _get_available_slots(user_id=user_id, days_ahead=7)

    if not available_slots:
        logger.warning("booking_node: no available slots found")
        return {
            "viewing_booked": False,
            "messages": [{"role": "assistant", "content": "[Booking] No available slots found."}],
        }

    # ------------------------------------------------------------------
    # Format slots for display
    # ------------------------------------------------------------------
    slot_labels = [s["label"] for s in available_slots[:4]]

    # ------------------------------------------------------------------
    # Compose natural availability message with Claude
    # ------------------------------------------------------------------
    system_prompt = (
        "You are a real estate agent sending a WhatsApp message to confirm viewing availability. "
        "Be warm and professional. Keep it conversational and concise — WhatsApp tone. "
        "Present the viewing options clearly. End with a question asking which slot they prefer."
    )

    slots_text = "\n".join(f"• {label}" for label in slot_labels)
    user_prompt = (
        f"Lead name: {lead_name}\n"
        f"Property they're interested in: {property_interest}\n\n"
        f"Available viewing slots:\n{slots_text}\n\n"
        f"Write a WhatsApp message presenting these viewing options. "
        f"Mention the property briefly. Ask which slot works best."
    )

    availability_message = ""
    try:
        response = _client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=512,
            system=system_prompt,
            messages=[{"role": "user", "content": user_prompt}],
        )
        availability_message = response.content[0].text.strip() if response.content else ""
    except Exception as exc:
        logger.error("booking_node: Claude availability message failed: %s", exc)
        availability_message = (
            f"Hi {lead_name}! Great news — I have some viewing slots available for {property_interest}.\n\n"
            f"{slots_text}\n\nWhich slot works best for you?"
        )

    # ------------------------------------------------------------------
    # Send availability message via WhatsApp
    # ------------------------------------------------------------------
    if phone:
        _send_whatsapp(phone=phone, message=availability_message)
    else:
        logger.warning("booking_node: no phone number available for lead")

    # ------------------------------------------------------------------
    # Simulate slot confirmation (in production, waits for lead reply webhook)
    # For graph execution purposes, we confirm the first available slot.
    # ------------------------------------------------------------------
    confirmed_slot = available_slots[0]
    confirmed_label = confirmed_slot["label"]
    confirmed_start = confirmed_slot["start"]

    # Create calendar event
    event_id = _create_calendar_event(
        user_id=user_id,
        lead_name=lead_name,
        lead_phone=phone,
        listing_name=property_interest,
        slot_start=confirmed_start,
        listing_address=lead_data.get("address", "property address TBC"),
    )

    # ------------------------------------------------------------------
    # Send confirmation message
    # ------------------------------------------------------------------
    confirmation_message = ""
    try:
        confirm_prompt = (
            f"Send a short WhatsApp confirmation message for a property viewing.\n\n"
            f"Lead name: {lead_name}\n"
            f"Property: {property_interest}\n"
            f"Confirmed slot: {confirmed_label}\n\n"
            f"Keep it to 2-3 sentences. Include: confirmed date/time, what to expect, "
            f"and let them know to message if they need to reschedule."
        )
        confirm_response = _client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=256,
            system="You are a real estate agent sending a WhatsApp confirmation. Be warm and brief.",
            messages=[{"role": "user", "content": confirm_prompt}],
        )
        confirmation_message = confirm_response.content[0].text.strip() if confirm_response.content else ""
    except Exception as exc:
        logger.error("booking_node: confirmation message failed: %s", exc)
        confirmation_message = (
            f"Great, {lead_name}! Your viewing for {property_interest} is confirmed for {confirmed_label}. "
            "See you there! Message me if anything changes."
        )

    if phone and confirmation_message:
        _send_whatsapp(phone=phone, message=confirmation_message)

    # ------------------------------------------------------------------
    # Update lead status in DB
    # ------------------------------------------------------------------
    _update_lead_status(lead_id=lead_id, status="viewing_scheduled")

    summary = (
        f"[Booking] Viewing scheduled for {lead_name} — {confirmed_label}. "
        f"Calendar event ID: {event_id}. Lead status updated to 'viewing_scheduled'."
    )

    return {
        "viewing_booked": True,
        "draft_reply": confirmation_message,
        "reply_sent": True,
        "escalate": False,
        "messages": [{"role": "assistant", "content": summary}],
    }
