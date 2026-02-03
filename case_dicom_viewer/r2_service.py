"""
Cloudflare R2 storage service for case image stacks.

Uses boto3 with S3-compatible API. Requires:
  R2_ACCOUNT_ID
  R2_ACCESS_KEY_ID
  R2_SECRET_ACCESS_KEY
  R2_BUCKET_NAME
"""

import logging
import os
from typing import BinaryIO

logger = logging.getLogger(__name__)

# Endpoint format: https://<ACCOUNT_ID>.r2.cloudflarestorage.com
R2_ENDPOINT_TEMPLATE = "https://{account_id}.r2.cloudflarestorage.com"

# Presigned URL expiry (seconds) - 48 hours
PRESIGNED_EXPIRY = 48 * 3600


def _get_client():
    """Create boto3 S3 client configured for Cloudflare R2."""
    try:
        import boto3
        from botocore.config import Config
    except ImportError:
        logger.warning("[R2] boto3 not installed; R2 storage disabled")
        return None

    account_id = os.environ.get("R2_ACCOUNT_ID")
    access_key = os.environ.get("R2_ACCESS_KEY_ID")
    secret_key = os.environ.get("R2_SECRET_ACCESS_KEY")

    if not all([account_id, access_key, secret_key]):
        logger.debug("[R2] Missing credentials (R2_ACCOUNT_ID, R2_ACCESS_KEY_ID, R2_SECRET_ACCESS_KEY)")
        return None

    endpoint = R2_ENDPOINT_TEMPLATE.format(account_id=account_id)

    config = Config(signature_version="s3v4", region_name="auto")
    return boto3.client(
        "s3",
        endpoint_url=endpoint,
        aws_access_key_id=access_key,
        aws_secret_access_key=secret_key,
        config=config,
    )


def is_configured() -> bool:
    """Return True if R2 credentials are set."""
    return bool(
        os.environ.get("R2_ACCOUNT_ID")
        and os.environ.get("R2_ACCESS_KEY_ID")
        and os.environ.get("R2_SECRET_ACCESS_KEY")
        and os.environ.get("R2_BUCKET_NAME")
    )


def get_bucket() -> str | None:
    return os.environ.get("R2_BUCKET_NAME")


def upload_object(key: str, body: BinaryIO | bytes, content_type: str | None = None) -> bool:
    """
    Upload object to R2.

    Args:
        key: Object key (e.g. cases/123/axial/slice_001.jpg)
        body: File-like object or bytes
        content_type: Optional MIME type

    Returns:
        True on success, False on failure
    """
    client = _get_client()
    bucket = get_bucket()
    if not client or not bucket:
        return False

    try:
        extra = {}
        if content_type:
            extra["ContentType"] = content_type

        if isinstance(body, bytes):
            client.put_object(Bucket=bucket, Key=key, Body=body, **extra)
        else:
            kwargs = {"ExtraArgs": extra} if extra else {}
            client.upload_fileobj(body, bucket, key, **kwargs)

        logger.debug("[R2] Uploaded %s", key)
        return True
    except Exception as e:
        logger.warning("[R2] Upload failed for %s: %s", key, e)
        return False


def generate_presigned_url(key: str, expiry: int = PRESIGNED_EXPIRY) -> str | None:
    """
    Generate presigned GET URL for an R2 object.

    Args:
        key: Object key
        expiry: URL expiry in seconds (default 48h)

    Returns:
        Presigned URL or None on failure
    """
    client = _get_client()
    bucket = get_bucket()
    if not client or not bucket:
        return None

    try:
        url = client.generate_presigned_url(
            "get_object",
            Params={"Bucket": bucket, "Key": key},
            ExpiresIn=expiry,
        )
        return url
    except Exception as e:
        logger.warning("[R2] Presigned URL failed for %s: %s", key, e)
        return None


def generate_presigned_urls(keys: list[str], expiry: int = PRESIGNED_EXPIRY) -> dict[str, str]:
    """
    Generate presigned URLs for a list of object keys.

    Returns:
        Dict mapping key -> presigned URL (keys that fail are omitted)
    """
    result = {}
    for k in keys:
        url = generate_presigned_url(k, expiry)
        if url:
            result[k] = url
    return result
