"""
Google Custom Search service for reference image curation.

Searches for CC-licensed radiology images:
- CT/MRI imaging for diagnosis
- Anatomy diagrams (line diagrams, schematics)
- Concept diagrams (staging, flowcharts)

All results MUST be Creative Commons or public domain (rights parameter).
"""

import os
import logging
from urllib.parse import urlencode

logger = logging.getLogger(__name__)

# CC license filter: public domain + attribution + sharealike
RIGHTS_CC = "cc_publicdomain,cc_attribute,cc_sharealike"

# Image types for query building
IMAGE_TYPE_CT_MRI = "ct_mri"
IMAGE_TYPE_ANATOMY_DIAGRAM = "anatomy_diagram"
IMAGE_TYPE_CONCEPT_DIAGRAM = "concept_diagram"


def _get_api_key():
    return os.environ.get("GOOGLE_SEARCH_API_KEY") or os.environ.get("GOOGLE_CSE_API_KEY")


def _get_cx():
    return os.environ.get("GOOGLE_SEARCH_ENGINE_ID") or os.environ.get("GOOGLE_CSE_ID")


def build_search_queries(diagnosis: str, body_part: str = "", modality: str = "CT") -> dict:
    """
    Build search queries for each image type.
    Returns dict: { image_type: [query1, query2, ...] }
    """
    diagnosis = (diagnosis or "").strip()
    body_part = (body_part or "").strip()
    modality = (modality or "CT").strip().upper()

    queries = {}

    # CT/MRI imaging: diagnosis + modality
    if diagnosis:
        queries[IMAGE_TYPE_CT_MRI] = [
            f"{diagnosis} {modality} imaging",
            f"{diagnosis} MRI" if modality == "CT" else f"{diagnosis} CT",
            f"{diagnosis} radiology",
        ]

    # Anatomy diagrams: body part + line diagram / schematic
    if body_part:
        queries[IMAGE_TYPE_ANATOMY_DIAGRAM] = [
            f"{body_part} anatomy line diagram",
            f"{body_part} anatomy cross section diagram",
            f"{body_part} anatomy schematic",
        ]
    elif diagnosis:
        queries[IMAGE_TYPE_ANATOMY_DIAGRAM] = [
            f"{diagnosis} anatomy diagram",
            f"{diagnosis} anatomy schematic",
        ]

    # Concept diagrams: staging, flowchart
    if diagnosis:
        queries[IMAGE_TYPE_CONCEPT_DIAGRAM] = [
            f"{diagnosis} staging diagram",
            f"{diagnosis} classification flowchart",
            f"{diagnosis} TNM staging diagram",
        ]

    return queries


def search_images(
    query: str,
    image_type: str = IMAGE_TYPE_CT_MRI,
    max_results: int = 10,
    rights: str = RIGHTS_CC,
) -> list[dict]:
    """
    Search for CC-licensed images via Google Custom Search API.

    Args:
        query: Search query
        image_type: ct_mri | anatomy_diagram | concept_diagram
        max_results: Max results to return (default 10)
        rights: License filter (default CC)

    Returns:
        List of dicts: { link, thumbnail_link, title, displayLink, ... }
    """
    api_key = _get_api_key()
    cx = _get_cx()
    if not api_key or not cx:
        missing = []
        if not api_key:
            missing.append("GOOGLE_SEARCH_API_KEY")
        if not cx:
            missing.append("GOOGLE_SEARCH_ENGINE_ID")
        raise ValueError(f"Missing config: {', '.join(missing)}. Add to .env and restart.")

    # Canonical endpoint per Google docs (cse.list method)
    url = "https://customsearch.googleapis.com/customsearch/v1"
    params = {
        "key": api_key,
        "cx": cx,
        "q": query,
        "searchType": "image",
        "num": min(max_results, 10),
        "rights": rights,
        "safe": "off",
    }

    try:
        import requests
        r = requests.get(url, params=params, timeout=15)
        data = r.json()

        # Google returns 200 with error in body for quota/auth issues
        if "error" in data:
            err = data["error"]
            code = err.get("code", 0)
            msg = err.get("message", str(err))
            logger.error(f"[ReferenceImage] API error: {code} - {msg}")
            raise ValueError(f"Google API: {msg}")

        r.raise_for_status()
        logger.info(f"[ReferenceImage] Search '{query[:50]}...': {len(data.get('items', []))} results")
    except ValueError:
        raise
    except Exception as e:
        logger.error(f"[ReferenceImage] Google search error: {e}", exc_info=True)
        raise ValueError(str(e)) from e

    results = []
    for item in data.get("items", []):
        link = item.get("link", "")
        if not link:
            continue
        domain = _extract_domain(link)
        results.append({
            "link": link,
            "thumbnail_link": item.get("image", {}).get("thumbnailLink") or link,
            "title": item.get("title", ""),
            "displayLink": item.get("displayLink", domain),
            "source_domain": domain,
            "image_type": image_type,
        })
    return results


def _extract_domain(url: str) -> str:
    """Extract domain from URL for source_domain."""
    try:
        from urllib.parse import urlparse
        parsed = urlparse(url)
        domain = parsed.netloc or ""
        if domain.startswith("www."):
            domain = domain[4:]
        return domain[:255] if domain else "unknown"
    except Exception:
        return "unknown"


def search_reference_images(
    diagnosis: str,
    body_part: str = "",
    modality: str = "CT",
    image_types: list[str] | None = None,
    max_per_type: int = 5,
) -> list[dict]:
    """
    Search for CC-licensed reference images across all types.
    Returns combined, deduplicated results.
    """
    if image_types is None:
        image_types = [IMAGE_TYPE_CT_MRI, IMAGE_TYPE_ANATOMY_DIAGRAM, IMAGE_TYPE_CONCEPT_DIAGRAM]

    queries = build_search_queries(diagnosis, body_part, modality)
    seen_urls = set()
    results = []

    for itype in image_types:
        for q in queries.get(itype, [])[:2]:  # Max 2 queries per type
            for hit in search_images(q, image_type=itype, max_results=max_per_type):
                if hit["link"] not in seen_urls:
                    seen_urls.add(hit["link"])
                    results.append(hit)
            if len([r for r in results if r["image_type"] == itype]) >= max_per_type:
                break

    return results
