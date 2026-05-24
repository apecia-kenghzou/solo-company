"""Research LangGraph — routes research tasks to the appropriate specialist nodes."""
from __future__ import annotations

import logging

from langgraph.graph import StateGraph, END

from backend.agents.state import ResearchState
from backend.agents.nodes.property_research import property_research_node
from backend.agents.nodes.market_intelligence import market_intelligence_node
from backend.agents.nodes.social_trend import social_trend_node

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# KB writer finalise node
# ---------------------------------------------------------------------------

def kb_writer_finalize_node(state: ResearchState) -> dict:
    """Finalise KB write step — logs completion and returns state unchanged.

    Each research node writes to KB directly. This node acts as a terminal
    checkpoint, confirming the write status and surfacing any warnings.
    """
    kb_written = state.get("kb_written", False)
    research_type = state.get("research_type", "unknown")
    report_preview = state.get("formatted_report", "")[:200]

    if not kb_written:
        logger.warning(
            "kb_writer_finalize: KB was NOT written for research_type=%s", research_type
        )
        message_content = (
            f"[KB Finalize] WARNING — KB write did not complete for research_type={research_type}. "
            f"Report preview: {report_preview}..."
        )
    else:
        logger.info(
            "kb_writer_finalize: KB write confirmed for research_type=%s", research_type
        )
        message_content = (
            f"[KB Finalize] Research complete and stored in KB. "
            f"Type: {research_type}. "
            f"Report preview: {report_preview}..."
        )

    return {
        "messages": [{"role": "assistant", "content": message_content}],
    }


# ---------------------------------------------------------------------------
# Conditional routing
# ---------------------------------------------------------------------------

def route_research_type(state: ResearchState) -> str:
    """Route to the appropriate research node based on research_type."""
    research_type = state.get("research_type", "").lower().strip()

    routing_map = {
        "property": "property_research",
        "property_research": "property_research",
        "competitor": "property_research",  # competitor analysis uses property research node
        "market": "market_intelligence",
        "market_intelligence": "market_intelligence",
        "market_report": "market_intelligence",
        "social_trend": "social_trend",
        "social": "social_trend",
        "trend": "social_trend",
        "trends": "social_trend",
    }

    destination = routing_map.get(research_type)
    if not destination:
        logger.warning(
            "route_research_type: unknown research_type='%s', defaulting to market_intelligence",
            research_type,
        )
        destination = "market_intelligence"

    return destination


# ---------------------------------------------------------------------------
# Graph builder
# ---------------------------------------------------------------------------

def build_research_graph() -> StateGraph:
    """Compile and return the Research StateGraph."""
    graph = StateGraph(ResearchState)

    # Register nodes
    graph.add_node("property_research", property_research_node)
    graph.add_node("market_intelligence", market_intelligence_node)
    graph.add_node("social_trend", social_trend_node)
    graph.add_node("kb_writer_finalize", kb_writer_finalize_node)

    # Entry point — route based on research_type
    graph.set_entry_point("router")

    # Add a router node that immediately routes to the correct specialist
    # LangGraph requires all edges to be declared, so we use a pass-through router node
    def _router_node(state: ResearchState) -> dict:
        """No-op router node — routing handled by conditional edge."""
        return {}

    graph.add_node("router", _router_node)

    graph.add_conditional_edges(
        "router",
        route_research_type,
        {
            "property_research": "property_research",
            "market_intelligence": "market_intelligence",
            "social_trend": "social_trend",
        },
    )

    # All research nodes flow to the KB finalizer
    graph.add_edge("property_research", "kb_writer_finalize")
    graph.add_edge("market_intelligence", "kb_writer_finalize")
    graph.add_edge("social_trend", "kb_writer_finalize")

    # KB finalizer → END
    graph.add_edge("kb_writer_finalize", END)

    return graph.compile()


# Module-level compiled graph instance
research_graph = build_research_graph()
