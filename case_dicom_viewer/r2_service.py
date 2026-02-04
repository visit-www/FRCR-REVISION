"""
Cloudflare R2 storage service for case image stacks.

Uses boto3 with S3-compatible API. Requires in .env:
  R2_ACCOUNT_ID
  R2_ACCESS_KEY_ID
  R2_SECRET_ACCESS_KEY
  R2_BUCKET_NAME

Note: .env is loaded by app.py before this module. .env.local overrides .env but typically
does not include R2 vars, so R2 values from .env are used.
"""

import logging
import os
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import BinaryIO

logger = logging.getLogger(__name__)

# Endpoint formats (jurisdiction-specific for EU/FedRAMP buckets)
R2_ENDPOINT_TEMPLATES = {
    "default": "https://{account_id}.r2.cloudflarestorage.com",
    "eu": "https://{account_id}.eu.r2.cloudflarestorage.com",
    "fedramp": "https://{account_id}.fedramp.r2.cloudflarestorage.com",
}

# Presigned URL expiry (seconds) - 48 hours
PRESIGNED_EXPIRY = 48 * 3600


def _get_env(key: str) -> str | None:
    """Get env var, stripping whitespace and newlines (common in .env files)."""
    v = os.environ.get(key)
    if v is None:
        return None
    return v.strip().replace("\n", "").replace("\r", "").replace("\\n", "") or None


def _get_client():
    """Create boto3 S3 client configured for Cloudflare R2."""
    try:
        import boto3
        from botocore.config import Config
    except ImportError:
        logger.warning("[R2] boto3 not installed; R2 storage disabled")
        return None

    account_id = _get_env("R2_ACCOUNT_ID")
    access_key = _get_env("R2_ACCESS_KEY_ID")
    secret_key = _get_env("R2_SECRET_ACCESS_KEY")

    if not all([account_id, access_key, secret_key]):
        logger.debug("[R2] Missing credentials (R2_ACCOUNT_ID, R2_ACCESS_KEY_ID, R2_SECRET_ACCESS_KEY)")
        return None

    jurisdiction = (_get_env("R2_JURISDICTION") or "").lower().strip()
    template = R2_ENDPOINT_TEMPLATES.get(jurisdiction) or R2_ENDPOINT_TEMPLATES["default"]
    endpoint = template.format(account_id=account_id)

    config = Config(signature_version="s3v4", region_name="auto")
    return boto3.client(
        "s3",
        endpoint_url=endpoint,
        aws_access_key_id=access_key,
        aws_secret_access_key=secret_key,
        config=config,
    )


def test_connection() -> tuple[bool, str]:
    """
    Test R2 credentials: head_bucket + small put/delete.
    Returns (success, message).
    """
    client = _get_client()
    bucket = get_bucket()
    if not client or not bucket:
        return False, "R2 not configured (missing credentials or bucket)"

    try:
        client.head_bucket(Bucket=bucket)
    except Exception as e:
        return False, f"head_bucket failed: {e}"

    test_key = "_r2_test_connection"
    try:
        client.put_object(Bucket=bucket, Key=test_key, Body=b"ok", ContentType="text/plain")
        client.delete_object(Bucket=bucket, Key=test_key)
    except Exception as e:
        return False, f"put/delete failed: {e}"

    return True, "OK"


def is_configured() -> bool:
    """Return True if R2 credentials are set."""
    return bool(
        _get_env("R2_ACCOUNT_ID")
        and _get_env("R2_ACCESS_KEY_ID")
        and _get_env("R2_SECRET_ACCESS_KEY")
        and _get_env("R2_BUCKET_NAME")
    )


def get_bucket() -> str | None:
    return _get_env("R2_BUCKET_NAME")


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


def upload_objects_parallel(
    items: list[tuple[str, bytes, str | None]],
    max_workers: int | None = None,
) -> tuple[list[str], list[str]]:
    """
    Upload multiple objects to R2 in parallel.

    Args:
        items: List of (key, body_bytes, content_type)
        max_workers: Thread pool size (default 20, or R2_UPLOAD_WORKERS env)

    Returns:
        (successful_keys, failed_keys)
    """
    if not items:
        return [], []

    n = int(_get_env("R2_UPLOAD_WORKERS") or "0") or max_workers or 20
    n = min(n, 32)
    client = _get_client()
    bucket = get_bucket()
    if not client or not bucket:
        return [], [k for k, _, _ in items]

    successful = []
    failed = []

    def _upload(args: tuple[str, bytes, str | None]) -> tuple[str, bool]:
        key, body, ct = args
        try:
            extra = {"ContentType": ct} if ct else {}
            client.put_object(Bucket=bucket, Key=key, Body=body, **extra)
            return (key, True)
        except Exception as e:
            logger.warning("[R2] Upload failed for %s: %s", key, e)
            return (key, False)

    with ThreadPoolExecutor(max_workers=n) as ex:
        futures = {ex.submit(_upload, item): item for item in items}
        for fut in as_completed(futures):
            key, ok = fut.result()
            if ok:
                successful.append(key)
            else:
                failed.append(key)

    return successful, failed


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


def list_objects(prefix: str = "", delimiter: str = "/", max_keys: int = 1000, continuation_token: str | None = None) -> dict:
    """
    List objects and common prefixes (folders) in the bucket.

    Args:
        prefix: Object key prefix (e.g. "cases/123/")
        delimiter: Delimiter for folder listing (default "/")
        max_keys: Max objects to return
        continuation_token: For pagination

    Returns:
        {
            "prefixes": ["cases/123/", ...],
            "objects": [{"Key": "...", "Size": 123, "LastModified": "..."}, ...],
            "is_truncated": bool,
            "next_token": str | None
        }
    """
    client = _get_client()
    bucket = get_bucket()
    if not client or not bucket:
        return {"prefixes": [], "objects": [], "is_truncated": False, "next_token": None}

    try:
        kwargs = {
            "Bucket": bucket,
            "Prefix": prefix,
            "Delimiter": delimiter,
            "MaxKeys": max_keys,
        }
        if continuation_token:
            kwargs["ContinuationToken"] = continuation_token

        resp = client.list_objects_v2(**kwargs)

        prefixes = [p["Prefix"] for p in resp.get("CommonPrefixes", [])]
        objects = [
            {"Key": o["Key"], "Size": o.get("Size", 0), "LastModified": str(o.get("LastModified", ""))}
            for o in resp.get("Contents", [])
        ]

        return {
            "prefixes": prefixes,
            "objects": objects,
            "is_truncated": resp.get("IsTruncated", False),
            "next_token": resp.get("NextContinuationToken"),
        }
    except Exception as e:
        logger.warning("[R2] List failed: %s", e)
        return {"prefixes": [], "objects": [], "is_truncated": False, "next_token": None}


def delete_objects(keys: list[str]) -> tuple[list[str], list[dict]]:
    """
    Delete objects by key. R2/S3 allows up to 1000 keys per request.

    Returns:
        (deleted_keys, errors)
    """
    client = _get_client()
    bucket = get_bucket()
    if not client or not bucket:
        return [], [{"Key": k, "Message": "R2 not configured"} for k in keys]

    deleted = []
    errors = []
    for i in range(0, len(keys), 1000):
        batch = keys[i : i + 1000]
        try:
            resp = client.delete_objects(
                Bucket=bucket,
                Delete={"Objects": [{"Key": k} for k in batch], "Quiet": False},
            )
            for d in resp.get("Deleted", []):
                if "Key" in d:
                    deleted.append(d["Key"])
            for e in resp.get("Errors", []):
                errors.append({"Key": e.get("Key", ""), "Message": e.get("Message", "Unknown")})
        except Exception as e:
            for k in batch:
                errors.append({"Key": k, "Message": str(e)})

    return deleted, errors


def delete_prefix(prefix: str) -> tuple[int, list[dict]]:
    """
    Delete all objects under a prefix. Lists then deletes in batches.

    Returns:
        (deleted_count, errors)
    """
    client = _get_client()
    bucket = get_bucket()
    if not client or not bucket:
        return 0, [{"Key": prefix, "Message": "R2 not configured"}]

    all_keys = []
    token = None
    while True:
        result = list_objects(prefix=prefix, delimiter="", max_keys=1000, continuation_token=token)
        for o in result["objects"]:
            all_keys.append(o["Key"])
        if not result["is_truncated"] or not result["next_token"]:
            break
        token = result["next_token"]

    if not all_keys:
        return 0, []

    deleted, errors = delete_objects(all_keys)
    return len(deleted), errors
