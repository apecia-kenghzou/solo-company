"""Celery tasks for the Solo Agent OS background worker."""
from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import List, Optional
from uuid import UUID

from workers.celery_app import celery_app

log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Helper — get a synchronous DB session inside a Celery task
# (Celery tasks run in a synchronous context; we use asyncio.run where needed)
# ---------------------------------------------------------------------------

def _get_sync_session():
    """Return a synchronous SQLAlchemy session for use inside Celery tasks."""
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from config.settings import settings

    engine = create_engine(settings.database_url, pool_pre_ping=True)
    Session = sessionmaker(bind=engine, expire_on_commit=False)
    return Session()


def _get_redis():
    """Return a synchronous Redis connection."""
    import redis
    from config.settings import settings

    return redis.from_url(settings.redis_url, decode_responses=True)


# ---------------------------------------------------------------------------
# Tasks
# ---------------------------------------------------------------------------

@celery_app.task(name="workers.tasks.generate_morning_briefing", bind=True, max_retries=3)
def generate_morning_briefing(self, user_id: Optional[str] = None) -> dict:
    """Generate a morning briefing for one or all active users.

    Collects:
    - Leads needing follow-up today
    - Pending content approvals count
    - Agent actions from the last 24 hours

    Stores the briefing in Redis under ``briefing:{user_id}:{date}``
    and triggers a summary email via Gmail.

    Args:
        user_id: If provided, generate for this user only; otherwise all
                 active users.
    """
    from sqlalchemy import and_, func, select
    from models.user import User
    from models.lead import Lead
    from models.content import AgentAction, ContentDraft
    from config.settings import settings
    import asyncio

    session = _get_sync_session()
    r = _get_redis()

    try:
        # Resolve target users
        if user_id:
            users = session.execute(
                select(User).where(User.id == UUID(user_id), User.is_active == True)
            ).scalars().all()
        else:
            users = session.execute(
                select(User).where(User.is_active == True)
            ).scalars().all()

        today = datetime.now(timezone.utc)
        today_str = today.strftime("%Y-%m-%d")

        results = []
        for user in users:
            uid = str(user.id)

            # Leads due for follow-up today
            leads_due = session.execute(
                select(Lead).where(
                    and_(
                        Lead.user_id == user.id,
                        Lead.next_follow_up_at <= today,
                        Lead.status.notin_(["closed", "lost"]),
                    )
                )
            ).scalars().all()

            # Pending content approvals
            pending_approvals = session.execute(
                select(func.count()).select_from(ContentDraft).where(
                    and_(
                        ContentDraft.user_id == user.id,
                        ContentDraft.status == "pending_approval",
                    )
                )
            ).scalar() or 0

            # Recent agent actions (last 24h)
            from datetime import timedelta
            yesterday = today - timedelta(hours=24)
            recent_actions = session.execute(
                select(AgentAction).where(
                    and_(
                        AgentAction.user_id == user.id,
                        AgentAction.created_at >= yesterday,
                    )
                ).order_by(AgentAction.created_at.desc()).limit(10)
            ).scalars().all()

            briefing = {
                "user_id": uid,
                "user_name": user.full_name,
                "date": today_str,
                "generated_at": today.isoformat(),
                "leads_to_follow_up": [
                    {
                        "id": str(lead.id),
                        "name": lead.name,
                        "phone": lead.phone,
                        "status": lead.status,
                        "temperature": lead.temperature,
                        "next_follow_up_at": (
                            lead.next_follow_up_at.isoformat()
                            if lead.next_follow_up_at
                            else None
                        ),
                    }
                    for lead in leads_due
                ],
                "pending_approvals_count": pending_approvals,
                "recent_agent_actions": [
                    {
                        "id": str(action.id),
                        "agent": action.agent_name,
                        "type": action.action_type,
                        "status": action.status,
                        "created_at": action.created_at.isoformat(),
                    }
                    for action in recent_actions
                ],
            }

            # Store in Redis for 24 hours
            redis_key = f"briefing:{uid}:{today_str}"
            r.setex(redis_key, 86400, json.dumps(briefing))
            log.info("briefing.stored", user_id=uid, key=redis_key)

            # Trigger email summary (async task)
            _send_briefing_email.delay(uid, briefing)

            results.append({"user_id": uid, "leads_due": len(leads_due)})

        return {"status": "ok", "users_processed": len(results), "results": results}

    except Exception as exc:
        log.error("briefing.error", error=str(exc))
        raise self.retry(exc=exc, countdown=60)
    finally:
        session.close()
        r.close()


@celery_app.task(name="workers.tasks._send_briefing_email", bind=True, max_retries=3)
def _send_briefing_email(self, user_id: str, briefing: dict) -> None:
    """Send the morning briefing as an email summary via Gmail."""
    import asyncio

    async def _async_send():
        from tools.gmail import GmailTool
        from sqlalchemy import select
        from models.user import User

        session = _get_sync_session()
        try:
            user = session.execute(
                select(User).where(User.id == UUID(user_id))
            ).scalar_one_or_none()
            if not user or not user.email:
                return

            leads_count = len(briefing.get("leads_to_follow_up", []))
            approvals = briefing.get("pending_approvals_count", 0)
            date_str = briefing.get("date", "")

            subject = f"[Solo Agent OS] Your Morning Briefing — {date_str}"
            body_lines = [
                f"Good morning, {user.full_name}!",
                "",
                f"Here is your briefing for {date_str}:",
                "",
                f"  Leads to follow up today:  {leads_count}",
                f"  Pending content approvals: {approvals}",
                "",
            ]

            if briefing.get("leads_to_follow_up"):
                body_lines.append("Leads needing your attention:")
                for lead in briefing["leads_to_follow_up"][:5]:
                    body_lines.append(
                        f"  • {lead['name'] or 'Unknown'} ({lead['status']}, {lead['temperature']})"
                    )
                body_lines.append("")

            body_lines.append("Visit your dashboard for the full picture.")
            body_lines.append("https://app.soloagent.os")

            gmail = GmailTool()
            await gmail.send_message(
                user_id=user_id,
                to=user.email,
                subject=subject,
                body="\n".join(body_lines),
            )
            log.info("briefing.email_sent", user_id=user_id, to=user.email)
        finally:
            session.close()

    try:
        asyncio.run(_async_send())
    except Exception as exc:
        log.warning("briefing.email_failed", user_id=user_id, error=str(exc))
        # Non-critical — do not retry the email if Gmail creds are missing


@celery_app.task(name="workers.tasks.run_social_trend_scan", bind=True, max_retries=3)
def run_social_trend_scan(self, user_id: Optional[str] = None) -> dict:
    """Scrape TikTok and Instagram trends, store in DB, update the KB.

    Args:
        user_id: If provided, use this user's vertical config; otherwise
                 uses the default vertical from settings.
    """
    import asyncio
    from config.settings import settings

    async def _async_scan():
        from tools.apify import ApifyTool
        from sqlalchemy.orm import Session

        # Load vertical config to get topics
        vertical_config = settings.load_vertical_config()
        social_config = vertical_config.get("social_trend_agent", {})
        topics = social_config.get("topics", ["real estate", "property"])

        apify = ApifyTool()

        tiktok_results = []
        ig_results = []

        try:
            tiktok_results = await apify.get_tiktok_trending(topics, max_results=20)
            log.info("trends.tiktok_fetched", count=len(tiktok_results))
        except Exception as exc:
            log.warning("trends.tiktok_failed", error=str(exc))

        try:
            ig_results = await apify.get_instagram_reels_trends(topics, max_results=20)
            log.info("trends.instagram_fetched", count=len(ig_results))
        except Exception as exc:
            log.warning("trends.instagram_failed", error=str(exc))

        # Store raw trend data in Redis for agent consumption
        r = _get_redis()
        today_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        r.setex(
            f"trends:tiktok:{today_str}",
            86400 * 7,
            json.dumps(tiktok_results),
        )
        r.setex(
            f"trends:instagram:{today_str}",
            86400 * 7,
            json.dumps(ig_results),
        )
        r.close()

        return {
            "tiktok_count": len(tiktok_results),
            "instagram_count": len(ig_results),
            "date": today_str,
        }

    try:
        result = asyncio.run(_async_scan())
        return {"status": "ok", **result}
    except Exception as exc:
        log.error("social_scan.error", error=str(exc))
        raise self.retry(exc=exc, countdown=300)


@celery_app.task(name="workers.tasks.run_market_intelligence", bind=True, max_retries=3)
def run_market_intelligence(self, user_id: Optional[str] = None) -> dict:
    """Run Tavily market research and store the report in Redis + update KB.

    Args:
        user_id: Optional user for context; uses default vertical otherwise.
    """
    import asyncio
    from config.settings import settings

    async def _async_research():
        from tools.tavily import TavilyTool

        vertical_config = settings.load_vertical_config()
        vertical = vertical_config.get("vertical", "real_estate")

        queries = {
            "real_estate": [
                "Malaysia property market latest news 2025",
                "Kuala Lumpur real estate trends 2025",
                "Malaysian housing price index 2025",
            ],
            "consultant": [
                "freelance consulting market trends 2025",
                "business consulting demand 2025",
            ],
            "recruiter": [
                "Malaysia job market trends 2025",
                "hiring trends Southeast Asia 2025",
            ],
        }

        search_queries = queries.get(vertical, queries["real_estate"])
        tavily = TavilyTool()
        all_results = []

        for query in search_queries:
            try:
                results = await tavily.search(query, max_results=5, search_depth="advanced")
                all_results.extend(results)
                log.info("market_intel.searched", query=query, hits=len(results))
            except Exception as exc:
                log.warning("market_intel.search_failed", query=query, error=str(exc))

        report = {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "vertical": vertical,
            "article_count": len(all_results),
            "articles": all_results[:20],
        }

        r = _get_redis()
        week_str = datetime.now(timezone.utc).strftime("%Y-W%W")
        r.setex(f"market_report:{week_str}", 86400 * 8, json.dumps(report))
        r.close()

        return report

    try:
        report = asyncio.run(_async_research())
        return {"status": "ok", "articles": report["article_count"]}
    except Exception as exc:
        log.error("market_intel.error", error=str(exc))
        raise self.retry(exc=exc, countdown=600)


@celery_app.task(name="workers.tasks.check_follow_up_queue", bind=True, max_retries=2)
def check_follow_up_queue(self) -> dict:
    """Query leads due for follow-up and dispatch individual follow-up tasks."""
    from sqlalchemy import and_, select
    from models.lead import Lead

    session = _get_sync_session()
    try:
        now = datetime.now(timezone.utc)
        due_leads = session.execute(
            select(Lead).where(
                and_(
                    Lead.next_follow_up_at <= now,
                    Lead.status.notin_(["closed", "lost"]),
                )
            ).limit(100)
        ).scalars().all()

        dispatched = 0
        for lead in due_leads:
            send_follow_up_message.delay(str(lead.id))
            dispatched += 1

        log.info("follow_up_queue.dispatched", count=dispatched)
        return {"status": "ok", "dispatched": dispatched}
    except Exception as exc:
        log.error("follow_up_queue.error", error=str(exc))
        raise self.retry(exc=exc, countdown=120)
    finally:
        session.close()


@celery_app.task(name="workers.tasks.send_follow_up_message", bind=True, max_retries=3)
def send_follow_up_message(self, lead_id: str) -> dict:
    """Load a lead, run the follow-up agent, and update the lead record.

    Args:
        lead_id: UUID string of the lead to follow up with.
    """
    import asyncio
    from sqlalchemy import select, update
    from models.lead import Lead
    from models.listing import Listing
    from datetime import timedelta

    session = _get_sync_session()
    try:
        lead = session.execute(
            select(Lead).where(Lead.id == UUID(lead_id))
        ).scalar_one_or_none()

        if not lead:
            log.warning("follow_up.lead_not_found", lead_id=lead_id)
            return {"status": "skipped", "reason": "lead_not_found"}

        listing = None
        if lead.listing_id:
            listing = session.execute(
                select(Listing).where(Listing.id == lead.listing_id)
            ).scalar_one_or_none()

        # Determine next follow-up interval based on vertical config
        from config.settings import settings
        vertical_config = settings.load_vertical_config()
        fu_config = vertical_config.get("follow_up_agent", {})
        sequences = fu_config.get("sequences", {})

        temperature = lead.temperature or "cold"
        if temperature == "hot":
            days_seq = sequences.get("warm_lead", [1, 3, 7])
        elif temperature == "warm":
            days_seq = sequences.get("warm_lead", [1, 3, 7])
        else:
            days_seq = sequences.get("cold_lead", [1, 3, 7, 30])

        count = lead.follow_up_count or 0
        next_days = days_seq[count] if count < len(days_seq) else days_seq[-1]

        now = datetime.now(timezone.utc)

        # Compose and send WhatsApp message
        async def _send():
            from tools.whatsapp import WhatsAppTool
            wa = WhatsAppTool()

            listing_name = listing.name if listing else "the property"
            lead_name = lead.name or "there"

            message = (
                f"Hi {lead_name}! Just checking in regarding {listing_name}. "
                f"Have you had a chance to consider it? "
                f"I'm here to help if you have any questions. \U0001f3e0"
            )

            if lead.phone:
                await wa.send_text(to=lead.phone, body=message)
                return True
            return False

        sent = False
        try:
            sent = asyncio.run(_send())
        except Exception as exc:
            log.warning("follow_up.send_failed", lead_id=lead_id, error=str(exc))

        # Update lead record
        session.execute(
            update(Lead)
            .where(Lead.id == UUID(lead_id))
            .values(
                follow_up_count=count + 1,
                last_contacted_at=now,
                next_follow_up_at=now + timedelta(days=next_days),
            )
        )
        session.commit()

        log.info(
            "follow_up.sent",
            lead_id=lead_id,
            sent=sent,
            next_follow_up_days=next_days,
        )
        return {"status": "ok", "sent": sent, "next_follow_up_days": next_days}

    except Exception as exc:
        session.rollback()
        log.error("follow_up.error", lead_id=lead_id, error=str(exc))
        raise self.retry(exc=exc, countdown=300)
    finally:
        session.close()


@celery_app.task(name="workers.tasks.index_listing_to_kb", bind=True, max_retries=3)
def index_listing_to_kb(self, listing_id: str) -> dict:
    """Embed a listing into the Pinecone knowledge base.

    Args:
        listing_id: UUID string of the listing to index.
    """
    import asyncio
    from sqlalchemy import select, update
    from models.listing import Listing

    session = _get_sync_session()
    try:
        listing = session.execute(
            select(Listing).where(Listing.id == UUID(listing_id))
        ).scalar_one_or_none()

        if not listing:
            return {"status": "skipped", "reason": "listing_not_found"}

        async def _index():
            from knowledge.kb_writer import KBWriter
            writer = KBWriter()
            await writer.index_listing(listing)

        asyncio.run(_index())

        session.execute(
            update(Listing).where(Listing.id == UUID(listing_id)).values(kb_indexed=True)
        )
        session.commit()

        log.info("kb.listing_indexed", listing_id=listing_id, name=listing.name)
        return {"status": "ok", "listing_id": listing_id}

    except Exception as exc:
        session.rollback()
        log.error("kb.index_error", listing_id=listing_id, error=str(exc))
        raise self.retry(exc=exc, countdown=120)
    finally:
        session.close()


@celery_app.task(name="workers.tasks.run_property_research", bind=True, max_retries=3)
def run_property_research(self, listing_id: str) -> dict:
    """Research a property's location/market and enrich the KB.

    Uses Tavily to search for:
    - Recent news about the property/development
    - Area price trends
    - Nearby infrastructure developments

    Args:
        listing_id: UUID string of the listing to research.
    """
    import asyncio
    from sqlalchemy import select
    from models.listing import Listing

    session = _get_sync_session()
    try:
        listing = session.execute(
            select(Listing).where(Listing.id == UUID(listing_id))
        ).scalar_one_or_none()

        if not listing:
            return {"status": "skipped", "reason": "listing_not_found"}

        async def _research():
            from tools.tavily import TavilyTool
            from knowledge.kb_writer import KBWriter

            tavily = TavilyTool()
            queries = [
                f"{listing.name} property Malaysia",
                f"{listing.address} real estate price trend",
                f"{listing.developer or listing.name} developer news",
            ]

            all_context = []
            for query in queries:
                ctx = await tavily.search_context(query, max_results=3)
                all_context.append(ctx)

            enriched_text = "\n\n---\n\n".join(all_context)

            # Write research findings to KB
            writer = KBWriter()
            await writer.index_document(
                doc_id=f"research:listing:{listing_id}",
                text=enriched_text,
                metadata={
                    "type": "property_research",
                    "listing_id": listing_id,
                    "listing_name": listing.name,
                    "address": listing.address,
                },
                namespace="research",
            )
            return len(all_context)

        query_count = asyncio.run(_research())
        log.info("research.completed", listing_id=listing_id, queries=query_count)
        return {"status": "ok", "listing_id": listing_id, "queries_run": query_count}

    except Exception as exc:
        session.rollback()
        log.error("research.error", listing_id=listing_id, error=str(exc))
        raise self.retry(exc=exc, countdown=300)
    finally:
        session.close()


@celery_app.task(name="workers.tasks.run_marketing_week", bind=True, max_retries=3)
def run_marketing_week(self, user_id: str) -> dict:
    """Run the full marketing graph to generate a week of content drafts."""
    try:
        from agents.graphs.marketing import marketing_graph
        from models.user import User
        from sqlalchemy import select
        import asyncio

        session = _get_sync_session()
        user = session.execute(select(User).where(User.id == UUID(user_id))).scalar_one_or_none()
        session.close()
        if not user:
            return {"error": "user_not_found"}

        # Load trend data from KB
        # Run for each active listing
        from models.listing import Listing
        session = _get_sync_session()
        listings = session.execute(
            select(Listing).where(Listing.user_id == UUID(user_id), Listing.status == "active")
        ).scalars().all()
        listing_data = [{"id": str(l.id), "name": l.name, "address": l.address} for l in listings]
        session.close()

        initial_state = {
            "user_id": user_id,
            "listing_id": listing_data[0]["id"] if listing_data else None,
            "trend_data": [],
            "content_plan": [],
            "current_post": {},
            "caption": "",
            "image_url": None,
            "hashtags": [],
            "scheduled": False,
            "approval_required": True,
            "draft_id": None,
            "messages": [],
        }

        marketing_graph.invoke(initial_state)
        return {"status": "complete", "user_id": user_id}

    except Exception as exc:
        log.error("run_marketing_week.error", user_id=user_id, error=str(exc))
        raise self.retry(exc=exc, countdown=60)


# ---------------------------------------------------------------------------
# Webhook-triggered tasks (dispatched from API routers)
# ---------------------------------------------------------------------------

@celery_app.task(name="workers.tasks.process_inbound_email", bind=True, max_retries=3)
def process_inbound_email(self, user_id: str, message_id: str) -> dict:
    """Process an inbound Gmail message through the InboxAgent.

    Args:
        user_id: Platform user ID.
        message_id: Gmail message ID to fetch and process.
    """
    import asyncio

    async def _process():
        from tools.gmail import GmailTool
        gmail = GmailTool()
        message = await gmail.get_message(user_id=user_id, message_id=message_id)
        log.info(
            "inbox.email_received",
            user_id=user_id,
            subject=message.get("subject", ""),
            from_=message.get("from", ""),
        )
        # TODO: route through InboxAgent graph node (M3)
        return {"user_id": user_id, "message_id": message_id, "subject": message.get("subject")}

    try:
        return asyncio.run(_process())
    except Exception as exc:
        log.error("inbox.email_error", user_id=user_id, message_id=message_id, error=str(exc))
        raise self.retry(exc=exc, countdown=60)


@celery_app.task(name="workers.tasks.process_whatsapp_message", bind=True, max_retries=3)
def process_whatsapp_message(self, user_id: str, message_data: dict) -> dict:
    """Process an inbound WhatsApp message through the Front Desk LangGraph.

    1. Extracts text content from the Meta Cloud API message payload.
    2. Looks up the lead by phone number (creates one if new).
    3. Routes through the FrontDeskGraph (intake → chat/email_reply → booking/escalation).

    Args:
        user_id: Platform user ID.
        message_data: Meta Cloud API ``messages[0]`` object from the webhook.
    """
    from tools.whatsapp import WhatsAppTool
    from sqlalchemy import select
    from models.lead import Lead

    from_number = message_data.get("from", "")
    msg_type = message_data.get("type", "unknown")
    msg_id = message_data.get("id", "")

    log.info(
        "inbox.whatsapp_received",
        user_id=user_id,
        from_=from_number,
        type_=msg_type,
        msg_id=msg_id,
    )

    # ── Extract human-readable text from any message type ────────────────
    text_body = WhatsAppTool.extract_text_body(message_data)

    if not text_body:
        log.info("inbox.whatsapp_received.empty_body — skipping", msg_type=msg_type)
        return {"status": "skipped", "reason": "empty_body"}

    # ── Look up or create lead ────────────────────────────────────────────
    session = _get_sync_session()
    try:
        result = session.execute(
            select(Lead).where(
                Lead.user_id == UUID(user_id),
                Lead.phone == from_number,
            )
        )
        lead = result.scalar_one_or_none()

        if lead is None:
            lead = Lead(
                user_id=UUID(user_id),
                phone=from_number,
                source="whatsapp",
                status="new",
                temperature="cold",
                conversation_history=[],
            )
            session.add(lead)
            session.commit()
            session.refresh(lead)
            log.info("inbox.whatsapp.new_lead_created", lead_id=str(lead.id), phone=from_number)

        lead_id = str(lead.id)
        lead_data = {
            "name": lead.name or "",
            "phone": lead.phone or "",
            "email": lead.email or "",
            "property_interest": lead.property_type_interest or "",
            "budget_min": str(lead.budget_min or ""),
            "budget_max": str(lead.budget_max or ""),
            "timeline": lead.timeline or "",
            "follow_up_count": lead.follow_up_count,
            "conversation_history": lead.conversation_history or [],
            "whatsapp_message_id": msg_id,  # for mark_read in chat node
        }
    finally:
        session.close()

    # ── Route through FrontDeskGraph ──────────────────────────────────────
    try:
        from agents.graphs.front_desk import front_desk_graph

        initial_state = {
            "user_id": user_id,
            "lead_id": lead_id,
            "listing_id": lead_data.get("listing_id"),
            "inbound_message": text_body,
            "channel": "whatsapp",
            "lead_data": lead_data,
            "classification": "",
            "kb_context": "",
            "draft_reply": "",
            "reply_sent": False,
            "escalate": False,
            "escalation_reason": "",
            "follow_up_scheduled": False,
            "viewing_booked": False,
            "messages": [],
        }

        result_state = front_desk_graph.invoke(initial_state)
        log.info(
            "inbox.whatsapp.graph_complete",
            user_id=user_id,
            lead_id=lead_id,
            reply_sent=result_state.get("reply_sent"),
            escalated=result_state.get("escalate"),
        )
        return {
            "status": "processed",
            "lead_id": lead_id,
            "reply_sent": result_state.get("reply_sent"),
            "escalated": result_state.get("escalate"),
        }

    except Exception as exc:
        log.error("inbox.whatsapp.graph_error", user_id=user_id, lead_id=lead_id, error=str(exc))
        raise self.retry(exc=exc, countdown=30)
