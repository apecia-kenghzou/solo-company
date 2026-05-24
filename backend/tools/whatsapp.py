"""360dialog WhatsApp Business API integration tool."""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential

from config.settings import settings

log = logging.getLogger(__name__)


class WhatsAppTool:
    """Async wrapper around the 360dialog WhatsApp Business API."""

    def __init__(self) -> None:
        self._base_url = settings.whatsapp_api_url.rstrip("/")
        self._headers = {
            "D360-API-KEY": settings.whatsapp_api_key,
            "Content-Type": "application/json",
        }

    # ------------------------------------------------------------------
    # Internal helper
    # ------------------------------------------------------------------

    async def _post(self, path: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Send a POST request to the 360dialog API and return the JSON response."""
        url = f"{self._base_url}{path}"
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(url, json=payload, headers=self._headers)
            resp.raise_for_status()
            return resp.json()

    async def _get(self, path: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Send a GET request to the 360dialog API."""
        url = f"{self._base_url}{path}"
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.get(url, headers=self._headers, params=params or {})
            resp.raise_for_status()
            return resp.json()

    # ------------------------------------------------------------------
    # Messaging
    # ------------------------------------------------------------------

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
    async def send_text(self, to: str, body: str) -> Dict[str, Any]:
        """Send a plain-text WhatsApp message.

        Args:
            to: Recipient phone number in E.164 format (e.g. ``+60123456789``).
            body: Plain text message body.

        Returns:
            API response dict containing ``messages[].id``.
        """
        payload = {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": to,
            "type": "text",
            "text": {"preview_url": False, "body": body},
        }
        log.debug("whatsapp.send_text", to=to, body_len=len(body))
        return await self._post("/messages", payload)

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
    async def send_template(
        self,
        to: str,
        template_name: str,
        params: List[str],
        language_code: str = "en",
    ) -> Dict[str, Any]:
        """Send a pre-approved WhatsApp message template.

        Args:
            to: Recipient phone number in E.164 format.
            template_name: Name of the approved template.
            params: List of string values for the template body components.
            language_code: BCP-47 language code (default ``"en"``).

        Returns:
            API response dict.
        """
        components = []
        if params:
            components.append(
                {
                    "type": "body",
                    "parameters": [{"type": "text", "text": p} for p in params],
                }
            )

        payload = {
            "messaging_product": "whatsapp",
            "to": to,
            "type": "template",
            "template": {
                "name": template_name,
                "language": {"code": language_code},
                "components": components,
            },
        }
        log.debug("whatsapp.send_template", to=to, template=template_name)
        return await self._post("/messages", payload)

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
    async def send_media(
        self,
        to: str,
        media_type: str,
        media_url: str,
        caption: str = "",
    ) -> Dict[str, Any]:
        """Send an image, document, or video via URL.

        Args:
            to: Recipient phone number in E.164 format.
            media_type: One of ``"image"``, ``"document"``, ``"video"``, ``"audio"``.
            media_url: Publicly accessible URL of the media file.
            caption: Optional caption (supported for image/video/document).

        Returns:
            API response dict.
        """
        media_payload: Dict[str, Any] = {"link": media_url}
        if caption:
            media_payload["caption"] = caption

        payload = {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": to,
            "type": media_type,
            media_type: media_payload,
        }
        log.debug("whatsapp.send_media", to=to, media_type=media_type)
        return await self._post("/messages", payload)

    # ------------------------------------------------------------------
    # Contacts
    # ------------------------------------------------------------------

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
    async def get_contacts(self) -> List[Dict[str, Any]]:
        """List WhatsApp contacts associated with this account.

        Returns:
            List of contact dicts with at minimum ``wa_id`` and ``profile.name``.
        """
        data = await self._get("/contacts")
        return data.get("contacts", [])
