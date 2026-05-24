"""Apify scraping / social-trend tool."""
from __future__ import annotations

import asyncio
import logging
from typing import Any, Dict, List, Optional

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential

from config.settings import settings

log = logging.getLogger(__name__)

APIFY_BASE = "https://api.apify.com/v2"

# Actor IDs for common tasks
TIKTOK_ACTOR = "clockworks/free-tiktok-scraper"
INSTAGRAM_ACTOR = "apify/instagram-hashtag-scraper"
PROPERTY_ACTOR = "apify/website-content-crawler"


class ApifyTool:
    """Async wrapper around the Apify REST API for social trend scraping."""

    def __init__(self) -> None:
        self._token = settings.apify_api_token
        self._headers = {"Authorization": f"Bearer {self._token}"}

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    async def _run_actor(
        self,
        actor_id: str,
        input_data: Dict[str, Any],
        timeout_secs: int = 120,
    ) -> List[Dict[str, Any]]:
        """Start an Apify actor run synchronously and return the dataset items.

        Uses the ``runs`` synchronous endpoint which blocks until the run
        completes (up to *timeout_secs*).
        """
        url = f"{APIFY_BASE}/acts/{actor_id}/run-sync-get-dataset-items"
        params = {"token": self._token, "timeout": timeout_secs}

        log.debug("apify.run_actor", actor=actor_id, input_keys=list(input_data.keys()))

        async with httpx.AsyncClient(timeout=timeout_secs + 30) as client:
            resp = await client.post(url, json=input_data, params=params)
            resp.raise_for_status()
            return resp.json()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    @retry(stop=stop_after_attempt(2), wait=wait_exponential(multiplier=2, min=5, max=30))
    async def get_tiktok_trending(
        self,
        topics: List[str],
        max_results: int = 20,
    ) -> List[Dict[str, Any]]:
        """Scrape trending TikTok videos for the given *topics* / hashtags.

        Args:
            topics: List of search terms or hashtags (without ``#``).
            max_results: Maximum number of videos to return.

        Returns:
            List of dicts with keys: ``id``, ``description``, ``author``,
            ``likes``, ``comments``, ``shares``, ``views``, ``url``,
            ``hashtags``, ``createTime``.
        """
        hashtags = [t.lstrip("#") for t in topics]
        input_data = {
            "hashtags": hashtags,
            "resultsPerPage": max_results,
            "shouldDownloadVideos": False,
            "shouldDownloadCovers": False,
        }
        items = await self._run_actor(TIKTOK_ACTOR, input_data)

        results = []
        for item in items[:max_results]:
            results.append(
                {
                    "id": item.get("id", ""),
                    "description": item.get("text", ""),
                    "author": item.get("authorMeta", {}).get("name", ""),
                    "likes": item.get("diggCount", 0),
                    "comments": item.get("commentCount", 0),
                    "shares": item.get("shareCount", 0),
                    "views": item.get("playCount", 0),
                    "url": item.get("webVideoUrl", ""),
                    "hashtags": [
                        h.get("name", "") for h in item.get("hashtags", [])
                    ],
                    "createTime": item.get("createTime", ""),
                }
            )
        return results

    @retry(stop=stop_after_attempt(2), wait=wait_exponential(multiplier=2, min=5, max=30))
    async def get_instagram_reels_trends(
        self,
        hashtags: List[str],
        max_results: int = 20,
    ) -> List[Dict[str, Any]]:
        """Scrape recent Instagram posts/reels for the given *hashtags*.

        Args:
            hashtags: List of hashtags (with or without ``#``).
            max_results: Maximum number of posts to return.

        Returns:
            List of dicts with keys: ``id``, ``caption``, ``likes``,
            ``comments``, ``url``, ``timestamp``, ``hashtags``.
        """
        clean_tags = [t.lstrip("#") for t in hashtags]
        input_data = {
            "hashtags": clean_tags,
            "resultsLimit": max_results,
            "scrapeType": "posts",
        }
        items = await self._run_actor(INSTAGRAM_ACTOR, input_data)

        results = []
        for item in items[:max_results]:
            results.append(
                {
                    "id": item.get("id", ""),
                    "caption": item.get("caption", ""),
                    "likes": item.get("likesCount", 0),
                    "comments": item.get("commentsCount", 0),
                    "url": item.get("url", ""),
                    "timestamp": item.get("timestamp", ""),
                    "hashtags": item.get("hashtags", []),
                }
            )
        return results

    @retry(stop=stop_after_attempt(2), wait=wait_exponential(multiplier=2, min=5, max=30))
    async def scrape_property_listing(self, url: str) -> Dict[str, Any]:
        """Scrape a property listing page and return structured data.

        Args:
            url: Full URL of the property listing page to scrape.

        Returns:
            Dict with scraped text content, title, and URL.
        """
        input_data = {
            "startUrls": [{"url": url}],
            "maxCrawlingDepth": 0,
            "maxPagesPerCrawl": 1,
            "pageFunction": "",
        }
        items = await self._run_actor(PROPERTY_ACTOR, input_data, timeout_secs=60)

        if not items:
            return {"url": url, "title": "", "text": "", "error": "No content scraped"}

        item = items[0]
        return {
            "url": url,
            "title": item.get("title", ""),
            "text": item.get("text", "")[:5000],  # Trim to 5k chars
            "metadata": item.get("metadata", {}),
        }
