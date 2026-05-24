"""Tavily search tool for web research."""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from tavily import AsyncTavilyClient

from config.settings import settings

log = logging.getLogger(__name__)


class TavilyTool:
    """Async wrapper around the Tavily search API."""

    def __init__(self) -> None:
        self._client = AsyncTavilyClient(api_key=settings.tavily_api_key)

    async def search(
        self,
        query: str,
        max_results: int = 5,
        include_domains: Optional[List[str]] = None,
        search_depth: str = "basic",
    ) -> List[Dict[str, Any]]:
        """Run a Tavily search and return a list of result dicts.

        Each result contains: ``title``, ``url``, ``content``, ``score``.

        Args:
            query: Natural language search query.
            max_results: Maximum number of results to return.
            include_domains: Optional whitelist of domains to restrict results.
            search_depth: ``"basic"`` (fast) or ``"advanced"`` (deeper).

        Returns:
            List of result dicts.
        """
        log.debug("tavily.search", query=query, max_results=max_results)

        kwargs: Dict[str, Any] = {
            "query": query,
            "max_results": max_results,
            "search_depth": search_depth,
            "include_answer": False,
            "include_raw_content": False,
        }
        if include_domains:
            kwargs["include_domains"] = include_domains

        response = await self._client.search(**kwargs)
        results = response.get("results", [])

        return [
            {
                "title": r.get("title", ""),
                "url": r.get("url", ""),
                "content": r.get("content", ""),
                "score": r.get("score", 0.0),
            }
            for r in results
        ]

    async def search_context(self, query: str, max_results: int = 5) -> str:
        """Run a search and return a formatted context string for LLM injection.

        The returned string lists each result as a numbered entry with title,
        URL, and a content snippet, ready to be inserted into a prompt.

        Args:
            query: Natural language search query.
            max_results: Number of results to include.

        Returns:
            Formatted multi-line string.
        """
        results = await self.search(query, max_results=max_results)
        if not results:
            return f"No search results found for: {query}"

        lines = [f"Search results for: {query}\n"]
        for i, r in enumerate(results, start=1):
            lines.append(f"{i}. {r['title']}")
            lines.append(f"   URL: {r['url']}")
            lines.append(f"   {r['content'][:400]}")
            lines.append("")

        return "\n".join(lines)
