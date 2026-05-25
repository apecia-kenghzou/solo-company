"""Object storage tool — AWS S3 / Cloudflare R2 / MinIO / Garage.

All four backends share boto3's S3 API. The differences are:

┌──────────┬──────────────┬────────────────┬─────────┬──────────────────────┐
│ Provider │ Endpoint     │ Addressing     │ ACL     │ Public URL pattern   │
├──────────┼──────────────┼────────────────┼─────────┼──────────────────────┤
│ aws      │ (default)    │ virtual-hosted │ ✅ yes  │ bucket.s3.region.aws │
│ r2       │ custom HTTPS │ virtual-hosted │ ❌ no   │ custom domain        │
│ minio    │ custom HTTP  │ path-style     │ ⚠️  opt │ endpoint/bucket/key  │
│ garage   │ custom HTTP  │ path-style     │ ❌ no   │ web-endpoint/key     │
└──────────┴──────────────┴────────────────┴─────────┴──────────────────────┘

MinIO / Garage notes
--------------------
Both require **path-style addressing** (`bucket` in the URL path, not subdomain).
Neither supports per-object ACLs — public access is granted via **bucket policy**:

  # MinIO:
  docker exec -it solo-minio mc alias set local http://localhost:9000 minioadmin minioadmin
  docker exec -it solo-minio mc policy set download local/solo-agent-files

  # Garage (via garage CLI):
  garage bucket allow --read solo-agent-files --website

For local dev, ``S3_VERIFY_SSL=false`` skips certificate validation.
"""
from __future__ import annotations

import asyncio
import logging
import mimetypes
from typing import List, Optional

import boto3
from botocore.config import Config as BotocoreConfig
from botocore.exceptions import ClientError

from config.settings import settings

log = logging.getLogger(__name__)

# Providers that do NOT accept ACL headers at all (will raise NotImplemented)
_NO_ACL_PROVIDERS = {"r2", "garage"}
# Providers that require path-style addressing
_PATH_STYLE_PROVIDERS = {"minio", "garage"}


def _build_s3_client():
    """Build a boto3 S3 client configured for the active provider."""
    provider = settings.s3_provider.lower()

    # Addressing style
    addressing_style = "path" if provider in _PATH_STYLE_PROVIDERS else "auto"

    boto_config = BotocoreConfig(
        signature_version="s3v4",
        s3={"addressing_style": addressing_style},
    )

    kwargs = {
        "region_name": settings.s3_region,
        "aws_access_key_id": settings.aws_access_key_id,
        "aws_secret_access_key": settings.aws_secret_access_key,
        "config": boto_config,
    }

    if settings.s3_endpoint_url:
        kwargs["endpoint_url"] = settings.s3_endpoint_url

    # SSL verification — disable for local MinIO/Garage without certs
    if not settings.s3_verify_ssl:
        import urllib3
        urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
        kwargs["verify"] = False

    return boto3.client("s3", **kwargs)


class StorageTool:
    """Async-friendly wrapper around boto3 for S3-compatible object storage.

    Supports AWS S3, Cloudflare R2, MinIO, and Garage out of the box.
    Select provider via ``S3_PROVIDER`` environment variable.

    Usage::

        from tools.s3 import storage
        url = await storage.upload_file(file_bytes, "listings/abc/photo.jpg")
    """

    def __init__(self) -> None:
        self._client = _build_s3_client()
        self._bucket = settings.s3_bucket_name
        self._provider = settings.s3_provider.lower()

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    async def _run(self, func, *args, **kwargs):
        """Run a blocking boto3 call in a thread-pool executor."""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, lambda: func(*args, **kwargs))

    def _extra_args(self, content_type: str) -> dict:
        """Build ExtraArgs for put_object / upload_fileobj.

        ACL is omitted for providers that don't support it (R2, Garage).
        For MinIO, ACL is also omitted by default — use bucket policy instead.
        """
        args: dict = {"ContentType": content_type}
        if self._provider == "aws":
            # Only AWS S3 gets per-object ACLs
            args["ACL"] = "public-read"
        return args

    def _public_url(self, key: str) -> str:
        """Build the public URL for an object key.

        Resolution order:
        1. ``S3_PUBLIC_URL_BASE`` — explicit override (e.g. nginx in front of MinIO)
        2. Endpoint-relative path (MinIO / Garage / R2 with custom endpoint)
        3. AWS S3 virtual-hosted pattern
        """
        # ── Explicit override ────────────────────────────────────────────
        if settings.s3_public_url_base:
            base = settings.s3_public_url_base.rstrip("/")
            return f"{base}/{key}"

        # ── Endpoint-relative (MinIO, Garage, R2) ───────────────────────
        if settings.s3_endpoint_url:
            endpoint = settings.s3_endpoint_url.rstrip("/")
            if self._provider == "garage":
                # Garage web endpoint serves files at /key (no bucket in URL)
                return f"{endpoint}/{key}"
            # MinIO / R2 — path-style: endpoint/bucket/key
            return f"{endpoint}/{self._bucket}/{key}"

        # ── AWS S3 virtual-hosted ────────────────────────────────────────
        region = settings.s3_region
        return f"https://{self._bucket}.s3.{region}.amazonaws.com/{key}"

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def upload_file(
        self,
        file_bytes: bytes,
        key: str,
        content_type: Optional[str] = None,
    ) -> str:
        """Upload *file_bytes* to object storage at *key*.

        Args:
            file_bytes: Raw file content.
            key: Object key / path (e.g. ``"listings/abc123/photo.jpg"``).
            content_type: MIME type; auto-detected from key extension if omitted.

        Returns:
            Public URL string for the uploaded object.

        Note:
            For MinIO and Garage, the bucket must have a public-read policy set
            separately (see module docstring). The URL returned will only be
            publicly accessible after that policy is applied.
        """
        if content_type is None:
            guessed, _ = mimetypes.guess_type(key)
            content_type = guessed or "application/octet-stream"

        extra = self._extra_args(content_type)

        log.debug(
            "s3.upload",
            provider=self._provider,
            bucket=self._bucket,
            key=key,
            size=len(file_bytes),
        )

        await self._run(
            self._client.put_object,
            Bucket=self._bucket,
            Key=key,
            Body=file_bytes,
            **extra,
        )

        url = self._public_url(key)
        log.debug("s3.upload.done", url=url)
        return url

    async def upload_file_obj(
        self,
        file_obj,
        key: str,
        content_type: Optional[str] = None,
    ) -> str:
        """Stream a file-like object to object storage.

        Useful for large files — avoids loading everything into memory.

        Args:
            file_obj: Any file-like object with a ``read()`` method.
            key: Object key / path.
            content_type: MIME type; auto-detected if omitted.

        Returns:
            Public URL string.
        """
        if content_type is None:
            guessed, _ = mimetypes.guess_type(key)
            content_type = guessed or "application/octet-stream"

        extra = self._extra_args(content_type)

        log.debug("s3.upload_fileobj", provider=self._provider, key=key)

        await self._run(
            self._client.upload_fileobj,
            file_obj,
            self._bucket,
            key,
            ExtraArgs=extra,
        )

        return self._public_url(key)

    async def delete_file(self, key: str) -> bool:
        """Delete an object from storage.

        Returns:
            ``True`` on success, ``False`` if the object was not found.
        """
        try:
            await self._run(
                self._client.delete_object,
                Bucket=self._bucket,
                Key=key,
            )
            log.debug("s3.delete", bucket=self._bucket, key=key)
            return True
        except ClientError as exc:
            code = exc.response["Error"]["Code"]
            if code in ("NoSuchKey", "404"):
                log.warning("s3.delete.not_found", key=key)
                return False
            raise

    async def get_presigned_url(self, key: str, expiry: int = 3600) -> str:
        """Generate a pre-signed URL for temporary private access.

        Works with all providers including MinIO and Garage.

        Args:
            key: Object key.
            expiry: Expiry in seconds (default 1 hour).

        Returns:
            Pre-signed URL string. Note: for local MinIO/Garage, the hostname
            in the URL will be the *internal* Docker hostname unless
            ``S3_PUBLIC_URL_BASE`` is set to the externally accessible address.
        """
        url: str = await self._run(
            self._client.generate_presigned_url,
            "get_object",
            Params={"Bucket": self._bucket, "Key": key},
            ExpiresIn=expiry,
        )

        # Rewrite internal Docker hostname to external address if configured
        if settings.s3_public_url_base and settings.s3_endpoint_url:
            internal = settings.s3_endpoint_url.rstrip("/")
            external = settings.s3_public_url_base.rstrip("/")
            url = url.replace(internal, external, 1)

        return url

    async def list_files(self, prefix: str) -> List[str]:
        """List all object keys under *prefix*.

        Returns:
            List of object key strings.
        """
        def _list():
            paginator = self._client.get_paginator("list_objects_v2")
            pages = paginator.paginate(Bucket=self._bucket, Prefix=prefix)
            keys: List[str] = []
            for page in pages:
                for obj in page.get("Contents", []):
                    keys.append(obj["Key"])
            return keys

        return await self._run(_list)

    async def ensure_bucket(self) -> None:
        """Create the configured bucket if it does not exist.

        Safe to call on startup — no-ops if the bucket already exists.
        Useful for MinIO / Garage where buckets must be created before first use.
        """
        try:
            await self._run(self._client.head_bucket, Bucket=self._bucket)
            log.debug("s3.ensure_bucket.exists", bucket=self._bucket)
        except ClientError as exc:
            code = exc.response["Error"]["Code"]
            if code in ("404", "NoSuchBucket"):
                log.info("s3.ensure_bucket.creating", bucket=self._bucket)
                create_kwargs: dict = {"Bucket": self._bucket}
                # AWS requires LocationConstraint for non-us-east-1 regions
                if self._provider == "aws" and settings.s3_region != "us-east-1":
                    create_kwargs["CreateBucketConfiguration"] = {
                        "LocationConstraint": settings.s3_region
                    }
                await self._run(self._client.create_bucket, **create_kwargs)
                log.info("s3.ensure_bucket.created", bucket=self._bucket)
            else:
                raise


# ---------------------------------------------------------------------------
# Module-level singleton
# ---------------------------------------------------------------------------
storage = StorageTool()
