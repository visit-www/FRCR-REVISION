"""
OneDrive / Microsoft Graph service for Case DICOM Viewer.

Share link encoding, folder listing, image URL extraction.
"""

import base64
import logging
import re
from urllib.parse import urlparse, unquote

import requests

logger = logging.getLogger(__name__)

GRAPH_BASE = "https://graph.microsoft.com/v1.0"

# Image extensions for stack viewer
IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".gif", ".bmp", ".webp", ".tiff", ".tif"}


def _natural_sort_key(url: str):
    """
    Return a sort key for natural/human order (1, 2, 10 not 1, 10, 2).
    Uses the filename part of the URL so slice order is preserved.
    """
    path = urlparse(url).path or url
    name = path.rsplit("/", 1)[-1] if "/" in path else path
    name = unquote(name)
    # Split into alternating non-digits and digits; convert digits to int
    parts = re.split(r"(\d+)", name.lower())
    return tuple(int(p) if p.isdigit() else p for p in parts if p)


def encode_share_url(share_url: str) -> str | None:
    """
    Encode OneDrive share URL for Graph API.

    Per Microsoft docs:
    1. Base64 encode the URL
    2. Convert to unpadded base64url: remove trailing =, replace / with _, + with -
    3. Prepend u!

    Args:
        share_url: OneDrive share link (e.g. https://1drv.ms/... or onedrive.live.com)

    Returns:
        Encoded string for use in /shares/{encodedUrl}, or None if invalid
    """
    if not share_url or not isinstance(share_url, str):
        return None
    share_url = share_url.strip()
    if not share_url.startswith("http"):
        return None
    try:
        b64 = base64.b64encode(share_url.encode("utf-8")).decode("ascii")
        b64url = b64.rstrip("=").replace("/", "_").replace("+", "-")
        return f"u!{b64url}"
    except Exception as e:
        logger.warning("[CaseDicomViewer] encode_share_url failed: %s", e)
        return None


def _is_image(name: str) -> bool:
    """Check if filename has an image extension."""
    if not name:
        return False
    return any(name.lower().endswith(ext) for ext in IMAGE_EXTENSIONS)


def _fetch_children(
    access_token: str,
    drive_id: str,
    item_id: str,
    *,
    next_link: str | None = None,
) -> list:
    """
    Fetch all children of a drive item via Graph API.
    Follows @odata.nextLink to get all pages (Graph returns 200 items per page by default).
    """
    headers = {"Authorization": f"Bearer {access_token}"}
    all_children: list = []
    # Request up to 999 per page (Graph default is 200); nextLink still used if more
    url = next_link or f"{GRAPH_BASE}/drives/{drive_id}/items/{item_id}/children?$top=999"
    page = 0
    while url:
        page += 1
        resp = requests.get(url, headers=headers, timeout=60)
        resp.raise_for_status()
        data = resp.json()
        value = data.get("value", []) or []
        all_children.extend(value)
        url = data.get("@odata.nextLink") or None
        if url and value:
            logger.debug("[CaseDicomViewer] Paginating folder children, page %s, got %s so far", page, len(all_children))
    if page > 1:
        logger.info("[CaseDicomViewer] Fetched %s children in %s page(s) for item %s", len(all_children), page, item_id[:20])
    return all_children


def list_folder_contents(
    access_token: str,
    encoded_share_id: str,
) -> dict:
    """
    List folder contents via Microsoft Graph API.

    GET /shares/{encodedShareId}/driveItem?$expand=children
    Then for each subfolder: GET /drives/{driveId}/items/{itemId}/children

    Returns:
        Dict with:
          - items: list of { name, id, is_folder, web_url, download_url? }
          - plans: dict of plan_name -> [image_url, ...] for subfolders (axial, sagittal, etc.)
    """
    headers = {"Authorization": f"Bearer {access_token}"}
    url = f"{GRAPH_BASE}/shares/{encoded_share_id}/driveItem?$expand=children"
    resp = requests.get(url, headers=headers, timeout=30)
    resp.raise_for_status()
    data = resp.json()

    items = []
    plans = {}
    raw_children = data.get("children") or []
    children = raw_children.get("value", raw_children) if isinstance(raw_children, dict) else (raw_children or [])
    parent_ref = data.get("parentReference", {})
    drive_id = parent_ref.get("driveId")

    for child in children:
        name = child.get("name", "")
        is_folder = "folder" in child
        web_url = child.get("webUrl") or ""
        download_url = child.get("@microsoft.graph.downloadUrl")
        item = {
            "name": name,
            "id": child.get("id"),
            "is_folder": is_folder,
            "web_url": web_url,
            "download_url": download_url,
        }
        items.append(item)

        # If subfolder, fetch its children and treat as a "plan" (axial, sagittal, etc.)
        if is_folder and drive_id:
            try:
                sub_children = _fetch_children(
                    access_token, drive_id, child.get("id", "")
                )
                image_urls = []
                for sub in sub_children:
                    sub_name = sub.get("name", "")
                    if _is_image(sub_name):
                        dl = sub.get("@microsoft.graph.downloadUrl")
                        if dl:
                            image_urls.append(dl)
                if image_urls:
                    # Natural sort by filename so slice order is preserved (1, 2, 10 not 1, 10, 2)
                    plans[name.lower()] = sorted(image_urls, key=_natural_sort_key)
            except Exception as e:
                logger.warning("[CaseDicomViewer] Failed to fetch subfolder %s: %s", name, e)

        # If root-level image file
        elif _is_image(name) and download_url:
            plans.setdefault("images", []).append(download_url)

    if plans.get("images"):
        plans["images"] = sorted(plans["images"], key=_natural_sort_key)

    return {"items": items, "plans": plans}


def parse_share_link_and_list(
    access_token: str,
    share_url: str,
) -> dict:
    """
    Encode share URL and list folder contents in one call.

    Returns:
        Dict with items, plans, encoded_share_id, or error
    """
    encoded = encode_share_url(share_url)
    if not encoded:
        return {"error": "Invalid share URL", "items": [], "plans": {}}

    try:
        result = list_folder_contents(access_token, encoded)
        result["encoded_share_id"] = encoded
        return result
    except requests.HTTPError as e:
        msg = e.response.text if e.response else str(e)
        logger.warning("[CaseDicomViewer] Graph API error: %s", msg)
        return {"error": f"OneDrive API error: {msg}", "items": [], "plans": {}}
    except Exception as e:
        logger.exception("[CaseDicomViewer] list_folder failed")
        return {"error": str(e), "items": [], "plans": {}}
