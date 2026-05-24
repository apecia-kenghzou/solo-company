"""Intake node — classifies inbound messages and extracts lead data."""
from __future__ import annotations

import json
import logging

import anthropic

from backend.agents.state import FrontDeskState
from backend.config.settings import settings

logger = logging.getLogger(__name__)

_client = anthropic.Anthropic(api_key=settings.anthropic_api_key)

_EXTRACT_LEAD_TOOL = {
    "name": "extract_lead_data",
    "description": (
        "Classify the inbound message and extract all available lead information."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "classification": {
                "type": "string",
                "enum": ["inquiry", "question", "spam", "complaint"],
                "description": "Message classification.",
            },
            "name": {
                "type": "string",
                "description": "Full name of the sender, if mentioned.",
            },
            "email": {
                "type": "string",
                "description": "Email address of the sender, if mentioned.",
            },
            "phone": {
                "type": "string",
                "description": "Phone/WhatsApp number of the sender, if mentioned.",
            },
            "property_interest": {
                "type": "string",
                "description": "Property type, location, or specific project they are interested in.",
            },
            "budget_min": {
                "type": "string",
                "description": "Minimum budget mentioned (number or text).",
            },
            "budget_max": {
                "type": "string",
                "description": "Maximum budget mentioned (number or text).",
            },
            "timeline": {
                "type": "string",
                "description": "Intended purchase / move-in timeline (e.g. '3 months', 'ASAP').",
            },
            "urgency": {
                "type": "string",
                "enum": ["low", "medium", "high"],
                "description": "Overall urgency level inferred from the message.",
            },
            "listing_id": {
                "type": "string",
                "description": "Specific listing ID or project name mentioned, if any.",
            },
            "notes": {
                "type": "string",
                "description": "Any other relevant notes extracted from the message.",
            },
        },
        "required": ["classification", "urgency"],
    },
}


def intake_node(state: FrontDeskState) -> dict:
    """Classify the inbound message and extract lead information.

    This node is intentionally synchronous so LangGraph can call it directly
    without an async executor.  The Anthropic SDK call is made with the sync
    client to keep the graph runner simple.
    """
    inbound = state.get("inbound_message", "")
    channel = state.get("channel", "email")

    logger.info("intake_node: classifying message from channel=%s", channel)

    try:
        response = _client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=1024,
            system=(
                "You are an AI assistant for a real estate business. "
                "Classify this inbound message and extract lead information. "
                "Be accurate — only extract information explicitly stated or strongly implied."
            ),
            messages=[
                {
                    "role": "user",
                    "content": (
                        f"Channel: {channel}\n\n"
                        f"Inbound message:\n{inbound}"
                    ),
                }
            ],
            tools=[_EXTRACT_LEAD_TOOL],
            tool_choice={"type": "tool", "name": "extract_lead_data"},
        )

        # Extract tool use result
        tool_result = next(
            (block for block in response.content if block.type == "tool_use"),
            None,
        )

        if tool_result:
            extracted: dict = tool_result.input
        else:
            logger.warning("intake_node: no tool_use block in response, using defaults")
            extracted = {"classification": "inquiry", "urgency": "low"}

    except Exception as exc:
        logger.error("intake_node: Anthropic call failed: %s", exc)
        extracted = {"classification": "inquiry", "urgency": "low"}

    classification = extracted.get("classification", "inquiry")
    listing_id = extracted.get("listing_id") or state.get("listing_id")

    lead_data = {
        "name": extracted.get("name", ""),
        "email": extracted.get("email", ""),
        "phone": extracted.get("phone", ""),
        "property_interest": extracted.get("property_interest", ""),
        "budget_min": extracted.get("budget_min", ""),
        "budget_max": extracted.get("budget_max", ""),
        "timeline": extracted.get("timeline", ""),
        "urgency": extracted.get("urgency", "low"),
        "notes": extracted.get("notes", ""),
        "channel": channel,
    }

    classification_summary = (
        f"[Intake] Classification: {classification}. "
        f"Urgency: {lead_data['urgency']}. "
        f"Name: {lead_data['name'] or 'unknown'}. "
        f"Interest: {lead_data['property_interest'] or 'not specified'}."
    )

    return {
        "classification": classification,
        "listing_id": listing_id,
        "lead_data": lead_data,
        "messages": [{"role": "assistant", "content": classification_summary}],
    }
