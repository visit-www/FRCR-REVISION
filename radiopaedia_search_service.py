"""
Radiopaedia search service for reference images.

Scrapes Radiopaedia HTML search results for CC-BY-NC-SA 3.0 radiology images.
No API key required. Uses BeautifulSoup for parsing.

Key: The X-Requested-With: XMLHttpRequest header makes Radiopaedia return
server-rendered HTML with case links and thumbnail images. Without it,
the page is a JS-only SPA shell with no content.
"""

import re
import logging
from urllib.parse import urlencode

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
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html",
    "Accept-Encoding": "gzip, deflate",
    "X-Requested-With": "XMLHttpRequest",
}
# Regex for thumbnail images hosted on Radiopaedia's image CDN
_IMG_CDN_RE = re.compile(r"prod-images-static\.radiopaedia\.org/images/")


def _full_size_url(thumb_url: str) -> str:
    """Convert thumbnail URL to full-size by removing _thumb suffix."""
    return re.sub(r"_thumb\.", ".", thumb_url)


def search_radiopaedia_single(
    query: str,
    image_type: str,
    max_results: int = 10,
) -> list[dict]:
    """
    Fetch Radiopaedia search page (cases scope) and parse results.
    Returns list of normalised result dicts.
    """
    import requests
    from bs4 import BeautifulSoup

    params = {
        "q": query,
        "scope": "cases",
        "lang": "us",
    }
    url = f"{SEARCH_URL}?{urlencode(params)}"

    try:
        r = requests.get(url, headers=HEADERS, timeout=15)
        r.raise_for_status()
    except Exception as e:
        logger.warning("[Radiopaedia] Request failed for '%s': %s", query, e)
        return []

    if len(r.text) < 500:
        logger.warning("[Radiopaedia] Empty/short response for '%s' (%d bytes)", query, len(r.text))
        return []

    soup = BeautifulSoup(r.text, "html.parser")

    # Find the search-results-listing container
    listing = soup.find("div", class_="search-results-listing")
    if not listing:
        listing = soup  # Fallback to whole page

    # Collect case links and case images in DOM order within the listing.
    # Radiopaedia renders one <a href="/cases/..."> and one <img> per result
    # as siblings/descendants in the same flat structure.
    case_links: list[dict] = []
    case_imgs: list[str] = []
    seen_slugs: set[str] = set()

    for tag in listing.descendants:
        if tag.name == "a":
            href = tag.get("href", "")
            m = re.match(r"^/cases/([^/?#]+)", href)
            if m:
                slug = m.group(1)
                if slug not in seen_slugs:
                    seen_slugs.add(slug)
                    # Extract title from pipe-separated text parts
                    raw = tag.get_text(separator="|", strip=True)
                    parts = [p.strip() for p in raw.split("|") if p.strip()]
                    title = parts[1] if len(parts) > 1 else slug.replace("-", " ").title()
                    case_links.append({"slug": slug, "href": href, "title": title})
        elif tag.name == "img":
            src = tag.get("src", "") or ""
            if _IMG_CDN_RE.search(src):
                case_imgs.append(src)

    # Match case links with images by position (1:1 correspondence in DOM order)
    results: list[dict] = []
    for i, case in enumerate(case_links):
        if len(results) >= max_results:
            break

        thumb = case_imgs[i] if i < len(case_imgs) else ""
        full_img = _full_size_url(thumb) if thumb else ""
        case_url = f"https://radiopaedia.org{case['href'].split('?')[0]}"

        results.append({
            "link": full_img or case_url,
            "thumbnail_link": thumb or case_url,
            "title": case["title"],
            "displayLink": SOURCE_DOMAIN,
            "source_domain": SOURCE_DOMAIN,
            "image_type": image_type,
            "case_url": case_url,
            "license": "CC BY-NC-SA 3.0",
        })

    return results


# ── Author scraping ──────────────────────────────────────────────────

_author_cache: dict[str, str | None] = {}


def scrape_case_author(case_url: str) -> str | None:
    """Scrape contributor/author name from a Radiopaedia case page.

    Returns the first author name found, or None.
    Results are cached in-memory to avoid duplicate requests.
    Never raises — returns None on any failure.
    """
    if case_url in _author_cache:
        return _author_cache[case_url]

    try:
        import requests
        from bs4 import BeautifulSoup

        r = requests.get(case_url, headers=HEADERS, timeout=10)
        r.raise_for_status()
        soup = BeautifulSoup(r.text, "html.parser")

        # Strategy 1: look for .contributor-name or .study-author
        for sel in ('.contributor-name', '.study-author', '.case-author',
                    '[class*="author"]', '[class*="contributor"]'):
            el = soup.select_one(sel)
            if el:
                name = el.get_text(strip=True)
                if name and len(name) < 100:
                    _author_cache[case_url] = name
                    return name

        # Strategy 2: meta tag
        meta = soup.find('meta', attrs={'name': 'author'})
        if meta and meta.get('content'):
            name = meta['content'].strip()
            if name and len(name) < 100:
                _author_cache[case_url] = name
                return name

        # Strategy 3: look for "by" pattern near case header
        header = soup.find('h1')
        if header:
            sib = header.find_next(['p', 'span', 'div'])
            if sib:
                text = sib.get_text(strip=True)
                m = re.search(r'(?:by|By|BY)\s+(.+?)(?:\s*[,|]|$)', text)
                if m:
                    name = m.group(1).strip()
                    if name and len(name) < 100:
                        _author_cache[case_url] = name
                        return name

    except Exception as exc:
        logger.debug("scrape_case_author failed for %s: %s", case_url, exc)

    _author_cache[case_url] = None
    return None


def search_radiopaedia_images(
    diagnosis: str,
    body_part: str = "",
    modality: str = "",
    image_types: list[str] | None = None,
    max_per_type: int = 5,
) -> list[dict]:
    """
    Search Radiopaedia for radiology case images.

    Unlike other providers, Radiopaedia IS a radiology site — so adding
    "radiology imaging" to queries over-restricts results. We search with
    the raw diagnosis first, then try built queries only if needed.
    """
    if image_types is None or not image_types:
        image_types = [IMAGE_TYPE_CT_MRI]

    seen_urls: set[str] = set()
    results: list[dict] = []

    # Primary search: raw diagnosis (optionally with modality)
    primary_query = diagnosis.strip()
    if modality and modality.strip():
        primary_query = f"{diagnosis.strip()} {modality.strip()}"
    for hit in search_radiopaedia_single(primary_query, IMAGE_TYPE_CT_MRI, max_results=max_per_type):
        if hit["link"] not in seen_urls:
            seen_urls.add(hit["link"])
            results.append(hit)

    # If we got enough, return early
    if len(results) >= max_per_type:
        return results[:max_per_type]

    # Fallback: try built queries for remaining slots
    queries = build_search_queries(diagnosis, body_part, modality)
    for itype in image_types:
        for q in queries.get(itype, [])[:2]:
            if len(results) >= max_per_type:
                break
            for hit in search_radiopaedia_single(q, itype, max_results=max_per_type):
                if hit["link"] not in seen_urls:
                    seen_urls.add(hit["link"])
                    results.append(hit)

    return results
