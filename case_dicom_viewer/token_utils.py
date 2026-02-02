"""
Encrypt/decrypt OneDrive refresh tokens for server-side URL refresh.
Uses Fernet (symmetric) with key derived from Flask SECRET_KEY.
"""

from __future__ import annotations

import base64
import hashlib
import logging
import os
from typing import Optional

logger = logging.getLogger(__name__)


def _get_fernet_key():
    """Derive a Fernet key from SECRET_KEY."""
    secret = os.environ.get("SECRET_KEY") or ""
    if not secret:
        return None
    # Fernet needs 32 url-safe base64-encoded bytes
    digest = hashlib.sha256(secret.encode()).digest()
    return base64.urlsafe_b64encode(digest)


def encrypt_refresh_token(plaintext: str) -> Optional[str]:
    """Encrypt a refresh token for storage. Returns None if encryption unavailable."""
    if not plaintext or not plaintext.strip():
        return None
    try:
        from cryptography.fernet import Fernet
        key = _get_fernet_key()
        if not key:
            logger.warning("[CaseDicomViewer] SECRET_KEY not set, cannot encrypt refresh token")
            return None
        f = Fernet(key)
        return f.encrypt(plaintext.encode()).decode()
    except Exception as e:
        logger.warning("[CaseDicomViewer] encrypt_refresh_token failed: %s", e)
        return None


def decrypt_refresh_token(encrypted: str) -> Optional[str]:
    """Decrypt a stored refresh token. Returns None on failure."""
    if not encrypted or not encrypted.strip():
        return None
    try:
        from cryptography.fernet import Fernet
        key = _get_fernet_key()
        if not key:
            return None
        f = Fernet(key)
        return f.decrypt(encrypted.encode()).decode()
    except Exception as e:
        logger.debug("[CaseDicomViewer] decrypt_refresh_token failed: %s", e)
        return None
