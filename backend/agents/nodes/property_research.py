"""Property research node — researches a listing and writes a showing brief to KB."""
from __future__ import annotations

import json
import logging
from typing import Optional

import anthropic

from backend.agents.state import ResearchState
from backend.config.settings import settings
from backend.knowledge.kb_writer import KBWriter

logger = logging.getLogger(__name__)

_client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
_kb = KBWriter()


# ---------------------------------------------------------------------------
# Tavily stub
# ---------------------------------------------------------------------------

def _tavily_search(query: str, max_results: int = 5) -> list[dict]:
    """Stub for Tavily search — returns mock results in production structure."""
    logger.info("Tavily stub: query='%s'", query)
    try:
        from tavily import TavilyClient
        tc = TavilyClient(api_key=settings.tavily_api_key)
        results = tc.search(query=query, max_results=max_results)
        return results.get("results", [])
    except Exception as exc:
        logger.warning("Tavily search failed for '%s': %s", query, exc)
        return [{"title": f"Result for: {query}", "content": f"Placeholder research content for: {query}", "url": ""}]


# ---------------------------------------------------------------------------
# Node
# ---------------------------------------------------------------------------

def property_research_node(state: ResearchState) -> dict:
    """Research a property listing and synthesise a structured showing brief.

    Searches for:
    - Location amenities and transport links
    - Comparable projects / competitor developments
    - Area development news
    - Investment thesis

    Synthesises into a brief with:
    - Key selling points
    - Top 5 FAQs with answers
    - Common objections and responses
    - Competitor comparison
    - Investment thesis
    """
    user_id = state.get("user_id", "")
    listing_id = state.get("listing_id")
    query = state.get("query", "")
    raw_results_existing = state.get("raw_results", [])

    # Derive search context from query or listing_id
    search_subject = query or listing_id or "property listing"

    # ------------------------------------------------------------------
    # Run Tavily searches
    # ------------------------------------------------------------------
    raw_results: list[dict] = list(raw_results_existing)

    search_queries = [
        f"{search_subject} location amenities transport links schools",
        f"{search_subject} comparable projects nearby developments",
        f"{search_subject} area development news infrastructure",
        f"{search_subject} investment potential rental yield capital appreciation",
        f"{search_subject} property review analysis pros cons",
    ]

    for sq in search_queries:
        results = _tavily_search(query=sq, max_results=4)
        raw_results.extend(results)

    # Deduplicate by URL
    seen_urls: set[str] = set()
    deduped: list[dict] = []
    for r in raw_results:
        url = r.get("url", "")
        if url not in seen_urls:
            seen_urls.add(url)
            deduped.append(r)
    raw_results = deduped

    # ------------------------------------------------------------------
    # Format research snippets for Claude
    # ------------------------------------------------------------------
    snippets = []
    for i, r in enumerate(raw_results[:20], 1):
        title = r.get("title", "")
        content = r.get("content", "")[:600]
        url = r.get("url", "")
        snippets.append(f"[{i}] {title}\n{content}\nSource: {url}")

    research_text = "\n\n".join(snippets) if snippets else "No research results available."

    # ------------------------------------------------------------------
    # Synthesise with Claude
    # ------------------------------------------------------------------
    synthesis_prompt = (
        f"You are a senior real estate research analyst. "
        f"Using the research below about '{search_subject}', "
        f"create a comprehensive showing brief for a real estate agent.\n\n"
        f"RESEARCH DATA:\n{research_text}\n\n"
        f"Create a JSON showing brief with these exact keys:\n"
        f"- key_selling_points: list of 5-7 researched selling points (not generic)\n"
        f"- faqs: list of 5 objects with 'question' and 'answer' keys\n"
        f"- objections: list of 4-5 objects with 'objection' and 'response' keys\n"
        f"- competitor_comparison: string describing nearby comparable projects and how this property compares\n"
        f"- investment_thesis: string with specific investment case (yield, capital growth, demand drivers)\n"
        f"- area_highlights: list of 3-5 notable area features discovered from research\n\n"
        f"Be specific and data-driven. Use facts from the research. Output valid JSON only."
    )

    brief_dict: dict = {}
    formatted_report = ""

    try:
        synthesis_response = _client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=2048,
            system="You are a real estate research analyst. Output only valid JSON, no markdown wrappers.",
            messages=[{"role": "user", "content": synthesis_prompt}],
        )
        raw_json = synthesis_response.content[0].text.strip() if synthesis_response.content else "{}"

        # Strip markdown code fences if present
        if raw_json.startswith("```"):
            raw_json = raw_json.split("```")[1]
            if raw_json.startswith("json"):
                raw_json = raw_json[4:]
            raw_json = raw_json.strip()

        brief_dict = json.loads(raw_json)

    except (json.JSONDecodeError, IndexError, Exception) as exc:
        logger.error("property_research_node: synthesis failed: %s", exc)
        brief_dict = {
            "key_selling_points": [f"Research for {search_subject} — synthesis unavailable"],
            "faqs": [],
            "objections": [],
            "competitor_comparison": "Research synthesis unavailable.",
            "investment_thesis": "Research synthesis unavailable.",
            "area_highlights": [],
        }

    # ------------------------------------------------------------------
    # Format human-readable report
    # ------------------------------------------------------------------
    formatted_sections = [f"# Property Research Brief: {search_subject}\n"]

    selling_points = brief_dict.get("key_selling_points", [])
    if selling_points:
        formatted_sections.append("## Key Selling Points")
        for i, sp in enumerate(selling_points, 1):
            formatted_sections.append(f"{i}. {sp}")

    area_highlights = brief_dict.get("area_highlights", [])
    if area_highlights:
        formatted_sections.append("\n## Area Highlights")
        for h in area_highlights:
            formatted_sections.append(f"• {h}")

    competitor = brief_dict.get("competitor_comparison", "")
    if competitor:
        formatted_sections.append(f"\n## Competitor Comparison\n{competitor}")

    investment = brief_dict.get("investment_thesis", "")
    if investment:
        formatted_sections.append(f"\n## Investment Thesis\n{investment}")

    faqs = brief_dict.get("faqs", [])
    if faqs:
        formatted_sections.append("\n## Top FAQs")
        for faq in faqs:
            formatted_sections.append(f"Q: {faq.get('question', '')}")
            formatted_sections.append(f"A: {faq.get('answer', '')}\n")

    objections = brief_dict.get("objections", [])
    if objections:
        formatted_sections.append("\n## Objection Handling")
        for obj in objections:
            formatted_sections.append(f"Objection: {obj.get('objection', '')}")
            formatted_sections.append(f"Response: {obj.get('response', '')}\n")

    formatted_report = "\n".join(formatted_sections)

    # ------------------------------------------------------------------
    # Write to KB
    # ------------------------------------------------------------------
    kb_written = False
    try:
        import asyncio

        # Store the full brief as a market/property report
        report_data = {
            "content": formatted_report,
            "date": __import__("datetime").datetime.now(__import__("datetime").timezone.utc).strftime("%Y-%m-%d"),
            "listing_id": listing_id or search_subject,
        }
        asyncio.run(_kb.write_market_report(user_id=user_id, report=report_data))

        # Store individual objections for future objection handling queries
        for obj in objections:
            objection_text = obj.get("objection", "")
            response_text = obj.get("response", "")
            if objection_text and response_text:
                asyncio.run(_kb.write_objection_answer(
                    user_id=user_id,
                    objection=objection_text,
                    answer=response_text,
                ))

        # Store as listing update if listing_id provided
        if listing_id:
            listing_update = {
                "id": listing_id,
                "name": search_subject,
                "selling_points": selling_points,
                "nearby_amenities": area_highlights,
                "investment_potential": investment,
            }
            asyncio.run(_kb.write_listing(user_id=user_id, listing=listing_update))

        kb_written = True
        logger.info("property_research_node: KB write complete for %s", search_subject)

    except Exception as exc:
        logger.error("property_research_node: KB write failed: %s", exc)

    summary = (
        f"[Property Research] Brief compiled for '{search_subject}'. "
        f"{len(raw_results)} sources reviewed. KB written: {kb_written}. "
        f"Selling points: {len(selling_points)}. FAQs: {len(faqs)}. Objections: {len(objections)}."
    )

    return {
        "raw_results": raw_results,
        "formatted_report": formatted_report,
        "kb_written": kb_written,
        "messages": [{"role": "assistant", "content": summary}],
    }
