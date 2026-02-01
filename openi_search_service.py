"""
Open-i (NIH) search service for biomedical/radiology images.

Searches https://openi.nlm.nih.gov/api - open access biomedical image index.
No API key required. License filter for CC-compatible images.
"""

import logging
from urllib.parse import urlencode

from google_search_service import (
    build_search_queries,
    IMAGE_TYPE_CT_MRI,
    IMAGE_TYPE_ANATOMY_DIAGRAM,
    IMAGE_TYPE_CONCEPT_DIAGRAM,
)

logger = logging.getLogger(__name__)

OPENI_BASE = "https://openi.nlm.nih.gov/api"
SOURCE_DOMAIN = "openi.nlm.nih.gov"


def _extract_image_url(item: dict) -> str | None:
    """Extract direct image URL from Open-i result item."""
    # Open-i response structure varies; common patterns:
    # - list[].imageURL
    # - list[].figure.imageURL
    # - list[].images[0].url
    if isinstance(item, dict):
        url = item.get("imageURL") or item.get("imageUrl")
        if url:
            return url
        fig = item.get("figure") or item.get("fig")
        if isinstance(fig, dict):
            return fig.get("imageURL") or fig.get("imageUrl") or fig.get("url")
        imgs = item.get("images") or item.get("image")
        if imgs and isinstance(imgs, list) and imgs:
            first = imgs[0]
            if isinstance(first, dict):
                return first.get("url") or first.get("imageURL")
        if isinstance(imgs, dict):
            return imgs.get("url") or imgs.get("imageURL")
    return None


def _extract_thumbnail(item: dict) -> str | None:
    """Extract thumbnail URL from Open-i result."""
    if isinstance(item, dict):
        t = item.get("thumbnail") or item.get("thumbURL") or item.get("thumbnailUrl")
        if t:
            return t
        fig = item.get("figure") or item.get("fig")
        if isinstance(fig, dict):
            return fig.get("thumbnail") or fig.get("thumbURL")
    return None


def _extract_title(item: dict) -> str:
    """Extract title/caption from Open-i result."""
    if isinstance(item, dict):
        return (
            item.get("caption")
            or item.get("title")
            or item.get("figureCaption")
            or item.get("figCaption")
            or ""
        )
    return ""


def search_openi_single(query: str, image_type: str, max_results: int = 10) -> list[dict]:
    """
    Search Open-i for a single query. Returns list of normalized result dicts.
    """
    import requests

    params = {
        "query": query,
        "m": 0,
        "n": min(max_results, 50),
        "lic": "by",  # CC Attribution
        "coll": "pmc",  # PubMed Central - radiology literature
    }
    url = f"{OPENI_BASE}/search?{urlencode(params)}"

    try:
        r = requests.get(url, timeout=15)
        r.raise_for_status()
        data = r.json()
    except Exception as e:
        logger.warning(f"[Open-i] Request failed: {e}")
        return []

    items = data.get("list") or data.get("results") or []
    results = []
    for item in items:
        link = _extract_image_url(item)
        if not link:
            continue
        thumb = _extract_thumbnail(item) or link
        title = _extract_title(item) or "Open-i biomedical image"
        results.append({
            "link": link,
            "thumbnail_link": thumb,
            "title": title[:500] if title else "",
            "displayLink": SOURCE_DOMAIN,
            "source_domain": SOURCE_DOMAIN,
            "image_type": image_type,
        })
    return results


def search_openi_images(
    diagnosis: str,
    body_part: str = "",
    modality: str = "",
    image_types: list[str] | None = None,
    max_per_type: int = 5,
) -> list[dict]:
    """
    Search Open-i for CC-licensed biomedical/radiology images.
    Uses same query logic as Google provider.
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
            for hit in search_openi_single(q, image_type=itype, max_results=max_per_type):
                if hit["link"] not in seen_urls:
                    seen_urls.add(hit["link"])
                    results.append(hit)
            if len([r for r in results if r["image_type"] == itype]) >= max_per_type:
                break

    return results
