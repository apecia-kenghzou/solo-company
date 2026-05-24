"""Google Calendar integration tool."""
from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from tenacity import retry, stop_after_attempt, wait_exponential

from config.settings import settings

log = logging.getLogger(__name__)

SCOPES = [
    "https://www.googleapis.com/auth/calendar",
    "https://www.googleapis.com/auth/calendar.events",
]


class CalendarTool:
    """Async-friendly wrapper around the Google Calendar API."""

    # ------------------------------------------------------------------
    # Credentials
    # ------------------------------------------------------------------

    async def _get_credentials(self, user_id: str) -> Credentials:
        """Load stored OAuth2 credentials for *user_id* from Redis."""
        import redis.asyncio as aioredis

        r = aioredis.from_url(settings.redis_url, decode_responses=True)
        raw = await r.get(f"gcal_token:{user_id}")
        await r.aclose()

        if not raw:
            raise ValueError(
                f"No Google Calendar credentials for user_id={user_id}. "
                "User must complete OAuth flow first."
            )

        token_data: Dict[str, Any] = json.loads(raw)
        return Credentials(
            token=token_data.get("token"),
            refresh_token=token_data.get("refresh_token"),
            token_uri="https://oauth2.googleapis.com/token",
            client_id=settings.google_calendar_client_id,
            client_secret=settings.google_calendar_client_secret,
            scopes=SCOPES,
        )

    def _build_service(self, creds: Credentials):
        return build("calendar", "v3", credentials=creds, cache_discovery=False)

    # ------------------------------------------------------------------
    # Availability
    # ------------------------------------------------------------------

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
    async def get_available_slots(
        self,
        user_id: str,
        date: datetime,
        duration_minutes: int = 60,
    ) -> List[Dict[str, Any]]:
        """Return available time slots on *date* for a meeting of *duration_minutes*.

        Queries the primary calendar for busy periods then computes free slots
        between 09:00 and 18:00 in the calendar's default timezone.

        Returns:
            List of dicts with ``start`` and ``end`` ISO-8601 strings.
        """
        creds = await self._get_credentials(user_id)
        service = self._build_service(creds)

        day_start = date.replace(hour=9, minute=0, second=0, microsecond=0, tzinfo=timezone.utc)
        day_end = date.replace(hour=18, minute=0, second=0, microsecond=0, tzinfo=timezone.utc)

        def _fetch() -> List[Dict[str, Any]]:
            body = {
                "timeMin": day_start.isoformat(),
                "timeMax": day_end.isoformat(),
                "items": [{"id": "primary"}],
            }
            freebusy = service.freebusy().query(body=body).execute()
            busy_periods = freebusy.get("calendars", {}).get("primary", {}).get("busy", [])

            # Build list of busy ranges
            busy = [
                (
                    datetime.fromisoformat(p["start"]),
                    datetime.fromisoformat(p["end"]),
                )
                for p in busy_periods
            ]

            slots = []
            cursor = day_start
            delta = timedelta(minutes=duration_minutes)
            while cursor + delta <= day_end:
                slot_end = cursor + delta
                overlapping = any(
                    not (slot_end <= b_start or cursor >= b_end)
                    for b_start, b_end in busy
                )
                if not overlapping:
                    slots.append(
                        {
                            "start": cursor.isoformat(),
                            "end": slot_end.isoformat(),
                        }
                    )
                cursor += timedelta(minutes=30)

            return slots

        return await asyncio.get_event_loop().run_in_executor(None, _fetch)

    # ------------------------------------------------------------------
    # Events
    # ------------------------------------------------------------------

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
    async def create_event(
        self,
        user_id: str,
        title: str,
        start_dt: datetime,
        end_dt: datetime,
        attendee_emails: List[str],
        description: str = "",
    ) -> str:
        """Create a Google Calendar event and return the event_id.

        Args:
            user_id: Platform user ID for credential lookup.
            title: Event summary / title.
            start_dt: Event start datetime (timezone-aware recommended).
            end_dt: Event end datetime.
            attendee_emails: List of attendee email addresses.
            description: Optional event description / notes.

        Returns:
            Google Calendar event ID string.
        """
        creds = await self._get_credentials(user_id)
        service = self._build_service(creds)

        event_body = {
            "summary": title,
            "description": description,
            "start": {"dateTime": start_dt.isoformat(), "timeZone": "UTC"},
            "end": {"dateTime": end_dt.isoformat(), "timeZone": "UTC"},
            "attendees": [{"email": e} for e in attendee_emails],
            "reminders": {
                "useDefault": False,
                "overrides": [
                    {"method": "email", "minutes": 24 * 60},
                    {"method": "popup", "minutes": 30},
                ],
            },
        }

        def _create() -> str:
            event = (
                service.events().insert(calendarId="primary", body=event_body,
                                        sendUpdates="all").execute()
            )
            return event["id"]

        return await asyncio.get_event_loop().run_in_executor(None, _create)

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
    async def send_viewing_confirmation(
        self,
        user_id: str,
        lead_email: str,
        listing_name: str,
        viewing_dt: datetime,
    ) -> str:
        """Create a viewing appointment and return the event_id.

        Convenience wrapper around :meth:`create_event` that formats
        the title and description for a property viewing.
        """
        title = f"Property Viewing: {listing_name}"
        description = (
            f"Property viewing scheduled for {listing_name}.\n"
            f"Date & Time: {viewing_dt.strftime('%A, %d %B %Y at %H:%M')}\n\n"
            "Please bring valid photo ID. Contact us if you need to reschedule."
        )
        end_dt = viewing_dt + timedelta(hours=1)

        event_id = await self.create_event(
            user_id=user_id,
            title=title,
            start_dt=viewing_dt,
            end_dt=end_dt,
            attendee_emails=[lead_email],
            description=description,
        )
        log.info(
            "calendar.viewing_confirmed",
            event_id=event_id,
            listing=listing_name,
            lead_email=lead_email,
        )
        return event_id
