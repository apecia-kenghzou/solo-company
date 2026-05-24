"""Market intelligence node — weekly property market research and reporting."""
from __future__ import annotations

import logging
from datetime import datetime, timezone

import anthropic

from backend.agents.state import ResearchState
from backend.config.settings import settings
from backend.knowledge.kb_writer import KBWriter

logger = logging.getLogger(__name__)

_client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
_kb = KBWriter()


# ---------------------------------------------------------------------------
# Tavily helper
# ---------------------------------------------------------------------------

def _tavily_search(query: str, max_results: int = 5) -> list[dict]:
    """Run a Tavily web search, with graceful fallback."""
    logger.info("Tavily market search: '%s'", query)
    try:
        from tavily import TavilyClient
        tc = TavilyClient(api_key=settings.tavily_api_key)
        results = tc.search(query=query, max_results=max_results)
        return results.get("results", [])
    except Exception as exc:
        logger.warning("Tavily search failed for '%s': %s", query, exc)
        return [{"title": f"Result for: {query}", "content": f"Placeholder content for: {query}", "url": ""}]


# ---------------------------------------------------------------------------
# Node
# ---------------------------------------------------------------------------

def market_intelligence_node(state: ResearchState) -> dict:
    """Run weekly market research and synthesise a structured market report.

    Searches for:
    - City/area property market trends this week
    - New property launches
    - Property price index for current month
    - Demand and transaction volume data
    - Economic news affecting property

    Synthesises into sections:
    - Price trend summary
    - Notable new launches
    - Demand insights
    - Agent talking points
    """
    user_id = state.get("user_id", "")
    query_context = state.get("query", "")

    # Infer city/area from query context or use generic terms
    location_hint = query_context.strip() if query_context else "property market"
    now = datetime.now(timezone.utc)
    month_year = now.strftime("%B %Y")
    this_week = now.strftime("week of %d %B %Y")

    # ------------------------------------------------------------------
    # Tavily searches
    # ------------------------------------------------------------------
    search_queries = [
        f"{location_hint} property market trends {this_week}",
        f"{location_hint} new property launches {month_year}",
        f"property price index {month_year}",
        f"{location_hint} residential property demand transactions {month_year}",
        f"real estate market outlook {month_year} buyers sellers",
        f"mortgage interest rates property affordability {month_year}",
    ]

    raw_results: list[dict] = list(state.get("raw_results", []))
    for sq in search_queries:
        results = _tavily_search(query=sq, max_results=4)
        raw_results.extend(results)

    # Deduplicate
    seen: set[str] = set()
    deduped: list[dict] = []
    for r in raw_results:
        url = r.get("url", r.get("title", ""))
        if url not in seen:
            seen.add(url)
            deduped.append(r)
    raw_results = deduped

    # ------------------------------------------------------------------
    # Format snippets for Claude synthesis
    # ------------------------------------------------------------------
    snippets = []
    for i, r in enumerate(raw_results[:20], 1):
        title = r.get("title", "No title")
        content = r.get("content", "")[:600]
        url = r.get("url", "")
        snippets.append(f"[Source {i}] {title}\n{content}\n{url}")

    research_text = "\n\n---\n\n".join(snippets) if snippets else "No search results available."

    # ------------------------------------------------------------------
    # Synthesise with Claude
    # ------------------------------------------------------------------
    synthesis_prompt = (
        f"You are a senior real estate market analyst. "
        f"Based on the research data below, write a weekly market intelligence report for real estate agents.\n\n"
        f"Context: {location_hint} — {this_week}\n\n"
        f"RESEARCH DATA:\n{research_text}\n\n"
        f"Structure your report with these EXACT sections:\n\n"
        f"## Price Trend Summary\n"
        f"(2-3 sentences on price movement, direction, and key data points)\n\n"
        f"## Notable New Launches\n"
        f"(2-4 bullet points on new or upcoming property projects — if none found, note market activity)\n\n"
        f"## Demand Insights\n"
        f"(2-3 sentences on buyer demand, transaction volumes, which buyer segments are active)\n\n"
        f"## Agent Talking Points\n"
        f"(4-5 numbered talking points — specific, actionable ways agents can use this week's data "
        f"in conversations with buyers and sellers)\n\n"
        f"Be specific and data-driven. Cite figures where available. "
        f"Keep each section concise but informative. "
        f"If data is limited, acknowledge it and provide directional insights."
    )

    formatted_report = ""
    try:
        synthesis_response = _client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=2048,
            system=(
                "You are a real estate market intelligence analyst. "
                "Write clear, factual market reports that are actionable for real estate agents."
            ),
            messages=[{"role": "user", "content": synthesis_prompt}],
        )
        formatted_report = synthesis_response.content[0].text.strip() if synthesis_response.content else ""
    except Exception as exc:
        logger.error("market_intelligence_node: synthesis failed: %s", exc)
        formatted_report = (
            f"# Weekly Market Report — {this_week}\n\n"
            f"## Price Trend Summary\nMarket data synthesis unavailable this week.\n\n"
            f"## Notable New Launches\nNo launch data compiled.\n\n"
            f"## Demand Insights\nDemand data synthesis unavailable.\n\n"
            f"## Agent Talking Points\n"
            f"1. Focus on fundamentals — buyers are still active.\n"
            f"2. Emphasise long-term value over short-term fluctuations.\n"
            f"3. Highlight any unique selling points of your listings.\n"
            f"4. Stay responsive — market conditions change quickly."
        )

    # Add header if not present
    if not formatted_report.startswith("#"):
        formatted_report = f"# Weekly Market Report — {this_week}\n\n{formatted_report}"

    # ------------------------------------------------------------------
    # Write to KB
    # ------------------------------------------------------------------
    kb_written = False
    report_date = now.strftime("%Y-%m-%d")
    try:
        import asyncio
        report_payload = {
            "content": formatted_report,
            "date": report_date,
            "price_trend": "",  # Claude already embedded these in formatted_report
            "agent_talking_points": "",
        }
        asyncio.run(_kb.write_market_report(user_id=user_id, report=report_payload))
        kb_written = True
        logger.info("market_intelligence_node: market report written to KB for %s", report_date)
    except Exception as exc:
        logger.error("market_intelligence_node: KB write failed: %s", exc)

    summary = (
        f"[Market Intelligence] Report compiled for {this_week}. "
        f"{len(raw_results)} sources reviewed. KB written: {kb_written}."
    )

    return {
        "raw_results": raw_results,
        "formatted_report": formatted_report,
        "kb_written": kb_written,
        "messages": [{"role": "assistant", "content": summary}],
    }
