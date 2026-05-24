"""S3 / Cloudflare R2 storage tool."""
from __future__ import annotations

import asyncio
import logging
import mimetypes
from typing import List, Optional

import boto3
from botocore.exceptions import ClientError

from config.settings import settings

log = logging.getLogger(__name__)


class StorageTool:
    """Async-friendly wrapper around boto3 for S3 / Cloudflare R2."""

    def __init__(self) -> None:
        kwargs = {
            "region_name": settings.s3_region,
            "aws_access_key_id": settings.aws_access_key_id,
            "aws_secret_access_key": settings.aws_secret_access_key,
        }
        if settings.s3_endpoint_url:
            kwargs["endpoint_url"] = settings.s3_endpoint_url

        self._client = boto3.client("s3", **kwargs)
        self._bucket = settings.s3_bucket_name

    # ------------------------------------------------------------------
    # Internal helper — run blocking boto3 calls in threadpool
    # ------------------------------------------------------------------

    async def _run(self, func, *args, **kwargs):
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, lambda: func(*args, **kwargs))

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def upload_file(
        self,
        file_bytes: bytes,
        key: str,
        content_type: Optional[str] = None,
    ) -> str:
        """Upload *file_bytes* to S3 at *key* and return the public URL.

        Args:
            file_bytes: Raw file content.
            key: S3 object key (path), e.g. ``"listings/abc123/photo.jpg"``.
            content_type: MIME type; auto-detected from key extension if omitted.

        Returns:
            Public URL string for the uploaded object.
        """
        if content_type is None:
            guessed, _ = mimetypes.guess_type(key)
            content_type = guessed or "application/octet-stream"

        extra_args = {
            "ContentType": content_type,
            "ACL": "public-read",
        }

        log.debug("s3.upload", bucket=self._bucket, key=key, size=len(file_bytes))

        await self._run(
            self._client.put_object,
            Bucket=self._bucket,
            Key=key,
            Body=file_bytes,
            **extra_args,
        )

        return self._public_url(key)

    async def delete_file(self, key: str) -> bool:
        """Delete an object from S3.

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
            error_code = exc.response["Error"]["Code"]
            if error_code == "NoSuchKey":
                log.warning("s3.delete.not_found", key=key)
                return False
            raise

    async def get_presigned_url(self, key: str, expiry: int = 3600) -> str:
        """Generate a pre-signed URL for temporary private access.

        Args:
            key: S3 object key.
            expiry: Expiry in seconds (default 1 hour).

        Returns:
            Pre-signed URL string.
        """
        url = await self._run(
            self._client.generate_presigned_url,
            "get_object",
            Params={"Bucket": self._bucket, "Key": key},
            ExpiresIn=expiry,
        )
        return url

    async def list_files(self, prefix: str) -> List[str]:
        """List all object keys under *prefix*.

        Returns:
            List of S3 object key strings.
        """
        def _list():
            paginator = self._client.get_paginator("list_objects_v2")
            pages = paginator.paginate(Bucket=self._bucket, Prefix=prefix)
            keys = []
            for page in pages:
                for obj in page.get("Contents", []):
                    keys.append(obj["Key"])
            return keys

        return await self._run(_list)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _public_url(self, key: str) -> str:
        """Build the public URL for a given key."""
        if settings.s3_endpoint_url:
            # Cloudflare R2 public bucket URL pattern
            endpoint = settings.s3_endpoint_url.rstrip("/")
            return f"{endpoint}/{self._bucket}/{key}"
        region = settings.s3_region
        return f"https://{self._bucket}.s3.{region}.amazonaws.com/{key}"
