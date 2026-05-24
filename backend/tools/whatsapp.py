"""WhatsApp Business API tool.

Supports two backends that share the same payload schema (Meta Cloud API format):

1. **Meta Cloud API direct** — ``graph.facebook.com/v{version}/{phone_number_id}/messages``
   Auth: ``Authorization: Bearer {META_ACCESS_TOKEN}``

2. **360dialog proxy** — ``waba.360dialog.io/v1/messages``
   Auth: ``D360-API-KEY: {WHATSAPP_API_KEY}``

The environment variable ``WHATSAPP_BACKEND`` selects the backend:
  - ``"meta"``      → Meta Cloud API direct (default)
  - ``"360dialog"`` → 360dialog proxy

This matches the approach used by nanoclaw and the broader OpenClaw ecosystem,
which treats the Meta Cloud API format as the canonical standard regardless of
which Business Solution Provider (BSP) is in use.

Message type reference (Meta Cloud API):
  https://developers.facebook.com/docs/whatsapp/cloud-api/reference/messages
"""
from __future__ import annotations

import logging
import os
from typing import Any, Dict, List, Optional

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential

from config.settings import settings

log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# API version pinned so upgrades are explicit
# ---------------------------------------------------------------------------
META_API_VERSION = "v20.0"
META_BASE = f"https://graph.facebook.com/{META_API_VERSION}"
D360_BASE = "https://waba.360dialog.io/v1"

# Which backend to use — can be overridden at runtime via env var
_BACKEND = os.getenv("WHATSAPP_BACKEND", "meta").lower()  # "meta" | "360dialog"


def _build_client_and_url(phone_number_id: Optional[str] = None) -> tuple[httpx.AsyncClient, str]:
    """Return an authenticated httpx client and the base messages endpoint URL.

    ``phone_number_id`` is required for the Meta backend (it's part of the URL).
    For 360dialog it's ignored — the BSP knows the WABA from the API key.
    """
    if _BACKEND == "360dialog":
        client = httpx.AsyncClient(
            timeout=30.0,
            headers={
                "D360-API-KEY": settings.whatsapp_api_key,
                "Content-Type": "application/json",
            },
        )
        url = f"{D360_BASE}/messages"
    else:
        # Meta Cloud API — phone_number_id is part of the path
        pid = phone_number_id or settings.meta_ig_user_id  # fallback to configured id
        client = httpx.AsyncClient(
            timeout=30.0,
            headers={
                "Authorization": f"Bearer {settings.meta_access_token}",
                "Content-Type": "application/json",
            },
        )
        url = f"{META_BASE}/{pid}/messages"

    return client, url


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


class WhatsAppTool:
    """Async wrapper around the WhatsApp Business Cloud API.

    All methods accept an optional ``phone_number_id`` parameter. For the Meta
    backend this identifies *which* WABA number is sending (a single agent may
    manage multiple numbers). For 360dialog it has no effect.

    Phone numbers must be in E.164 format without the ``+`` prefix
    (e.g., ``60123456789``).  Meta's API rejects the leading ``+``.
    """

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _strip_plus(number: str) -> str:
        """Remove a leading ``+`` — Meta Cloud API rejects it."""
        return number.lstrip("+")

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
    async def _post(
        self,
        payload: Dict[str, Any],
        phone_number_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """POST a payload to the messages endpoint and return the JSON response."""
        client, url = _build_client_and_url(phone_number_id)
        async with client:
            resp = await client.post(url, json=payload)
            if resp.status_code >= 400:
                log.error(
                    "whatsapp._post.error",
                    status=resp.status_code,
                    body=resp.text[:500],
                )
            resp.raise_for_status()
            return resp.json()

    # ------------------------------------------------------------------
    # Text messages
    # ------------------------------------------------------------------

    async def send_text(
        self,
        to: str,
        body: str,
        phone_number_id: Optional[str] = None,
        preview_url: bool = False,
    ) -> Dict[str, Any]:
        """Send a plain-text message.

        Args:
            to: Recipient in E.164 format (``+`` optional, will be stripped).
            body: Message text (max 4096 chars for WhatsApp).
            phone_number_id: Sender WABA phone number ID (Meta backend).
            preview_url: Whether to render a URL preview if the text contains one.

        Returns:
            Meta API response ``{"messages": [{"id": "wamid.xxx"}]}``.
        """
        payload: Dict[str, Any] = {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": self._strip_plus(to),
            "type": "text",
            "text": {"preview_url": preview_url, "body": body},
        }
        log.debug("whatsapp.send_text", to=to, chars=len(body))
        return await self._post(payload, phone_number_id)

    # ------------------------------------------------------------------
    # Template messages (required for first contact / 24-hour window expiry)
    # ------------------------------------------------------------------

    async def send_template(
        self,
        to: str,
        template_name: str,
        params: List[str],
        language_code: str = "en",
        phone_number_id: Optional[str] = None,
        header_params: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """Send a pre-approved WhatsApp message template.

        Templates are required when messaging outside the 24-hour customer
        service window. Body ``params`` map to ``{{1}}``, ``{{2}}``… variables
        in the approved template. Optionally pass ``header_params`` for header
        components that also have variables.

        Args:
            to: Recipient E.164 number.
            template_name: Exact name of the approved template in Meta Business Manager.
            params: List of string values for body ``{{n}}`` variables, in order.
            language_code: BCP-47 code (e.g. ``"en"``, ``"ms"``).
            phone_number_id: Sender phone number ID.
            header_params: Optional list of values for header ``{{n}}`` variables.

        Returns:
            Meta API response.
        """
        components: List[Dict[str, Any]] = []

        if header_params:
            components.append({
                "type": "header",
                "parameters": [{"type": "text", "text": p} for p in header_params],
            })

        if params:
            components.append({
                "type": "body",
                "parameters": [{"type": "text", "text": p} for p in params],
            })

        payload: Dict[str, Any] = {
            "messaging_product": "whatsapp",
            "to": self._strip_plus(to),
            "type": "template",
            "template": {
                "name": template_name,
                "language": {"code": language_code},
                "components": components,
            },
        }
        log.debug("whatsapp.send_template", to=to, template=template_name, params=len(params))
        return await self._post(payload, phone_number_id)

    # ------------------------------------------------------------------
    # Media messages
    # ------------------------------------------------------------------

    async def send_media(
        self,
        to: str,
        media_type: str,
        media_url: str,
        caption: str = "",
        filename: Optional[str] = None,
        phone_number_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Send an image, document, video, or audio by URL.

        Args:
            to: Recipient E.164 number.
            media_type: One of ``"image"``, ``"document"``, ``"video"``, ``"audio"``.
            media_url: Publicly accessible HTTPS URL (must be reachable by Meta).
            caption: Optional caption (supported for image / video / document).
            filename: Display filename for documents.
            phone_number_id: Sender phone number ID.

        Returns:
            Meta API response.
        """
        media_payload: Dict[str, Any] = {"link": media_url}
        if caption and media_type in ("image", "video", "document"):
            media_payload["caption"] = caption
        if filename and media_type == "document":
            media_payload["filename"] = filename

        payload: Dict[str, Any] = {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": self._strip_plus(to),
            "type": media_type,
            media_type: media_payload,
        }
        log.debug("whatsapp.send_media", to=to, type=media_type)
        return await self._post(payload, phone_number_id)

    # ------------------------------------------------------------------
    # Interactive messages (buttons / list)
    # ------------------------------------------------------------------

    async def send_buttons(
        self,
        to: str,
        body_text: str,
        buttons: List[Dict[str, str]],
        header_text: Optional[str] = None,
        footer_text: Optional[str] = None,
        phone_number_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Send an interactive button message (max 3 buttons).

        Args:
            to: Recipient E.164 number.
            body_text: Main message body.
            buttons: List of ``{"id": "btn_1", "title": "Yes"}`` dicts (max 3).
            header_text: Optional header text.
            footer_text: Optional footer text (e.g. for disclaimers).
            phone_number_id: Sender phone number ID.

        Example::

            await wa.send_buttons(
                to="+60123456789",
                body_text="Are you interested in scheduling a viewing?",
                buttons=[
                    {"id": "yes_viewing", "title": "Yes, book now"},
                    {"id": "more_info",   "title": "Send more info"},
                    {"id": "not_now",     "title": "Maybe later"},
                ],
            )
        """
        action = {
            "buttons": [
                {"type": "reply", "reply": {"id": b["id"], "title": b["title"][:20]}}
                for b in buttons[:3]  # Meta limit: 3
            ]
        }
        interactive: Dict[str, Any] = {
            "type": "button",
            "body": {"text": body_text},
            "action": action,
        }
        if header_text:
            interactive["header"] = {"type": "text", "text": header_text}
        if footer_text:
            interactive["footer"] = {"text": footer_text}

        payload: Dict[str, Any] = {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": self._strip_plus(to),
            "type": "interactive",
            "interactive": interactive,
        }
        log.debug("whatsapp.send_buttons", to=to, n_buttons=len(buttons))
        return await self._post(payload, phone_number_id)

    # ------------------------------------------------------------------
    # Read receipts
    # ------------------------------------------------------------------

    async def mark_read(
        self,
        message_id: str,
        phone_number_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Mark an inbound message as read (shows blue ticks to the sender).

        Should be called immediately after processing an inbound message to
        signal to the lead that their message has been seen.

        Args:
            message_id: The ``wamid.xxx`` ID from the inbound webhook.
            phone_number_id: Sender phone number ID.
        """
        payload: Dict[str, Any] = {
            "messaging_product": "whatsapp",
            "status": "read",
            "message_id": message_id,
        }
        log.debug("whatsapp.mark_read", message_id=message_id)
        return await self._post(payload, phone_number_id)

    # ------------------------------------------------------------------
    # Utilities
    # ------------------------------------------------------------------

    @staticmethod
    def extract_text_body(message: Dict[str, Any]) -> str:
        """Extract plain-text content from any inbound message type.

        Handles all Meta Cloud API message types: text, image, document,
        audio, video, sticker, location, contacts, interactive (button_reply
        / list_reply), and button.

        Args:
            message: The ``messages[0]`` object from the Meta Cloud API webhook.

        Returns:
            Human-readable string representation of the message content,
            or an empty string if the content cannot be extracted.
        """
        msg_type = message.get("type", "")

        if msg_type == "text":
            return message.get("text", {}).get("body", "")

        if msg_type in ("image", "video", "document", "audio", "sticker"):
            media = message.get(msg_type, {})
            caption = media.get("caption", "")
            mime = media.get("mime_type", "")
            filename = media.get("filename", "")
            parts = [f"[{msg_type.upper()}]"]
            if filename:
                parts.append(filename)
            if caption:
                parts.append(caption)
            if mime:
                parts.append(f"({mime})")
            return " ".join(parts)

        if msg_type == "location":
            loc = message.get("location", {})
            lat = loc.get("latitude", "?")
            lng = loc.get("longitude", "?")
            name = loc.get("name", "")
            address = loc.get("address", "")
            text = f"[LOCATION] {lat},{lng}"
            if name:
                text += f" — {name}"
            if address:
                text += f", {address}"
            return text

        if msg_type == "interactive":
            interactive = message.get("interactive", {})
            itype = interactive.get("type", "")
            if itype == "button_reply":
                reply = interactive.get("button_reply", {})
                return f"[BUTTON_REPLY] id={reply.get('id','')} title={reply.get('title','')}"
            if itype == "list_reply":
                reply = interactive.get("list_reply", {})
                return f"[LIST_REPLY] id={reply.get('id','')} title={reply.get('title','')}"

        if msg_type == "button":
            return message.get("button", {}).get("text", "")

        if msg_type == "contacts":
            contacts = message.get("contacts", [])
            names = [c.get("name", {}).get("formatted_name", "?") for c in contacts]
            return f"[CONTACTS] {', '.join(names)}"

        log.warning("whatsapp.extract_text_body.unknown_type", msg_type=msg_type)
        return f"[{msg_type.upper()}]"


# ---------------------------------------------------------------------------
# Module-level singleton — import and use directly
# ---------------------------------------------------------------------------
whatsapp = WhatsAppTool()
