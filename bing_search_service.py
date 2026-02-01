"""
Bing Image Search service for reference images.

Uses Azure Cognitive Services Bing Image Search API v7.
Requires BING_IMAGE_SEARCH_KEY. Optional: only used when key is set.
"""

import os
import logging
from urllib.parse import urlparse

from google_search_service import (
    build_search_queries,
    IMAGE_TYPE_CT_MRI,
    IMAGE_TYPE_ANATOMY_DIAGRAM,
    IMAGE_TYPE_CONCEPT_DIAGRAM,
)

logger = logging.getLogger(__name__)

BING_ENDPOINT = "https://api.bing.microsoft.com/v7.0/images/search"
# CC-compatible: Share = free to share (Bing license filter)
BING_LICENSE = "Share"


def _get_api_key() -> str | None:
    return (
        os.environ.get("BING_IMAGE_SEARCH_KEY")
        or os.environ.get("BING_SEARCH_KEY")
        or None
    )


def _extract_domain(url: str) -> str:
    try:
        parsed = urlparse(url)
        domain = parsed.netloc or ""
        if domain.startswith("www."):
            domain = domain[4:]
        return domain[:255] if domain else "unknown"
    except Exception:
        return "unknown"


def search_bing_single(
    query: str,
    image_type: str,
    max_results: int = 10,
) -> list[dict]:
    """
    Search Bing Images for a single query. Returns list of normalized result dicts.
    Returns [] if API key not set (Bing is optional). Raises on request failure.
    """
    api_key = _get_api_key()
    if not api_key:
        return []

    import requests

    params = {
        "q": query,
        "count": min(max_results, 50),
        "license": BING_LICENSE,
        "mkt": "en-us",
        "safeSearch": "Moderate",
    }
    headers = {
        "Ocp-Apim-Subscription-Key": api_key,
        "Accept": "application/json",
    }

    try:
        r = requests.get(BING_ENDPOINT, params=params, headers=headers, timeout=15)
        r.raise_for_status()
        data = r.json()
    except requests.RequestException as e:
        logger.warning(f"[Bing] Request failed: {e}")
        raise

    items = data.get("value") or []
    results = []
    for item in items:
        link = item.get("contentUrl") or item.get("url")
        if not link:
            continue
        thumb = (
            item.get("thumbnailUrl")
            or item.get("contentUrl")
            or link
        )
        title = item.get("name") or item.get("description") or ""
        domain = _extract_domain(link)
        results.append({
            "link": link,
            "thumbnail_link": thumb,
            "title": (title[:500] if title else ""),
            "displayLink": domain,
            "source_domain": domain,
            "image_type": image_type,
        })
    return results


def search_bing_images(
    diagnosis: str,
    body_part: str = "",
    modality: str = "",
    image_types: list[str] | None = None,
    max_per_type: int = 5,
) -> list[dict]:
    """
    Search Bing for CC-licensed images. Uses same query logic as Google provider.
    """
    if image_types is None or not image_types:
        image_types = [IMAGE_TYPE_ANATOMY_DIAGRAM, IMAGE_TYPE_CONCEPT_DIAGRAM]
        if modality and modality.strip().upper() in ("CT", "MRI"):
            image_types = [IMAGE_TYPE_CT_MRI] + image_types

    queries = build_search_queries(diagnosis, body_part, modality)
    seen_urls: set[str] = set()
    results: list[dict] = []

    for itype in image_types:
        for q in queries.get(itype, [])[:2]:
            for hit in search_bing_single(q, image_type=itype, max_results=max_per_type):
                if hit["link"] not in seen_urls:
                    seen_urls.add(hit["link"])
                    results.append(hit)
            if len([r for r in results if r["image_type"] == itype]) >= max_per_type:
                break

    return results
