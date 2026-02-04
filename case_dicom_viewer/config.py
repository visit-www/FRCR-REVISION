"""
Case DICOM Viewer - Azure / OneDrive configuration.

Env vars:
  AZURE_CLIENT_ID - Azure app registration client ID
  AZURE_CLIENT_SECRET - Azure app registration client secret
  APP_URL - Base URL for OAuth redirect (e.g. https://yourapp.vercel.app)
"""

import os


def get_client_id() -> str | None:
    return os.environ.get("AZURE_CLIENT_ID") or os.environ.get("ONEDRIVE_CLIENT_ID")


def get_client_secret() -> str | None:
    return os.environ.get("AZURE_CLIENT_SECRET") or os.environ.get("ONEDRIVE_CLIENT_SECRET")


def get_app_url() -> str:
    """Base URL for OAuth redirect. Must match Azure app redirect URI."""
    return (
        os.environ.get("APP_URL")
        or os.environ.get("VERCEL_URL", "http://localhost:5000")
    ).rstrip("/")


def get_oauth_redirect_uri() -> str:
    return f"{get_app_url()}/case-dicom-viewer/oauth/callback"


# Microsoft Graph API scopes for OneDrive (User.Read, Files.Read)
# Note: offline_access, openid, profile are MSAL-reserved; do not include them
SCOPES = ["User.Read", "Files.Read"]

# Authority for personal Microsoft accounts (supports both personal and work/school)
AUTHORITY = "https://login.microsoftonline.com/common"

class Config:
    MAIL_FROM = "RadInsights <no-reply@radinsights.com>"
