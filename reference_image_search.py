"""
Reference Image Search Aggregator.

Tries multiple providers (Google, Open-i, Bing, Wikimedia Commons) in order
until enough results are found. Keeps current workflow, adds fallbacks.
"""

import os
import logging
from typing import Callable

from google_search_service import (
    build_search_queries,
    search_reference_images as _google_search,
    IMAGE_TYPE_CT_MRI,
    IMAGE_TYPE_ANATOMY_DIAGRAM,
    IMAGE_TYPE_CONCEPT_DIAGRAM,
)

logger = logging.getLogger(__name__)

# Provider IDs
PROVIDER_GOOGLE = "google"
PROVIDER_OPENI = "openi"
PROVIDER_BING = "bing"
PROVIDER_COMMONS = "commons"
PROVIDER_RADIOPAEDIA = "radiopaedia"

# Result shape: { link, thumbnail_link, title, displayLink, source_domain, image_type }


def _get_provider_order() -> list[str]:
    """Read provider order from env. Default: radiopaedia (free, CC-BY-NC-SA 3.0).
    Add google when CSE works; add bing with BING_IMAGE_SEARCH_KEY for web search."""
    raw = os.environ.get("REFERENCE_IMAGE_SEARCH_PROVIDERS", "radiopaedia")
    order = [p.strip().lower() for p in raw.split(",") if p.strip()]
    return order or [PROVIDER_RADIOPAEDIA]


def _search_google(
    diagnosis: str,
    body_part: str,
    modality: str,
    image_types: list[str] | None,
    max_per_type: int,
) -> list[dict]:
    """Delegate to existing Google search. Raises on config error."""
    return _google_search(
        diagnosis=diagnosis,
        body_part=body_part,
        modality=modality,
        image_types=image_types,
        max_per_type=max_per_type,
    )


def _search_openi(
    diagnosis: str,
    body_part: str,
    modality: str,
    image_types: list[str] | None,
    max_per_type: int,
) -> list[dict]:
    """Search Open-i NIH. Returns [] on error."""
    try:
        from openi_search_service import search_openi_images
        return search_openi_images(
            diagnosis=diagnosis,
            body_part=body_part,
            modality=modality,
            image_types=image_types,
            max_per_type=max_per_type,
        )
    except Exception as e:
        logger.warning(f"[ReferenceImage] Open-i search failed: {e}")
        return []


def _search_bing(
    diagnosis: str,
    body_part: str,
    modality: str,
    image_types: list[str] | None,
    max_per_type: int,
) -> list[dict]:
    """Search Bing Image API. Returns [] if no key or on error."""
    try:
        from bing_search_service import search_bing_images
        return search_bing_images(
            diagnosis=diagnosis,
            body_part=body_part,
            modality=modality,
            image_types=image_types,
            max_per_type=max_per_type,
        )
    except Exception as e:
        logger.warning(f"[ReferenceImage] Bing search failed: {e}")
        return []


def _search_commons(
    diagnosis: str,
    body_part: str,
    modality: str,
    image_types: list[str] | None,
    max_per_type: int,
) -> list[dict]:
    """Search Wikimedia Commons. Returns [] on error."""
    try:
        from wikimedia_search_service import search_wikimedia_images
        return search_wikimedia_images(
            diagnosis=diagnosis,
            body_part=body_part,
            modality=modality,
            image_types=image_types,
            max_per_type=max_per_type,
        )
    except Exception as e:
        logger.warning(f"[ReferenceImage] Wikimedia search failed: {e}")
        return []


def _search_radiopaedia(
    diagnosis: str,
    body_part: str,
    modality: str,
    image_types: list[str] | None,
    max_per_type: int,
) -> list[dict]:
    """Search Radiopaedia. Returns [] on error."""
    try:
        from radiopaedia_search_service import search_radiopaedia_images
        return search_radiopaedia_images(
            diagnosis=diagnosis,
            body_part=body_part,
            modality=modality,
            image_types=image_types,
            max_per_type=max_per_type,
        )
    except Exception as e:
        logger.warning(f"[ReferenceImage] Radiopaedia search failed: {e}")
        return []


_PROVIDER_FUNCS: dict[str, Callable] = {
    PROVIDER_GOOGLE: _search_google,
    PROVIDER_OPENI: _search_openi,
    PROVIDER_BING: _search_bing,
    PROVIDER_COMMONS: _search_commons,
    PROVIDER_RADIOPAEDIA: _search_radiopaedia,
}


def search_reference_images(
    diagnosis: str,
    body_part: str = "",
    modality: str = "",
    image_types: list[str] | None = None,
    max_per_type: int = 5,
) -> list[dict]:
    """
    Search for CC-licensed reference images using multiple providers.

    Tries providers in REFERENCE_IMAGE_SEARCH_PROVIDERS order until enough
    results are found or all have been tried. Merges and deduplicates by URL.

    Raises only if the primary provider (google) fails and no fallback succeeds.
    """
    providers = _get_provider_order()
    seen_urls: set[str] = set()
    all_results: list[dict] = []
    last_error: Exception | None = None

    for pid in providers:
        func = _PROVIDER_FUNCS.get(pid)
        if not func:
            logger.warning(f"[ReferenceImage] Unknown provider: {pid}")
            continue

        try:
            results = func(
                diagnosis=diagnosis,
                body_part=body_part,
                modality=modality,
                image_types=image_types,
                max_per_type=max_per_type,
            )
        except Exception as e:
            last_error = e
            logger.warning(f"[ReferenceImage] Provider {pid} error: {e}")
            continue

        added = 0
        for r in results:
            link = r.get("link", "")
            if link and link not in seen_urls:
                seen_urls.add(link)
                all_results.append(r)
                added += 1

        if added > 0:
            logger.info(f"[ReferenceImage] Provider {pid} returned {added} new results (total {len(all_results)})")
            # Stop once we have a reasonable set
            if len(all_results) >= max_per_type * 2:
                break

    if all_results:
        return all_results

    if last_error:
        raise last_error

    return []
