"""
PII Guard v2 — Server-side Patient Data Detection Middleware
Regex-only detection (no spaCy). Dual-layer protection with static/pii-guard.js (client).

Intercepts POST/PUT requests with JSON bodies and rejects any containing
patient-identifiable information (422 with tier info).
"""

import re
import logging
from flask import request, jsonify

logger = logging.getLogger(__name__)

# ======================== CONFIDENCE TIERS ========================

TIER_HIGH = 'high'
TIER_MEDIUM = 'medium'
TIER_LOW = 'low'

# Map pattern types to tiers
_TYPE_TIERS = {
    'NHS Number': TIER_HIGH,
    'US SSN': TIER_HIGH,
    'MRN / Hospital ID': TIER_HIGH,
    'Email Address': TIER_HIGH,
    'UK National Insurance Number': TIER_HIGH,
    'Aadhaar Number': TIER_HIGH,
    'PAN Card': TIER_HIGH,
    'Possible Patient ID': TIER_HIGH,
    'Patient Name': TIER_MEDIUM,
    'Doctor / Clinician Name': TIER_MEDIUM,
    'Date of Birth': TIER_MEDIUM,
    'Phone Number': TIER_MEDIUM,
    'Patient Address': TIER_MEDIUM,
    'UK Postcode': TIER_LOW,
    'Patient Age': TIER_LOW,
    'Patient Gender': TIER_LOW,
    'IP Address': TIER_LOW,
}


def _get_tier(pattern_type):
    return _TYPE_TIERS.get(pattern_type, TIER_MEDIUM)


# ======================== PII PATTERNS ========================

_NAME_STOP = (
    r'(?!(?:for|was|is|has|had|the|with|by|and|or|in|at|to|of|on|an|a'
    r'|this|that|no|who|will|may|should|could|would|not|been|being'
    r'|reviewed|presented|attended|referred|consulted|evaluated|diagnosed'
    r'|from|about|into|over|under|after|before|during|through)\b)'
)

# Invalid NINO prefixes
_NINO_INVALID = r'(?!(?:BG|GB|NK|KN|TN|NT|ZZ))'

PII_PATTERNS = [
    ('NHS Number', re.compile(
        r'\bNHS\s*(?:no|number|#)?[:\s]+\d{3}[-\s]?\d{3}[-\s]?\d{4}\b', re.IGNORECASE)),
    ('NHS Number', re.compile(
        r'\bNHS\s*(?:no|number|#)?[:\s]+\d{6,10}\b', re.IGNORECASE)),
    ('NHS Number', re.compile(r'\b\d{3}[-\s]\d{3}[-\s]\d{4}\b')),
    ('US SSN', re.compile(r'\b\d{3}-\d{2}-\d{4}\b')),
    ('MRN / Hospital ID', re.compile(
        r'\b(?:MRN|UHID|ACCN|ACC\s*NO|hospital\s*(?:id|no|number|#)|hosp\s*id|patient\s*(?:id|no)|medical\s*record)[:\s#]*\d{4,10}\b',
        re.IGNORECASE)),
    ('Date of Birth', re.compile(
        r'\b(?:DOB|dob|D\.O\.B|born|date\s*of\s*birth|birth\s*date)[:\s]*\d{1,2}[/\-.]\d{1,2}[/\-.]\d{2,4}\b',
        re.IGNORECASE)),
    ('UK Postcode', re.compile(r'\b[A-Z]{1,2}\d[A-Z\d]?\s*\d[A-Z]{2}\b', re.IGNORECASE)),
    ('Phone Number', re.compile(
        r'\b(?:phone|tel|mobile|cell|contact|ph)\s*[:=\-#]?\s*\+?[(\d][\d\s\-.()]{7,15}\d',
        re.IGNORECASE)),
    ('Phone Number', re.compile(
        r'\b(?:his|her|my|their|the)\s+(?:number|no|contact)\s+(?:is|was)\s*:?\s*\+?[\d][\d\s\-.()]{6,15}\d\b',
        re.IGNORECASE)),
    ('Phone Number', re.compile(
        r'\bnumber\s+(?:is|was)\s*:?\s*\+?[\d][\d\s\-.()]{6,15}\d\b',
        re.IGNORECASE)),
    ('Phone Number', re.compile(r'\+\d{1,3}[\s.-]?\d{4,5}[\s.-]?\d{4,6}\b')),
    ('Email Address', re.compile(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b')),
    ('Patient Name', re.compile(
        r'\b(?:patient\s*name|patient|pt\s*name|pt|name)\s*[:=\-]\s*(?:Mr|Mrs|Ms|Miss|Dr|Prof)\.?\s*[A-Za-z][A-Za-z\'-]+(?:\s+[A-Za-z][A-Za-z\'-]+){0,3}(?=\s*(?:[,;.\n|]|\bage\b|\bgender\b|\bsex\b|\bdob\b|\baddress\b|\bmrn\b|\bnhs\b|$))',
        re.IGNORECASE)),
    ('Patient Name', re.compile(
        r'\b(?:Mr|Mrs|Ms|Miss|Dr|Prof)\b\.?\s*'
        + _NAME_STOP + r'[A-Za-z][a-zA-Z\'-]+'
        + r'(?:\s+' + _NAME_STOP + r'[A-Za-z][a-zA-Z\'-]+){0,3}'
        + r'(?=\s*(?:[,;.\n|/()]|\d|\bage\b|\bgender\b|\bsex\b|\bdob\b|\bpresented\b|\battended\b|\bwas\b|\bis\b|\bhas\b|\bfor\b|\bwith\b|\breviewed\b|\breferred\b|$))'
    )),
    ('Patient Name', re.compile(
        r'\b(?:patient\s*name|pt\s*name)\s*[:=\-]\s*[A-Za-z][A-Za-z\'-]+(?:\s+[A-Za-z][A-Za-z\'-]+){0,3}(?=\s*(?:[,;.\n|]|\bage\b|\bgender\b|\bsex\b|\bdob\b|\baddress\b|\bmrn\b|\bnhs\b|$))',
        re.IGNORECASE)),
    ('Patient Name', re.compile(
        r'\bname\s*[:=\-]\s*[A-Za-z][A-Za-z\'-]+(?:\s+[A-Za-z][A-Za-z\'-]+){1,3}(?=\s*(?:[,;.\n|]|\bage\b|\bgender\b|\bsex\b|\bdob\b|\baddress\b|\bmrn\b|\bnhs\b|\d|$))',
        re.IGNORECASE)),
    ('Patient Name', re.compile(
        r'\d{1,3}[-\s]?year[-\s]?old\b[^.\n]{0,30}?'
        r'([A-Z][a-zA-Z\'-]+(?:\s+[A-Z][a-zA-Z\'-]+){1,3})'
        r'(?=\s*(?:[,;.\n|]|\bpresented\b|\battended\b|\bwas\b|\bis\b|\bhas\b|\bwith\b|$))')),
    ('Patient Name', re.compile(
        r'\b[Pp](?:atient|t)(?:\s*[:=\-]\s*|\s+)'
        + _NAME_STOP + r'([A-Z][a-zA-Z\'-]+'
        + r'(?:\s+' + _NAME_STOP + r'[A-Z][a-zA-Z\'-]+){0,3})'
        + r'(?=\s*(?:[,;.\n|/()]|\d|\bpresented\b|\battended\b|\bwas\b|\bis\b|\bhas\b|\bwith\b|\bfor\b|$))'
    )),
    ('Patient Name', re.compile(
        r'\b[Tt]his\s+is\s+'
        + _NAME_STOP + r'[A-Z][a-zA-Z\'-]{2,}'
        + r'(?:\s+' + _NAME_STOP + r'[A-Z][a-zA-Z\'-]+){1,3}'
        + r'(?=\s*,?\s+(?:a\s+|an\s+)?\d{1,3}[-\s]?years?[-\s]?old\b)'
    )),
    ('Doctor / Clinician Name', re.compile(
        r'\b(?:referred\s+by|reporting\s+(?:radiologist|doctor|consultant)|reported\s+by|consultant|registrar|SpR|SHO|GP)\b\s*[:=\-]?\s*(?:Dr\.?\s+)?[A-Z][a-zA-Z\'-]+(?:\s+[A-Z]\.?[a-zA-Z\'-]*){0,3}',
        re.IGNORECASE)),
    ('Doctor / Clinician Name', re.compile(
        r'\bDr\.?\s+[A-Z][a-zA-Z\'-]+(?:\s+[A-Z]\.?[a-zA-Z\'-]*){1,3}\b')),
    ('Possible Patient ID', re.compile(r'^\d{7,10}$', re.MULTILINE)),
    ('Patient Age', re.compile(
        r'\b(?:age|aged)\s*[:=\-]\s*\d{1,3}\b', re.IGNORECASE)),
    ('Patient Gender', re.compile(
        r'\b(?:gender|sex)\s*[:=\-]\s*(?:male|female|m|f|other|non-binary)\b', re.IGNORECASE)),
    ('Patient Address', re.compile(
        r'\b(?:address|addr|home)\s*[:=\-]\s*[A-Za-z0-9][A-Za-z0-9\s,.\'\-]{5,}', re.IGNORECASE)),
    ('UK National Insurance Number', re.compile(
        _NINO_INVALID + r'\b[A-Z]{2}\d{6}[A-D]\b', re.IGNORECASE)),
    ('IP Address', re.compile(
        r'\b(?:(?:25[0-5]|2[0-4]\d|1\d{2}|[1-9]?\d)\.){3}(?:25[0-5]|2[0-4]\d|1\d{2}|[1-9]?\d)\b')),
    ('Aadhaar Number', re.compile(r'\b\d{4}\s?\d{4}\s?\d{4}\b')),
    ('PAN Card', re.compile(r'\b[A-Z]{5}\d{4}[A-Z]\b')),
]

# ======================== MEDICAL ALLOWLIST ========================

MEDICAL_ALLOWLIST = frozenset({
    'C1','C2','C3','C4','C5','C6','C7',
    'T1','T2','T3','T4','T5','T6','T7','T8','T9','T10','T11','T12',
    'L1','L2','L3','L4','L5','S1','S2','S3','S4','S5',
    'C1-C2','C2-C3','C3-C4','C4-C5','C5-C6','C6-C7',
    'T1-T2','T2-T3','T3-T4','T4-T5','T5-T6','T6-T7','T7-T8','T8-T9','T9-T10','T10-T11','T11-T12','T12-L1',
    'L1-L2','L2-L3','L3-L4','L4-L5','L5-S1',
    'T0','T1A','T1B','T1C','T2A','T2B','T2C','T3A','T3B','T4A','T4B',
    'N0','N1','N1A','N1B','N2','N2A','N2B','N3','N3A','N3B',
    'M0','M1','M1A','M1B','M1C',
    'STAGE I','STAGE IA','STAGE IB','STAGE II','STAGE IIA','STAGE IIB','STAGE IIC',
    'STAGE III','STAGE IIIA','STAGE IIIB','STAGE IIIC','STAGE IV','STAGE IVA','STAGE IVB',
    'CT','MRI','MRA','MRV','PET','SPECT','DEXA','BMD',
    'FLAIR','DWI','ADC','SWI','GRE','STIR','FIESTA','CISS',
    'T1W','T2W','T1 WEIGHTED','T2 WEIGHTED','T1 W','T2 W',
    'DR','CR','US','XR',
    'HU','SUV','ADC VALUE','SUV MAX','SUVMAX',
    'IV CONTRAST',
    'G1','G2','G3','G4','GX',
    'BI-RADS','BIRADS','PI-RADS','PIRADS','TI-RADS','TIRADS','LI-RADS','LIRADS',
    'SA NODE','AV NODE','SI JOINT','SI JOINTS',
})

IMAGING_MODALITY_TERMS = frozenset({
    'CT','MRI','MRA','MRV','PET','SPECT','DEXA','BMD',
    'FLAIR','DWI','ADC','SWI','GRE','STIR','FIESTA','CISS',
    'XR','CXR','AXR','USS','HRCT','CECT','NCCT','MRE','MRCP',
})

NER_FALSE_POSITIVE_TERMS = frozenset({
    'GREY','BAKER','COLLES','CROHN','CUSHING','GRAVES','HASHIMOTO',
    'HODGKIN','WILMS','EWING','PAGET','DUPUYTREN','MECKEL','BARRETT',
    'BELL','ADDISON','MARFAN','PARKINSON','ALZHEIMER','RAYNAUD',
    'SJOGREN','WEGENER','BEHCET','HIRSCHSPRUNG','BUDD','CHIARI',
    'ARNOLD','DANDY','WALKER','KLATSKIN','WARTHIN','RICHTER',
    'VIRCHOW','TROUSSEAU','MURPHY','COURVOISIER','WHIPPLE',
    'HARTMANN','BILLROTH','NISSEN','BANKART','HILL','SACHS',
    'MOREL','LAVALLEE','MONTEGGIA','GALEAZZI','SMITH','BARTON',
    'CHAUFFEUR','BENNETT','ROLANDO','GAMEKEEPER','STENER','SEGOND',
    'PELLEGRINI','STIEDA','OSGOOD','SCHLATTER','SEVER','KOHLER',
    'FREIBERG','KIENBOCK','PREISER','LEGG','CALVE','PERTHES',
    'BLOUNT','SCHEUERMANN','CHANCE','JEFFERSON','HANGMAN',
    'SALTER','HARRIS','TILLAUX','MAISONNEUVE','LISFRANC','JONES',
    'MARCH','STRESS',
    'FLEISCHNER','KERLEY','RIGLER','CHILAIDITI','WESTERMARK','FELSON',
    'HAMPTON','CODMAN','SUNBURST','ONION','TERRY','THOMAS',
    'BOSNIAK','FISHER','CHILD','PUGH','DEAUVILLE','NEER','MASON',
    'WEBER','SCHATZKER','GARDEN','GUSTILO','ANDERSON','ROCKWOOD',
    'DENIS','MAGERL','FRANKEL','ASIA','HUNT','HESS','SPETZLER',
    'MARTIN','LUGANO','ANN','ARBOR','CLARK','BRESLOW','GLEASON',
    'FUHRMAN','EDMONDSON','STEINER','CLAVIEN','DINDO','BISMUTH',
    'TODANI','HINCHEY','ALVARADO','BALTHAZAR','DUKE',
    'WHITE','WARD','LIVER','BRAIN','SPINE','BOWEL','COLON',
    'RECTUM','KIDNEY','LUNG','HEART','AORTA','PANCREAS',
    'SPLEEN','ADRENAL','BLADDER','PROSTATE','UTERUS','OVARY',
    'BREAST','THYROID','TRACHEA','OESOPHAGUS','ESOPHAGUS',
    'FINDINGS','IMPRESSION','INDICATION','TECHNIQUE','COMPARISON',
    'CLINICAL','HISTORY','CONCLUSION','RECOMMENDATION','COMMENT',
    'OPINION','SUMMARY','DISCUSSION','PROTOCOL','PROCEDURE',
    'NORMAL','UNREMARKABLE','STABLE','UNCHANGED','MILD','MODERATE',
    'SEVERE','ACUTE','CHRONIC','BILATERAL','LATERAL','MEDIAL',
    'ANTERIOR','POSTERIOR','SUPERIOR','INFERIOR','PROXIMAL','DISTAL',
})


def _is_medical_term(match_text):
    if not match_text:
        return False
    upper = match_text.strip().upper()
    if upper in MEDICAL_ALLOWLIST:
        return True
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

# Route prefixes to skip PII checking
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


def check_pii(text):
    """Scan text for PII patterns (regex only). Returns list of (type, match) tuples."""
    if not text or not isinstance(text, str) or len(text) < 5:
        return []

    matches = []
    for pattern_type, regex in PII_PATTERNS:
        for match in regex.finditer(text):
            if not _is_medical_term(match.group()):
                matches.append((pattern_type, match.group()))

    # Filter out name matches containing imaging modality terms
    matches = [
        (ptype, ptext) for ptype, ptext in matches
        if ptype not in ('Patient Name', 'Doctor / Clinician Name')
        or not any(w.upper() in IMAGING_MODALITY_TERMS
                   for w in re.split(r'[\s:=\-]+', ptext) if w)
    ]

    # Filter out name matches where ALL content words are medical eponyms
    _TITLE_WORDS = {'PT', 'PATIENT', 'NAME', 'DR', 'MR', 'MRS', 'MS', 'MISS', 'PROF'}

    def _all_words_medical(ptext):
        words = [w for w in re.split(r'[\s:=.\-]+', ptext)
                 if w and w.upper() not in _TITLE_WORDS]
        return len(words) > 0 and all(w.upper() in NER_FALSE_POSITIVE_TERMS for w in words)

    matches = [
        (ptype, ptext) for ptype, ptext in matches
        if ptype not in ('Patient Name', 'Doctor / Clinician Name')
        or not _all_words_medical(ptext)
    ]

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

        if any(request.path.startswith(prefix) for prefix in SKIP_ROUTE_PREFIXES):
            return None

        if request.headers.get('X-PII-Override') == '1':
            logger.info(f"PII override accepted on {request.method} {request.path}")
            return None

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
            seen = set()
            unique = []
            for ptype, ptext in all_matches:
                key = f"{ptype}:{ptext}"
                if key not in seen:
                    seen.add(key)
                    unique.append({
                        'type': ptype,
                        'match': ptext,
                        'tier': _get_tier(ptype),
                    })

            logger.warning(
                f"PII blocked on {request.method} {request.path}: "
                f"{len(unique)} pattern(s) detected — "
                f"{[{'type': m['type'], 'match': m['match'][:20]} for m in unique]}"
            )

            return jsonify({
                'error': 'Patient-identifiable data detected.',
                'pii_detected': unique,
                'pii_blocked': True,
            }), 422

        return None
