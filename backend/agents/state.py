"""TypedDict state classes for all LangGraph agents."""
from __future__ import annotations

import operator
from typing import Annotated, List, Optional, TypedDict


class FrontDeskState(TypedDict):
    user_id: str
    lead_id: Optional[str]
    listing_id: Optional[str]
    inbound_message: str
    channel: str  # email | whatsapp | website
    lead_data: dict
    classification: str  # inquiry | question | spam | complaint
    kb_context: str
    draft_reply: str
    reply_sent: bool
    escalate: bool
    escalation_reason: str
    follow_up_scheduled: bool
    viewing_booked: bool
    messages: Annotated[list, operator.add]  # LangGraph messages


class ResearchState(TypedDict):
    user_id: str
    listing_id: Optional[str]
    research_type: str  # property | market | social_trend | competitor
    query: str
    raw_results: list
    formatted_report: str
    kb_written: bool
    messages: Annotated[list, operator.add]


class MarketingState(TypedDict):
    user_id: str
    listing_id: Optional[str]
    trend_data: list
    content_plan: list
    current_post: dict
    caption: str
    image_url: Optional[str]
    hashtags: list
    scheduled: bool
    approval_required: bool
    draft_id: Optional[str]
    messages: Annotated[list, operator.add]
