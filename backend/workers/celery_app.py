"""Celery application configuration and beat schedule."""
from __future__ import annotations

from celery import Celery
from celery.schedules import crontab

from config.settings import settings

# ---------------------------------------------------------------------------
# Application
# ---------------------------------------------------------------------------

celery_app = Celery(
    "solo_agent_os",
    broker=settings.celery_broker_url,
    backend=settings.celery_result_backend,
    include=["workers.tasks"],
)

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="Asia/Kuala_Lumpur",
    enable_utc=True,
    task_track_started=True,
    task_acks_late=True,
    worker_prefetch_multiplier=1,
    result_expires=86400,  # 24 hours
    # Beat schedule
    beat_schedule={
        # Daily morning briefing at 07:00 KL time
        "morning-briefing": {
            "task": "workers.tasks.generate_morning_briefing",
            "schedule": crontab(hour=7, minute=0),
            "args": (),
            "kwargs": {},
            "options": {"expires": 3600},
        },
        # Daily social trend scan at 09:00 KL time
        "daily-social-trend-scan": {
            "task": "workers.tasks.run_social_trend_scan",
            "schedule": crontab(hour=9, minute=0),
            "args": (),
            "kwargs": {},
            "options": {"expires": 3600},
        },
        # Weekly market intelligence report — every Monday 08:00 KL
        "weekly-market-report": {
            "task": "workers.tasks.run_market_intelligence",
            "schedule": crontab(hour=8, minute=0, day_of_week="monday"),
            "args": (),
            "kwargs": {},
            "options": {"expires": 7200},
        },
        # Hourly lead follow-up queue check
        "lead-follow-up-check": {
            "task": "workers.tasks.check_follow_up_queue",
            "schedule": crontab(minute=0),  # top of every hour
            "args": (),
            "kwargs": {},
            "options": {"expires": 3540},
        },
    },
)

# ---------------------------------------------------------------------------
# Expose app at module level (required for Celery CLI: -A workers.celery_app)
# ---------------------------------------------------------------------------
app = celery_app
