"""Webhook handlers for Gmail, WhatsApp, Meta, and Stripe."""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import logging
from typing import Any, Dict

from fastapi import APIRouter, BackgroundTasks, Header, HTTPException, Request, status

from config.settings import settings

log = logging.getLogger(__name__)
router = APIRouter()


# ---------------------------------------------------------------------------
# Gmail Pub/Sub webhook
# ---------------------------------------------------------------------------

@router.post("/gmail", status_code=status.HTTP_200_OK)
async def gmail_webhook(
    request: Request,
    background_tasks: BackgroundTasks,
) -> Dict[str, str]:
    """Handle Gmail Pub/Sub push notification.

    Google Pub/Sub sends a POST with a JSON body containing a base64-encoded
    ``message.data`` field. We decode it to extract the user's email and
    historyId, identify the platform user, then dispatch an async task to
    process the new message.

    Always returns 200 quickly to acknowledge receipt.
    """
    try:
        body = await request.json()
        pubsub_message = body.get("message", {})
        raw_data = pubsub_message.get("data", "")

        if raw_data:
            decoded = base64.b64decode(raw_data + "==").decode("utf-8")
            data: Dict[str, Any] = json.loads(decoded)
        else:
            data = {}

        email_address = data.get("emailAddress", "")
        history_id = data.get("historyId", "")

        log.info("webhook.gmail", email=email_address, history_id=history_id)

        if email_address:
            # Look up the platform user by email and dispatch task
            background_tasks.add_task(
                _dispatch_gmail_task,
                email_address=email_address,
                history_id=str(history_id),
            )

    except Exception as exc:
        # Log but always return 200 to prevent Pub/Sub retry storms
        log.error("webhook.gmail.parse_error", error=str(exc))

    return {"status": "ok"}


async def _dispatch_gmail_task(email_address: str, history_id: str) -> None:
    """Identify user from email and dispatch Celery task."""
    try:
        from models.base import AsyncSessionLocal
        from models.user import User
        from sqlalchemy import select

        async with AsyncSessionLocal() as session:
            result = await session.execute(
                select(User).where(User.email == email_address, User.is_active == True)
            )
            user = result.scalar_one_or_none()
            if not user:
                log.warning("webhook.gmail.user_not_found", email=email_address)
                return

            from workers.tasks import process_inbound_email
            process_inbound_email.delay(str(user.id), history_id)
            log.info("webhook.gmail.task_dispatched", user_id=str(user.id))

    except Exception as exc:
        log.error("webhook.gmail.dispatch_error", error=str(exc))


# ---------------------------------------------------------------------------
# WhatsApp webhook — Meta Cloud API format
#
# Meta sends ALL WhatsApp webhooks (whether via direct API or a BSP like
# 360dialog) in the same nested envelope:
#
#   {
#     "object": "whatsapp_business_account",
#     "entry": [{
#       "id": "<WABA_ID>",
#       "changes": [{
#         "value": {
#           "messaging_product": "whatsapp",
#           "metadata": {
#             "display_phone_number": "601x-xxxxxxx",
#             "phone_number_id": "<PHONE_NUMBER_ID>"   ← routes to correct user
#           },
#           "contacts": [{"profile": {"name": "..."}, "wa_id": "..."}],
#           "messages": [{ ... }],
#           "statuses": [{ ... }]          ← delivery receipts (optional)
#         },
#         "field": "messages"
#       }]
#     }]
#   }
#
# This is the format used by nanoclaw and all Meta Cloud API integrations.
# We also accept the legacy 360dialog v1 flat format as a fallback:
#   { "messages": [...], "contacts": [...] }
# ---------------------------------------------------------------------------

def _verify_whatsapp_signature(raw_body: bytes, signature_header: str) -> bool:
    """Verify X-Hub-Signature-256 sent by Meta on every webhook POST.

    Meta signs the raw request body with the app secret using HMAC-SHA256.
    The header value is ``sha256=<hex_digest>``.

    Returns True if the signature is valid or if no app secret is configured
    (to allow local dev without env vars set).
    """
    app_secret = settings.app_secret_key
    if not app_secret or not signature_header:
        # Skip verification in dev — warn but don't block
        log.warning("webhook.whatsapp.signature_skip — set APP_SECRET_KEY in production")
        return True

    if not signature_header.startswith("sha256="):
        return False

    expected = hmac.new(
        app_secret.encode(),
        raw_body,
        digestmod=hashlib.sha256,
    ).hexdigest()

    received = signature_header[len("sha256="):]
    return hmac.compare_digest(expected, received)


def _parse_whatsapp_body(body: Dict[str, Any]) -> list[tuple[str, Dict[str, Any], str]]:
    """Extract (from_number, message_dict, phone_number_id) tuples from a webhook body.

    Handles both:
    - Meta Cloud API format (``entry[].changes[].value.messages[]``)
    - Legacy 360dialog v1 flat format (``messages[]`` at root)

    Returns a list of tuples ready for dispatch.
    """
    results: list[tuple[str, Dict[str, Any], str]] = []

    # ── Meta Cloud API format ────────────────────────────────────────────
    if body.get("object") == "whatsapp_business_account":
        for entry in body.get("entry", []):
            for change in entry.get("changes", []):
                if change.get("field") != "messages":
                    continue
                value = change.get("value", {})
                phone_number_id = value.get("metadata", {}).get("phone_number_id", "")
                for msg in value.get("messages", []):
                    from_number = msg.get("from", "")
                    if from_number:
                        results.append((from_number, msg, phone_number_id))
        return results

    # ── Legacy 360dialog v1 flat format ─────────────────────────────────
    for msg in body.get("messages", []):
        from_number = msg.get("from", "")
        if from_number:
            # No phone_number_id in this format — will fall back to first user
            results.append((from_number, msg, ""))
    return results


@router.get("/whatsapp", status_code=status.HTTP_200_OK)
async def whatsapp_webhook_verify(request: Request) -> Any:
    """Handle Meta webhook verification challenge.

    Meta (and 360dialog) send a GET request when the webhook URL is first
    registered.  We must echo back ``hub.challenge`` if ``hub.verify_token``
    matches our secret.
    """
    from fastapi.responses import PlainTextResponse

    params = dict(request.query_params)
    mode = params.get("hub.mode")
    token = params.get("hub.verify_token")
    challenge = params.get("hub.challenge", "")

    if mode == "subscribe" and token == settings.app_secret_key:
        log.info("webhook.whatsapp.verified")
        return PlainTextResponse(content=challenge)

    log.warning("webhook.whatsapp.verify_failed", mode=mode, token=token)
    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Verification failed")


@router.post("/whatsapp", status_code=status.HTTP_200_OK)
async def whatsapp_webhook(
    request: Request,
    background_tasks: BackgroundTasks,
    x_hub_signature_256: str = Header(default="", alias="X-Hub-Signature-256"),
) -> Dict[str, str]:
    """Handle inbound WhatsApp messages via Meta Cloud API webhook format.

    Accepts the standard Meta Cloud API nested envelope as well as the legacy
    360dialog v1 flat format.  Verifies ``X-Hub-Signature-256`` before
    dispatching any work.  Always returns 200 immediately — actual processing
    is async via Celery.
    """
    raw_body = await request.body()

    # ── Signature verification ───────────────────────────────────────────
    if not _verify_whatsapp_signature(raw_body, x_hub_signature_256):
        log.error("webhook.whatsapp.invalid_signature")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid signature",
        )

    try:
        body: Dict[str, Any] = json.loads(raw_body)
        messages_to_dispatch = _parse_whatsapp_body(body)

        for from_number, message, phone_number_id in messages_to_dispatch:
            msg_type = message.get("type", "text")
            msg_id = message.get("id", "")
            log.info(
                "webhook.whatsapp.message",
                from_=from_number,
                type_=msg_type,
                id_=msg_id,
                phone_number_id=phone_number_id,
            )
            background_tasks.add_task(
                _dispatch_whatsapp_task,
                from_number=from_number,
                message=message,
                phone_number_id=phone_number_id,
            )

    except Exception as exc:
        log.error("webhook.whatsapp.parse_error", error=str(exc))

    return {"status": "ok"}


async def _dispatch_whatsapp_task(
    from_number: str,
    message: Dict[str, Any],
    phone_number_id: str,
) -> None:
    """Route the inbound message to the correct platform user and dispatch task.

    Lookup priority:
    1. Match ``phone_number_id`` → ``users.whatsapp_phone_number_id`` (multi-tenant)
    2. If no phone_number_id (legacy format) fall back to the single active user
       — acceptable for single-tenant / local dev deployments.
    """
    try:
        from models.base import AsyncSessionLocal
        from models.user import User
        from sqlalchemy import select

        async with AsyncSessionLocal() as session:
            user = None

            # ── Primary lookup: phone_number_id ──────────────────────────
            if phone_number_id:
                result = await session.execute(
                    select(User).where(
                        User.whatsapp_phone_number_id == phone_number_id,
                        User.is_active == True,
                    )
                )
                user = result.scalar_one_or_none()

            # ── Fallback: single-tenant / dev ────────────────────────────
            if user is None:
                result = await session.execute(
                    select(User).where(User.is_active == True).limit(1)
                )
                user = result.scalar_one_or_none()
                if phone_number_id:
                    log.warning(
                        "webhook.whatsapp.phone_number_id_unmatched",
                        phone_number_id=phone_number_id,
                        fallback_user=str(user.id) if user else None,
                    )

            if not user:
                log.error("webhook.whatsapp.no_active_user")
                return

            from workers.tasks import process_whatsapp_message
            process_whatsapp_message.delay(str(user.id), message)
            log.info("webhook.whatsapp.task_dispatched", user_id=str(user.id))

    except Exception as exc:
        log.error("webhook.whatsapp.dispatch_error", error=str(exc))


# ---------------------------------------------------------------------------
# Meta Graph API webhook
# ---------------------------------------------------------------------------

@router.get("/meta", status_code=status.HTTP_200_OK)
async def meta_webhook_verify(
    request: Request,
) -> Any:
    """Handle Meta webhook verification challenge.

    Meta sends a GET request with ``hub.mode``, ``hub.verify_token``,
    and ``hub.challenge`` parameters for initial webhook setup.
    """
    params = dict(request.query_params)
    mode = params.get("hub.mode")
    token = params.get("hub.verify_token")
    challenge = params.get("hub.challenge")

    # Use the app secret key as the verify token
    if mode == "subscribe" and token == settings.app_secret_key:
        log.info("webhook.meta.verified")
        from fastapi.responses import PlainTextResponse
        return PlainTextResponse(content=challenge or "")

    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Verification failed")


@router.post("/meta", status_code=status.HTTP_200_OK)
async def meta_webhook(
    request: Request,
    background_tasks: BackgroundTasks,
) -> Dict[str, str]:
    """Handle Meta Graph API webhook events.

    Processes:
    - ``feed`` entry changes: post published confirmations
    - ``mention`` changes: brand mentions
    - Instagram engagement events (likes, comments)

    Always returns 200 immediately; real work happens in background.
    """
    try:
        body = await request.json()
        object_type = body.get("object", "")
        entries = body.get("entry", [])

        for entry in entries:
            changes = entry.get("changes", [])
            for change in changes:
                field = change.get("field", "")
                value = change.get("value", {})
                log.info(
                    "webhook.meta.event",
                    object_type=object_type,
                    field=field,
                )
                # Dispatch background processing for engagement tracking
                if field in ("feed", "mention", "comments", "reactions"):
                    background_tasks.add_task(
                        _process_meta_event,
                        object_type=object_type,
                        field=field,
                        value=value,
                    )

    except Exception as exc:
        log.error("webhook.meta.parse_error", error=str(exc))

    return {"status": "ok"}


async def _process_meta_event(object_type: str, field: str, value: Dict[str, Any]) -> None:
    """Update engagement data for published content."""
    try:
        post_id = value.get("post_id") or value.get("media_id", "")
        if not post_id:
            return

        from models.base import AsyncSessionLocal
        from models.content import ContentDraft
        from sqlalchemy import select, update

        async with AsyncSessionLocal() as session:
            result = await session.execute(
                select(ContentDraft).where(ContentDraft.buffer_post_id == post_id)
            )
            draft = result.scalar_one_or_none()
            if draft:
                existing = dict(draft.engagement_data or {})
                existing[field] = value
                draft.engagement_data = existing
                await session.commit()
                log.info("webhook.meta.engagement_updated", post_id=post_id, field=field)

    except Exception as exc:
        log.error("webhook.meta.process_error", error=str(exc))


# ---------------------------------------------------------------------------
# Stripe webhook
# ---------------------------------------------------------------------------

@router.post("/stripe", status_code=status.HTTP_200_OK)
async def stripe_webhook(
    request: Request,
    background_tasks: BackgroundTasks,
    stripe_signature: str = Header(default="", alias="Stripe-Signature"),
) -> Dict[str, str]:
    """Handle Stripe billing webhook events.

    Verifies the Stripe-Signature header before processing.
    Handles:
    - ``customer.subscription.created``
    - ``customer.subscription.updated``
    - ``customer.subscription.deleted``
    - ``invoice.payment_succeeded``
    - ``invoice.payment_failed``
    """
    payload = await request.body()

    # Verify Stripe signature
    try:
        import stripe
        stripe.api_key = settings.stripe_secret_key
        event = stripe.Webhook.construct_event(
            payload=payload,
            sig_header=stripe_signature,
            secret=settings.stripe_webhook_secret,
        )
    except Exception as exc:
        log.error("webhook.stripe.signature_invalid", error=str(exc))
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid Stripe signature: {exc}",
        )

    event_type = event["type"]
    data_object = event["data"]["object"]

    log.info("webhook.stripe.event", type=event_type)

    background_tasks.add_task(_process_stripe_event, event_type, data_object)

    return {"status": "ok", "event_type": event_type}


async def _process_stripe_event(event_type: str, data: Dict[str, Any]) -> None:
    """Update user plan based on Stripe subscription events."""
    try:
        from models.base import AsyncSessionLocal
        from models.user import User
        from sqlalchemy import select, update

        customer_id = data.get("customer", "")
        if not customer_id:
            return

        async with AsyncSessionLocal() as session:
            result = await session.execute(
                select(User).where(User.stripe_customer_id == customer_id)
            )
            user = result.scalar_one_or_none()
            if not user:
                log.warning("webhook.stripe.user_not_found", customer_id=customer_id)
                return

            if event_type in ("customer.subscription.created", "customer.subscription.updated"):
                plan = data.get("items", {}).get("data", [{}])[0].get(
                    "price", {}
                ).get("lookup_key", "starter")
                user.plan = plan
                await session.commit()
                log.info(
                    "webhook.stripe.plan_updated",
                    user_id=str(user.id),
                    plan=plan,
                )

            elif event_type == "customer.subscription.deleted":
                user.plan = "starter"
                await session.commit()
                log.info("webhook.stripe.subscription_cancelled", user_id=str(user.id))

            elif event_type == "invoice.payment_failed":
                log.warning(
                    "webhook.stripe.payment_failed",
                    user_id=str(user.id),
                    customer_id=customer_id,
                )

    except Exception as exc:
        log.error("webhook.stripe.process_error", event_type=event_type, error=str(exc))
