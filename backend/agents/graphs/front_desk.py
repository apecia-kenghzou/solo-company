"""Front Desk LangGraph — routes inbound leads through intake, reply, chat, booking, escalation."""
from __future__ import annotations

from langgraph.graph import StateGraph, END

from backend.agents.state import FrontDeskState
from backend.agents.nodes.intake import intake_node
from backend.agents.nodes.email_reply import email_reply_node
from backend.agents.nodes.whatsapp import whatsapp_followup_node
from backend.agents.nodes.chat import chat_node
from backend.agents.nodes.booking import booking_node
from backend.agents.nodes.escalation import escalation_node


# ---------------------------------------------------------------------------
# Conditional edge functions
# ---------------------------------------------------------------------------

def should_escalate(state: FrontDeskState) -> str:
    """Route to escalation if flagged, otherwise end."""
    if state.get("escalate"):
        return "escalate"
    if state.get("viewing_booked"):
        return "end"
    return "end"


def should_book_viewing(state: FrontDeskState) -> str:
    """After chat, check if lead expressed viewing interest."""
    draft = state.get("draft_reply", "").lower()
    # Check for viewing intent signals in draft reply or explicit escalate
    viewing_signals = [
        "viewing", "visit", "show you", "inspect", "walk through",
        "which slot", "available slots", "book a time",
    ]
    if any(signal in draft for signal in viewing_signals):
        return "booking"
    return "check_escalate"


def route_inbound(state: FrontDeskState) -> str:
    """Route inbound message to correct first handler.

    - WhatsApp + existing lead_id → chat (continuing conversation)
    - Everything else → email_reply (new lead or email channel)
    """
    channel = state.get("channel", "email")
    lead_id = state.get("lead_id")
    classification = state.get("classification", "inquiry")

    # Spam: still route to email_reply which handles the early-exit
    if classification == "spam":
        return "email_reply"

    if channel == "whatsapp" and lead_id:
        return "chat"

    # New WhatsApp lead or email inquiry → email reply first
    return "email_reply"


def check_escalate_or_end(state: FrontDeskState) -> str:
    """After chat's check_escalate branch — decide escalation vs end."""
    if state.get("escalate"):
        return "escalate"
    return "end"


# ---------------------------------------------------------------------------
# Graph builder
# ---------------------------------------------------------------------------

def build_front_desk_graph() -> StateGraph:
    """Compile and return the Front Desk StateGraph."""
    graph = StateGraph(FrontDeskState)

    # Register nodes
    graph.add_node("intake", intake_node)
    graph.add_node("email_reply", email_reply_node)
    graph.add_node("chat", chat_node)
    graph.add_node("booking", booking_node)
    graph.add_node("escalation", escalation_node)
    graph.add_node("whatsapp_followup", whatsapp_followup_node)

    # Entry point
    graph.set_entry_point("intake")

    # Intake → route based on channel / lead context
    graph.add_conditional_edges(
        "intake",
        route_inbound,
        {
            "email_reply": "email_reply",
            "chat": "chat",
        },
    )

    # Email reply → escalate if hot signal, else end
    graph.add_conditional_edges(
        "email_reply",
        should_escalate,
        {
            "escalate": "escalation",
            "end": END,
        },
    )

    # Chat → booking if viewing interest, else check escalation
    graph.add_conditional_edges(
        "chat",
        should_book_viewing,
        {
            "booking": "booking",
            "check_escalate": "escalation",
        },
    )

    # Booking → escalate if offer intent during booking, else end
    graph.add_conditional_edges(
        "booking",
        should_escalate,
        {
            "escalate": "escalation",
            "end": END,
        },
    )

    # Terminal nodes → END
    graph.add_edge("escalation", END)
    graph.add_edge("whatsapp_followup", END)

    return graph.compile()


# Module-level compiled graph instance
front_desk_graph = build_front_desk_graph()
