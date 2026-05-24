"""Meta Graph API integration tool for Instagram and Facebook publishing."""
from __future__ import annotations

import logging
from typing import Any, Dict, Optional

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential

from config.settings import settings

log = logging.getLogger(__name__)

GRAPH_BASE = "https://graph.facebook.com/v20.0"


class MetaAPITool:
    """Async wrapper around the Meta (Facebook / Instagram) Graph API."""

    def __init__(self) -> None:
        self._access_token = settings.meta_access_token
        self._page_id = settings.meta_page_id
        self._ig_user_id = settings.meta_ig_user_id

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    async def _get(self, path: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        url = f"{GRAPH_BASE}{path}"
        p = {"access_token": self._access_token}
        if params:
            p.update(params)
        async with httpx.AsyncClient(timeout=60.0) as client:
            resp = await client.get(url, params=p)
            resp.raise_for_status()
            return resp.json()

    async def _post(self, path: str, data: Dict[str, Any]) -> Dict[str, Any]:
        url = f"{GRAPH_BASE}{path}"
        data["access_token"] = self._access_token
        async with httpx.AsyncClient(timeout=60.0) as client:
            resp = await client.post(url, data=data)
            resp.raise_for_status()
            return resp.json()

    # ------------------------------------------------------------------
    # Instagram
    # ------------------------------------------------------------------

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=15))
    async def publish_instagram_post(self, image_url: str, caption: str) -> str:
        """Publish a single-image Instagram post.

        Follows the two-step Meta API flow:
        1. Create a media container.
        2. Publish the container.

        Args:
            image_url: Publicly accessible URL of the image.
            caption: Post caption (may include hashtags).

        Returns:
            Instagram post ID string.
        """
        log.info("meta.ig_post.creating_container", ig_user_id=self._ig_user_id)

        # Step 1: create container
        container = await self._post(
            f"/{self._ig_user_id}/media",
            {"image_url": image_url, "caption": caption},
        )
        container_id = container["id"]

        # Step 2: publish
        result = await self._post(
            f"/{self._ig_user_id}/media_publish",
            {"creation_id": container_id},
        )
        post_id = result["id"]
        log.info("meta.ig_post.published", post_id=post_id)
        return post_id

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=15))
    async def publish_instagram_reel(self, video_url: str, caption: str) -> str:
        """Publish an Instagram Reel.

        Args:
            video_url: Publicly accessible URL of the video file.
            caption: Reel caption.

        Returns:
            Instagram media ID string.
        """
        log.info("meta.ig_reel.creating_container", ig_user_id=self._ig_user_id)

        # Step 1: create reel container
        container = await self._post(
            f"/{self._ig_user_id}/media",
            {
                "media_type": "REELS",
                "video_url": video_url,
                "caption": caption,
            },
        )
        container_id = container["id"]

        # Step 2: publish
        result = await self._post(
            f"/{self._ig_user_id}/media_publish",
            {"creation_id": container_id},
        )
        reel_id = result["id"]
        log.info("meta.ig_reel.published", reel_id=reel_id)
        return reel_id

    # ------------------------------------------------------------------
    # Facebook
    # ------------------------------------------------------------------

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=15))
    async def publish_facebook_post(
        self,
        message: str,
        image_url: Optional[str] = None,
    ) -> str:
        """Publish a post to the connected Facebook Page.

        Args:
            message: Post text content.
            image_url: Optional image to attach.

        Returns:
            Facebook post ID string.
        """
        payload: Dict[str, Any] = {"message": message}
        if image_url:
            payload["link"] = image_url

        log.info("meta.fb_post.publishing", page_id=self._page_id)
        result = await self._post(f"/{self._page_id}/feed", payload)
        post_id = result["id"]
        log.info("meta.fb_post.published", post_id=post_id)
        return post_id

    # ------------------------------------------------------------------
    # Insights
    # ------------------------------------------------------------------

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=15))
    async def get_post_insights(self, post_id: str) -> Dict[str, Any]:
        """Fetch engagement insights for a published post.

        Args:
            post_id: The Instagram or Facebook post ID.

        Returns:
            Dict with engagement metrics (impressions, reach, likes, comments, shares).
        """
        log.debug("meta.insights.fetch", post_id=post_id)
        data = await self._get(
            f"/{post_id}/insights",
            params={
                "metric": "impressions,reach,likes,comments,shares,saves",
                "period": "lifetime",
            },
        )
        metrics: Dict[str, Any] = {}
        for item in data.get("data", []):
            metrics[item["name"]] = item.get("values", [{}])[0].get("value", 0)
        return metrics
