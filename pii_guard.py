"""
PII Guard — Server-side Patient Data Detection Middleware
Dual-layer protection: this file (server) + static/pii-guard.js (client)

L1: Regex patterns for structured identifiers (NHS, MRN, DOB, postcodes, etc.)
L2: spaCy NER for free-text name detection (PERSON entities)

Intercepts POST/PUT requests with JSON bodies and rejects any containing
patient-identifiable information.
"""

import re
import logging
import os
from flask import request, jsonify

logger = logging.getLogger(__name__)

# ======================== spaCy NER (L2) ========================
# Lazy-loaded on first use to avoid cold-start penalty on every request.

_nlp = None
_nlp_loaded = False


def _get_nlp():
    """Lazy-load the spaCy NER model. Returns None if unavailable."""
    global _nlp, _nlp_loaded
    if _nlp_loaded:
        return _nlp
    _nlp_loaded = True
    try:
        import spacy
        _nlp = spacy.load('en_core_web_sm', disable=['parser', 'lemmatizer', 'tagger', 'attribute_ruler'])
        logger.info('PII Guard L2: spaCy en_core_web_sm loaded (NER only)')
    except Exception as exc:
        logger.warning(f'PII Guard L2: spaCy unavailable, falling back to regex only — {exc}')
        _nlp = None
    return _nlp

# ======================== PII PATTERNS ========================

# Common English words that must NOT be treated as parts of a person's name.
# Used as a per-word negative lookahead in name-detection patterns.
_NAME_STOP = (
    r'(?!(?:for|was|is|has|had|the|with|by|and|or|in|at|to|of|on|an|a'
    r'|this|that|no|who|will|may|should|could|would|not|been|being'
    r'|reviewed|presented|attended|referred|consulted|evaluated|diagnosed'
    r'|from|about|into|over|under|after|before|during|through)\b)'
)

PII_PATTERNS = [
    # NHS with keyword anchor (separators optional)
    ('NHS Number', re.compile(
        r'\bNHS\s*(?:no|number|#)?[:\s]+\d{3}[-\s]?\d{3}[-\s]?\d{4}\b', re.IGNORECASE)),
    # NHS with keyword anchor (short format — 6-10 digits)
    ('NHS Number', re.compile(
        r'\bNHS\s*(?:no|number|#)?[:\s]+\d{6,10}\b', re.IGNORECASE)),
    # NHS by format only (separators REQUIRED to avoid confusion with bare phone numbers)
    ('NHS Number', re.compile(r'\b\d{3}[-\s]\d{3}[-\s]\d{4}\b')),
    ('US SSN', re.compile(r'\b\d{3}-\d{2}-\d{4}\b')),
    ('MRN / Hospital ID', re.compile(
        r'\b(?:MRN|UHID|hospital\s*(?:id|no|number|#)|hosp\s*id|patient\s*id)[:\s#]*\d{4,10}\b', re.IGNORECASE)),
    ('Date of Birth', re.compile(
        r'\b(?:DOB|dob|D\.O\.B|born|date\s*of\s*birth|birth\s*date)[:\s]*\d{1,2}[/\-.]\d{1,2}[/\-.]\d{2,4}\b',
        re.IGNORECASE)),
    ('UK Postcode', re.compile(r'\b[A-Z]{1,2}\d[A-Z\d]?\s*\d[A-Z]{2}\b', re.IGNORECASE)),
    # Phone with keyword anchor (phone:, tel:, mobile: etc.)
    ('Phone Number', re.compile(
        r'\b(?:phone|tel|mobile|cell|contact|ph)\s*[:=\-#]?\s*\+?[(\d][\d\s\-.()]{7,15}\d',
        re.IGNORECASE)),
    # Phone with pronoun context (His number is 9876543210)
    ('Phone Number', re.compile(
        r'\b(?:his|her|my|their|the)\s+(?:number|no|contact)\s+(?:is|was)\s*:?\s*\+?[\d][\d\s\-.()]{6,15}\d\b',
        re.IGNORECASE)),
    # Phone with "number is" keyword (number is 9876543210)
    ('Phone Number', re.compile(
        r'\bnumber\s+(?:is|was)\s*:?\s*\+?[\d][\d\s\-.()]{6,15}\d\b',
        re.IGNORECASE)),
    # International phone (+country code)
    ('Phone Number', re.compile(r'\+\d{1,3}[\s.-]?\d{4,5}[\s.-]?\d{4,6}\b')),
    ('Email Address', re.compile(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b')),
    # Patient name with keyword prefix + title (patient name: Mr Smith)
    ('Patient Name', re.compile(
        r'\b(?:patient\s*name|patient|pt\s*name|pt|name)\s*[:=\-]\s*(?:Mr|Mrs|Ms|Miss|Dr|Prof)\.?\s*[A-Za-z][A-Za-z\'-]+(?:\s+[A-Za-z][A-Za-z\'-]+){0,3}(?=\s*(?:[,;.\n|]|\bage\b|\bgender\b|\bsex\b|\bdob\b|\baddress\b|\bmrn\b|\bnhs\b|$))',
        re.IGNORECASE)),
    # Patient name with title in prose (Mr. Suresh Kumar / Dr. Amit Singh)
    # Per-word stopword filter prevents "Dr. Amit Singh for evaluation" matching "for"
    ('Patient Name', re.compile(
        r'\b(?:Mr|Mrs|Ms|Miss|Dr|Prof)\b\.?\s*'
        + _NAME_STOP + r'[A-Za-z][a-zA-Z\'-]+'
        + r'(?:\s+' + _NAME_STOP + r'[A-Za-z][a-zA-Z\'-]+){0,3}'
        + r'(?=\s*(?:[,;.\n|/()]|\d|\bage\b|\bgender\b|\bsex\b|\bdob\b|\bpresented\b|\battended\b|\bwas\b|\bis\b|\bhas\b|\bfor\b|\bwith\b|\breviewed\b|\breferred\b|$))'
    )),
    # Patient name without title (requires "patient name:" or "pt name:" prefix)
    ('Patient Name', re.compile(
        r'\b(?:patient\s*name|pt\s*name)\s*[:=\-]\s*[A-Za-z][A-Za-z\'-]+(?:\s+[A-Za-z][A-Za-z\'-]+){0,3}(?=\s*(?:[,;.\n|]|\bage\b|\bgender\b|\bsex\b|\bdob\b|\baddress\b|\bmrn\b|\bnhs\b|$))',
        re.IGNORECASE)),
    # Bare "name:" keyword (no "patient"/"pt" prefix) — requires 2+ words to reduce false positives
    ('Patient Name', re.compile(
        r'\bname\s*[:=\-]\s*[A-Za-z][A-Za-z\'-]+(?:\s+[A-Za-z][A-Za-z\'-]+){1,3}(?=\s*(?:[,;.\n|]|\bage\b|\bgender\b|\bsex\b|\bdob\b|\baddress\b|\bmrn\b|\bnhs\b|\d|$))',
        re.IGNORECASE)),
    # Bare name after "X-year-old" context (52-year-old male, Suresh Kumar, presented)
    ('Patient Name', re.compile(
        r'\d{1,3}[-\s]?year[-\s]?old\b[^.\n]{0,30}?'
        r'([A-Z][a-zA-Z\'-]+(?:\s+[A-Z][a-zA-Z\'-]+){1,3})'
        r'(?=\s*(?:[,;.\n|]|\bpresented\b|\battended\b|\bwas\b|\bis\b|\bhas\b|\bwith\b|$))')),
    # Bare name after "patient"/"pt" keyword (with or without colon/separator)
    ('Patient Name', re.compile(
        r'\b[Pp](?:atient|t)(?:\s*[:=\-]\s*|\s+)'
        + _NAME_STOP + r'([A-Z][a-zA-Z\'-]+'
        + r'(?:\s+' + _NAME_STOP + r'[A-Z][a-zA-Z\'-]+){0,3})'
        + r'(?=\s*(?:[,;.\n|/()]|\d|\bpresented\b|\battended\b|\bwas\b|\bis\b|\bhas\b|\bwith\b|\bfor\b|$))'
    )),
    # Name introduced with "This is" + age context (This is Ramesh Gupta, 60-year-old)
    ('Patient Name', re.compile(
        r'\b[Tt]his\s+is\s+'
        + _NAME_STOP + r'[A-Z][a-zA-Z\'-]{2,}'
        + r'(?:\s+' + _NAME_STOP + r'[A-Z][a-zA-Z\'-]+){1,3}'
        + r'(?=\s*,?\s+(?:a\s+|an\s+)?\d{1,3}[-\s]?years?[-\s]?old\b)'
    )),
    # Doctor / clinician name with context keyword
    ('Doctor / Clinician Name', re.compile(
        r'\b(?:referred\s+by|reporting\s+(?:radiologist|doctor|consultant)|reported\s+by|consultant|registrar|SpR|SHO|GP)\b\s*[:=\-]?\s*(?:Dr\.?\s+)?[A-Z][a-zA-Z\'-]+(?:\s+[A-Z]\.?[a-zA-Z\'-]*){0,3}',
        re.IGNORECASE)),
    # Doctor name with Dr. title (requires 2+ name segments, supports initials like "Dr Gaurav G")
    ('Doctor / Clinician Name', re.compile(
        r'\bDr\.?\s+[A-Z][a-zA-Z\'-]+(?:\s+[A-Z]\.?[a-zA-Z\'-]*){1,3}\b')),
    # Bare 7-10 digit number on its own line (likely hospital number / MRN / NHS number)
    ('Possible Patient ID', re.compile(r'^\d{7,10}$', re.MULTILINE)),
    # Patient age
    ('Patient Age', re.compile(
        r'\b(?:age|aged)\s*[:=\-]\s*\d{1,3}\b', re.IGNORECASE)),
    # Patient gender/sex
    ('Patient Gender', re.compile(
        r'\b(?:gender|sex)\s*[:=\-]\s*(?:male|female|m|f|other|non-binary)\b', re.IGNORECASE)),
    # Patient address
    ('Patient Address', re.compile(
        r'\b(?:address|addr|home)\s*[:=\-]\s*[A-Za-z0-9][A-Za-z0-9\s,.\'\-]{5,}', re.IGNORECASE)),
    ('UK National Insurance Number', re.compile(
        r'\b[A-Z]{2}\d{6}[A-D]\b', re.IGNORECASE)),
    # IPv4 address (HIPAA Safe Harbor identifier #16)
    ('IP Address', re.compile(
        r'\b(?:(?:25[0-5]|2[0-4]\d|1\d{2}|[1-9]?\d)\.){3}(?:25[0-5]|2[0-4]\d|1\d{2}|[1-9]?\d)\b')),
    # Indian Aadhaar number (12 digits in 4-4-4 groups)
    ('Aadhaar Number', re.compile(r'\b\d{4}\s?\d{4}\s?\d{4}\b')),
    # Indian PAN card (ABCDE1234F format)
    ('PAN Card', re.compile(r'\b[A-Z]{5}\d{4}[A-Z]\b')),
]

# ======================== MEDICAL ALLOWLIST ========================
# Known medical/radiology terms that should NOT trigger PII warnings.
# Suppresses false positives from vertebral levels, TNM staging, MRI sequences, etc.

MEDICAL_ALLOWLIST = frozenset({
    # Vertebral levels
    'C1','C2','C3','C4','C5','C6','C7',
    'T1','T2','T3','T4','T5','T6','T7','T8','T9','T10','T11','T12',
    'L1','L2','L3','L4','L5','S1','S2','S3','S4','S5',
    # Vertebral ranges
    'C1-C2','C2-C3','C3-C4','C4-C5','C5-C6','C6-C7',
    'T1-T2','T2-T3','T3-T4','T4-T5','T5-T6','T6-T7','T7-T8','T8-T9','T9-T10','T10-T11','T11-T12','T12-L1',
    'L1-L2','L2-L3','L3-L4','L4-L5','L5-S1',
    # TNM staging
    'T0','T1A','T1B','T1C','T2A','T2B','T2C','T3A','T3B','T4A','T4B',
    'N0','N1','N1A','N1B','N2','N2A','N2B','N3','N3A','N3B',
    'M0','M1','M1A','M1B','M1C',
    'STAGE I','STAGE IA','STAGE IB','STAGE II','STAGE IIA','STAGE IIB','STAGE IIC',
    'STAGE III','STAGE IIIA','STAGE IIIB','STAGE IIIC','STAGE IV','STAGE IVA','STAGE IVB',
    # Radiology / imaging
    'CT','MRI','MRA','MRV','PET','SPECT','DEXA','BMD',
    'FLAIR','DWI','ADC','SWI','GRE','STIR','FIESTA','CISS',
    'T1W','T2W','T1 WEIGHTED','T2 WEIGHTED','T1 W','T2 W',
    'DR','CR','US','XR',
    # Measurements
    'HU','SUV','ADC VALUE','SUV MAX','SUVMAX',
    # Contrast
    'IV CONTRAST',
    # Grading
    'G1','G2','G3','G4','GX',
    # RADS scoring
    'BI-RADS','BIRADS','PI-RADS','PIRADS','TI-RADS','TIRADS','LI-RADS','LIRADS',
    # Anatomy abbreviations
    'SA NODE','AV NODE','SI JOINT','SI JOINTS',
})

# Imaging modality terms that should never be treated as part of a person's name.
# Prevents false positives like "Pt CT Facial Bones" being flagged as a patient name.
IMAGING_MODALITY_TERMS = frozenset({
    'CT','MRI','MRA','MRV','PET','SPECT','DEXA','BMD',
    'FLAIR','DWI','ADC','SWI','GRE','STIR','FIESTA','CISS',
    'XR','CXR','AXR','USS','HRCT','CECT','NCCT','MRE','MRCP',
})


def _is_medical_term(match_text):
    """Check if matched text is a known medical/radiology term (false positive suppression)."""
    if not match_text:
        return False
    upper = match_text.strip().upper()
    if upper in MEDICAL_ALLOWLIST:
        return True
    # Check hyphenated/slashed compound terms (e.g. C3-C4, L4/L5)
    parts = re.split(r'[-/]', upper)
    if len(parts) >= 2 and all(p.strip() in MEDICAL_ALLOWLIST for p in parts):
        return True
    return False


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
    '/api/pii-override-log',
    '/radiology-protocols/admin/',
    '/incidental-findings/admin/',
    '/admin/reporting-algorithms/',
    '/vetting/admin/',
    '/api/vetting/admin/',
    '/stripe/webhook',
)


def _spacy_scan(text):
    """L2: Use spaCy NER to detect PERSON entities in free text.
    Returns list of (pattern_type, matched_text) tuples.
    Only flags entities NOT already in the medical allowlist."""
    nlp = _get_nlp()
    if nlp is None:
        return []

    try:
        doc = nlp(text)
    except Exception:
        return []

    matches = []
    for ent in doc.ents:
        if ent.label_ != 'PERSON':
            continue
        name = ent.text.strip()
        if len(name) < 2:
            continue
        if _is_medical_term(name):
            continue
        # Skip if all words are imaging modality terms (e.g. "Dr CR")
        words = [w for w in re.split(r'[\s.]+', name) if w]
        if all(w.upper() in IMAGING_MODALITY_TERMS for w in words):
            continue
        matches.append(('Person Name (NER)', name))

    return matches


def check_pii(text):
    """
    Scan text for PII patterns.
    L1: Regex patterns for structured identifiers.
    L2: spaCy NER for free-text name detection.
    Returns list of (pattern_type, matched_text) tuples.
    """
    if not text or not isinstance(text, str) or len(text) < 5:
        return []

    matches = []

    # L1: Regex scan
    for pattern_type, regex in PII_PATTERNS:
        for match in regex.finditer(text):
            if not _is_medical_term(match.group()):
                matches.append((pattern_type, match.group()))

    # Filter out Patient/Doctor Name matches containing imaging modality terms
    # e.g. "Pt CT Facial Bones" — "CT" is an imaging modality, not a person's name
    matches = [
        (ptype, ptext) for ptype, ptext in matches
        if ptype not in ('Patient Name', 'Doctor / Clinician Name')
        or not any(w.upper() in IMAGING_MODALITY_TERMS
                   for w in re.split(r'[\s:=\-]+', ptext) if w)
    ]

    # L2: spaCy NER scan — catches names that regex misses
    ner_matches = _spacy_scan(text)
    # Only add NER matches that aren't already covered by regex
    regex_texts = {ptext.lower() for _, ptext in matches}
    for ptype, ptext in ner_matches:
        if ptext.lower() not in regex_texts:
            matches.append((ptype, ptext))

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

        # Honor client-side PII override (user confirmed not PII, logged to audit trail)
        if request.headers.get('X-PII-Override') == '1':
            logger.info(f"PII override accepted on {request.method} {request.path}")
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
                    unique.append({'type': ptype, 'match': ptext})

            logger.warning(
                f"PII blocked on {request.method} {request.path}: "
                f"{len(unique)} pattern(s) detected — "
                f"{[{'type': m['type'], 'match': m['match'][:20]} for m in unique]}"
            )

            return jsonify({
                'error': 'Patient-identifiable data detected. Please remove before submitting.',
                'pii_detected': unique,
                'pii_blocked': True,
            }), 422

        return None
