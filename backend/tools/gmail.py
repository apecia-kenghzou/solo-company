"""Gmail API integration tool."""
from __future__ import annotations

import base64
import email as email_lib
import json
import logging
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Any, Dict, List, Optional

import httpx
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from tenacity import retry, stop_after_attempt, wait_exponential

from config.settings import settings

log = logging.getLogger(__name__)

SCOPES = [
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/gmail.send",
    "https://www.googleapis.com/auth/gmail.labels",
    "https://www.googleapis.com/auth/gmail.modify",
]


class GmailTool:
    """Async-friendly wrapper around the Gmail REST API."""

    # ------------------------------------------------------------------
    # Credentials
    # ------------------------------------------------------------------

    async def get_credentials(self, user_id: str) -> Credentials:
        """Load stored OAuth token for *user_id* from Redis / DB.

        The token JSON is expected to be stored under key
        ``gmail_token:{user_id}`` in Redis as a serialised
        ``google.oauth2.credentials.Credentials`` dict.
        """
        import redis.asyncio as aioredis

        r = aioredis.from_url(settings.redis_url, decode_responses=True)
        raw = await r.get(f"gmail_token:{user_id}")
        await r.aclose()

        if not raw:
            raise ValueError(
                f"No Gmail credentials found for user_id={user_id}. "
                "User must complete OAuth flow first."
            )

        token_data: Dict[str, Any] = json.loads(raw)
        creds = Credentials(
            token=token_data.get("token"),
            refresh_token=token_data.get("refresh_token"),
            token_uri="https://oauth2.googleapis.com/token",
            client_id=settings.gmail_client_id,
            client_secret=settings.gmail_client_secret,
            scopes=SCOPES,
        )
        return creds

    def _build_service(self, creds: Credentials):
        """Build a synchronous Gmail API service object."""
        return build("gmail", "v1", credentials=creds, cache_discovery=False)

    # ------------------------------------------------------------------
    # Messages
    # ------------------------------------------------------------------

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
    async def list_messages(
        self,
        user_id: str,
        max_results: int = 10,
        query: str = "",
    ) -> List[Dict[str, Any]]:
        """Return a list of message summaries (id, threadId, snippet, subject, from, date)."""
        import asyncio

        creds = await self.get_credentials(user_id)
        service = self._build_service(creds)

        def _fetch() -> List[Dict[str, Any]]:
            result = (
                service.users()
                .messages()
                .list(userId="me", maxResults=max_results, q=query)
                .execute()
            )
            messages = result.get("messages", [])
            summaries = []
            for msg in messages:
                detail = (
                    service.users()
                    .messages()
                    .get(userId="me", id=msg["id"], format="metadata",
                         metadataHeaders=["Subject", "From", "Date"])
                    .execute()
                )
                headers = {
                    h["name"]: h["value"]
                    for h in detail.get("payload", {}).get("headers", [])
                }
                summaries.append(
                    {
                        "id": detail["id"],
                        "thread_id": detail["threadId"],
                        "snippet": detail.get("snippet", ""),
                        "subject": headers.get("Subject", ""),
                        "from": headers.get("From", ""),
                        "date": headers.get("Date", ""),
                        "label_ids": detail.get("labelIds", []),
                    }
                )
            return summaries

        return await asyncio.get_event_loop().run_in_executor(None, _fetch)

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
    async def get_message(self, user_id: str, message_id: str) -> Dict[str, Any]:
        """Return full message content with decoded plain-text body."""
        import asyncio

        creds = await self.get_credentials(user_id)
        service = self._build_service(creds)

        def _fetch() -> Dict[str, Any]:
            detail = (
                service.users()
                .messages()
                .get(userId="me", id=message_id, format="full")
                .execute()
            )
            headers = {
                h["name"]: h["value"]
                for h in detail.get("payload", {}).get("headers", [])
            }
            body = _decode_body(detail.get("payload", {}))
            return {
                "id": detail["id"],
                "thread_id": detail["threadId"],
                "subject": headers.get("Subject", ""),
                "from": headers.get("From", ""),
                "to": headers.get("To", ""),
                "date": headers.get("Date", ""),
                "body": body,
                "label_ids": detail.get("labelIds", []),
            }

        return await asyncio.get_event_loop().run_in_executor(None, _fetch)

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
    async def send_message(
        self,
        user_id: str,
        to: str,
        subject: str,
        body: str,
        thread_id: Optional[str] = None,
    ) -> str:
        """Send an email and return the sent message_id."""
        import asyncio

        creds = await self.get_credentials(user_id)
        service = self._build_service(creds)

        mime = MIMEMultipart("alternative")
        mime["to"] = to
        mime["subject"] = subject
        mime.attach(MIMEText(body, "plain"))
        raw = base64.urlsafe_b64encode(mime.as_bytes()).decode()

        message_body: Dict[str, Any] = {"raw": raw}
        if thread_id:
            message_body["threadId"] = thread_id

        def _send() -> str:
            sent = (
                service.users().messages().send(userId="me", body=message_body).execute()
            )
            return sent["id"]

        return await asyncio.get_event_loop().run_in_executor(None, _send)

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
    async def create_label(self, user_id: str, label_name: str) -> str:
        """Create a Gmail label and return its label_id."""
        import asyncio

        creds = await self.get_credentials(user_id)
        service = self._build_service(creds)

        def _create() -> str:
            label_obj = {"name": label_name, "labelListVisibility": "labelShow",
                         "messageListVisibility": "show"}
            result = (
                service.users().labels().create(userId="me", body=label_obj).execute()
            )
            return result["id"]

        return await asyncio.get_event_loop().run_in_executor(None, _create)

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
    async def watch_inbox(self, user_id: str, topic_name: str) -> Dict[str, Any]:
        """Set up Gmail Pub/Sub push notifications for this user's inbox."""
        import asyncio

        creds = await self.get_credentials(user_id)
        service = self._build_service(creds)

        def _watch() -> Dict[str, Any]:
            request_body = {
                "labelIds": ["INBOX"],
                "topicName": topic_name,
            }
            return service.users().watch(userId="me", body=request_body).execute()

        return await asyncio.get_event_loop().run_in_executor(None, _watch)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _decode_body(payload: Dict[str, Any]) -> str:
    """Recursively extract plain-text body from a Gmail message payload."""
    mime_type = payload.get("mimeType", "")
    if mime_type == "text/plain":
        data = payload.get("body", {}).get("data", "")
        if data:
            return base64.urlsafe_b64decode(data + "==").decode("utf-8", errors="replace")
    elif mime_type.startswith("multipart/"):
        for part in payload.get("parts", []):
            text = _decode_body(part)
            if text:
                return text
    return ""
