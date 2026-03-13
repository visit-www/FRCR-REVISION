"""
PII Guard — Server-side Patient Data Detection Middleware
Dual-layer protection: this file (server) + static/pii-guard.js (client)

Intercepts POST/PUT requests with JSON bodies and rejects any containing
patient-identifiable information (NHS numbers, MRNs, DOBs, etc.).
"""

import re
import logging
from flask import request, jsonify

logger = logging.getLogger(__name__)

# ======================== PII PATTERNS ========================

PII_PATTERNS = [
    ('NHS Number', re.compile(r'\b\d{3}[-\s]?\d{3}[-\s]?\d{4}\b')),
    ('US SSN', re.compile(r'\b\d{3}-\d{2}-\d{4}\b')),
    ('MRN / Hospital ID', re.compile(
        r'\b(?:MRN|mrn|Mrn|hospital\s*(?:id|no|number|#)|hosp\s*id)[:\s#]*\d{4,10}\b', re.IGNORECASE)),
    ('Date of Birth', re.compile(
        r'\b(?:DOB|dob|D\.O\.B|born|date\s*of\s*birth|birth\s*date)[:\s]*\d{1,2}[/\-.]\d{1,2}[/\-.]\d{2,4}\b',
        re.IGNORECASE)),
    ('UK Postcode', re.compile(r'\b[A-Z]{1,2}\d[A-Z\d]?\s*\d[A-Z]{2}\b', re.IGNORECASE)),
    ('Phone Number', re.compile(r'\b(?:\+44|0)\d{4}[\s-]?\d{5,6}\b')),
    ('Email Address', re.compile(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b')),
    ('Patient Name', re.compile(
        r'\b(?:patient|pt|name)[:\s]+(?:Mr|Mrs|Ms|Miss|Dr)\.?\s*[A-Z][a-z]+(?:\s+[A-Z][a-z]+)+\b',
        re.IGNORECASE)),
    ('UK National Insurance Number', re.compile(
        r'\b[A-Z]{2}\d{6}[A-D]\b', re.IGNORECASE)),
]

# Keys in JSON payloads that are safe to skip
SKIP_KEYS = frozenset({
    'password', 'token', 'csrf', 'username',
    'model', 'provider', 'slug', 'category', 'status',
    'modality', 'body_section', 'image_url', 'image_public_id',
    'image_type', 'filename', 'image_thumbnail_url',
})

# Route prefixes to skip PII checking (admin content creation, auth, backups)
SKIP_ROUTE_PREFIXES = (
    '/api/admin/',
    '/auth/',
    '/login',
    '/register',
    '/api/backup',
    '/on-call-helper/admin/',
    '/incidental-findings/admin/',
    '/admin/reporting-algorithms/',
)


def check_pii(text):
    """
    Scan text for PII patterns.
    Returns list of (pattern_type, matched_text) tuples.
    """
    if not text or not isinstance(text, str) or len(text) < 5:
        return []

    matches = []
    for pattern_type, regex in PII_PATTERNS:
        for match in regex.finditer(text):
            matches.append((pattern_type, match.group()))
    return matches


def _extract_strings(data, parent_key=''):
    """Recursively extract all string values from a JSON-like structure."""
    strings = []
    if isinstance(data, str):
        strings.append(data)
    elif isinstance(data, dict):
        for key, val in data.items():
            if key in SKIP_KEYS:
                continue
            strings.extend(_extract_strings(val, key))
    elif isinstance(data, list):
        for item in data:
            strings.extend(_extract_strings(item, parent_key))
    return strings


def create_pii_middleware(app):
    """Register a before_request hook that scans POST/PUT JSON for PII."""

    @app.before_request
    def _pii_check():
        if request.method not in ('POST', 'PUT'):
            return None

        # Skip admin, auth, and backup routes
        if any(request.path.startswith(prefix) for prefix in SKIP_ROUTE_PREFIXES):
            return None

        # Skip non-JSON requests (file uploads, form data)
        content_type = request.content_type or ''
        if 'application/json' not in content_type:
            return None

        data = request.get_json(silent=True)
        if not data:
            return None

        all_text = _extract_strings(data)
        all_matches = []
        for text in all_text:
            matches = check_pii(text)
            all_matches.extend(matches)

        if all_matches:
            # Deduplicate
            seen = set()
            unique = []
            for ptype, ptext in all_matches:
                key = f"{ptype}:{ptext}"
                if key not in seen:
                    seen.add(key)
                    unique.append({'type': ptype, 'match': ptext[:20] + '...' if len(ptext) > 20 else ptext})

            logger.warning(
                f"PII blocked on {request.method} {request.path}: "
                f"{len(unique)} pattern(s) detected — {[m['type'] for m in unique]}"
            )

            return jsonify({
                'error': 'Patient-identifiable data detected. Please remove before submitting.',
                'pii_detected': unique,
                'pii_blocked': True,
            }), 422

        return None
