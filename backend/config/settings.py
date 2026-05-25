"""Application settings loaded from environment variables."""
from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict

import yaml
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # App
    app_env: str = "development"
    app_secret_key: str = "change-me-in-production"
    frontend_url: str = "http://localhost:3000"

    # Anthropic
    anthropic_api_key: str = ""

    # OpenAI (embeddings + DALL-E)
    openai_api_key: str = ""

    # Pinecone
    pinecone_api_key: str = ""
    pinecone_index_name: str = "solo-agent-os"
    pinecone_environment: str = "us-east-1-aws"

    # PostgreSQL
    database_url: str = "postgresql://postgres:postgres@localhost:5432/soloagent"

    # Redis
    redis_url: str = "redis://localhost:6379/0"

    # Object storage — AWS S3 / Cloudflare R2 / MinIO / Garage
    # S3_PROVIDER controls behaviour for ACLs and URL building:
    #   "aws"    — AWS S3 (virtual-hosted URLs, ACL support)
    #   "r2"     — Cloudflare R2 (no ACL, virtual-hosted via custom domain)
    #   "minio"  — MinIO self-hosted (path-style, bucket-policy public access)
    #   "garage" — Garage self-hosted (path-style, no ACL header support)
    s3_provider: str = "minio"          # aws | r2 | minio | garage
    s3_bucket_name: str = "solo-agent-files"
    s3_region: str = "us-east-1"
    aws_access_key_id: str = ""
    aws_secret_access_key: str = ""
    s3_endpoint_url: str = "http://minio:9000"   # MinIO/Garage API endpoint
    # Base URL used to build public object links.
    # MinIO (direct):  http://localhost:9000/solo-agent-files
    # MinIO (nginx):   https://files.yourdomain.com
    # Garage web:      http://localhost:3902
    # Leave blank → auto-built from s3_endpoint_url or AWS/R2 pattern.
    s3_public_url_base: str = ""
    # Set False for local MinIO/Garage without TLS certificates
    s3_verify_ssl: bool = True

    # Gmail
    gmail_client_id: str = ""
    gmail_client_secret: str = ""
    gmail_redirect_uri: str = "http://localhost:8000/api/auth/gmail/callback"

    # WhatsApp (360dialog)
    whatsapp_api_key: str = ""
    whatsapp_api_url: str = "https://waba.360dialog.io/v1"

    # Meta Graph API
    meta_access_token: str = ""
    meta_page_id: str = ""
    meta_ig_user_id: str = ""

    # Buffer
    buffer_access_token: str = ""

    # Google Calendar
    google_calendar_client_id: str = ""
    google_calendar_client_secret: str = ""

    # Apify
    apify_api_token: str = ""

    # Tavily
    tavily_api_key: str = ""

    # Ideogram
    ideogram_api_key: str = ""

    # Stripe
    stripe_secret_key: str = ""
    stripe_webhook_secret: str = ""

    # Clerk
    clerk_secret_key: str = ""
    next_public_clerk_publishable_key: str = ""

    # LangSmith
    langchain_tracing_v2: bool = False
    langchain_api_key: str = ""
    langchain_project: str = "solo-agent-os"

    # Celery
    celery_broker_url: str = "redis://localhost:6379/0"
    celery_result_backend: str = "redis://localhost:6379/1"

    # Vertical
    vertical: str = "real_estate"

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "ignore"

    def load_vertical_config(self) -> Dict[str, Any]:
        """Load and return the YAML config for the current vertical."""
        # Resolve path relative to this file's parent (backend/config/) -> go up to backend -> config dir
        base_dir = Path(__file__).resolve().parent.parent.parent
        yaml_path = base_dir / "config" / "verticals" / f"{self.vertical}.yaml"
        if not yaml_path.exists():
            raise FileNotFoundError(
                f"Vertical config not found: {yaml_path}. "
                f"Valid verticals: real_estate, consultant, recruiter"
            )
        with open(yaml_path, "r", encoding="utf-8") as fh:
            return yaml.safe_load(fh)


@lru_cache()
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
