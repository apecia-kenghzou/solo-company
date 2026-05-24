"""Marketing LangGraph — plans, writes, illustrates, and schedules social media content."""
from __future__ import annotations

import logging

from langgraph.graph import StateGraph, END

from backend.agents.state import MarketingState
from backend.agents.nodes.strategist import strategist_node
from backend.agents.nodes.copywriter import copywriter_node
from backend.agents.nodes.image_gen import image_gen_node
from backend.agents.nodes.scheduler import scheduler_node

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Conditional edge: approval gate before scheduling
# ---------------------------------------------------------------------------

def approval_gate(state: MarketingState) -> str:
    """Decide whether to auto-schedule or hold for human approval.

    If approval_required is True: save draft and end (human reviews later).
    If False: proceed directly to scheduler.
    """
    if state.get("approval_required", False):
        return "hold_for_approval"
    return "schedule"


def save_draft_node(state: MarketingState) -> dict:
    """Save content draft for human approval and end the graph run.

    In production this writes/updates a ContentDraft DB record with
    status='pending_approval'. The human approves via the web UI,
    which then triggers the scheduler separately.
    """
    user_id = state.get("user_id", "")
    draft_id = state.get("draft_id")
    current_post = state.get("current_post", {})
    caption = state.get("caption", "")
    hashtags = state.get("hashtags", [])
    image_url = state.get("image_url", "")

    platform = current_post.get("platform", "unknown")
    content_type = current_post.get("content_type", "unknown")
    scheduled_at = current_post.get("scheduled_at", "")

    logger.info(
        "save_draft_node: saving draft for approval — user=%s platform=%s type=%s",
        user_id, platform, content_type,
    )

    # Stub DB write
    logger.info(
        "DB stub: ContentDraft upsert id=%s status=pending_approval platform=%s scheduled_at=%s",
        draft_id, platform, scheduled_at,
    )

    # In production: calls ORM ContentDraft.create_or_update(
    #   id=draft_id, user_id=user_id, status='pending_approval',
    #   platform=platform, caption=caption, hashtags=hashtags,
    #   image_url=image_url, scheduled_at=scheduled_at
    # )

    summary = (
        f"[Draft Saved] Content pending approval. "
        f"Platform: {platform}. Type: {content_type}. "
        f"Draft ID: {draft_id or 'new'}. "
        f"Caption: {len(caption)} chars. Image: {'yes' if image_url else 'no'}."
    )

    return {
        "messages": [{"role": "assistant", "content": summary}],
    }


# ---------------------------------------------------------------------------
# Graph builder
# ---------------------------------------------------------------------------

def build_marketing_graph() -> StateGraph:
    """Compile and return the Marketing StateGraph.

    Flow:
    strategist → copywriter → image_gen → [approval_gate]
                                               ├─ hold_for_approval → save_draft → END
                                               └─ schedule → scheduler → END
    """
    graph = StateGraph(MarketingState)

    # Register all nodes
    graph.add_node("strategist", strategist_node)
    graph.add_node("copywriter", copywriter_node)
    graph.add_node("image_gen", image_gen_node)
    graph.add_node("save_draft", save_draft_node)
    graph.add_node("scheduler", scheduler_node)

    # Entry point
    graph.set_entry_point("strategist")

    # Linear pipeline: strategist → copywriter → image_gen
    graph.add_edge("strategist", "copywriter")
    graph.add_edge("copywriter", "image_gen")

    # Approval gate after image generation
    graph.add_conditional_edges(
        "image_gen",
        approval_gate,
        {
            "hold_for_approval": "save_draft",
            "schedule": "scheduler",
        },
    )

    # Terminal nodes
    graph.add_edge("save_draft", END)
    graph.add_edge("scheduler", END)

    return graph.compile()


# Module-level compiled graph instance
marketing_graph = build_marketing_graph()
