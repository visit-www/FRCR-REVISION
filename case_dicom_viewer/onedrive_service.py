"""
OneDrive / Microsoft Graph service for Case DICOM Viewer.

OAuth flow, share link parsing, folder listing. Uses MSAL or requests.
"""

import logging

logger = logging.getLogger(__name__)


def parse_share_link(share_url: str) -> dict | None:
    """
    Parse OneDrive share link and extract share ID for Graph API.

    Args:
        share_url: OneDrive share link (e.g. https://1drv.ms/... or onedrive.live.com)

    Returns:
        Dict with share_id, or None if parse fails
    """
    # TODO: Implement share ID extraction per Microsoft docs
    # shares/{encodedShareId}/driveItem/children
    logger.info("[CaseDicomViewer] parse_share_link stub: %s", share_url[:50])
    return None


def list_folder_contents(access_token: str, share_id: str, folder_path: str = "") -> list[dict]:
    """
    List folder contents via Microsoft Graph API.

    Returns list of items: { name, id, is_folder, web_url, ... }
    """
    # TODO: Implement Graph API call
    logger.info("[CaseDicomViewer] list_folder_contents stub")
    return []
