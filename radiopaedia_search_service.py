"""
Radiopaedia search service for reference images.

Scrapes Radiopaedia HTML search results for CC-BY-NC-SA 3.0 radiology images.
No API key required. Uses BeautifulSoup for parsing.
"""

import re
import logging
from urllib.parse import urlencode, quote_plus

from google_search_service import (
    build_search_queries,
    IMAGE_TYPE_CT_MRI,
    IMAGE_TYPE_ANATOMY_DIAGRAM,
    IMAGE_TYPE_CONCEPT_DIAGRAM,
)

logger = logging.getLogger(__name__)

SOURCE_DOMAIN = "radiopaedia.org"
SEARCH_URL = "https://radiopaedia.org/search"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; RadInsights/1.0; radiology education app)",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}


def _full_size_url(thumb_url: str) -> str:
    """Convert thumbnail URL to full-size by removing _thumb suffix."""
    return re.sub(r'_thumb\.', '.', thumb_url)


def search_radiopaedia_single(
    query: str,
    image_type: str,
    max_results: int = 10,
) -> list[dict]:
    """
    Scrape Radiopaedia search results for a query.
    Returns list of normalized result dicts.
    """
    import requests
    from bs4 import BeautifulSoup

    params = {
        "utf8": "✓",
        "q": query,
        "scope": "cases",
        "lang": "us",
    }
    url = f"{SEARCH_URL}?{urlencode(params)}"

    try:
        r = requests.get(url, headers=HEADERS, timeout=15)
        r.raise_for_status()
    except Exception as e:
        logger.warning(f"[Radiopaedia] Request failed for '{query}': {e}")
        return []

    soup = BeautifulSoup(r.text, "html.parser")
    results = []

    # Find case links: <a> with href matching /cases/{slug}
    case_links = soup.find_all("a", href=re.compile(r"/cases/[^/]+"))
    seen_hrefs = set()

    for link_tag in case_links:
        if len(results) >= max_results:
            break

        href = link_tag.get("href", "")
        # Normalize href
        if href.startswith("/"):
            href = f"https://radiopaedia.org{href}"

        # Skip duplicates and non-case URLs
        case_match = re.search(r"/cases/([^/?#]+)", href)
        if not case_match:
            continue
        case_slug = case_match.group(1)
        if case_slug in seen_hrefs:
            continue
        seen_hrefs.add(case_slug)

        # Find thumbnail: look for <img> inside or near this link
        img_tag = link_tag.find("img")
        if not img_tag:
            # Check parent for img siblings
            parent = link_tag.parent
            if parent:
                img_tag = parent.find("img")

        thumb_url = ""
        full_url = href  # Default to case page URL
        if img_tag:
            src = img_tag.get("src", "") or img_tag.get("data-src", "")
            if src and "radiopaedia" in src:
                thumb_url = src
                full_url = _full_size_url(src)

        # Extract title from link text or slug
        title = link_tag.get_text(strip=True)
        if not title or len(title) < 3:
            title = case_slug.replace("-", " ").title()

        # Skip non-useful entries (navigation links etc)
        if title.lower() in ("cases", "articles", "courses", "playlists"):
            continue

        results.append({
            "link": full_url,
            "thumbnail_link": thumb_url or full_url,
            "title": title,
            "displayLink": SOURCE_DOMAIN,
            "source_domain": SOURCE_DOMAIN,
            "image_type": image_type,
            "case_url": href,
            "license": "CC BY-NC-SA 3.0",
        })

    return results


def search_radiopaedia_images(
    diagnosis: str,
    body_part: str = "",
    modality: str = "",
    image_types: list[str] | None = None,
    max_per_type: int = 5,
) -> list[dict]:
    """
    Search Radiopaedia for radiology case images.
    Uses same query logic as other providers via build_search_queries().
    """
    if image_types is None or not image_types:
        image_types = [IMAGE_TYPE_CT_MRI]
        if modality and modality.strip().upper() in ("CT", "MRI"):
            image_types = [IMAGE_TYPE_CT_MRI]
        else:
            image_types = [IMAGE_TYPE_CT_MRI, IMAGE_TYPE_ANATOMY_DIAGRAM]

    queries = build_search_queries(diagnosis, body_part, modality)
    seen_urls: set[str] = set()
    results: list[dict] = []

    for itype in image_types:
        for q in queries.get(itype, [])[:2]:
            for hit in search_radiopaedia_single(
                q, image_type=itype, max_results=max_per_type
            ):
                if hit["link"] not in seen_urls:
                    seen_urls.add(hit["link"])
                    results.append(hit)
            if len([r for r in results if r["image_type"] == itype]) >= max_per_type:
                break

    return results
