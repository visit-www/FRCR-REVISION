"""
Wikimedia Commons search service for reference images.

Searches Commons (CC-licensed by design) via MediaWiki API.
No API key required.
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

COMMONS_API = "https://commons.wikimedia.org/w/api.php"
SOURCE_DOMAIN = "commons.wikimedia.org"
# File namespace on Commons
NS_FILE = 6


def search_wikimedia_single(
    query: str,
    image_type: str,
    max_results: int = 10,
) -> list[dict]:
    """
    Search Wikimedia Commons File namespace for a query.
    Returns list of normalized result dicts.
    """
    import requests

    params = {
        "action": "query",
        "generator": "search",
        "gsrsearch": query,
        "gsrnamespace": NS_FILE,
        "gsrlimit": min(max_results, 50),
        "prop": "imageinfo",
        "iiprop": "url",
        "iiurlwidth": 300,  # Thumbnail width
        "format": "json",
        "origin": "*",
    }
    url = f"{COMMONS_API}?{urlencode(params)}"

    try:
        r = requests.get(url, timeout=15)
        r.raise_for_status()
        data = r.json()
    except Exception as e:
        logger.warning(f"[Wikimedia] Request failed: {e}")
        return []

    pages = data.get("query", {}).get("pages") or {}
    results = []
    for page_id, page in pages.items():
        if page_id < 0:  # Special pages (missing, etc.)
            continue
        title = page.get("title", "")
        if not title.startswith("File:"):
            continue
        info_list = page.get("imageinfo") or []
        if not info_list:
            continue
        info = info_list[0]
        link = info.get("url") or info.get("descriptionurl")
        if not link:
            continue
        thumb = info.get("thumburl") or info.get("url") or link
        display_name = title[5:] if title.startswith("File:") else title  # Strip "File:"
        results.append({
            "link": link,
            "thumbnail_link": thumb,
            "title": display_name.replace("_", " "),
            "displayLink": SOURCE_DOMAIN,
            "source_domain": SOURCE_DOMAIN,
            "image_type": image_type,
        })
    return results


def search_wikimedia_images(
    diagnosis: str,
    body_part: str = "",
    modality: str = "",
    image_types: list[str] | None = None,
    max_per_type: int = 5,
) -> list[dict]:
    """
    Search Wikimedia Commons for CC-licensed images.
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
            for hit in search_wikimedia_single(
                q, image_type=itype, max_results=max_per_type
            ):
                if hit["link"] not in seen_urls:
                    seen_urls.add(hit["link"])
                    results.append(hit)
            if len([r for r in results if r["image_type"] == itype]) >= max_per_type:
                break

    return results
