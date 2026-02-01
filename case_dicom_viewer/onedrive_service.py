"""
OneDrive / Microsoft Graph service for Case DICOM Viewer.

Share link encoding, folder listing, image URL extraction.
"""

import base64
import logging
from urllib.parse import urlparse

import requests

logger = logging.getLogger(__name__)

GRAPH_BASE = "https://graph.microsoft.com/v1.0"

# Image extensions for stack viewer
IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".gif", ".bmp", ".webp", ".tiff", ".tif"}


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
) -> list:
    """Fetch children of a drive item via /drives/{driveId}/items/{itemId}/children."""
    headers = {"Authorization": f"Bearer {access_token}"}
    url = f"{GRAPH_BASE}/drives/{drive_id}/items/{item_id}/children"
    resp = requests.get(url, headers=headers, timeout=30)
    resp.raise_for_status()
    data = resp.json()
    return data.get("value", []) or []


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
                    plans[name.lower()] = sorted(image_urls)
            except Exception as e:
                logger.warning("[CaseDicomViewer] Failed to fetch subfolder %s: %s", name, e)

        # If root-level image file
        elif _is_image(name) and download_url:
            plans.setdefault("images", []).append(download_url)

    if plans.get("images"):
        plans["images"] = sorted(plans["images"])

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
