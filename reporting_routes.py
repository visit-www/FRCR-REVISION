"""
Reporting & Algorithm Finder Routes

Flask blueprint for:
- Unified Algorithm Finder (search across existing cases + oncologic calculators + IF calculators)
- Case-based algorithmic approach: if a matching case exists, show its discussion;
  if not, generate via case_prelim_data, auto-create DRAFT case, email superadmin
- Non-oncologic reporting templates (Layer B: admin-curated trauma, grading, emergency)
- Admin management of reporting templates
"""

from flask import Blueprint, request, render_template, jsonify, redirect, url_for
from flask_login import login_required, current_user
from datetime import datetime
import json
import os
import re
import logging
import requests as http_requests
import time

from models import (
    db, Case, CaseStatus, Question, Answer, CaseApprovalQueue,
    RadiologyTemplate, ReportingAlgorithm,
    TNMCalculatorContent, ClinicalProtocol,
    IncidentalFindingCalculator, AJCCDiseaseSite, AJCCBodySection,
    User, AiPrelimCaseData, ContentRequest, RadiologyPearl,
    ContentIntelligence, UserGeneratedIntelligence,
    SubscriptionStatus, LearningQuestion,
)
from access_control import require_admin
from clinical_tool_generator import extract_html_content

logger = logging.getLogger(__name__)


def _get_ai_cross_links(content_type, content_id):
    """Load resolved cross-links from ContentIntelligence for a content item."""
    ci = ContentIntelligence.query.filter_by(
        content_type=content_type, content_id=content_id
    ).first()
    if not ci or not ci.cross_links_json:
        return []
    try:
        links = json.loads(ci.cross_links_json)
        return [link for link in links if link.get('url')]
    except (json.JSONDecodeError, TypeError):
        return []


# ==================== MODALITY NORMALIZATION ====================
_MODALITY_MAP = {
    'ct': 'CT', 'ct scan': 'CT', 'computed tomography': 'CT',
    'ct with contrast': 'CT', 'ct without contrast': 'CT',
    'ct with and without contrast': 'CT', 'cect': 'CT', 'ncct': 'CT',
    'mri': 'MRI', 'mr': 'MRI', 'magnetic resonance': 'MRI',
    'mri with contrast': 'MRI', 'mri without contrast': 'MRI',
    'mri with and without contrast': 'MRI',
    'us': 'Ultrasound', 'ultrasound': 'Ultrasound', 'usg': 'Ultrasound',
    'ultrasonography': 'Ultrasound',
    'xr': 'X-ray', 'x-ray': 'X-ray', 'x ray': 'X-ray',
    'plain film': 'X-ray', 'radiograph': 'X-ray', 'plain radiograph': 'X-ray',
    'nm': 'Nuclear Medicine', 'nuclear medicine': 'Nuclear Medicine',
    'scintigraphy': 'Nuclear Medicine',
    'pet': 'PET-CT', 'pet-ct': 'PET-CT', 'pet ct': 'PET-CT', 'petct': 'PET-CT',
    'fluoroscopy': 'Fluoroscopy', 'fluoro': 'Fluoroscopy',
}

# ==================== SEARCH SYNONYM EXPANSION ====================
# Each tuple is a group of synonyms. The LONGEST term is used as the canonical
# form for pg_trgm similarity() scoring; the original short-form is kept as an
# extra ILIKE pattern so abbreviations still match keywords/tags.
_SYNONYM_GROUPS = [
    # --- Clinical abbreviations ---
    ('pe', 'pulmonary embolism'),
    ('dvt', 'deep vein thrombosis'),
    ('sah', 'subarachnoid haemorrhage', 'subarachnoid hemorrhage'),
    ('sdh', 'subdural haematoma', 'subdural hematoma'),
    ('edh', 'epidural haematoma', 'epidural hematoma', 'extradural haematoma', 'extradural hematoma'),
    ('ich', 'intracerebral haemorrhage', 'intracerebral hemorrhage'),
    ('aaa', 'abdominal aortic aneurysm'),
    ('taa', 'thoracic aortic aneurysm'),
    ('rcc', 'renal cell carcinoma'),
    ('hcc', 'hepatocellular carcinoma'),
    ('nsclc', 'non-small cell lung cancer', 'non small cell lung cancer'),
    ('sclc', 'small cell lung cancer'),
    ('crc', 'colorectal cancer', 'colorectal carcinoma'),
    ('scc', 'squamous cell carcinoma'),
    ('bcc', 'basal cell carcinoma'),
    ('gist', 'gastrointestinal stromal tumour', 'gastrointestinal stromal tumor'),
    ('nac', 'necrotising acute cholecystitis', 'necrotizing acute cholecystitis', 'acute cholecystitis'),
    ('ivc', 'inferior vena cava'),
    ('svc', 'superior vena cava'),
    ('sma', 'superior mesenteric artery'),
    ('cbd', 'common bile duct'),
    ('nph', 'normal pressure hydrocephalus'),
    ('avf', 'arteriovenous fistula'),
    ('avm', 'arteriovenous malformation'),
    ('tia', 'transient ischaemic attack', 'transient ischemic attack'),
    ('acs', 'acute coronary syndrome'),
    ('copd', 'chronic obstructive pulmonary disease'),
    ('ild', 'interstitial lung disease'),
    ('ipf', 'idiopathic pulmonary fibrosis'),
    ('uip', 'usual interstitial pneumonia'),
    ('nsip', 'nonspecific interstitial pneumonia', 'non-specific interstitial pneumonia'),
    ('op', 'organising pneumonia', 'organizing pneumonia', 'cryptogenic organizing pneumonia'),
    ('dip', 'desquamative interstitial pneumonia'),
    ('pah', 'pulmonary arterial hypertension'),
    ('ards', 'acute respiratory distress syndrome'),
    ('ggo', 'ground glass opacity', 'ground-glass opacity'),

    # --- Guideline / classification systems ---
    ('fleischner', 'fleischner society', 'pulmonary nodule follow-up', 'lung nodule guidelines'),
    ('bosniak', 'bosniak classification', 'renal cyst classification'),
    ('li-rads', 'lirads', 'liver imaging reporting and data system', 'liver imaging'),
    ('lung-rads', 'lungrads', 'lung imaging reporting and data system'),
    ('bi-rads', 'birads', 'breast imaging reporting and data system'),
    ('pi-rads', 'pirads', 'prostate imaging reporting and data system'),
    ('ti-rads', 'tirads', 'thyroid imaging reporting and data system'),
    ('o-rads', 'orads', 'ovarian-adnexal reporting and data system'),
    ('ni-rads', 'nirads', 'neck imaging reporting and data system'),

    # --- Scoring systems ---
    ('aspects', 'alberta stroke programme early ct score', 'stroke ct score'),
    ('agatston', 'agatston score', 'coronary calcium score', 'calcium scoring'),
    ('child-pugh', 'child pugh', 'child-pugh score', 'liver cirrhosis score'),
    ('meld', 'model for end-stage liver disease'),
    ('recist', 'response evaluation criteria in solid tumors', 'response evaluation criteria in solid tumours'),

    # --- Technique / anatomy associations ---
    ('chemical shift', 'chemical shift imaging', 'in-phase out-of-phase', 'adrenal adenoma mri'),
    ('diffusion weighted', 'dwi', 'diffusion-weighted imaging', 'diffusion restriction'),
    ('dynamic contrast', 'dce', 'dynamic contrast enhanced', 'perfusion mri'),
    ('fat sat', 'fat saturation', 'fat-suppressed'),
    ('stir', 'short tau inversion recovery', 'stir sequence'),
    ('flair', 'fluid attenuated inversion recovery'),
    ('mrcp', 'magnetic resonance cholangiopancreatography'),
    ('mra', 'magnetic resonance angiography'),
    ('cta', 'ct angiography', 'ct angiogram'),
    ('ctpa', 'ct pulmonary angiography', 'ct pulmonary angiogram'),
    ('hrct', 'high resolution ct', 'high-resolution ct'),

    # --- Fracture classifications ---
    ('weber', 'weber classification', 'ankle fracture classification'),
    ('salter-harris', 'salter harris', 'salter-harris classification', 'paediatric fracture classification', 'pediatric fracture classification'),
    ('garden', 'garden classification', 'femoral neck fracture classification'),
    ('neer', 'neer classification', 'proximal humerus fracture classification'),
    ('schatzker', 'schatzker classification', 'tibial plateau fracture classification'),
    ('denis', 'denis classification', 'spinal fracture classification', 'thoracolumbar fracture classification'),
    ('aoc', 'ao classification', 'ao/ota fracture classification'),

    # --- UK / US spelling variants ---
    ('haemorrhage', 'hemorrhage'),
    ('haematoma', 'hematoma'),
    ('oedema', 'edema'),
    ('anaemia', 'anemia'),
    ('leukaemia', 'leukemia'),
    ('oesophagus', 'esophagus'),
    ('oesophageal', 'esophageal'),
    ('paediatric', 'pediatric'),
    ('gynaecological', 'gynecological', 'gynaecologic', 'gynecologic'),
    ('tumour', 'tumor'),
    ('colour', 'color'),
    ('favour', 'favor'),
    ('ischaemic', 'ischemic'),
    ('ischaemia', 'ischemia'),
    ('anaesthesia', 'anesthesia'),
    ('coeliac', 'celiac'),
    ('foetus', 'fetus'),
    ('foetal', 'fetal'),
    ('fibre', 'fiber'),
    ('grey', 'gray'),
    ('programme', 'program'),
    ('organising', 'organizing'),
    ('necrotising', 'necrotizing'),
    ('characterise', 'characterize'),
    ('standardise', 'standardize'),
    ('minimise', 'minimize'),
    ('specialise', 'specialize'),
]

# Build lookup: for any term in a group, maps to all other terms in that group
_SYNONYM_LOOKUP = {}
for _group in _SYNONYM_GROUPS:
    _lower_group = tuple(t.lower() for t in _group)
    for _term in _lower_group:
        if _term not in _SYNONYM_LOOKUP:
            _SYNONYM_LOOKUP[_term] = set()
        _SYNONYM_LOOKUP[_term].update(_lower_group)


def _expand_search_query(query):
    """Expand a search query using synonym groups.

    Returns (canonical_query, like_raw):
    - canonical_query: longest synonym (best for pg_trgm similarity scoring)
    - like_raw: '%alternate_term%' for ILIKE, catches the OTHER form.
      Returns None if no expansion happened.

    Examples:
        "PE"           → ("pulmonary embolism", "%pe%")
        "haemorrhage"  → ("haemorrhage",        "%hemorrhage%")
        "hemorrhage"   → ("haemorrhage",        "%hemorrhage%")
        "liver"        → ("liver",              None)
    """
    lower_q = query.lower().strip()
    if lower_q in _SYNONYM_LOOKUP:
        synonyms = _SYNONYM_LOOKUP[lower_q]
        canonical = max(synonyms, key=len)
        if canonical != lower_q:
            # User typed a short form / alternate — canonical expands it,
            # like_raw keeps the original so abbreviations in keywords match
            return canonical, f'%{lower_q}%'
        else:
            # User typed the longest form — pick shortest alternate
            # (abbreviation or alternate spelling) for like_raw
            others = sorted((s for s in synonyms if s != lower_q), key=len)
            if others:
                return lower_q, f'%{others[0]}%'
    return query, None


def normalize_modality(raw):
    """Normalize modality string to canonical form. Handles compound like 'CT/MRI'."""
    if not raw or not raw.strip():
        return None
    raw = raw.strip()
    # Handle compound modalities (e.g. "CT/MRI", "CT / MR")
    if '/' in raw:
        parts = [normalize_modality(p) for p in raw.split('/')]
        parts = [p for p in parts if p]
        # Deduplicate while preserving order
        seen = set()
        unique = []
        for p in parts:
            if p not in seen:
                seen.add(p)
                unique.append(p)
        return '/'.join(unique) if unique else None
    key = raw.lower().strip()
    return _MODALITY_MAP.get(key, raw.strip())

reporting_bp = Blueprint('reporting', __name__)

TIER_LIMITS = {
    'free':     {'sr_monthly': 10,   'radiq_monthly': 5,   'trial_days': 7},
    'standard': {'sr_monthly': 75,   'radiq_monthly': 20,  'trial_days': None},
    'elite':    {'sr_monthly': 1500, 'radiq_monthly': 60,  'trial_days': None},
}


def _check_ai_rate_limit(usage_type='sr'):
    """Tier-based monthly AI rate limit. Returns (ok, remaining, error_response)."""
    from datetime import date, timedelta
    from models import UserRole

    # Admin bypass
    if current_user.role == UserRole.ADMIN or getattr(current_user, 'is_superadmin', False):
        return True, 9999, None

    tier = getattr(current_user, 'subscription_tier', 'free') or 'free'
    limits = TIER_LIMITS.get(tier, TIER_LIMITS['free'])

    # Trial expiry check (free tier only, non-grandfathered)
    if tier == 'free' and current_user.trial_started_at is not None:
        trial_end = current_user.trial_started_at + timedelta(days=limits['trial_days'])
        if datetime.utcnow() > trial_end:
            return False, 0, (jsonify({
                'error': 'Your 7-day free trial has ended. Upgrade to continue using AI features.',
                'upgrade_required': True,
                'trial_expired': True,
            }), 429)

    # Monthly reset — if usage_reset_date is in a different month/year, reset counters
    today = date.today()
    reset_date = current_user.usage_reset_date
    if reset_date is None or reset_date.month != today.month or reset_date.year != today.year:
        current_user.sr_usage_month = 0
        current_user.radiq_usage_month = 0
        current_user.usage_reset_date = today

    # Pick the right counter & limit
    if usage_type == 'radiq':
        used = current_user.radiq_usage_month or 0
        limit = limits['radiq_monthly']
    else:
        used = current_user.sr_usage_month or 0
        limit = limits['sr_monthly']

    if used >= limit:
        return False, 0, (jsonify({
            'error': f'You have used all {limit} {"RadIQ queries" if usage_type == "radiq" else "Smart Reporter actions"} '
                     f'for this month. Upgrade for more.',
            'upgrade_required': True,
            'trial_expired': False,
            'limit': limit,
            'tier': tier,
        }), 429)

    # Increment the appropriate counter
    if usage_type == 'radiq':
        current_user.radiq_usage_month = used + 1
    else:
        current_user.sr_usage_month = used + 1

    # Also bump legacy daily counter for analytics
    today_date = date.today()
    if current_user.ai_usage_date != today_date:
        current_user.ai_usage_date = today_date
        current_user.ai_usage_count = 0
    current_user.ai_usage_count = (current_user.ai_usage_count or 0) + 1

    try:
        db.session.commit()
    except Exception:
        db.session.rollback()

    remaining = limit - (used + 1)
    return True, remaining, None


@reporting_bp.route('/api/smart-reporter/ai-usage', methods=['GET'])
@login_required
def get_ai_usage():
    """Return tier-aware AI usage info without incrementing counters."""
    from datetime import date, timedelta
    from models import UserRole

    tier = getattr(current_user, 'subscription_tier', 'free') or 'free'
    limits = TIER_LIMITS.get(tier, TIER_LIMITS['free'])

    # Monthly reset check
    today = date.today()
    reset_date = current_user.usage_reset_date
    if reset_date is None or reset_date.month != today.month or reset_date.year != today.year:
        sr_used = 0
        radiq_used = 0
    else:
        sr_used = current_user.sr_usage_month or 0
        radiq_used = current_user.radiq_usage_month or 0

    sr_limit = limits['sr_monthly']
    radiq_limit = limits['radiq_monthly']

    # Admin bypass
    if current_user.role == UserRole.ADMIN or getattr(current_user, 'is_superadmin', False):
        sr_used = 0
        radiq_used = 0
        sr_limit = 9999
        radiq_limit = 9999

    # Trial info
    trial_expired = False
    trial_days_left = None
    if tier == 'free' and current_user.trial_started_at is not None:
        trial_end = current_user.trial_started_at + timedelta(days=limits['trial_days'])
        now = datetime.utcnow()
        if now > trial_end:
            trial_expired = True
            trial_days_left = 0
        else:
            trial_days_left = (trial_end - now).days

    return jsonify({
        'sr_remaining': max(0, sr_limit - sr_used),
        'sr_limit': sr_limit,
        'radiq_remaining': max(0, radiq_limit - radiq_used),
        'radiq_limit': radiq_limit,
        'tier': tier,
        'trial_expired': trial_expired,
        'trial_days_left': trial_days_left,
        # Legacy compat keys
        'remaining_requests': max(0, sr_limit - sr_used),
        'daily_limit': sr_limit,
    })


# ==================== ALGORITHM FINDER (Unified Search) ====================

@reporting_bp.route('/api/algorithms/search')
@login_required
def unified_search():
    """
    Unified search across all algorithm types using pg_trgm.
    Returns results grouped by type: case, oncologic, incidental, reporting.
    Cases with published discussions are the PRIMARY source.
    """
    raw_query = request.args.get('q', '').strip()
    filter_type = request.args.get('type', '')
    limit = request.args.get('limit', 20, type=int)
    limit = min(limit, 50)
    offset = request.args.get('offset', 0, type=int)
    offset = max(offset, 0)

    if len(raw_query) < 2:
        return jsonify({'results': [], 'query': raw_query, 'total': 0, 'offset': 0, 'has_more': False})

    query, like_raw = _expand_search_query(raw_query)
    like_query = f'%{query}%'
    # When no synonym expansion, like_raw falls back to like_query (no-op extra OR)
    if like_raw is None:
        like_raw = like_query
    results = []

    try:
        from sqlalchemy import text

        # Search existing PUBLISHED cases by diagnosis (PRIMARY source)
        if filter_type in ('', 'case'):
            case_sql = text("""
                SELECT c.id, c.case_number, c.diagnosis, c.status,
                       c.module, c.body_part,
                       COALESCE(ci.summary, '') AS ci_summary,
                       GREATEST(
                           similarity(lower(c.diagnosis), lower(:query)),
                           similarity(
                               regexp_replace(lower(c.diagnosis), '^(right|left|bilateral|rt|lt|bilat)\\s+', ''),
                               lower(:query)
                           ),
                           COALESCE(similarity(ci.search_tags, lower(:query)), 0) * 0.8
                       ) AS sim
                FROM "case" c
                LEFT JOIN content_intelligence ci ON ci.content_type = 'case' AND ci.content_id = c.id
                WHERE c.status = 'PUBLISHED'
                  AND c.discussion IS NOT NULL
                  AND c.discussion != ''
                  AND (
                      similarity(lower(c.diagnosis), lower(:query)) > 0.1
                      OR c.diagnosis ILIKE :like_query
                      OR c.diagnosis ILIKE :like_raw
                      OR similarity(ci.search_tags, lower(:query)) > 0.15
                      OR ci.search_tags ILIKE :like_query
                      OR ci.search_tags ILIKE :like_raw
                  )
                ORDER BY sim DESC
                LIMIT :limit
            """)
            case_results = db.session.execute(case_sql, {
                'query': query, 'like_query': like_query, 'like_raw': like_raw, 'limit': limit
            }).fetchall()

            for r in case_results:
                bp_val = r.body_part.value if hasattr(r.body_part, 'value') else str(r.body_part) if r.body_part else None
                desc = r.ci_summary if r.ci_summary else (f'Case {r.case_number}' if r.case_number else 'Published case')
                results.append({
                    'type': 'case',
                    'id': r.id,
                    'title': r.diagnosis,
                    'body_section': bp_val,
                    'description': desc,
                    'subtitle': 'Algorithmic Approach Available',
                    'url': f'/view-case/{r.id}',
                    'case_id': r.id,
                    'similarity': float(r.sim) if r.sim else 0,
                })

        # Search oncologic (TNM calculators)
        if filter_type in ('', 'oncologic'):
            onc_sql = text("""
                SELECT tc.id, tc.slug, tc.cancer_name, tc.body_section, tc.description,
                       tc.staging_system,
                       similarity(tc.cancer_name, :query) AS sim
                FROM tnm_calculator_content tc
                WHERE tc.is_available = TRUE
                  AND (
                      similarity(tc.cancer_name, :query) > 0.1
                      OR tc.cancer_name ILIKE :like_query
                      OR tc.cancer_name ILIKE :like_raw
                  )
                ORDER BY sim DESC
                LIMIT :limit
            """)
            onc_results = db.session.execute(onc_sql, {
                'query': query, 'like_query': like_query, 'like_raw': like_raw, 'limit': limit
            }).fetchall()

            for r in onc_results:
                results.append({
                    'type': 'oncologic',
                    'id': r.id,
                    'slug': r.slug,
                    'title': r.cancer_name,
                    'body_section': r.body_section,
                    'description': r.description,
                    'subtitle': r.staging_system or 'AJCC 9th Edition',
                    'url': f'/tnm-calculator/{r.slug}',
                    'similarity': float(r.sim) if r.sim else 0,
                })

        # Search incidental findings calculators
        if filter_type in ('', 'incidental'):
            if_sql = text("""
                SELECT ifc.id, ifc.slug, ifc.finding_name, ifc.category, ifc.body_section,
                       ifc.description, ifc.guideline_source,
                       COALESCE(ci.summary, '') AS ci_summary,
                       GREATEST(
                           similarity(ifc.finding_name, :query),
                           COALESCE(similarity(ifc.keywords, :query), 0),
                           COALESCE(similarity(ci.search_tags, lower(:query)), 0) * 0.8
                       ) AS sim
                FROM incidental_finding_calculator ifc
                LEFT JOIN content_intelligence ci ON ci.content_type = 'radiology_tool' AND ci.content_id = ifc.id
                WHERE ifc.is_available = TRUE
                  AND (
                      similarity(ifc.finding_name, :query) > 0.1
                      OR similarity(ifc.keywords, :query) > 0.1
                      OR ifc.finding_name ILIKE :like_query
                      OR ifc.finding_name ILIKE :like_raw
                      OR ifc.keywords ILIKE :like_query
                      OR ifc.keywords ILIKE :like_raw
                      OR similarity(ci.search_tags, lower(:query)) > 0.15
                      OR ci.search_tags ILIKE :like_query
                      OR ci.search_tags ILIKE :like_raw
                  )
                ORDER BY sim DESC
                LIMIT :limit
            """)
            if_results = db.session.execute(if_sql, {
                'query': query, 'like_query': like_query, 'like_raw': like_raw, 'limit': limit
            }).fetchall()

            for r in if_results:
                desc = r.ci_summary if r.ci_summary else (r.description or '')
                results.append({
                    'type': 'incidental',
                    'id': r.id,
                    'slug': r.slug,
                    'title': r.finding_name,
                    'body_section': r.body_section,
                    'description': desc,
                    'subtitle': r.guideline_source or r.category,
                    'url': f'/incidental-findings/{r.slug}',
                    'similarity': float(r.sim) if r.sim else 0,
                })

        # Search reporting algorithms (admin-curated only, exclude anatomy_cache/user drafts)
        if filter_type in ('', 'reporting'):
            rt_sql = text("""
                SELECT ra.id, ra.slug, ra.title, ra.category, ra.body_section,
                       ra.description, ra.source_citation,
                       COALESCE(ra.is_ai_generated, FALSE) AS is_ai_generated,
                       COALESCE(ci.summary, '') AS ci_summary,
                       GREATEST(
                           similarity(ra.title, :query),
                           COALESCE(similarity(ra.keywords, :query), 0),
                           COALESCE(similarity(ci.search_tags, lower(:query)), 0) * 0.8
                       ) AS sim
                FROM reporting_algorithm ra
                LEFT JOIN content_intelligence ci ON ci.content_type = 'reporting_algorithm' AND ci.content_id = ra.id
                WHERE ra.is_available = TRUE
                  AND ra.origin = 'admin'
                  AND (
                      similarity(ra.title, :query) > 0.1
                      OR similarity(ra.keywords, :query) > 0.1
                      OR ra.title ILIKE :like_query
                      OR ra.title ILIKE :like_raw
                      OR ra.keywords ILIKE :like_query
                      OR ra.keywords ILIKE :like_raw
                      OR similarity(ci.search_tags, lower(:query)) > 0.15
                      OR ci.search_tags ILIKE :like_query
                      OR ci.search_tags ILIKE :like_raw
                  )
                ORDER BY sim DESC
                LIMIT :limit
            """)
            rt_results = db.session.execute(rt_sql, {
                'query': query, 'like_query': like_query, 'like_raw': like_raw, 'limit': limit
            }).fetchall()

            for r in rt_results:
                # source_citation may contain JSON — use category as subtitle instead
                subtitle = r.category or ''
                if r.source_citation and not r.source_citation.strip().startswith('{'):
                    subtitle = r.source_citation
                desc = r.ci_summary if r.ci_summary else (r.description or '')
                results.append({
                    'type': 'reporting',
                    'id': r.id,
                    'slug': r.slug,
                    'title': r.title,
                    'body_section': r.body_section,
                    'description': desc,
                    'subtitle': subtitle,
                    'url': f'/reporting-template/{r.slug}',
                    'similarity': float(r.sim) if r.sim else 0,
                    'is_ai_generated': bool(r.is_ai_generated),
                })

        # Search radiology templates (plain-text PACS reports)
        if filter_type in ('', 'template'):
            tmpl_sql = text("""
                SELECT rt.id, rt.slug, rt.title, rt.category, rt.body_section,
                       rt.description,
                       COALESCE(ci.summary, '') AS ci_summary,
                       GREATEST(
                           similarity(rt.title, :query),
                           COALESCE(similarity(rt.keywords, :query), 0),
                           COALESCE(similarity(ci.search_tags, lower(:query)), 0) * 0.8
                       ) AS sim
                FROM radiology_template rt
                LEFT JOIN content_intelligence ci ON ci.content_type = 'radiology_template' AND ci.content_id = rt.id
                WHERE rt.is_available = TRUE
                  AND (
                      similarity(rt.title, :query) > 0.1
                      OR similarity(rt.keywords, :query) > 0.1
                      OR rt.title ILIKE :like_query
                      OR rt.title ILIKE :like_raw
                      OR rt.keywords ILIKE :like_query
                      OR rt.keywords ILIKE :like_raw
                      OR similarity(ci.search_tags, lower(:query)) > 0.15
                      OR ci.search_tags ILIKE :like_query
                      OR ci.search_tags ILIKE :like_raw
                  )
                ORDER BY sim DESC
                LIMIT :limit
            """)
            tmpl_results = db.session.execute(tmpl_sql, {
                'query': query, 'like_query': like_query, 'like_raw': like_raw, 'limit': limit
            }).fetchall()

            for r in tmpl_results:
                desc = r.ci_summary if r.ci_summary else (r.description or '')
                results.append({
                    'type': 'template',
                    'id': r.id,
                    'slug': r.slug,
                    'title': r.title,
                    'body_section': r.body_section,
                    'description': desc,
                    'subtitle': r.category or 'Radiology Template',
                    'url': f'/radiology-template/view/{r.id}',
                    'similarity': float(r.sim) if r.sim else 0,
                })

        # Search anatomy snippets
        if filter_type in ('', 'anatomy'):
            anat_sql = text("""
                SELECT ra.id, ra.slug, ra.title, ra.body_section,
                       ra.description, ra.keywords,
                       COALESCE(ci.summary, '') AS ci_summary,
                       GREATEST(
                           similarity(ra.title, :query),
                           COALESCE(similarity(ra.keywords, :query), 0),
                           COALESCE(similarity(ci.search_tags, lower(:query)), 0) * 0.8
                       ) AS sim
                FROM reporting_algorithm ra
                LEFT JOIN content_intelligence ci ON ci.content_type = 'anatomy_snippet' AND ci.content_id = ra.id
                WHERE ra.is_available = TRUE
                  AND ra.origin = 'anatomy_cache'
                  AND (
                      similarity(ra.title, :query) > 0.1
                      OR similarity(ra.keywords, :query) > 0.1
                      OR ra.title ILIKE :like_query
                      OR ra.title ILIKE :like_raw
                      OR ra.keywords ILIKE :like_query
                      OR ra.keywords ILIKE :like_raw
                      OR similarity(ci.search_tags, lower(:query)) > 0.15
                      OR ci.search_tags ILIKE :like_query
                      OR ci.search_tags ILIKE :like_raw
                  )
                ORDER BY sim DESC
                LIMIT :limit
            """)
            anat_results = db.session.execute(anat_sql, {
                'query': query, 'like_query': like_query, 'like_raw': like_raw, 'limit': limit
            }).fetchall()

            for r in anat_results:
                desc = r.ci_summary if r.ci_summary else (r.description or '')
                results.append({
                    'type': 'anatomy',
                    'id': r.id,
                    'slug': r.slug,
                    'title': r.title,
                    'body_section': r.body_section,
                    'description': desc,
                    'subtitle': 'Anatomy Snippet',
                    'url': f'/anatomy-snippets/{r.slug}',
                    'similarity': float(r.sim) if r.sim else 0,
                })

        # Search radiology pearls
        if filter_type in ('', 'pearl'):
            pearl_sql = text("""
                SELECT rp.id, rp.pearl_text, rp.body_section, rp.modality,
                       rp.tags, rp.is_verified,
                       COALESCE(ci.summary, '') AS ci_summary,
                       GREATEST(
                           similarity(rp.pearl_text, :query),
                           COALESCE(similarity(rp.tags, :query), 0),
                           COALESCE(similarity(ci.search_tags, lower(:query)), 0) * 0.8
                       ) AS sim
                FROM radiology_pearl rp
                LEFT JOIN content_intelligence ci ON ci.content_type = 'radiology_pearl' AND ci.content_id = rp.id
                WHERE rp.is_verified = TRUE
                  AND (
                      similarity(rp.pearl_text, :query) > 0.1
                      OR similarity(rp.tags, :query) > 0.1
                      OR rp.pearl_text ILIKE :like_query
                      OR rp.pearl_text ILIKE :like_raw
                      OR rp.tags ILIKE :like_query
                      OR rp.tags ILIKE :like_raw
                      OR similarity(ci.search_tags, lower(:query)) > 0.15
                      OR ci.search_tags ILIKE :like_query
                      OR ci.search_tags ILIKE :like_raw
                  )
                ORDER BY sim DESC
                LIMIT :limit
            """)
            pearl_results = db.session.execute(pearl_sql, {
                'query': query, 'like_query': like_query, 'like_raw': like_raw, 'limit': limit
            }).fetchall()

            for r in pearl_results:
                pearl_title = r.pearl_text[:100] + '...' if len(r.pearl_text or '') > 100 else r.pearl_text
                results.append({
                    'type': 'pearl',
                    'id': r.id,
                    'title': pearl_title,
                    'body_section': r.body_section,
                    'description': r.modality or '',
                    'subtitle': 'Radiology Pearl',
                    'url': '/radiology-pearls',
                    'similarity': float(r.sim) if r.sim else 0,
                })

        # Search clinical protocols
        if filter_type in ('', 'protocol'):
            proto_sql = text("""
                SELECT cp.id, cp.title, cp.category, cp.keywords,
                       COALESCE(ci.summary, '') AS ci_summary,
                       GREATEST(
                           similarity(cp.title, :query),
                           COALESCE(similarity(cp.keywords, :query), 0),
                           COALESCE(similarity(ci.search_tags, lower(:query)), 0) * 0.8
                       ) AS sim
                FROM clinical_protocol cp
                LEFT JOIN content_intelligence ci ON ci.content_type = 'protocol' AND ci.content_id = cp.id
                WHERE cp.is_published = TRUE
                  AND (
                      similarity(cp.title, :query) > 0.1
                      OR similarity(cp.keywords, :query) > 0.1
                      OR cp.title ILIKE :like_query
                      OR cp.title ILIKE :like_raw
                      OR cp.keywords ILIKE :like_query
                      OR cp.keywords ILIKE :like_raw
                      OR similarity(ci.search_tags, lower(:query)) > 0.15
                      OR ci.search_tags ILIKE :like_query
                      OR ci.search_tags ILIKE :like_raw
                  )
                ORDER BY sim DESC
                LIMIT :limit
            """)
            proto_results = db.session.execute(proto_sql, {
                'query': query, 'like_query': like_query, 'like_raw': like_raw, 'limit': limit
            }).fetchall()

            for r in proto_results:
                desc = r.ci_summary if r.ci_summary else (r.keywords or '')
                results.append({
                    'type': 'protocol',
                    'id': r.id,
                    'title': r.title,
                    'description': desc,
                    'subtitle': r.category or 'Protocol',
                    'url': f'/radiology-protocols/view/{r.id}',
                    'similarity': float(r.sim) if r.sim else 0,
                })

        # Search TNM Essentials (AJCC disease sites)
        if filter_type in ('', 'tnm_case'):
            tnm_sql = text("""
                SELECT ds.id, ds.disease_name, ds.slug AS disease_slug,
                       bs.section_name, bs.slug AS section_slug,
                       GREATEST(
                           similarity(ds.disease_name, :query),
                           COALESCE(similarity(bs.section_name, :query), 0)
                       ) AS sim
                FROM ajcc_disease_site ds
                JOIN ajcc_body_section bs ON ds.body_section_id = bs.id
                WHERE (
                    similarity(ds.disease_name, :query) > 0.1
                    OR ds.disease_name ILIKE :like_query
                    OR ds.disease_name ILIKE :like_raw
                )
                ORDER BY sim DESC
                LIMIT :limit
            """)
            tnm_results = db.session.execute(tnm_sql, {
                'query': query, 'like_query': like_query, 'like_raw': like_raw, 'limit': limit
            }).fetchall()

            for r in tnm_results:
                results.append({
                    'type': 'tnm_case',
                    'id': r.id,
                    'title': r.disease_name,
                    'body_section': r.section_name,
                    'description': f'TNM Essentials — {r.section_name}',
                    'subtitle': 'AJCC 9th Edition',
                    'url': f'/tnm/{r.section_slug}/{r.disease_slug}',
                    'similarity': float(r.sim) if r.sim else 0,
                })

        # Search verified+processed UGI (RadInsight Notes)
        if filter_type in ('', 'intelligence'):
            ugi_sql = text("""
                SELECT ugi.id, ugi.diagnosis, ugi.body_section, ugi.modality,
                       ugi.notes, ugi.search_tags,
                       GREATEST(
                           COALESCE(similarity(ugi.diagnosis, :query), 0),
                           COALESCE(similarity(ugi.search_tags, :query), 0)
                       ) AS sim
                FROM user_generated_intelligence ugi
                WHERE ugi.is_verified = TRUE
                  AND ugi.processing_status = 'processed'
                  AND (
                      similarity(ugi.diagnosis, :query) > 0.1
                      OR similarity(ugi.search_tags, :query) > 0.1
                      OR ugi.diagnosis ILIKE :like_query
                      OR ugi.diagnosis ILIKE :like_raw
                      OR ugi.search_tags ILIKE :like_query
                      OR ugi.search_tags ILIKE :like_raw
                  )
                ORDER BY sim DESC
                LIMIT :limit
            """)
            ugi_results = db.session.execute(ugi_sql, {
                'query': query, 'like_query': like_query, 'like_raw': like_raw, 'limit': limit
            }).fetchall()

            for r in ugi_results:
                # Show first note bullet as description preview
                notes_preview = ''
                if r.notes:
                    try:
                        notes_list = json.loads(r.notes)
                        if notes_list:
                            notes_preview = notes_list[0][:120]
                    except (json.JSONDecodeError, TypeError):
                        pass
                results.append({
                    'type': 'intelligence',
                    'id': r.id,
                    'title': r.diagnosis or 'RadInsight Note',
                    'body_section': r.body_section,
                    'description': notes_preview,
                    'subtitle': r.modality or 'RadInsight Note',
                    'url': f'/admin/intelligence?highlight={r.id}',
                    'similarity': float(r.sim) if r.sim else 0,
                })

    except Exception as exc:
        logger.warning(f"pg_trgm unified search failed, falling back to ILIKE: {exc}")
        results = _fallback_search(query, filter_type, limit, raw_query=raw_query)

    # Sort by similarity descending, with type priority as tiebreaker
    TYPE_PRIORITY = {
        'case': 0, 'protocol': 1, 'reporting': 2, 'template': 3,
        'oncologic': 4, 'tnm_case': 5, 'incidental': 6, 'anatomy': 7, 'pearl': 8, 'intelligence': 9,
    }
    results.sort(key=lambda r: (-r.get('similarity', 0), TYPE_PRIORITY.get(r.get('type'), 99)))

    total = len(results)
    paginated = results[offset:offset + limit]

    response = {
        'results': paginated,
        'query': raw_query,
        'total': total,
        'offset': offset,
        'limit': limit,
        'has_more': (offset + limit) < total,
    }
    if query.lower() != raw_query.lower():
        response['expanded_to'] = query
    return jsonify(response)


def _fallback_search(query, filter_type, limit, raw_query=None):
    """Fallback ILIKE search for SQLite compatibility."""
    results = []
    # Build list of ILIKE patterns: canonical form + raw form (if different)
    likes = [f'%{query}%']
    if raw_query and raw_query.lower() != query.lower():
        likes.append(f'%{raw_query}%')

    def _or_ilike(column):
        """Build OR condition across all synonym ILIKE patterns for a column."""
        return db.or_(*[column.ilike(l) for l in likes])

    if filter_type in ('', 'case'):
        cases = Case.query.filter(
            Case.status == CaseStatus.PUBLISHED,
            Case.discussion.isnot(None),
            Case.discussion != '',
            _or_ilike(Case.diagnosis),
        ).limit(limit).all()
        for c in cases:
            results.append({
                'type': 'case', 'id': c.id,
                'title': c.diagnosis,
                'body_section': c.body_part.value if c.body_part else None,
                'description': f'Case {c.case_number}' if c.case_number else 'Published case',
                'subtitle': 'Algorithmic Approach Available',
                'url': f'/view-case/{c.id}',
                'case_id': c.id,
                'similarity': 0.5,
            })

    if filter_type in ('', 'oncologic'):
        calcs = TNMCalculatorContent.query.filter(
            TNMCalculatorContent.is_available == True,
            _or_ilike(TNMCalculatorContent.cancer_name),
        ).limit(limit).all()
        for c in calcs:
            results.append({
                'type': 'oncologic', 'id': c.id, 'slug': c.slug,
                'title': c.cancer_name, 'body_section': c.body_section,
                'description': c.description,
                'subtitle': c.staging_system or 'AJCC 9th Edition',
                'url': f'/tnm-calculator/{c.slug}',
                'similarity': 0.5,
            })

    if filter_type in ('', 'incidental'):
        ifs = IncidentalFindingCalculator.query.filter(
            IncidentalFindingCalculator.is_available == True,
            db.or_(
                _or_ilike(IncidentalFindingCalculator.finding_name),
                _or_ilike(IncidentalFindingCalculator.keywords),
            ),
        ).limit(limit).all()
        for f in ifs:
            results.append({
                'type': 'incidental', 'id': f.id, 'slug': f.slug,
                'title': f.finding_name, 'body_section': f.body_section,
                'description': f.description,
                'subtitle': f.guideline_source or f.category,
                'url': f'/incidental-findings/{f.slug}',
                'similarity': 0.5,
            })

    if filter_type in ('', 'reporting'):
        templates = ReportingAlgorithm.query.filter(
            ReportingAlgorithm.is_available == True,
            ReportingAlgorithm.origin == 'admin',
            db.or_(
                _or_ilike(ReportingAlgorithm.title),
                _or_ilike(ReportingAlgorithm.keywords),
            ),
        ).limit(limit).all()
        for t in templates:
            sub = t.category or ''
            if t.source_citation and not t.source_citation.strip().startswith('{'):
                sub = t.source_citation
            results.append({
                'type': 'reporting', 'id': t.id, 'slug': t.slug,
                'title': t.title, 'body_section': t.body_section,
                'description': t.description,
                'subtitle': sub,
                'url': f'/reporting-template/{t.slug}',
                'similarity': 0.5,
            })

    if filter_type in ('', 'template'):
        tmpls = RadiologyTemplate.query.filter(
            RadiologyTemplate.is_available == True,
            db.or_(
                _or_ilike(RadiologyTemplate.title),
                _or_ilike(RadiologyTemplate.keywords),
            ),
        ).limit(limit).all()
        for t in tmpls:
            results.append({
                'type': 'template', 'id': t.id, 'slug': t.slug,
                'title': t.title, 'body_section': t.body_section,
                'description': t.description,
                'subtitle': t.category or 'Radiology Template',
                'url': f'/radiology-template/view/{t.id}',
                'similarity': 0.5,
            })

    if filter_type in ('', 'anatomy'):
        anats = ReportingAlgorithm.query.filter(
            ReportingAlgorithm.is_available == True,
            ReportingAlgorithm.origin == 'anatomy_cache',
            db.or_(
                _or_ilike(ReportingAlgorithm.title),
                _or_ilike(ReportingAlgorithm.keywords),
            ),
        ).limit(limit).all()
        for a in anats:
            results.append({
                'type': 'anatomy', 'id': a.id, 'slug': a.slug,
                'title': a.title, 'body_section': a.body_section,
                'description': a.description,
                'subtitle': 'Anatomy Snippet',
                'url': f'/anatomy-snippets/{a.slug}',
                'similarity': 0.5,
            })

    if filter_type in ('', 'pearl'):
        pearls = RadiologyPearl.query.filter(
            RadiologyPearl.is_verified == True,
            db.or_(
                _or_ilike(RadiologyPearl.pearl_text),
                _or_ilike(RadiologyPearl.tags),
            ),
        ).limit(limit).all()
        for p in pearls:
            results.append({
                'type': 'pearl', 'id': p.id,
                'title': p.pearl_text[:100] + '...' if len(p.pearl_text or '') > 100 else p.pearl_text,
                'body_section': p.body_section,
                'description': p.modality or '',
                'subtitle': 'Radiology Pearl',
                'url': '/radiology-pearls',
                'similarity': 0.5,
            })

    if filter_type in ('', 'protocol'):
        protos = ClinicalProtocol.query.filter(
            ClinicalProtocol.is_published == True,
            db.or_(
                _or_ilike(ClinicalProtocol.title),
                _or_ilike(ClinicalProtocol.keywords),
            ),
        ).limit(limit).all()
        for p in protos:
            results.append({
                'type': 'protocol', 'id': p.id,
                'title': p.title,
                'description': p.keywords or '',
                'subtitle': p.category or 'Protocol',
                'url': f'/radiology-protocols/view/{p.id}',
                'similarity': 0.5,
            })

    if filter_type in ('', 'tnm_case'):
        sites = AJCCDiseaseSite.query.filter(
            _or_ilike(AJCCDiseaseSite.disease_name),
        ).limit(limit).all()
        for s in sites:
            bs = AJCCBodySection.query.get(s.body_section_id)
            results.append({
                'type': 'tnm_case', 'id': s.id,
                'title': s.disease_name,
                'body_section': bs.section_name if bs else '',
                'description': f'TNM Essentials — {bs.section_name if bs else ""}',
                'subtitle': 'AJCC 9th Edition',
                'url': f'/tnm/{bs.slug if bs else "unknown"}/{s.slug}',
                'similarity': 0.5,
            })

    if filter_type in ('', 'intelligence'):
        ugis = UserGeneratedIntelligence.query.filter(
            UserGeneratedIntelligence.is_verified == True,
            UserGeneratedIntelligence.processing_status == 'processed',
            db.or_(
                _or_ilike(UserGeneratedIntelligence.diagnosis),
                _or_ilike(UserGeneratedIntelligence.search_tags),
            ),
        ).limit(limit).all()
        for u in ugis:
            notes_preview = ''
            notes_list = u.get_notes()
            if notes_list:
                notes_preview = notes_list[0][:120]
            results.append({
                'type': 'intelligence', 'id': u.id,
                'title': u.diagnosis or 'RadInsight Note',
                'body_section': u.body_section,
                'description': notes_preview,
                'subtitle': u.modality or 'RadInsight Note',
                'url': f'/admin/intelligence?highlight={u.id}',
                'similarity': 0.5,
            })

    return results


# ==================== CASE-BASED ALGORITHMIC APPROACH GENERATION ====================

@reporting_bp.route('/api/algorithms/generate', methods=['POST'])
@login_required
def generate_algorithmic_approach():
    """
    Generate an algorithmic approach for a diagnosis that has no existing case.

    Flow:
    1. Receive diagnosis query from radiologist
    2. Create a new Case in DRAFT status with that diagnosis
    3. Call generate_prelim_case_data() (same as suggest-case) to generate discussion + Q&A
    4. Apply generated content to the case
    5. Add to CaseApprovalQueue and email superadmin
    6. Return the generated discussion HTML immediately to the radiologist

    This enriches the case library with every new query.
    """
    # DEPRECATED (Feb 2026): Use /api/smart-reporter/generate-tree instead.
    # Kept for backward compatibility — generates ReportingAlgorithm cache entries.
    logger.info(f"[DEPRECATED] /api/algorithms/generate called by user {current_user.id}. "
                "Consider using /api/smart-reporter/generate-tree instead.")

    data = request.get_json()
    if not data:
        return jsonify({'error': 'JSON body required.'}), 400

    diagnosis = (data.get('diagnosis') or '').strip()
    if not diagnosis:
        return jsonify({'error': 'Diagnosis is required.'}), 400

    if len(diagnosis) > 500:
        return jsonify({'error': 'Diagnosis too long (max 500 characters).'}), 400

    # Optional metadata from the radiologist
    body_section = (data.get('body_section') or '').strip()
    notes = (data.get('notes') or '').strip()

    # Rate limit: max 10 algorithm-generated DRAFT cases per user
    draft_count = Case.query.filter_by(
        created_by_user_id=current_user.id,
        status=CaseStatus.DRAFT,
    ).count()
    if draft_count >= 10:
        return jsonify({
            'error': 'You have too many draft cases pending review. '
                     'Please wait for admin review before generating more.'
        }), 429

    # Step 1: Map body_section to BodyPart enum if provided
    body_part_enum = None
    module_enum = None
    if body_section:
        body_part_enum = _map_body_section_to_enum(body_section)
        module_enum = _map_body_section_to_module(body_section)

    # Step 2: Auto-generate case_number
    case_number = _generate_case_number(body_part_enum)

    # Step 3: Create DRAFT case
    try:
        case = Case(
            case_number=case_number,
            diagnosis=diagnosis,
            module=module_enum,
            body_part=body_part_enum,
            status=CaseStatus.DRAFT,
            is_public=False,
            created_by_user_id=current_user.id,
            contributor_name=current_user.full_name,
            contributor_notes=f"Auto-generated via Algorithm Finder. Query: {diagnosis}" + (
                f"\nBody section: {body_section}" if body_section else ""
            ) + (
                f"\nNotes: {notes}" if notes else ""
            ),
        )
        db.session.add(case)
        db.session.flush()  # Get case.id without committing yet
    except Exception as exc:
        db.session.rollback()
        logger.error(f"Failed to create draft case: {exc}")
        return jsonify({'error': f'Failed to create case: {exc}'}), 500

    # Step 4: Generate content using ai_prelim
    # (ai_algorithmic_reporter was removed in production hardening — Feb 2026)
    algorithmic_result = None
    used_new_reporter = False

    if used_new_reporter and algorithmic_result:
        # New reporter path: use algorithmic_approach_html as discussion
        discussion_html = algorithmic_result.get('algorithmic_approach_html', '')
        case.discussion = discussion_html
        added_pairs = []  # New reporter doesn't generate Q&A pairs
        provider = algorithmic_result.get('provider', 'claude')
        model_name = algorithmic_result.get('model', '')

        # Save audit trail
        audit = AiPrelimCaseData(
            case_id=case.id,
            created_by_user_id=current_user.id,
            provider=provider,
            model_name=model_name,
            prompt_version='algorithmic_reporter_v1',
            request_payload=json.dumps({'diagnosis': diagnosis, 'body_section': body_section, 'notes': notes}),
            response_payload=json.dumps({
                'algorithmic_approach_html': discussion_html,
                'pacs_report': algorithmic_result.get('pacs_report', ''),
                'differential_diagnosis': algorithmic_result.get('differential_diagnosis', []),
                'recommendations': algorithmic_result.get('recommendations', []),
            }),
        )
        db.session.add(audit)

        # Cache as ReportingAlgorithm
        _create_reporting_template_from_algorithm(
            diagnosis=diagnosis,
            body_section=body_section,
            algorithmic_result=algorithmic_result,
            user_id=current_user.id,
        )

    else:
        # Fallback path: use ai_prelim (educational content)
        from ai_prelim import generate_prelim_case_data, AiPrelimError

        context = {
            'diagnosis': diagnosis,
            'module': module_enum.name if module_enum else '',
            'body_part': body_part_enum.name if body_part_enum else '',
            'notes': notes,
            'existing_summary': '',
            'sources': [
                'https://radiologyassistant.nl',
                'https://radiopaedia.org',
                'https://www.nice.org.uk',
            ],
        }

        try:
            result = generate_prelim_case_data(context, provider='claude')
        except AiPrelimError as exc:
            db.session.rollback()
            return jsonify({'error': f'AI generation failed: {exc}'}), 400
        except Exception as exc:
            db.session.rollback()
            logger.error(f"AI generation error: {exc}")
            return jsonify({'error': f'AI generation failed: {exc}'}), 500

        output = result.get('output', {})

        # Auto-fetch Radiopaedia images for case discussion
        try:
            from ai_pearl_generator import fetch_radiopaedia_images, render_reference_images_html
            rp_images = fetch_radiopaedia_images(diagnosis, max_images=3)
            if rp_images:
                captions = output.get('image_captions', [])
                image_html = render_reference_images_html(rp_images, captions)
                output['discussion'] = output.get('discussion', '') + image_html
        except Exception as img_exc:
            logger.warning("Failed to add images to case discussion: %s", img_exc)

        added_pairs = _apply_qa_pairs(case, output)
        discussion_html = _apply_discussion(case, output, result.get('provider', 'claude'), result.get('model', ''))
        provider = result.get('provider', 'claude')
        model_name = result.get('model', '')

        audit = AiPrelimCaseData(
            case_id=case.id,
            created_by_user_id=current_user.id,
            provider=provider,
            model_name=model_name,
            prompt_version=result.get('prompt_version', 'v1'),
            request_payload=json.dumps(context),
            response_payload=json.dumps(result),
        )
        db.session.add(audit)
        algorithmic_result = None

    # Step 7: Add to approval queue
    queue_entry = CaseApprovalQueue(
        case_id=case.id,
        submitted_by_user_id=current_user.id,
    )
    db.session.add(queue_entry)

    # Update status to PENDING_REVIEW so admin sees it
    case.status = CaseStatus.PENDING_REVIEW

    try:
        db.session.commit()
    except Exception as exc:
        db.session.rollback()
        logger.error(f"Failed to save generated case: {exc}")
        return jsonify({'error': f'Failed to save: {exc}'}), 500

    # Step 8: Email superadmin (best effort — don't fail if email fails)
    try:
        from auth import send_case_review_notification
        send_case_review_notification(case, current_user)
    except Exception as exc:
        logger.warning(f"Email notification failed for algorithm case {case.id}: {exc}")

    # Step 9: Return the generated content immediately
    response_data = {
        'success': True,
        'case_id': case.id,
        'case_number': case.case_number,
        'diagnosis': diagnosis,
        'discussion_html': discussion_html or '',
        'qa_pairs': added_pairs if not used_new_reporter else [],
        'qa_count': len(added_pairs) if not used_new_reporter else 0,
        'warnings': (algorithmic_result or {}).get('warnings', []),
        'safety_checklist': [],
        'sources': (algorithmic_result or {}).get('sources', []),
        'provider': provider,
        'model': model_name,
        'message': 'Algorithmic approach generated. Case created and submitted for admin review.',
        'case_url': f'/view-case/{case.id}',
        'used_new_reporter': used_new_reporter,
    }

    # Enrich with new reporter data if available
    if used_new_reporter and algorithmic_result:
        response_data['pacs_report'] = algorithmic_result.get('pacs_report', '')
        response_data['differential_diagnosis'] = algorithmic_result.get('differential_diagnosis', [])
        response_data['recommendations'] = algorithmic_result.get('recommendations', [])
        response_data['key_findings_checklist'] = algorithmic_result.get('key_findings_checklist', [])
        response_data['pitfalls'] = algorithmic_result.get('pitfalls', [])

    return jsonify(response_data)


def _apply_qa_pairs(case, output):
    """Create Question/Answer records from AI output. Mirrors app.py _apply_qa_pairs_from_output."""
    next_q = 1
    next_a = 1
    added = []

    for pair in output.get('qa_pairs', []) or []:
        q_text = (pair.get('question') or '').strip()
        a_text = (pair.get('answer') or '').strip()
        if not q_text and not a_text:
            continue

        if q_text:
            q_text = f'<div data-ai-generated="true" class="ai-generated-wrapper">{q_text}</div>'
            db.session.add(Question(case_id=case.id, question_number=next_q, question_text=q_text))
            next_q += 1
        if a_text:
            a_text = f'<div data-ai-generated="true" class="ai-generated-wrapper">{a_text}</div>'
            db.session.add(Answer(case_id=case.id, answer_number=next_a, answer_text=a_text))
            next_a += 1
        added.append({'question': q_text, 'answer': a_text})
    return added


def _apply_discussion(case, output, provider, model_name):
    """Build discussion HTML and apply to case. Mirrors app.py _apply_discussion_from_output."""
    discussion = output.get('discussion', '')
    if not discussion:
        return ''

    # Build attribution footer
    timestamp = datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')
    contributor_line = ''
    if current_user and current_user.full_name:
        contributor_line = f'with inputs from <strong>{current_user.full_name}</strong> '

    attribution = (
        f'<p style="font-size: 0.82em; color: #8b94a3; font-style: italic; margin: 4px 0 0 0;">'
        f'Generated {contributor_line}by RadInsights Intelligence on {timestamp}</p>'
    )

    footer = f'''<!-- Footer -->
<div style="background: #f3f4f6; padding: 12px 16px; border-top: 1px solid #e5e7eb; margin-top: 20px; border-radius: 0 0 8px 8px;">
    {attribution}
    <div style="display: flex; align-items: center; justify-content: flex-end; gap: 8px; margin-top: 6px;">
        <img style="width: 30px; height: 30px; object-fit: contain;" src="https://res.cloudinary.com/dx7b7chvn/image/upload/v1769503548/frcr-rev-logo-transp_o2hmrq.png" alt="RadiologyInsights Logo">
        <span style="font-size: 0.85em; color: #6b7280;">&copy; All rights reserved RadiologyInsights</span>
    </div>
</div>'''

    case.discussion = f"{discussion}{footer}"
    return discussion


def _map_body_section_to_enum(body_section):
    """Best-effort mapping from a body section string to BodyPart enum."""
    from models import BodyPart

    section_lower = body_section.lower()
    mappings = {
        'head': BodyPart.HEAD_NECK,
        'neck': BodyPart.HEAD_NECK,
        'brain': BodyPart.BRAIN_PITUITARY,
        'spine': BodyPart.SPINE,
        'thorax': BodyPart.LUNG_MEDIASTINUM,
        'chest': BodyPart.LUNG_MEDIASTINUM,
        'lung': BodyPart.LUNG_MEDIASTINUM,
        'cardiac': BodyPart.CARDIOVASCULAR,
        'heart': BodyPart.CARDIOVASCULAR,
        'vascular': BodyPart.CARDIOVASCULAR,
        'abdomen': BodyPart.GASTROINTESTINAL,
        'liver': BodyPart.HEPATOPANCREATICOBILIARY,
        'pancreas': BodyPart.HEPATOPANCREATICOBILIARY,
        'biliary': BodyPart.HEPATOPANCREATICOBILIARY,
        'renal': BodyPart.KUB,
        'kidney': BodyPart.KUB,
        'urinary': BodyPart.KUB,
        'adrenal': BodyPart.ADRENAL,
        'pelvis': BodyPart.GYNAECOLOGY,
        'breast': BodyPart.BREAST,
        'thyroid': BodyPart.THYROID_PARATHYROID,
        'msk': BodyPart.BONES,
        'musculoskeletal': BodyPart.BONES,
        'bone': BodyPart.BONES,
        'soft tissue': BodyPart.SOFT_TISSUE,
        'paediatric': BodyPart.MULTISYSTEM,
        'pediatric': BodyPart.MULTISYSTEM,
        'trauma': BodyPart.MULTISYSTEM,
    }

    for key, val in mappings.items():
        if key in section_lower:
            return val
    return None


def _map_body_section_to_module(body_section):
    """Best-effort mapping from a body section string to FRCRModule enum."""
    from models import FRCRModule

    section_lower = body_section.lower()
    mappings = {
        'head': FRCRModule.CNS_HEAD_NECK,
        'neck': FRCRModule.CNS_HEAD_NECK,
        'brain': FRCRModule.CNS_HEAD_NECK,
        'spine': FRCRModule.CNS_HEAD_NECK,
        'thorax': FRCRModule.CARDIOTHORACIC_VASCULAR,
        'chest': FRCRModule.CARDIOTHORACIC_VASCULAR,
        'lung': FRCRModule.CARDIOTHORACIC_VASCULAR,
        'cardiac': FRCRModule.CARDIOTHORACIC_VASCULAR,
        'heart': FRCRModule.CARDIOTHORACIC_VASCULAR,
        'vascular': FRCRModule.CARDIOTHORACIC_VASCULAR,
        'abdomen': FRCRModule.GASTROINTESTINAL,
        'liver': FRCRModule.GASTROINTESTINAL,
        'pancreas': FRCRModule.GASTROINTESTINAL,
        'biliary': FRCRModule.GASTROINTESTINAL,
        'gi': FRCRModule.GASTROINTESTINAL,
        'renal': FRCRModule.GENITOURINARY_BREAST,
        'kidney': FRCRModule.GENITOURINARY_BREAST,
        'urinary': FRCRModule.GENITOURINARY_BREAST,
        'adrenal': FRCRModule.GENITOURINARY_BREAST,
        'pelvis': FRCRModule.GENITOURINARY_BREAST,
        'breast': FRCRModule.GENITOURINARY_BREAST,
        'msk': FRCRModule.MUSCULOSKELETAL_TRAUMA,
        'musculoskeletal': FRCRModule.MUSCULOSKELETAL_TRAUMA,
        'bone': FRCRModule.MUSCULOSKELETAL_TRAUMA,
        'trauma': FRCRModule.MUSCULOSKELETAL_TRAUMA,
        'paediatric': FRCRModule.PAEDIATRIC,
        'pediatric': FRCRModule.PAEDIATRIC,
    }

    for key, val in mappings.items():
        if key in section_lower:
            return val
    return None


def _generate_case_number(body_part_enum):
    """Auto-generate a case number in the same format as suggest-case."""
    if body_part_enum:
        short_code = body_part_enum.name.replace('_', '').upper()[:6]
    else:
        short_code = 'ALGO'
    prefix = f"{short_code}-"

    existing = Case.query.filter(
        Case.case_number.ilike(f"{prefix}%")
    ).all()
    max_num = 0
    for c in existing:
        if c.case_number:
            match = re.search(r'-(\d+)$', c.case_number)
            if match:
                num = int(match.group(1))
                if num > max_num:
                    max_num = num
    return f"{prefix}{max_num + 1:03d}"


def _create_reporting_template_from_algorithm(diagnosis, body_section, algorithmic_result, user_id):
    """
    Cache an AI-generated algorithm as a ReportingAlgorithm for instant future search hits.
    If an entry with the same slug already exists, skip (no overwrite).
    """
    slug = re.sub(r'[^a-z0-9]+', '-', diagnosis.lower()).strip('-')
    if not slug:
        return None

    existing = ReportingAlgorithm.query.filter_by(slug=slug).first()
    if existing:
        logger.info(f"ReportingAlgorithm slug '{slug}' already exists, skipping cache creation.")
        return None

    # Build keywords from diagnosis + differentials
    keywords_parts = [diagnosis]
    for d in algorithmic_result.get('differential_diagnosis', []):
        if isinstance(d, dict) and d.get('diagnosis'):
            keywords_parts.append(d['diagnosis'])
    # Add suggested keywords from AI
    keywords_parts.extend(algorithmic_result.get('suggested_keywords', []))
    keywords = ', '.join(dict.fromkeys(keywords_parts))  # dedupe preserving order

    entry = ReportingAlgorithm(
        slug=slug,
        title=diagnosis,
        origin='ai_generated',
        category='ai_generated',
        body_section=body_section or None,
        description=f'AI-generated reporting algorithm for {diagnosis}',
        keywords=keywords,
        algorithm_html=algorithmic_result.get('algorithmic_approach_html', ''),
        source_citation='AI-generated — verify against published guidelines',
        is_available=True,
        is_ai_generated=True,
        generation_model=algorithmic_result.get('model', ''),
        generated_at=datetime.utcnow(),
        created_by_user_id=user_id,
    )

    db.session.add(entry)
    logger.info(f"Cached ReportingAlgorithm '{slug}' from algorithm generation.")
    return entry


@reporting_bp.route('/api/algorithms/browse')
@login_required
def browse_algorithms():
    """Browse all available algorithms grouped by body section."""
    # Published cases with discussions
    cases = Case.query.filter(
        Case.status == CaseStatus.PUBLISHED,
        Case.discussion.isnot(None),
        Case.discussion != '',
    ).order_by(Case.body_part, Case.diagnosis).all()

    oncologic = TNMCalculatorContent.query.filter_by(
        is_available=True
    ).order_by(TNMCalculatorContent.body_section, TNMCalculatorContent.cancer_name).all()

    ifs = IncidentalFindingCalculator.query.filter_by(
        is_available=True
    ).order_by(IncidentalFindingCalculator.category, IncidentalFindingCalculator.finding_name).all()

    grouped = {}

    for c in cases:
        section = c.body_part.value if c.body_part else 'Other'
        grouped.setdefault(section, []).append({
            'type': 'case', 'id': c.id, 'title': c.diagnosis,
            'description': f'Case {c.case_number}' if c.case_number else '',
            'url': f'/view-case/{c.id}',
        })

    for c in oncologic:
        section = c.body_section or 'Other'
        grouped.setdefault(section, []).append({
            'type': 'oncologic', 'slug': c.slug, 'title': c.cancer_name,
            'description': c.description,
            'url': f'/tnm-calculator/{c.slug}',
        })

    for f in ifs:
        section = f.body_section or f.category or 'Other'
        grouped.setdefault(section, []).append({
            'type': 'incidental', 'slug': f.slug, 'title': f.finding_name,
            'description': f.description,
            'url': f'/incidental-findings/{f.slug}',
        })

    return jsonify(grouped)


# ==================== REPORTING TEMPLATE VIEWS ====================

@reporting_bp.route('/reporting-template/<slug>')
@login_required
def view_reporting_template(slug):
    """View a specific admin-curated reporting template."""
    template = ReportingAlgorithm.query.filter_by(slug=slug, is_available=True).first_or_404()

    content = {'styles': '', 'body': ''}
    if template.template_html:
        content = extract_html_content(template.template_html)

    # For AI-generated templates, use algorithm_html as body if no template_html
    if not template.template_html and template.algorithm_html:
        content['body'] = template.algorithm_html

    # Parse resources from source_citation JSON
    resources = {'references': [], 'linked_cases': [], 'linked_tnm': [], 'pdfs': []}
    if template.source_citation:
        try:
            parsed = json.loads(template.source_citation)
            if isinstance(parsed, dict):
                resources = {
                    'references': parsed.get('references', []),
                    'linked_cases': parsed.get('linked_cases', []),
                    'linked_tnm': parsed.get('linked_tnm', []),
                    'pdfs': parsed.get('pdfs', []),
                }
            elif isinstance(parsed, list):
                resources['references'] = parsed
        except (json.JSONDecodeError, TypeError):
            if template.source_citation.strip():
                resources['references'] = [{'source': template.source_citation.strip(), 'version': '', 'url': ''}]

    # Determine which nav tab to highlight based on referrer context
    nav_active = request.args.get('from', 'templates')

    return render_template('reporting_template_view.html',
                           template=template,
                           content=content,
                           resources=resources,
                           nav_active=nav_active,
                           ai_cross_links=_get_ai_cross_links('reporting_algorithm', template.id))


@reporting_bp.route('/reporting-template/embed/<slug>')
@login_required
def embed_reporting_template(slug):
    """Render a reporting template in embed mode (for Smart Reporter Tool Panel)."""
    template = ReportingAlgorithm.query.filter_by(slug=slug, is_available=True).first_or_404()

    if template.template_html:
        return template.template_html
    elif template.algorithm_html:
        return template.algorithm_html
    else:
        return "Template content not available", 404


# ==================== USER: REPORTING ALGORITHMS BROWSE ====================

@reporting_bp.route('/reporting-algorithms')
@login_required
def browse_reporting_algorithms():
    """User-facing browse page for reporting algorithms (interactive decision trees)."""
    templates = ReportingAlgorithm.query.filter(
        ReportingAlgorithm.is_available == True,
        ReportingAlgorithm.origin == 'admin',
    ).order_by(
        ReportingAlgorithm.category, ReportingAlgorithm.title
    ).all()

    grouped = {}
    for t in templates:
        cat = t.category or 'Other'
        grouped.setdefault(cat, []).append(t)

    return render_template('reporting_algorithms_browse.html', grouped=grouped)


# ==================== USER: RADIOLOGY TEMPLATES BROWSE ====================

@reporting_bp.route('/knowledge-hub')
@login_required
def knowledge_hub():
    """Unified Knowledge Hub combining Radiology Pearls and Anatomy Snippets."""
    from models import UserRole

    # Fetch pearls (verified + own unverified)
    pearls = RadiologyPearl.query.filter(
        db.or_(
            RadiologyPearl.is_verified == True,
            RadiologyPearl.created_by_user_id == current_user.id,
        )
    ).order_by(RadiologyPearl.created_at.desc()).all()

    # Fetch anatomy snippets
    snippets = ReportingAlgorithm.query.filter(
        ReportingAlgorithm.origin == 'anatomy_cache',
        ReportingAlgorithm.is_available == True,
    ).order_by(ReportingAlgorithm.title).all()

    # Collect distinct modalities (normalized) from both pearls and snippets
    all_modality_parts = set()
    for item in list(pearls) + list(snippets):
        if item.modality:
            for part in item.modality.split('/'):
                normalized = normalize_modality(part)
                if normalized:
                    all_modality_parts.add(normalized)
    modalities = sorted(all_modality_parts)

    # Tag frequency for tag cloud (top 40)
    tag_counts = {}
    for p in pearls:
        if p.tags:
            for tag in p.tags.split(','):
                tag = tag.strip().lower()
                if tag:
                    tag_counts[tag] = tag_counts.get(tag, 0) + 1
    tag_cloud = sorted(tag_counts.items(), key=lambda x: -x[1])[:40]
    max_tag_count = tag_cloud[0][1] if tag_cloud else 1

    # Count items per body section (for body map)
    section_counts = {}
    for p in pearls:
        section = p.body_section or 'General'
        section_counts[section] = section_counts.get(section, 0) + 1
    for s in snippets:
        section = s.body_section or 'General'
        section_counts[section] = section_counts.get(section, 0) + 1

    is_admin = current_user.is_authenticated and current_user.role == UserRole.ADMIN

    return render_template('knowledge_hub.html',
        pearls=pearls,
        snippets=snippets,
        modalities=modalities,
        tag_cloud=tag_cloud,
        max_tag_count=max_tag_count,
        section_counts=section_counts,
        pearl_count=len(pearls),
        snippet_count=len(snippets),
        is_admin=is_admin,
        cloudinary_cloud_name=os.environ.get('CLOUDINARY_CLOUD_NAME', ''),
        cloudinary_upload_preset=os.environ.get('CLOUDINARY_UPLOAD_PRESET', ''),
    )


@reporting_bp.route('/admin/pearls')
@login_required
@require_admin
def admin_pearls():
    """Admin page for managing all radiology pearls."""
    pearls = RadiologyPearl.query.order_by(RadiologyPearl.created_at.desc()).all()
    return render_template('admin_pearls.html', pearls=pearls)


@reporting_bp.route('/anatomy-snippets')
@login_required
def browse_anatomy_snippets():
    """Redirect to Knowledge Hub."""
    return redirect(url_for('reporting.knowledge_hub'), code=301)


@reporting_bp.route('/anatomy-snippets/<slug>')
@login_required
def view_anatomy_snippet(slug):
    """View a single anatomy snippet in styled layout."""
    snippet = ReportingAlgorithm.query.filter(
        ReportingAlgorithm.slug == slug,
        ReportingAlgorithm.origin == 'anatomy_cache',
        ReportingAlgorithm.is_available == True,
    ).first_or_404()

    return render_template('anatomy_snippet_view.html', snippet=snippet,
                           ai_cross_links=_get_ai_cross_links('anatomy_snippet', snippet.id))


@reporting_bp.route('/api/anatomy-snippets/search')
@login_required
def search_anatomy_snippets():
    """Return cached anatomy snippets matching body_section and/or keyword query.

    Query params:
        body_section (str): Filter by body section (ILIKE match)
        q (str): Free-text search on title and keywords
        limit (int): Max results (default 10, max 20)
    """
    body_section = (request.args.get('body_section') or '').strip()
    q = (request.args.get('q') or '').strip()
    limit = min(int(request.args.get('limit', 10)), 20)

    query = ReportingAlgorithm.query.filter(
        ReportingAlgorithm.origin == 'anatomy_cache',
        ReportingAlgorithm.is_available == True,
    )

    if body_section:
        query = query.filter(ReportingAlgorithm.body_section.ilike(f'%{body_section}%'))
    if q:
        query = query.filter(db.or_(
            ReportingAlgorithm.title.ilike(f'%{q}%'),
            ReportingAlgorithm.keywords.ilike(f'%{q}%'),
        ))

    snippets = query.order_by(ReportingAlgorithm.title).limit(limit).all()

    return jsonify([{
        'id': s.id,
        'slug': s.slug,
        'title': s.title,
        'body_section': s.body_section,
        'modality': s.modality,
        'description': (s.description or '')[:200],
    } for s in snippets])


@reporting_bp.route('/radiology-pearls')
@login_required
def browse_radiology_pearls():
    """Redirect to Knowledge Hub."""
    return redirect(url_for('reporting.knowledge_hub'), code=301)


@reporting_bp.route('/reporting-templates')
@login_required
def browse_reporting_templates():
    """User-facing browse page for radiology templates (plain-text PACS reports)."""
    radiology_templates = RadiologyTemplate.query.filter_by(
        is_available=True
    ).order_by(RadiologyTemplate.title).all()

    return render_template('reporting_templates_browse.html',
                           radiology_templates=radiology_templates)


@reporting_bp.route('/radiology-template/text/<int:template_id>')
@login_required
def get_radiology_template_text(template_id):
    """User-facing endpoint to fetch radiology template text for preview/copy."""
    t = RadiologyTemplate.query.get_or_404(template_id)
    if not t.is_available or t.origin not in ('admin', 'personal'):
        return jsonify({'error': 'Template not available'}), 404
    return jsonify({
        'title': t.title,
        'pacs_report_text': t.template_text or '',
    })


@reporting_bp.route('/radiology-template/view/<int:template_id>')
@login_required
def view_radiology_template(template_id):
    """Full-page view for a radiology template with resources and Smart Reporter integration."""
    t = RadiologyTemplate.query.get_or_404(template_id)
    if not t.is_available or t.origin not in ('admin', 'personal'):
        from flask import abort
        abort(404)

    # Parse resources from source_citation JSON
    resources = {'references': [], 'pdfs': []}
    if t.source_citation:
        try:
            parsed = json.loads(t.source_citation)
            if isinstance(parsed, dict):
                resources = {
                    'references': parsed.get('references', []),
                    'pdfs': parsed.get('pdfs', []),
                }
            elif isinstance(parsed, list):
                resources['references'] = parsed
        except (json.JSONDecodeError, TypeError):
            if t.source_citation.strip():
                resources['references'] = [{'source': t.source_citation.strip(), 'version': '', 'url': ''}]

    return render_template('radiology_template_view.html', template=t, resources=resources,
                           ai_cross_links=_get_ai_cross_links('radiology_template', t.id))


# ==================== ADMIN: REPORTING ALGORITHM MANAGEMENT ====================

@reporting_bp.route('/admin/reporting-algorithms')
@require_admin
def admin_reporting_algorithms():
    """Admin page for managing reporting algorithms (interactive decision trees)."""
    origin_filter = request.args.get('origin', '').strip()
    if origin_filter:
        templates = ReportingAlgorithm.query.filter_by(origin=origin_filter).order_by(
            ReportingAlgorithm.category, ReportingAlgorithm.title
        ).all()
    else:
        templates = ReportingAlgorithm.query.filter(
            ReportingAlgorithm.origin.in_(['admin', 'user'])
        ).order_by(
            ReportingAlgorithm.category, ReportingAlgorithm.title
        ).all()
    return render_template('admin_reporting_algorithms.html', templates=templates,
                           origin_filter=origin_filter,
                           cloudinary_cloud_name=os.environ.get('CLOUDINARY_CLOUD_NAME', ''),
                           cloudinary_upload_preset=os.environ.get('CLOUDINARY_UPLOAD_PRESET', ''))


@reporting_bp.route('/admin/reporting-algorithms/edit/<int:algorithm_id>')
@require_admin
def edit_reporting_algorithm(algorithm_id):
    """Full-page editor for reporting algorithm content + metadata."""
    algorithm = ReportingAlgorithm.query.get_or_404(algorithm_id)
    return render_template('edit_reporting_algorithm.html', algorithm=algorithm,
                           origin_context=algorithm.origin,
                           cloudinary_cloud_name=os.environ.get('CLOUDINARY_CLOUD_NAME', ''),
                           cloudinary_upload_preset=os.environ.get('CLOUDINARY_UPLOAD_PRESET', ''))


@reporting_bp.route('/admin/reporting-algorithms/api', methods=['POST'])
@require_admin
def create_reporting_template():
    """API: Create a new reporting template."""
    data = request.get_json()
    if not data:
        return jsonify({'error': 'JSON body required.'}), 400

    title = data.get('title', '').strip()
    category = data.get('category', '').strip()
    if not title or not category:
        return jsonify({'error': 'title and category are required.'}), 400

    slug = re.sub(r'[^a-z0-9]+', '-', title.lower()).strip('-')

    existing = ReportingAlgorithm.query.filter_by(slug=slug).first()
    if existing:
        return jsonify({'error': f'Template with slug "{slug}" already exists.'}), 409

    _raw_template_html = data.get('template_html', '').strip() or None
    _raw_algorithm_html = data.get('algorithm_html', '').strip() or None

    allowed_origins = ('admin', 'anatomy_cache')
    req_origin = data.get('origin', 'admin').strip()
    if req_origin not in allowed_origins:
        req_origin = 'admin'

    template = ReportingAlgorithm(
        slug=slug,
        title=title,
        origin=req_origin,
        category=category,
        body_section=data.get('body_section', '').strip() or None,
        description=data.get('description', '').strip() or None,
        keywords=data.get('keywords', '').strip() or None,
        template_html=_raw_template_html,
        algorithm_html=_raw_algorithm_html,
        source_citation=data.get('source_citation', '').strip() or None,
        guideline_version=data.get('guideline_version', '').strip() or None,
        is_available=data.get('is_available', False),
        created_by_user_id=current_user.id,
    )

    db.session.add(template)
    db.session.commit()

    return jsonify(template.to_dict()), 201


@reporting_bp.route('/admin/reporting-algorithms/api/<int:template_id>', methods=['GET'])
@require_admin
def get_reporting_template(template_id):
    """API: Get a single reporting template (includes HTML for admin edit/preview)."""
    template = ReportingAlgorithm.query.get_or_404(template_id)
    return jsonify(template.to_dict(include_html=True))


@reporting_bp.route('/admin/reporting-algorithms/api/<int:template_id>/verify', methods=['POST'])
@require_admin
def verify_reporting_template(template_id):
    """API: Verify and publish a reporting template."""
    template = ReportingAlgorithm.query.get_or_404(template_id)
    template.verified_by_user_id = current_user.id
    template.verified_at = datetime.utcnow()
    template.is_available = True
    db.session.commit()
    return jsonify({'success': True, 'message': f'Template "{template.title}" verified and published.'})


@reporting_bp.route('/admin/reporting-algorithms/api/<int:template_id>', methods=['PUT'])
@require_admin
def update_reporting_template(template_id):
    """API: Update a reporting template."""
    template = ReportingAlgorithm.query.get_or_404(template_id)
    data = request.get_json()
    if not data:
        return jsonify({'error': 'JSON body required.'}), 400

    for field in ['title', 'category', 'body_section', 'modality', 'description', 'keywords',
                  'template_html', 'algorithm_html', 'source_citation', 'guideline_version',
                  'last_edit_note']:
        if field in data:
            val = data[field].strip() if isinstance(data[field], str) else data[field]
            if field == 'modality' and isinstance(val, str):
                val = normalize_modality(val)
            setattr(template, field, val)

    if 'is_available' in data:
        template.is_available = bool(data['is_available'])

    template.updated_at = datetime.utcnow()
    db.session.commit()

    return jsonify(template.to_dict())


@reporting_bp.route('/admin/reporting-algorithms/api/<int:template_id>', methods=['DELETE'])
@require_admin
def delete_reporting_template(template_id):
    """API: Delete a reporting template."""
    template = ReportingAlgorithm.query.get_or_404(template_id)
    title = template.title
    db.session.delete(template)
    db.session.commit()
    return jsonify({'success': True, 'message': f'Template "{title}" deleted.'})


@reporting_bp.route('/admin/reporting-algorithms/generate', methods=['POST'])
@require_admin
def generate_reporting_template():
    """API: Generate a reporting template using Claude (mirrors TNM generator pattern)."""
    data = request.get_json()
    if not data:
        return jsonify({'error': 'JSON body required.'}), 400

    title = data.get('title', '').strip()
    category = data.get('category', '').strip()
    if not title or not category:
        return jsonify({'error': 'title and category are required.'}), 400

    # Parse source_citation JSON into resources dict for URL fetching
    source_citation = data.get('source_citation', '')
    resources = None
    if source_citation:
        try:
            resources = json.loads(source_citation) if isinstance(source_citation, str) else source_citation
        except (json.JSONDecodeError, TypeError):
            pass

    try:
        from reporting_template_generator import generate_reporting_template_html
        result = generate_reporting_template_html(
            title=title,
            category=category,
            body_section=data.get('body_section', ''),
            source_citation=source_citation,
            additional_context=data.get('additional_context', ''),
            user_id=current_user.id,
            resources=resources,
        )
        return jsonify(result)

    except Exception as exc:
        logger.error(f"Reporting template generation failed: {exc}")
        return jsonify({'error': str(exc)}), 500


# ==================== RADIOLOGY TEMPLATES (ADMIN) ====================


@reporting_bp.route('/admin/radiology-templates')
@require_admin
def admin_radiology_templates():
    """Admin page for managing plain-text radiology report templates."""
    templates = RadiologyTemplate.query.order_by(
        RadiologyTemplate.created_at.desc()
    ).all()
    return render_template('admin_radiology_templates.html', templates=templates,
                           cloudinary_cloud_name=os.environ.get('CLOUDINARY_CLOUD_NAME', ''),
                           cloudinary_upload_preset=os.environ.get('CLOUDINARY_UPLOAD_PRESET', ''))


@reporting_bp.route('/admin/radiology-templates/generate', methods=['POST'])
@require_admin
def generate_radiology_template_route():
    """Generate a radiology report template via AI from clinical scenario."""
    data = request.get_json()
    if not data:
        return jsonify({'error': 'JSON body required.'}), 400

    clinical_scenario = (data.get('clinical_scenario') or '').strip()
    if not clinical_scenario:
        return jsonify({'error': 'clinical_scenario is required.'}), 400

    modality = (data.get('modality') or '').strip()
    body_section = (data.get('body_section') or '').strip()

    # Parse source_citation JSON into resources dict for URL fetching
    resources = None
    source_citation = data.get('source_citation', '')
    if source_citation:
        try:
            resources = json.loads(source_citation) if isinstance(source_citation, str) else source_citation
        except (json.JSONDecodeError, TypeError):
            pass

    try:
        from ai_smart_reporter import generate_radiology_template
        result = generate_radiology_template(
            clinical_scenario=clinical_scenario,
            modality=modality,
            body_section=body_section,
            resources=resources,
        )
    except Exception as exc:
        logger.error(f"Radiology template generation failed: {exc}")
        return jsonify({'error': str(exc)}), 500

    # Save to DB
    slug = re.sub(r'[^a-z0-9]+', '-', clinical_scenario.lower()).strip('-')
    # Handle slug collisions
    base_slug = slug
    counter = 1
    while RadiologyTemplate.query.filter_by(slug=slug).first():
        slug = f"{base_slug}-{counter}"
        counter += 1

    template = RadiologyTemplate(
        slug=slug,
        title=clinical_scenario,
        origin='admin',
        category=None,
        body_section=body_section,
        description=f"{modality} — {clinical_scenario}" if modality else clinical_scenario,
        template_text=result['template_text'],
        is_available=False,
        is_ai_generated=True,
        generation_model=result.get('model', ''),
        generation_prompt=clinical_scenario,
        generated_at=datetime.utcnow(),
        created_by_user_id=current_user.id,
    )
    db.session.add(template)
    db.session.commit()

    return jsonify({
        'success': True,
        'id': template.id,
        'slug': slug,
        'message': f'Template "{clinical_scenario}" generated successfully.',
    })


@reporting_bp.route('/admin/radiology-templates/api/<int:template_id>', methods=['GET'])
@require_admin
def get_radiology_template(template_id):
    """Fetch a single radiology template for editing."""
    t = RadiologyTemplate.query.get_or_404(template_id)
    return jsonify({
        'id': t.id,
        'title': t.title,
        'slug': t.slug,
        'category': t.category,
        'body_section': t.body_section or '',
        'description': t.description or '',
        'keywords': t.keywords or '',
        'pacs_report_text': t.template_text or '',
        'is_available': t.is_available,
        'is_ai_generated': t.is_ai_generated,
        'verified_at': t.verified_at.isoformat() if t.verified_at else None,
        'created_at': t.created_at.isoformat() if t.created_at else None,
    })


@reporting_bp.route('/admin/radiology-templates/api/<int:template_id>', methods=['PUT'])
@require_admin
def update_radiology_template(template_id):
    """Update a radiology template's text and metadata."""
    t = RadiologyTemplate.query.get_or_404(template_id)
    data = request.get_json()
    if not data:
        return jsonify({'error': 'JSON body required.'}), 400

    if 'title' in data:
        t.title = data['title'].strip()
    if 'body_section' in data:
        t.body_section = data['body_section'].strip()
    if 'keywords' in data:
        t.keywords = data['keywords'].strip()
    if 'description' in data:
        t.description = data['description'].strip()
    if 'pacs_report_text' in data:
        t.template_text = data['pacs_report_text']
    if 'is_available' in data:
        t.is_available = bool(data['is_available'])
    if 'last_edit_note' in data:
        t.last_edit_note = data['last_edit_note'].strip()

    t.updated_at = datetime.utcnow()
    db.session.commit()

    return jsonify({'success': True, 'message': 'Template updated.'})


@reporting_bp.route('/admin/radiology-templates/api/<int:template_id>/verify', methods=['POST'])
@require_admin
def verify_radiology_template(template_id):
    """Verify and publish a radiology template."""
    t = RadiologyTemplate.query.get_or_404(template_id)
    t.verified_by_user_id = current_user.id
    t.verified_at = datetime.utcnow()
    t.is_available = True
    db.session.commit()
    return jsonify({'success': True, 'message': f'Template "{t.title}" verified and published.'})


@reporting_bp.route('/admin/radiology-templates/api/<int:template_id>', methods=['DELETE'])
@require_admin
def delete_radiology_template(template_id):
    """Delete a radiology template."""
    t = RadiologyTemplate.query.get_or_404(template_id)
    title = t.title
    db.session.delete(t)
    db.session.commit()
    return jsonify({'success': True, 'message': f'Template "{title}" deleted.'})


# ==================== INTELLIGENCE ADMIN ROUTES ====================


@reporting_bp.route('/admin/intelligence')
@login_required
@require_admin
def admin_intelligence():
    """Admin page for managing UserGeneratedIntelligence records."""
    status_filter = request.args.get('status', '')
    body_section_filter = request.args.get('body_section', '')
    verified_filter = request.args.get('verified', '')

    query = UserGeneratedIntelligence.query

    if status_filter:
        query = query.filter(UserGeneratedIntelligence.processing_status == status_filter)
    if body_section_filter:
        query = query.filter(UserGeneratedIntelligence.body_section == body_section_filter)
    if verified_filter == 'true':
        query = query.filter(UserGeneratedIntelligence.is_verified == True)
    elif verified_filter == 'false':
        query = query.filter(UserGeneratedIntelligence.is_verified == False)

    records = query.order_by(UserGeneratedIntelligence.created_at.desc()).all()

    # Stats
    total = UserGeneratedIntelligence.query.count()
    pending = UserGeneratedIntelligence.query.filter_by(processing_status='pending').count()
    processed = UserGeneratedIntelligence.query.filter_by(processing_status='processed').count()
    verified = UserGeneratedIntelligence.query.filter_by(is_verified=True).count()

    return render_template('admin_intelligence.html',
                           records=records,
                           stats={'total': total, 'pending': pending, 'processed': processed, 'verified': verified},
                           status_filter=status_filter,
                           body_section_filter=body_section_filter,
                           verified_filter=verified_filter)


@reporting_bp.route('/admin/intelligence/<int:record_id>')
@login_required
@require_admin
def view_intelligence_record(record_id):
    """Dedicated view page for a single UGI record."""
    record = UserGeneratedIntelligence.query.get_or_404(record_id)
    return render_template('view_intelligence.html', record=record)


@reporting_bp.route('/admin/intelligence/api/<int:record_id>', methods=['GET'])
@login_required
@require_admin
def get_intelligence_record(record_id):
    """Get full details of a UGI record."""
    try:
        ugi = UserGeneratedIntelligence.query.get_or_404(record_id)
        return jsonify(ugi.to_dict())
    except Exception as exc:
        logger.error(f"get_intelligence_record({record_id}) failed: {exc}")
        return jsonify({'error': str(exc)}), 500


@reporting_bp.route('/admin/intelligence/api/<int:record_id>/verify', methods=['POST'])
@login_required
@require_admin
def verify_intelligence_record(record_id):
    """Verify a UGI record (makes it visible in search)."""
    ugi = UserGeneratedIntelligence.query.get_or_404(record_id)
    ugi.is_verified = True
    ugi.verified_by_user_id = current_user.id
    ugi.verified_at = datetime.utcnow()
    ugi.updated_at = datetime.utcnow()
    db.session.commit()
    return jsonify({'success': True, 'message': f'Record #{record_id} verified.'})


@reporting_bp.route('/admin/intelligence/api/<int:record_id>', methods=['DELETE'])
@login_required
@require_admin
def delete_intelligence_record(record_id):
    """Delete a UGI record."""
    ugi = UserGeneratedIntelligence.query.get_or_404(record_id)
    db.session.delete(ugi)
    db.session.commit()
    return jsonify({'success': True, 'message': f'Record #{record_id} deleted.'})


@reporting_bp.route('/admin/intelligence/api/process-pending', methods=['POST'])
@login_required
@require_admin
def process_pending_intelligence():
    """Process up to 20 pending UGI records via Haiku."""
    try:
        from ai_intelligence import process_ugi_for_record

        pending = UserGeneratedIntelligence.query.filter(
            UserGeneratedIntelligence.processing_status.in_(['pending', 'failed'])
        ).order_by(UserGeneratedIntelligence.created_at.asc()).limit(20).all()

        if not pending:
            return jsonify({'success': True, 'message': 'No pending records to process.', 'processed': 0})

        processed_count = 0
        for ugi in pending:
            if process_ugi_for_record(ugi.id):
                processed_count += 1

        return jsonify({
            'success': True,
            'message': f'Processed {processed_count} of {len(pending)} records.',
            'processed': processed_count,
            'total_attempted': len(pending),
        })
    except Exception as exc:
        logger.error(f"process_pending_intelligence failed: {exc}")
        return jsonify({'error': str(exc), 'message': f'Processing failed: {exc}'}), 500


@reporting_bp.route('/api/admin/backfill-intelligence', methods=['POST'])
@login_required
@require_admin
def backfill_content_intelligence():
    """Process up to 20 content items without intelligence records."""
    try:
        return _do_backfill_intelligence()
    except Exception as exc:
        logger.error(f"backfill_content_intelligence top-level error: {exc}")
        return jsonify({'error': str(exc), 'message': f'Backfill failed: {exc}'}), 500


def _do_backfill_intelligence():
    from ai_intelligence import process_content_intelligence

    # Find content items missing CI records
    content_types = [
        ('case', Case, 'diagnosis', lambda c: c.discussion or '',
         lambda c: c.body_part.value if c.body_part else '',
         Case.status == CaseStatus.PUBLISHED),
        ('protocol', ClinicalProtocol, 'title', lambda c: (c.content_html or '') + ' ' + (c.keywords or ''),
         lambda c: '', ClinicalProtocol.is_published == True),
        ('reporting_algorithm', ReportingAlgorithm, 'title', lambda c: (c.description or '') + ' ' + (c.keywords or ''),
         lambda c: c.body_section or '',
         db.and_(ReportingAlgorithm.is_available == True, ReportingAlgorithm.origin == 'admin')),
    ]

    processed_count = 0
    errors = 0

    for ctype, model_cls, title_field, content_fn, section_fn, extra_filter in content_types:
        if processed_count >= 20:
            break

        try:
            existing_ids = {ci.content_id for ci in
                            ContentIntelligence.query.filter_by(content_type=ctype).all()}
            items = model_cls.query.filter(extra_filter).all()
        except Exception as exc:
            logger.error(f"Backfill CI: failed to query {ctype}: {exc}")
            db.session.rollback()
            errors += 1
            continue

        for item in items:
            if processed_count >= 20:
                break
            if item.id in existing_ids:
                continue

            try:
                result = process_content_intelligence(
                    content_type=ctype,
                    content_id=item.id,
                    title=getattr(item, title_field, 'Untitled'),
                    body_section=section_fn(item),
                    content_text=content_fn(item),
                )
                ci = ContentIntelligence(
                    content_type=ctype,
                    content_id=item.id,
                    summary=result['summary'],
                    search_tags=result['search_tags'],
                    cross_links_json=result.get('cross_links_json'),
                    processing_model=result['processing_model'],
                    processing_tokens=result['processing_tokens'],
                    processed_at=datetime.utcnow(),
                )
                db.session.add(ci)
                db.session.commit()
                processed_count += 1
            except Exception as exc:
                db.session.rollback()
                logger.error(f"Backfill CI failed for {ctype}:{item.id}: {exc}")
                errors += 1

    return jsonify({
        'success': True,
        'message': f'Processed {processed_count} items ({errors} errors).',
        'processed': processed_count,
        'errors': errors,
    })


# ==================== SMART REPORTER ROUTES ====================


@reporting_bp.route('/smart-reporter')
@login_required
def smart_reporter():
    """Landing page for Smart Reporter — sessions loaded dynamically via JS."""
    return render_template('smart_reporter.html')


@reporting_bp.route('/api/smart-reporter/generate-tree', methods=['POST'])
@login_required
def smart_reporter_generate_tree():
    """Generate an algorithm tree for interactive scan reading walkthrough."""
    data = request.get_json()
    if not data:
        return jsonify({'error': 'JSON body required.'}), 400

    clinical_question = (data.get('clinical_question') or '').strip()
    if not clinical_question:
        return jsonify({'error': 'Clinical question is required.'}), 400
    if len(clinical_question) > 500:
        return jsonify({'error': 'Clinical question too long (max 500 characters).'}), 400

    modality = (data.get('modality') or '').strip()
    body_section = (data.get('body_section') or '').strip()

    # --- Cache lookup: check for existing ReportingAlgorithm with matching slug ---
    cache_slug = re.sub(r'[^a-z0-9]+', '-', clinical_question.lower()).strip('-')
    cached_template = None
    if cache_slug:
        cached_template = ReportingAlgorithm.query.filter_by(
            slug=cache_slug, is_available=True
        ).first()
        if not cached_template:
            cached_template = ReportingAlgorithm.query.filter_by(
                slug=cache_slug, created_by_user_id=current_user.id
            ).first()

    if cached_template and cached_template.algorithm_html:
        try:
            cached_tree = json.loads(cached_template.algorithm_html)
            if cached_tree and cached_tree.get('steps'):
                logger.info(f"Smart Reporter cache hit for slug '{cache_slug}'")
                return jsonify({
                    'success': True,
                    'algorithm_tree': cached_tree,
                    'cached': True,
                })
        except (json.JSONDecodeError, TypeError):
            logger.warning(f"Cache entry '{cache_slug}' has invalid algorithm_html, regenerating.")
            cached_template = None

    # Per-user daily rate limit (only for AI generation, not cache hits)
    ok, remaining, err = _check_ai_rate_limit()
    if not ok:
        return err

    # --- Generate algorithm tree via AI ---
    try:
        from ai_smart_reporter import generate_algorithm_tree, SmartReporterError
        result = generate_algorithm_tree(
            clinical_question=clinical_question,
            modality=modality,
            body_section=body_section,
        )
    except Exception as exc:
        logger.error(f"Smart Reporter tree generation failed: {exc}")
        from models import log_ai_usage
        log_ai_usage(current_user.id, 'generate_tree', provider='anthropic',
                     input_summary=clinical_question, status='error', error_message=str(exc))
        return jsonify({'error': f'Algorithm generation failed: {exc}'}), 500

    # Audit log for successful generation
    from models import log_ai_usage
    log_ai_usage(current_user.id, 'generate_tree', provider='anthropic',
                 model=result.get('model', ''), input_summary=clinical_question,
                 input_tokens=result.get('input_tokens'), output_tokens=result.get('output_tokens'))

    tree_json = json.dumps({
        'steps': result.get('steps', []),
        'lines_tubes_step': result.get('lines_tubes_step', {}),
        'incidental_findings_step': result.get('incidental_findings_step', {}),
        'report_template': result.get('report_template', {}),
    })

    # --- Cache write: store tree as ReportingAlgorithm for future reuse ---
    if cache_slug:
        existing_cache = ReportingAlgorithm.query.filter_by(slug=cache_slug).first()
        if not existing_cache:
            try:
                cache_entry = ReportingAlgorithm(
                    slug=cache_slug,
                    title=clinical_question,
                    origin='user',
                    category='uncategorized',
                    body_section=body_section or None,
                    description=f'AI-generated algorithm for: {clinical_question}',
                    keywords=f'{clinical_question}, {modality or ""}, {body_section or ""}',
                    algorithm_html=tree_json,
                    is_available=False,
                    is_ai_generated=True,
                    generation_model=result.get('model', ''),
                    generated_at=datetime.utcnow(),
                    created_by_user_id=current_user.id,
                )
                db.session.add(cache_entry)
                db.session.commit()
                logger.info(f"Cached Smart Reporter tree as ReportingAlgorithm '{cache_slug}'")
            except Exception as cache_exc:
                db.session.rollback()
                logger.warning(f"Failed to cache tree as ReportingAlgorithm: {cache_exc}")

    return jsonify({
        'success': True,
        'algorithm_tree': json.loads(tree_json),
        'remaining_requests': remaining,
    })


@reporting_bp.route('/api/smart-reporter/ask-claude', methods=['POST'])
@login_required
def smart_reporter_ask_claude():
    """Ask Claude a question about the current report."""
    data = request.get_json()
    if not data:
        return jsonify({'error': 'JSON body required.'}), 400

    question = (data.get('question') or '').strip()
    current_report = (data.get('current_report') or '').strip()

    if not question:
        return jsonify({'error': 'Question is required.'}), 400
    if len(question) > 1000:
        return jsonify({'error': 'Question too long (max 1000 characters).'}), 400

    ok, remaining, err = _check_ai_rate_limit()
    if not ok:
        return err

    try:
        from ai_smart_reporter import ask_claude_about_report, SmartReporterError
        result = ask_claude_about_report(
            current_report=current_report,
            question=question,
        )
    except Exception as exc:
        logger.error(f"Smart Reporter ask-claude failed: {exc}")
        from models import log_ai_usage
        log_ai_usage(current_user.id, 'ask_claude', provider='anthropic',
                     input_summary=question[:500], status='error', error_message=str(exc))
        return jsonify({'error': f'Failed to get response: {exc}'}), 500

    from models import log_ai_usage
    log_ai_usage(current_user.id, 'ask_claude', provider='anthropic',
                 model=result.get('model', ''), input_summary=question[:500],
                 input_tokens=result.get('input_tokens'), output_tokens=result.get('output_tokens'))

    return jsonify({
        'success': True,
        'answer': result.get('answer', ''),
        'remaining_requests': remaining,
    })


@reporting_bp.route('/api/smart-reporter/review-report', methods=['POST'])
@login_required
def smart_reporter_review_report():
    """Review a report for spelling, grammar, phrasing, and structure."""
    data = request.get_json()
    if not data:
        return jsonify({'error': 'JSON body required.'}), 400

    report_text = (data.get('report_text') or '').strip()

    if not report_text:
        return jsonify({'error': 'Report text is required.'}), 400
    if len(report_text) > 10000:
        return jsonify({'error': 'Report text too long (max 10000 characters).'}), 400

    ok, remaining, err = _check_ai_rate_limit()
    if not ok:
        return err

    try:
        from ai_smart_reporter import review_report, SmartReporterError
        result = review_report(report_text=report_text)
    except Exception as exc:
        logger.error(f"Smart Reporter review failed: {exc}")
        from models import log_ai_usage
        log_ai_usage(current_user.id, 'review_report', provider='anthropic',
                     input_summary=report_text[:200], status='error', error_message=str(exc))
        return jsonify({'error': f'Review failed: {exc}'}), 500

    from models import log_ai_usage
    log_ai_usage(current_user.id, 'review_report', provider='anthropic',
                 model=result.get('model', ''), input_summary=report_text[:200],
                 input_tokens=result.get('input_tokens'), output_tokens=result.get('output_tokens'))

    return jsonify({
        'success': True,
        'improved_report': result.get('improved_report', ''),
        'suggestions': result.get('suggestions', []),
        'remaining_requests': remaining,
    })


@reporting_bp.route('/api/smart-reporter/quick-review', methods=['POST'])
@login_required
def smart_reporter_quick_review():
    """Quick Check: lightweight spelling/grammar/phrasing review using Haiku."""
    data = request.get_json()
    if not data:
        return jsonify({'error': 'JSON body required.'}), 400

    report_text = (data.get('report_text') or '').strip()

    if not report_text:
        return jsonify({'error': 'Report text is required.'}), 400
    if len(report_text) > 10000:
        return jsonify({'error': 'Report text too long (max 10000 characters).'}), 400

    ok, remaining, err = _check_ai_rate_limit()
    if not ok:
        return err

    try:
        from ai_smart_reporter import quick_review, SmartReporterError
        result = quick_review(report_text=report_text)
    except Exception as exc:
        logger.error(f"Smart Reporter quick review failed: {exc}")
        return jsonify({'error': f'Quick review failed: {exc}'}), 500

    return jsonify({
        'success': True,
        'improved_report': result.get('improved_report', ''),
        'suggestions': result.get('suggestions', []),
        'remaining_requests': remaining,
    })


def _capture_ugi_silently(insights, modality, body_section, clinical_question, exam_type, user_id):
    """Silently save teaching_point + differentials as UGI. Never raises."""
    try:
        import hashlib
        teaching_point = (insights.get('teaching_point') or '').strip()
        differentials = insights.get('differentials_to_consider') or []
        if not teaching_point or len(teaching_point) < 30:
            return
        # SHA-256 dedup
        hash_input = teaching_point.lower() + json.dumps(sorted(differentials) if differentials else []).lower()
        content_hash = hashlib.sha256(hash_input.encode('utf-8')).hexdigest()
        if UserGeneratedIntelligence.query.filter_by(content_hash=content_hash).first():
            return  # duplicate
        ugi = UserGeneratedIntelligence(
            content_hash=content_hash,
            raw_teaching_point=teaching_point,
            raw_differentials=json.dumps(differentials) if differentials else None,
            modality=modality or None,
            body_section=body_section or None,
            clinical_question=clinical_question or None,
            exam_type=exam_type or None,
            processing_status='pending',
            created_by_user_id=user_id,
        )
        db.session.add(ugi)
        db.session.commit()
        logger.info(f"UGI captured silently for user {user_id}: {teaching_point[:60]}...")
    except Exception as exc:
        db.session.rollback()
        logger.warning(f"UGI silent capture failed (non-blocking): {exc}")


@reporting_bp.route('/api/smart-reporter/ai-assist', methods=['POST'])
@login_required
def smart_reporter_ai_assist():
    """Unified AI assistant: corrections + answer + insights in one call."""
    data = request.get_json()
    if not data:
        return jsonify({'error': 'JSON body required.'}), 400

    question = (data.get('question') or '').strip()
    report_text = (data.get('report_text') or '').strip()

    if not question:
        return jsonify({'error': 'Question is required.'}), 400
    if len(question) > 1000:
        return jsonify({'error': 'Question too long (max 1000 characters).'}), 400

    ok, remaining, err = _check_ai_rate_limit()
    if not ok:
        return err

    clinical_question = (data.get('clinical_question') or '')
    modality = (data.get('modality') or '')
    body_section = (data.get('body_section') or '')
    external_context = data.get('external_context')

    try:
        from ai_smart_reporter import unified_ai_assist, SmartReporterError
        result = unified_ai_assist(
            report_text=report_text,
            question=question,
            clinical_question=clinical_question,
            modality=modality,
            body_section=body_section,
            external_context=external_context,
        )
    except Exception as exc:
        logger.error(f"Smart Reporter AI assist failed: {exc}")
        from models import log_ai_usage
        log_ai_usage(current_user.id, 'ai_assist', provider='anthropic',
                     input_summary=question[:500], status='error', error_message=str(exc))
        return jsonify({'error': f'AI assist failed: {exc}'}), 500

    from models import log_ai_usage
    log_ai_usage(current_user.id, 'ai_assist', provider='anthropic',
                 model=result.get('model', ''), input_summary=question[:500],
                 input_tokens=result.get('input_tokens'), output_tokens=result.get('output_tokens'))

    # Silently capture teaching point + differentials as UGI (never blocks response)
    insights = result.get('insights') or {}
    if insights.get('teaching_point'):
        _capture_ugi_silently(
            insights=insights,
            modality=modality,
            body_section=body_section,
            clinical_question=clinical_question,
            exam_type=data.get('exam_type', ''),
            user_id=current_user.id,
        )

    return jsonify({
        'success': True,
        'response_type': result.get('response_type', 'advisory'),
        'corrections': result.get('corrections', []),
        'answer': result.get('answer', ''),
        'report_text': result.get('report_text', ''),
        'insights': insights,
        'remaining_requests': remaining,
    })


ALLOWED_REPORT_ACTIONS = {'mdt', 'sba', 'viva', 'email_colleague', 'email_patient'}

@reporting_bp.route('/api/smart-reporter/report-action', methods=['POST'])
@login_required
def smart_reporter_report_action():
    """Generate a report-derived action (MDT summary, SBA, viva, email)."""
    data = request.get_json()
    if not data:
        return jsonify({'error': 'JSON body required.'}), 400

    action = (data.get('action') or '').strip()
    report_text = (data.get('report_text') or '').strip()

    if action not in ALLOWED_REPORT_ACTIONS:
        return jsonify({'error': f'Invalid action. Must be one of: {", ".join(sorted(ALLOWED_REPORT_ACTIONS))}'}), 400
    if not report_text:
        return jsonify({'error': 'Report text is required.'}), 400

    ok, remaining, err = _check_ai_rate_limit()
    if not ok:
        return err

    clinical_question = (data.get('clinical_question') or '')
    modality = (data.get('modality') or '')
    body_section = (data.get('body_section') or '')
    insights = data.get('insights')

    try:
        from ai_smart_reporter import generate_report_action, SmartReporterError
        html_text, model_used, token_count = generate_report_action(
            report_text=report_text,
            action=action,
            clinical_question=clinical_question,
            modality=modality,
            body_section=body_section,
            insights=insights,
        )
    except Exception as exc:
        logger.error(f"Report action '{action}' failed: {exc}")
        from models import log_ai_usage
        log_ai_usage(current_user.id, f'report_action_{action}', provider='anthropic',
                     input_summary=report_text[:200], status='error', error_message=str(exc))
        return jsonify({'error': f'Report action failed: {exc}'}), 500

    from models import log_ai_usage
    log_ai_usage(current_user.id, f'report_action_{action}', provider='anthropic',
                 model=model_used, input_summary=report_text[:200])

    # --- Silent capture: save SBA / Viva to learning database ---
    if action in ('sba', 'viva') and html_text:
        try:
            _capture_learning_question(
                question_type=action,
                html_content=html_text,
                body_section=body_section,
                modality=modality,
                report_text=report_text,
                user_id=current_user.id,
            )
        except Exception as cap_exc:
            logger.warning(f"Learning capture ({action}) failed (non-fatal): {cap_exc}")

    return jsonify({
        'success': True,
        'action': action,
        'html': html_text,
        'remaining_requests': remaining,
    })


def _infer_frcr_module(body_section):
    """Infer FRCR 2B module from body section."""
    if not body_section:
        return None
    bs = body_section.strip().lower()
    mapping = {
        'thorax': 'Cardiothoracic and Vascular',
        'cardiovascular': 'Cardiothoracic and Vascular',
        'musculoskeletal': 'Musculoskeletal and Trauma',
        'abdomen': 'Gastrointestinal',
        'pelvis': 'Genitourinary, Adrenal, O&G and Breast',
        'breast': 'Genitourinary, Adrenal, O&G and Breast',
        'brain': 'CNS and Head & Neck',
        'spine': 'CNS and Head & Neck',
        'head and neck': 'CNS and Head & Neck',
    }
    return mapping.get(bs)


def _capture_learning_question(question_type, html_content, body_section, modality,
                               report_text, user_id):
    """Silently save an SBA or Viva question set to the learning_question table."""
    import hashlib

    content_hash = hashlib.sha256(html_content.encode('utf-8')).hexdigest()

    # Skip if duplicate
    if LearningQuestion.query.filter_by(content_hash=content_hash).first():
        return

    # Auto-generate a short title from the HTML
    title = _extract_learning_title(html_content, question_type)

    # Auto-infer FRCR module from body section
    module = _infer_frcr_module(body_section)

    q = LearningQuestion(
        question_type=question_type,
        body_section=body_section or None,
        modality=modality or None,
        module=module,
        title=title,
        html_content=html_content,
        source_report_context=report_text[:200] if report_text else None,
        content_hash=content_hash,
        created_by_user_id=user_id,
    )
    db.session.add(q)
    db.session.commit()


def _extract_learning_title(html_content, question_type):
    """Extract a brief title from generated HTML for the learning question."""
    import re
    # Try to pull the first vignette or scenario text
    if question_type == 'sba':
        m = re.search(r'<strong>Clinical vignette:</strong>\s*(.*?)</p>', html_content, re.DOTALL)
        if m:
            text = re.sub(r'<[^>]+>', '', m.group(1)).strip()
            return text[:120] + ('...' if len(text) > 120 else '')
    elif question_type == 'viva':
        m = re.search(r'<em>Scenario:\s*(.*?)</em>', html_content, re.DOTALL)
        if m:
            text = re.sub(r'<[^>]+>', '', m.group(1)).strip()
            return text[:120] + ('...' if len(text) > 120 else '')
    # Fallback: strip all tags from first 120 chars
    text = re.sub(r'<[^>]+>', '', html_content[:300]).strip()
    return text[:120] + ('...' if len(text) > 120 else '')


@reporting_bp.route('/api/smart-reporter/route-intent', methods=['POST'])
@login_required
def smart_reporter_route_intent():
    """Classify user input into an intent category for Smart Reporter routing."""
    data = request.get_json() or {}
    user_input = (data.get('query') or '').strip()
    if not user_input:
        return jsonify({'error': 'Query is required.'}), 400

    try:
        from ai_smart_reporter import classify_intent, SmartReporterError
        result = classify_intent(user_input)
    except Exception as exc:
        logger.error(f"Smart Reporter intent classification failed: {exc}")
        # Fallback: default to walkthrough intent
        result = {
            'intent': 'walkthrough',
            'canonical_topic': '',
            'display_title': user_input,
            'modality': None,
            'body_section': None,
            'category': None,
        }

    # Check cache for walkthrough intent
    cached_tree = None
    if result.get('intent') == 'walkthrough' and result.get('canonical_topic'):
        slug = result['canonical_topic']
        # Check admin-verified templates first, then unverified, then user cache
        cached = ReportingAlgorithm.query.filter(
            ReportingAlgorithm.slug == slug,
            ReportingAlgorithm.is_available == True,
        ).order_by(
            ReportingAlgorithm.verified_at.desc().nullslast(),
        ).first()
        if cached and cached.algorithm_html:
            cached_tree = {
                'source': 'cache',
                'template_id': cached.id,
                'title': cached.title,
                'verified': cached.verified_at is not None,
            }

    return jsonify({
        'success': True,
        'intent': result.get('intent', 'walkthrough'),
        'canonical_topic': result.get('canonical_topic', ''),
        'display_title': result.get('display_title', user_input),
        'modality': result.get('modality'),
        'body_section': result.get('body_section'),
        'category': result.get('category'),
        'cached_tree': cached_tree,
    })


@reporting_bp.route('/api/smart-reporter/blank-template', methods=['POST'])
@login_required
def smart_reporter_blank_template():
    """Generate a blank structured reporting template (Gap 3 abort flow)."""
    data = request.get_json() or {}

    modality = (data.get('modality') or '').strip()
    body_section = (data.get('body_section') or '').strip()
    clinical_question = (data.get('clinical_question') or '').strip()

    if not modality and not body_section and not clinical_question:
        return jsonify({'error': 'At least one of modality, body_section, or clinical_question is required.'}), 400

    try:
        from ai_smart_reporter import generate_blank_template, SmartReporterError
        result = generate_blank_template(
            modality=modality,
            body_section=body_section,
            clinical_question=clinical_question,
        )
    except Exception as exc:
        logger.error(f"Smart Reporter blank template generation failed: {exc}")
        return jsonify({'error': f'Template generation failed: {exc}'}), 500

    return jsonify({
        'success': True,
        'template_text': result.get('template_text', ''),
        'model': result.get('model', ''),
        'token_count': result.get('token_count', 0),
    })




## ==================== PERSONAL TEMPLATES (Phase 4, Gap 4) ====================

@reporting_bp.route('/api/smart-reporter/personal-templates', methods=['GET'])
@login_required
def smart_reporter_list_personal_templates():
    """List the current user's personal templates."""
    search = request.args.get('q', '').strip()
    offset = request.args.get('offset', 0, type=int)
    limit = request.args.get('limit', 20, type=int)
    limit = min(limit, 50)

    query = RadiologyTemplate.query.filter_by(
        origin='personal',
        created_by_user_id=current_user.id,
    )

    if search:
        query = query.filter(
            db.or_(
                RadiologyTemplate.title.ilike(f'%{search}%'),
                RadiologyTemplate.body_section.ilike(f'%{search}%'),
                RadiologyTemplate.keywords.ilike(f'%{search}%'),
            )
        )

    total = query.count()
    templates = query.order_by(
        RadiologyTemplate.updated_at.desc()
    ).offset(offset).limit(limit).all()

    return jsonify({
        'templates': [{
            'id': t.id,
            'title': t.title,
            'slug': t.slug,
            'body_section': t.body_section,
            'description': t.description,
            'updated_at': t.updated_at.isoformat() if t.updated_at else None,
            'has_content': bool(t.template_text),
        } for t in templates],
        'total': total,
        'offset': offset,
        'has_more': (offset + limit) < total,
    })


@reporting_bp.route('/api/smart-reporter/personal-templates', methods=['POST'])
@login_required
def smart_reporter_create_personal_template():
    """Save a report as a personal template (Gap 4)."""
    data = request.get_json() or {}
    title = (data.get('title') or '').strip()
    report_text = (data.get('report_text') or '').strip()

    if not title:
        return jsonify({'error': 'Template title is required.'}), 400
    if not report_text:
        return jsonify({'error': 'Report text is required.'}), 400

    # Rate limit: max 50 personal templates per user
    count = RadiologyTemplate.query.filter_by(
        origin='personal',
        created_by_user_id=current_user.id,
    ).count()
    if count >= 50:
        return jsonify({
            'error': 'You have reached the maximum of 50 personal templates. '
                     'Please delete some before creating new ones.'
        }), 429

    # Generate unique slug: pt-{user_id}-{normalized-title}
    import re as _re
    base_slug = _re.sub(r'[^a-z0-9]+', '-', title.lower()).strip('-')
    slug = f'pt-{current_user.id}-{base_slug}'

    # Handle slug collision (shouldn't happen often with user prefix)
    existing = RadiologyTemplate.query.filter_by(slug=slug).first()
    if existing:
        # If same user owns it, update instead
        if existing.created_by_user_id == current_user.id and existing.origin == 'personal':
            existing.title = title
            existing.template_text = report_text
            existing.body_section = (data.get('body_section') or '').strip() or None
            existing.description = (data.get('description') or '').strip() or None
            existing.updated_at = datetime.utcnow()
            db.session.commit()
            return jsonify({
                'success': True,
                'template_id': existing.id,
                'message': f'Template "{title}" updated.',
            })
        # Different owner — append counter
        counter = 1
        while RadiologyTemplate.query.filter_by(slug=f'{slug}-{counter}').first():
            counter += 1
        slug = f'{slug}-{counter}'

    template = RadiologyTemplate(
        slug=slug,
        title=title,
        origin='personal',
        body_section=(data.get('body_section') or '').strip() or None,
        description=(data.get('description') or '').strip() or None,
        template_text=report_text,
        is_available=True,
        created_by_user_id=current_user.id,
    )
    db.session.add(template)

    try:
        db.session.commit()
    except Exception as exc:
        db.session.rollback()
        logger.error(f"Failed to save personal template: {exc}")
        return jsonify({'error': 'Failed to save template.'}), 500

    return jsonify({
        'success': True,
        'template_id': template.id,
        'message': f'Template "{title}" saved.',
    }), 201


@reporting_bp.route('/api/smart-reporter/personal-templates/<int:template_id>', methods=['GET'])
@login_required
def smart_reporter_get_personal_template(template_id):
    """Get a personal template's content."""
    template = RadiologyTemplate.query.get_or_404(template_id)
    if template.created_by_user_id != current_user.id or template.origin != 'personal':
        return jsonify({'error': 'Access denied.'}), 403

    return jsonify({
        'id': template.id,
        'title': template.title,
        'slug': template.slug,
        'body_section': template.body_section,
        'description': template.description,
        'pacs_report_text': template.template_text or '',
        'updated_at': template.updated_at.isoformat() if template.updated_at else None,
    })


@reporting_bp.route('/api/smart-reporter/personal-templates/<int:template_id>', methods=['PUT'])
@login_required
def smart_reporter_update_personal_template(template_id):
    """Update a personal template (rename, change content)."""
    template = RadiologyTemplate.query.get_or_404(template_id)
    if template.created_by_user_id != current_user.id or template.origin != 'personal':
        return jsonify({'error': 'Access denied.'}), 403

    data = request.get_json() or {}

    if 'title' in data:
        title = (data['title'] or '').strip()
        if title:
            template.title = title
    if 'report_text' in data:
        template.template_text = (data['report_text'] or '').strip()
    if 'body_section' in data:
        template.body_section = (data['body_section'] or '').strip() or None
    if 'description' in data:
        template.description = (data['description'] or '').strip() or None

    template.updated_at = datetime.utcnow()

    try:
        db.session.commit()
    except Exception as exc:
        db.session.rollback()
        logger.error(f"Failed to update personal template {template_id}: {exc}")
        return jsonify({'error': 'Failed to update template.'}), 500

    return jsonify({'success': True, 'message': f'Template "{template.title}" updated.'})


@reporting_bp.route('/api/smart-reporter/personal-templates/<int:template_id>', methods=['DELETE'])
@login_required
def smart_reporter_delete_personal_template(template_id):
    """Delete a personal template."""
    template = RadiologyTemplate.query.get_or_404(template_id)
    if template.created_by_user_id != current_user.id or template.origin != 'personal':
        return jsonify({'error': 'Access denied.'}), 403

    title = template.title
    try:
        db.session.delete(template)
        db.session.commit()
    except Exception as exc:
        db.session.rollback()
        logger.error(f"Failed to delete personal template {template_id}: {exc}")
        return jsonify({'error': 'Failed to delete template.'}), 500

    return jsonify({'success': True, 'message': f'Template "{title}" deleted.'})




@reporting_bp.route('/api/smart-reporter/admin-templates', methods=['GET'])
@login_required
def smart_reporter_admin_templates():
    """List verified (admin-curated) templates for the Smart Reporter landing page.

    Merges results from RadiologyTemplate (plain-text PACS reports) and
    ReportingAlgorithm (interactive decision trees).
    """
    search = request.args.get('q', '').strip()
    offset = request.args.get('offset', 0, type=int)
    limit = min(request.args.get('limit', 20, type=int), 50)

    # --- RadiologyTemplate (admin, verified) ---
    rt_query = RadiologyTemplate.query.filter(
        RadiologyTemplate.is_available == True,
        RadiologyTemplate.verified_at.isnot(None),
        RadiologyTemplate.origin == 'admin',
    )
    if search:
        rt_query = rt_query.filter(
            db.or_(
                RadiologyTemplate.title.ilike(f'%{search}%'),
                RadiologyTemplate.keywords.ilike(f'%{search}%'),
                RadiologyTemplate.body_section.ilike(f'%{search}%'),
            )
        )

    # --- ReportingAlgorithm (verified) ---
    ra_query = ReportingAlgorithm.query.filter(
        ReportingAlgorithm.is_available == True,
        ReportingAlgorithm.verified_at.isnot(None),
    )
    if search:
        ra_query = ra_query.filter(
            db.or_(
                ReportingAlgorithm.title.ilike(f'%{search}%'),
                ReportingAlgorithm.keywords.ilike(f'%{search}%'),
                ReportingAlgorithm.body_section.ilike(f'%{search}%'),
            )
        )

    rt_results = rt_query.all()
    ra_results = ra_query.all()

    combined = []
    for t in rt_results:
        combined.append({
            'id': t.id,
            'slug': t.slug,
            'title': t.title,
            'category': t.category,
            'body_section': t.body_section,
            'description': t.description,
            'source_table': 'radiology_template',
            'has_algorithm': False,
            'has_pacs_report': bool(t.template_text),
            'verified_at': t.verified_at.isoformat() if t.verified_at else None,
            'created_at': t.created_at.isoformat() if t.created_at else None,
        })
    for t in ra_results:
        combined.append({
            'id': t.id,
            'slug': t.slug,
            'title': t.title,
            'category': t.category,
            'body_section': t.body_section,
            'description': t.description,
            'source_table': 'reporting_algorithm',
            'has_algorithm': bool(t.algorithm_html),
            'has_pacs_report': False,
            'verified_at': t.verified_at.isoformat() if t.verified_at else None,
            'created_at': t.created_at.isoformat() if t.created_at else None,
        })

    # Sort by verified_at descending
    combined.sort(key=lambda x: x.get('verified_at') or '', reverse=True)

    total = len(combined)
    page = combined[offset:offset + limit]

    return jsonify({
        'templates': page,
        'total': total,
        'offset': offset,
        'has_more': (offset + limit) < total,
    })


@reporting_bp.route('/api/smart-reporter/admin-templates/<int:template_id>', methods=['GET'])
@login_required
def smart_reporter_get_admin_template(template_id):
    """Get a single admin template (full content) for loading into editor.

    Checks both RadiologyTemplate and ReportingAlgorithm tables.
    The source_table query param indicates which table to look in.
    """
    source_table = request.args.get('source_table', 'reporting_algorithm')

    if source_table == 'radiology_template':
        template = RadiologyTemplate.query.get_or_404(template_id)
        if not template.is_available or not template.verified_at:
            return jsonify({'error': 'Template not available.'}), 404
        result = template.to_dict()
        result['pacs_report_text'] = template.template_text or ''
        result['has_pacs_report'] = bool(template.template_text)
        result['has_algorithm'] = False
        result['source_table'] = 'radiology_template'
        return jsonify(result)

    # Default: ReportingAlgorithm
    template = ReportingAlgorithm.query.get_or_404(template_id)
    if not template.is_available or not template.verified_at:
        return jsonify({'error': 'Template not available.'}), 404

    result = template.to_dict()
    result['algorithm_html'] = template.algorithm_html
    result['template_html'] = template.template_html
    result['has_algorithm'] = bool(template.algorithm_html)
    result['has_pacs_report'] = False
    result['source_table'] = 'reporting_algorithm'
    return jsonify(result)


@reporting_bp.route('/api/smart-reporter/relevant-content', methods=['GET'])
@login_required
def smart_reporter_relevant_content():
    """Search across DB for content relevant to the current report context.

    Searches: Cases, TNM calculators, TNM cases (AJCC disease sites),
    Radiology tools (IF calculators + clinical protocols), Anatomy references.
    Does NOT include radiology templates or algorithms (those have dedicated cards).
    """
    q = request.args.get('q', '').strip()
    body_section = request.args.get('body_section', '').strip()

    if not q and not body_section:
        return jsonify({'results': []})

    results = []
    search_terms = [t for t in q.lower().split() if len(t) > 2]

    # --- Cases (published, matching diagnosis or body_part) ---
    try:
        case_query = Case.query.filter(Case.status == CaseStatus.PUBLISHED)
        if q:
            # body_part is an Enum — cast to text for ILIKE
            case_query = case_query.filter(
                db.or_(
                    Case.diagnosis.ilike(f'%{q}%'),
                    db.cast(Case.body_part, db.String).ilike(f'%{q}%'),
                )
            )
        elif body_section:
            case_query = case_query.filter(
                db.cast(Case.body_part, db.String).ilike(f'%{body_section}%')
            )

        cases = case_query.order_by(Case.diagnosis).limit(4).all()
        for c in cases:
            bp = c.body_part.value if hasattr(c.body_part, 'value') else str(c.body_part) if c.body_part else ''
            results.append({
                'type': 'case',
                'icon': 'fa-book-medical',
                'color': '#e96304',
                'title': c.diagnosis or 'Case',
                'subtitle': bp,
                'url': f'/view-case/{c.id}',
            })
    except Exception:
        pass

    # --- TNM Calculators (available, matching cancer name or body section) ---
    try:
        tnm_query = TNMCalculatorContent.query.filter_by(is_available=True)
        if q:
            tnm_query = tnm_query.filter(
                db.or_(
                    TNMCalculatorContent.cancer_name.ilike(f'%{q}%'),
                    TNMCalculatorContent.body_section.ilike(f'%{q}%'),
                )
            )
        elif body_section:
            tnm_query = tnm_query.filter(TNMCalculatorContent.body_section.ilike(f'%{body_section}%'))

        tnms = tnm_query.limit(4).all()
        for t in tnms:
            results.append({
                'type': 'tnm',
                'icon': 'fa-dna',
                'color': '#6b46c1',
                'title': f'TNM: {t.cancer_name}',
                'subtitle': t.body_section or '',
                'url': f'/tnm-calculator/{t.slug}',
            })
    except Exception:
        pass

    # --- TNM Cases (AJCC disease site staging data) ---
    try:
        ds_query = AJCCDiseaseSite.query.join(AJCCBodySection)
        if q:
            ds_query = ds_query.filter(
                db.or_(
                    AJCCDiseaseSite.disease_name.ilike(f'%{q}%'),
                    AJCCBodySection.section_name.ilike(f'%{q}%'),
                )
            )
        elif body_section:
            ds_query = ds_query.filter(AJCCBodySection.section_name.ilike(f'%{body_section}%'))

        disease_sites = ds_query.limit(4).all()
        for ds in disease_sites:
            section_slug = ds.body_section.slug if ds.body_section else ''
            results.append({
                'type': 'tnm_case',
                'icon': 'fa-disease',
                'color': '#d63384',
                'title': ds.disease_name,
                'subtitle': ds.body_section.section_name if ds.body_section else '',
                'url': f'/tnm/{section_slug}/{ds.slug}',
            })
    except Exception:
        pass

    # --- Radiology Tools (IF calculators + Clinical protocols) ---
    try:
        if_query = IncidentalFindingCalculator.query.filter_by(is_available=True)
        if q:
            if_query = if_query.filter(
                db.or_(
                    IncidentalFindingCalculator.finding_name.ilike(f'%{q}%'),
                    IncidentalFindingCalculator.keywords.ilike(f'%{q}%'),
                )
            )
        elif body_section:
            if_query = if_query.filter(IncidentalFindingCalculator.body_section.ilike(f'%{body_section}%'))

        ifs = if_query.limit(3).all()
        for f in ifs:
            results.append({
                'type': 'radiology_tool',
                'icon': 'fa-tools',
                'color': '#5E899E',
                'title': f.finding_name,
                'subtitle': f.guideline_source or f.body_section or '',
                'url': f'/incidental-findings/{f.slug}',
            })
    except Exception:
        pass

    try:
        cp_query = ClinicalProtocol.query.filter_by(is_published=True)
        if q:
            cp_query = cp_query.filter(
                db.or_(
                    ClinicalProtocol.title.ilike(f'%{q}%'),
                    ClinicalProtocol.keywords.ilike(f'%{q}%'),
                )
            )
        elif body_section:
            cp_query = cp_query.filter(ClinicalProtocol.body_section.ilike(f'%{body_section}%'))

        cps = cp_query.limit(3).all()
        for p in cps:
            results.append({
                'type': 'radiology_tool',
                'icon': 'fa-tools',
                'color': '#5E899E',
                'title': p.title,
                'subtitle': p.category or '',
                'url': f'/radiology-protocols/view/{p.id}',
            })
    except Exception:
        pass

    # --- Anatomy References (cached) ---
    try:
        anat_query = ReportingAlgorithm.query.filter(
            ReportingAlgorithm.is_available == True,
            ReportingAlgorithm.origin == 'anatomy_cache',
        )
        if q:
            anat_query = anat_query.filter(
                db.or_(
                    ReportingAlgorithm.title.ilike(f'%{q}%'),
                    ReportingAlgorithm.keywords.ilike(f'%{q}%'),
                )
            )
        elif body_section:
            anat_query = anat_query.filter(ReportingAlgorithm.body_section.ilike(f'%{body_section}%'))

        anats = anat_query.limit(3).all()
        for a in anats:
            results.append({
                'type': 'anatomy',
                'icon': 'fa-bone',
                'color': '#6f42c1',
                'title': a.title,
                'subtitle': 'Anatomy Snippet',
                'url': f'/anatomy-snippets/{a.slug}',
            })
    except Exception:
        pass

    return jsonify({'results': results[:20]})


@reporting_bp.route('/api/smart-reporter/anatomy-suggest')
@login_required
def smart_reporter_anatomy_suggest():
    """Return cached anatomy topics matching a query (for typeahead)."""
    q = (request.args.get('q') or '').strip()
    if len(q) < 2:
        return jsonify({'results': []})

    matches = ReportingAlgorithm.query.filter(
        ReportingAlgorithm.category == 'anatomy',
        ReportingAlgorithm.origin == 'anatomy_cache',
        ReportingAlgorithm.is_available == True,
        db.or_(
            ReportingAlgorithm.title.ilike(f'%{q}%'),
            ReportingAlgorithm.keywords.ilike(f'%{q}%'),
        ),
    ).order_by(ReportingAlgorithm.title).limit(8).all()

    return jsonify({
        'results': [{'title': m.title, 'slug': m.slug} for m in matches],
    })


@reporting_bp.route('/api/smart-reporter/anatomy', methods=['POST'])
@reporting_bp.route('/api/smart-reporter/anatomy-reference', methods=['POST'])
@login_required
def smart_reporter_anatomy():
    """Generate or retrieve anatomy reference content for the Anatomy Panel."""
    # Support both JSON and FormData (when PDFs are uploaded)
    if request.content_type and 'multipart/form-data' in request.content_type:
        data = request.form
    else:
        data = request.get_json() or {}

    topic = (data.get('topic') or '').strip()
    if not topic:
        return jsonify({'error': 'Anatomy topic is required.'}), 400

    modality_raw = (data.get('modality') or '').strip()
    body_section = (data.get('body_section') or '').strip()
    modality = normalize_modality(modality_raw) if modality_raw else ''
    manual_html = (data.get('manual_html') or '').strip()

    # Manual HTML: admin wrote content directly — skip AI and DB lookup, just save
    if manual_html:
        try:
            slug = re.sub(r'[^a-z0-9]+', '-', topic.lower()).strip('-')[:200]
            user_keywords = (data.get('keywords') or '').strip()
            entry = ReportingAlgorithm(
                title=topic.title(),
                slug=f'anatomy-{slug}',
                category='anatomy',
                origin='anatomy_cache',
                template_html=manual_html,
                keywords=user_keywords or topic.lower(),
                is_available=True,
                is_ai_generated=False,
            )
            if body_section:
                entry.body_section = body_section
            if modality:
                entry.modality = modality
            db.session.add(entry)
            db.session.commit()
            return jsonify({
                'success': True,
                'title': entry.title,
                'content_html': manual_html,
                'source': 'manual',
                'algorithm_id': entry.id,
            })
        except Exception as exc:
            db.session.rollback()
            logger.error(f"Failed to save manual anatomy snippet: {exc}")
            return jsonify({'error': f'Failed to save: {exc}'}), 500

    # Check force_regenerate flag
    force_regenerate = data.get('force_regenerate', False)
    if isinstance(force_regenerate, str):
        force_regenerate = force_regenerate.lower() not in ('false', '0', '')

    # DB-first: check for cached anatomy content
    cached = ReportingAlgorithm.query.filter(
        ReportingAlgorithm.category == 'anatomy',
        ReportingAlgorithm.is_available == True,
        db.or_(
            ReportingAlgorithm.title.ilike(f'%{topic}%'),
            ReportingAlgorithm.keywords.ilike(f'%{topic}%'),
        ),
    ).first()

    if cached and cached.template_html and not force_regenerate:
        return jsonify({
            'success': True,
            'cached': True,
            'title': cached.title,
            'algorithm_id': cached.id,
            'is_ai_generated': cached.is_ai_generated,
            'source': 'database',
        })

    # Build additional context + extract reference images from optional admin inputs
    instructions = (data.get('instructions') or '').strip()
    if request.content_type and 'multipart/form-data' in request.content_type:
        reference_urls = request.form.getlist('reference_url')
        pdf_files = request.files.getlist('pdf')
    else:
        reference_urls = data.get('reference_urls') or ([data['reference_url']] if data.get('reference_url') else [])
        pdf_files = []
    additional_context, ref_images = _build_generation_context(instructions, reference_urls, pdf_files)

    # AI fallback: generate anatomy reference
    try:
        from ai_smart_reporter import generate_anatomy_reference
        result = generate_anatomy_reference(topic, modality=modality, body_section=body_section,
                                            additional_context=additional_context)
    except Exception as exc:
        logger.error(f"Anatomy reference generation failed: {exc}")
        return jsonify({'error': f'Failed to generate anatomy reference: {exc}'}), 500

    # If reference images from URL/PDF, re-render with combined images
    if ref_images:
        try:
            from ai_smart_reporter import render_anatomy_html
            rp_images = result.get('radiopaedia_images', [])
            all_images = rp_images + ref_images
            all_images = all_images[:5]
            # Re-parse the content to get the parsed data — use existing HTML
            # Since we can't easily re-parse, just append images to existing HTML
            from ai_pearl_generator import render_reference_images_html
            captions = []  # captions already embedded in content_html from generate_anatomy_reference
            extra_html = render_reference_images_html(ref_images, captions)
            result['content_html'] = result.get('content_html', '') + extra_html
        except Exception as img_exc:
            logger.warning(f"Failed to add reference images to snippet: {img_exc}")

    # Auto-save to cache for future lookups (update existing if force_regenerate)
    content_html = result.get('content_html', '')
    algorithm_id = None
    if content_html:
        try:
            if cached and force_regenerate:
                # Update existing record instead of creating duplicate
                cache_entry = cached
                cache_entry.title = result.get('title', topic.title())
                cache_entry.template_html = content_html
                cache_entry.keywords = topic.lower()
                cache_entry.is_ai_generated = True
                if body_section:
                    cache_entry.body_section = body_section
                if modality:
                    cache_entry.modality = modality
            else:
                slug = re.sub(r'[^a-z0-9]+', '-', topic.lower()).strip('-')[:200]
                ai_user_keywords = (data.get('keywords') or '').strip()
                cache_entry = ReportingAlgorithm(
                    title=result.get('title', topic.title()),
                    slug=f'anatomy-{slug}',
                    category='anatomy',
                    origin='anatomy_cache',
                    template_html=content_html,
                    keywords=ai_user_keywords or topic.lower(),
                    is_available=True,
                    is_ai_generated=True,
                )
                if body_section:
                    cache_entry.body_section = body_section
                if modality:
                    cache_entry.modality = modality
                db.session.add(cache_entry)
            db.session.commit()
            algorithm_id = cache_entry.id
            logger.info(f"Cached anatomy reference: {topic}")

            # Auto-create SnippetImage records for each Radiopaedia image
            rp_images = result.get('radiopaedia_images', [])
            if rp_images and algorithm_id:
                try:
                    from models import SnippetImage
                    for idx, rp_img in enumerate(rp_images):
                        si = SnippetImage(
                            algorithm_id=algorithm_id,
                            source_url=rp_img.get('url', ''),
                            source_domain=rp_img.get('source_domain', 'radiopaedia.org'),
                            thumbnail_url=rp_img.get('url', ''),
                            image_type='ct_mri',
                            modality=modality or None,
                            description=rp_img.get('title', ''),
                            display_order=idx,
                            license=rp_img.get('license', 'CC BY-NC-SA 3.0'),
                            attribution=f"{rp_img.get('author') or 'Radiopaedia.org'} — {rp_img.get('title', '')}",
                            added_by_user_id=current_user.id if current_user.is_authenticated else None,
                        )
                        db.session.add(si)
                    db.session.commit()
                except Exception as img_exc:
                    db.session.rollback()
                    logger.warning(f"Failed to save Radiopaedia images: {img_exc}")

        except Exception as cache_exc:
            db.session.rollback()
            logger.warning(f"Failed to cache anatomy reference: {cache_exc}")

    return jsonify({
        'success': True,
        'title': result.get('title', topic.title()),
        'content_html': content_html,
        'source': result.get('source', 'ai'),
        'token_count': result.get('token_count', 0),
        'algorithm_id': algorithm_id,
    })


# ==================== SNIPPET BODY SECTION UPDATE ====================

@reporting_bp.route('/api/smart-reporter/update-snippet-metadata', methods=['POST'])
@login_required
@require_admin
def update_snippet_metadata():
    """Update body_section and/or modality on a recently generated anatomy snippet."""
    data = request.get_json() or {}
    topic = (data.get('topic') or '').strip()
    if not topic:
        return jsonify({'error': 'topic required'}), 400

    slug = re.sub(r'[^a-z0-9]+', '-', topic.lower()).strip('-')[:200]
    snippet = ReportingAlgorithm.query.filter(
        ReportingAlgorithm.origin == 'anatomy_cache',
        ReportingAlgorithm.slug == f'anatomy-{slug}',
    ).first()
    if not snippet:
        return jsonify({'error': 'Snippet not found'}), 404

    body_section = (data.get('body_section') or '').strip()
    if body_section:
        snippet.body_section = body_section

    modality_raw = (data.get('modality') or '').strip()
    if modality_raw:
        snippet.modality = normalize_modality(modality_raw)

    db.session.commit()
    return jsonify({'success': True})


# ==================== SNIPPET REFERENCES ====================

@reporting_bp.route('/api/snippet/<int:alg_id>/references', methods=['GET'])
@login_required
def list_snippet_references(alg_id):
    """List all references for an anatomy snippet."""
    from models import SnippetReference
    refs = SnippetReference.query.filter_by(algorithm_id=alg_id).order_by(SnippetReference.ref_number).all()
    return jsonify({'references': [r.to_dict() for r in refs]})


@reporting_bp.route('/api/snippet/<int:alg_id>/references', methods=['POST'])
@login_required
@require_admin
def add_snippet_reference(alg_id):
    """Add a URL reference to an anatomy snippet."""
    from models import SnippetReference
    snippet = ReportingAlgorithm.query.get_or_404(alg_id)
    data = request.get_json() or {}
    title = (data.get('title') or '').strip()
    url = (data.get('url') or '').strip()
    if not title or not url:
        return jsonify({'error': 'title and url are required'}), 400

    # Auto-assign next ref_number
    max_ref = db.session.query(db.func.max(SnippetReference.ref_number)).filter_by(
        algorithm_id=alg_id
    ).scalar() or 0

    ref = SnippetReference(
        algorithm_id=alg_id,
        ref_number=max_ref + 1,
        title=title,
        url=url,
        journal=(data.get('journal') or '').strip() or None,
        year=(data.get('year') or '').strip() or None,
    )
    db.session.add(ref)
    db.session.commit()
    return jsonify({'success': True, 'reference': ref.to_dict()}), 201


@reporting_bp.route('/api/snippet/<int:alg_id>/references/<int:ref_id>', methods=['DELETE'])
@login_required
@require_admin
def delete_snippet_reference(alg_id, ref_id):
    """Delete a reference from an anatomy snippet."""
    from models import SnippetReference
    ref = SnippetReference.query.filter_by(id=ref_id, algorithm_id=alg_id).first_or_404()
    db.session.delete(ref)
    db.session.commit()
    return jsonify({'success': True})


# ==================== SNIPPET DOCUMENTS ====================

@reporting_bp.route('/api/snippet/<int:alg_id>/documents', methods=['GET'])
@login_required
def list_snippet_documents(alg_id):
    """List all documents for an anatomy snippet."""
    from models import SnippetDocument
    docs = SnippetDocument.query.filter_by(algorithm_id=alg_id).order_by(SnippetDocument.created_at.desc()).all()
    return jsonify({'documents': [d.to_dict() for d in docs]})


@reporting_bp.route('/api/snippet/<int:alg_id>/documents', methods=['POST'])
@login_required
@require_admin
def upload_snippet_document(alg_id):
    """Upload a PDF/document to Cloudinary and attach to an anatomy snippet."""
    snippet = ReportingAlgorithm.query.get_or_404(alg_id)
    if 'file' not in request.files:
        return jsonify({'error': 'No file provided'}), 400

    file = request.files['file']
    if not file.filename:
        return jsonify({'error': 'Empty filename'}), 400

    # Check file size (10MB max)
    file.seek(0, 2)
    size_bytes = file.tell()
    file.seek(0)
    if size_bytes > 10 * 1024 * 1024:
        return jsonify({'error': 'File too large (max 10MB)'}), 400

    title = (request.form.get('title') or file.filename).strip()

    try:
        import cloudinary
        import cloudinary.uploader
        upload_result = cloudinary.uploader.upload(
            file,
            resource_type='raw',
            folder='snippet-documents/',
        )
    except Exception as exc:
        logger.error(f"Cloudinary upload failed: {exc}")
        return jsonify({'error': 'Upload failed'}), 500

    from models import SnippetDocument
    doc = SnippetDocument(
        algorithm_id=alg_id,
        title=title,
        cloudinary_url=upload_result.get('secure_url', upload_result.get('url', '')),
        cloudinary_public_id=upload_result.get('public_id'),
        file_type=file.filename.rsplit('.', 1)[-1].lower() if '.' in file.filename else 'pdf',
        file_size_kb=round(size_bytes / 1024),
        uploaded_by_user_id=current_user.id,
    )
    db.session.add(doc)
    db.session.commit()
    return jsonify({'success': True, 'document': doc.to_dict()}), 201


@reporting_bp.route('/api/snippet/<int:alg_id>/documents/<int:doc_id>', methods=['DELETE'])
@login_required
@require_admin
def delete_snippet_document(alg_id, doc_id):
    """Delete a document from an anatomy snippet."""
    from models import SnippetDocument
    doc = SnippetDocument.query.filter_by(id=doc_id, algorithm_id=alg_id).first_or_404()
    # Optionally delete from Cloudinary
    if doc.cloudinary_public_id:
        try:
            import cloudinary
            import cloudinary.uploader
            cloudinary.uploader.destroy(doc.cloudinary_public_id, resource_type='raw')
        except Exception:
            pass  # Non-critical
    db.session.delete(doc)
    db.session.commit()
    return jsonify({'success': True})


# ==================== REGENERATE SNIPPET ====================

@reporting_bp.route('/api/snippet/<int:alg_id>/regenerate', methods=['POST'])
@login_required
@require_admin
def regenerate_snippet(alg_id):
    """Regenerate an anatomy snippet's content using AI, replacing template_html in place."""
    snippet = ReportingAlgorithm.query.get_or_404(alg_id)
    if snippet.category != 'anatomy':
        return jsonify({'error': 'Not an anatomy snippet'}), 400

    topic = snippet.title or ''
    body_section = snippet.body_section or ''
    modality = snippet.modality or ''

    # Rate limit check
    ok, remaining, err = _check_ai_rate_limit()
    if not ok:
        return err

    try:
        from ai_smart_reporter import generate_anatomy_reference
        result = generate_anatomy_reference(topic, modality=modality, body_section=body_section)
    except Exception as exc:
        logger.error(f"Snippet regeneration failed for id={alg_id}: {exc}")
        return jsonify({'error': f'Failed to regenerate: {exc}'}), 500

    content_html = result.get('content_html', '')
    if not content_html:
        return jsonify({'error': 'AI returned empty content'}), 500

    try:
        snippet.template_html = content_html
        snippet.is_ai_generated = True
        db.session.commit()
        logger.info(f"Regenerated anatomy snippet id={alg_id}: {topic}")

        # Auto-update Radiopaedia images (multiple)
        rp_images = result.get('radiopaedia_images', [])
        if rp_images:
            try:
                from models import SnippetImage
                for idx, rp_img in enumerate(rp_images):
                    si = SnippetImage(
                        algorithm_id=alg_id,
                        source_url=rp_img.get('url', ''),
                        source_domain=rp_img.get('source_domain', 'radiopaedia.org'),
                        thumbnail_url=rp_img.get('url', ''),
                        image_type='ct_mri',
                        modality=modality or None,
                        description=rp_img.get('title', ''),
                        display_order=idx,
                        license=rp_img.get('license', 'CC BY-NC-SA 3.0'),
                        attribution=f"{rp_img.get('author') or 'Radiopaedia.org'} — {rp_img.get('title', '')}",
                        added_by_user_id=current_user.id if current_user.is_authenticated else None,
                    )
                    db.session.add(si)
                db.session.commit()
            except Exception as img_exc:
                db.session.rollback()
                logger.warning(f"Failed to save Radiopaedia images during regeneration: {img_exc}")

    except Exception as save_exc:
        db.session.rollback()
        logger.error(f"Failed to save regenerated snippet: {save_exc}")
        return jsonify({'error': f'Failed to save: {save_exc}'}), 500

    return jsonify({
        'success': True,
        'content_html': content_html,
    })


# ==================== SNIPPET IMAGES ====================

@reporting_bp.route('/api/snippet/<int:alg_id>/images', methods=['GET'])
@login_required
def list_snippet_images(alg_id):
    """List all images for an anatomy snippet."""
    from models import SnippetImage
    imgs = SnippetImage.query.filter_by(algorithm_id=alg_id).order_by(SnippetImage.display_order).all()
    return jsonify({'images': [i.to_dict() for i in imgs]})


@reporting_bp.route('/api/snippet/<int:alg_id>/images', methods=['POST'])
@login_required
@require_admin
def add_snippet_image(alg_id):
    """Add an image to an anatomy snippet."""
    from models import SnippetImage
    snippet = ReportingAlgorithm.query.get_or_404(alg_id)
    data = request.get_json() or {}
    source_url = (data.get('source_url') or '').strip()
    if not source_url:
        return jsonify({'error': 'source_url is required'}), 400

    # Auto display_order
    max_order = db.session.query(db.func.max(SnippetImage.display_order)).filter_by(
        algorithm_id=alg_id
    ).scalar() or 0

    img = SnippetImage(
        algorithm_id=alg_id,
        source_url=source_url,
        source_domain=(data.get('source_domain') or '').strip() or _extract_domain(source_url),
        thumbnail_url=(data.get('thumbnail_url') or '').strip() or None,
        image_type=(data.get('image_type') or 'ct_mri').strip(),
        modality=(data.get('modality') or '').strip() or None,
        description=(data.get('description') or '').strip() or None,
        display_order=max_order + 1,
        license=(data.get('license') or 'CC BY-NC-SA 3.0').strip(),
        attribution=(data.get('attribution') or '').strip() or _extract_domain(source_url),
        added_by_user_id=current_user.id,
    )
    db.session.add(img)
    db.session.commit()
    return jsonify({'success': True, 'image': img.to_dict()}), 201


@reporting_bp.route('/api/snippet/<int:alg_id>/images/<int:img_id>', methods=['DELETE'])
@login_required
@require_admin
def delete_snippet_image(alg_id, img_id):
    """Delete an image from an anatomy snippet."""
    from models import SnippetImage
    img = SnippetImage.query.filter_by(id=img_id, algorithm_id=alg_id).first_or_404()
    db.session.delete(img)
    db.session.commit()
    return jsonify({'success': True})


def _extract_domain(url):
    """Extract domain from a URL."""
    try:
        from urllib.parse import urlparse
        return urlparse(url).netloc or url
    except Exception:
        return url


# ==================== SNIPPET IMAGE SEARCH ====================

@reporting_bp.route('/api/snippet/<int:alg_id>/search-images', methods=['POST'])
@login_required
@require_admin
def search_snippet_images(alg_id):
    """Search for images: user references first, then Radiopaedia, then broad CC."""
    from models import SnippetReference
    snippet = ReportingAlgorithm.query.get_or_404(alg_id)
    data = request.get_json() or {}
    topic = (data.get('topic') or snippet.title or '').strip()
    modality = (data.get('modality') or '').strip()
    body_section = (data.get('body_section') or '').strip()

    all_results = []

    # Step 1: Search within user-provided reference domains
    refs = SnippetReference.query.filter_by(algorithm_id=alg_id).all()
    ref_domains = set()
    for ref in refs:
        domain = _extract_domain(ref.url)
        if domain:
            ref_domains.add(domain)

    if ref_domains:
        try:
            from google_search_service import search_images
            for domain in ref_domains:
                query = f'site:{domain} {topic} radiology imaging'
                results = search_images(query, max_results=5)
                for r in results:
                    r['source_group'] = 'reference'
                    r['source_domain'] = r.get('source_domain', domain)
                    r['license'] = r.get('license', 'Check source')
                    r['attribution'] = r.get('attribution', domain)
                all_results.extend(results)
        except Exception as exc:
            logger.warning(f"Reference domain image search failed: {exc}")

    # Step 2: Radiopaedia (always)
    try:
        from radiopaedia_search_service import search_radiopaedia_images
        rp_results = search_radiopaedia_images(
            diagnosis=topic, modality=modality, max_per_type=5,
        )
        for r in rp_results:
            r['source_group'] = 'radiopaedia'
            r['source_domain'] = 'radiopaedia.org'
            r['source_url'] = r.get('link', '')
            r['thumbnail_url'] = r.get('thumbnail_link', '')
            r['attribution'] = f"Radiopaedia.org — {r.get('title', '')}"
        all_results.extend(rp_results)
    except Exception as exc:
        logger.warning(f"Radiopaedia image search failed: {exc}")

    # Step 3: Broad CC search (fallback if < 3 results so far)
    if len(all_results) < 3:
        try:
            from google_search_service import search_reference_images
            cc_results = search_reference_images(
                diagnosis=topic, body_part=body_section, modality=modality, max_per_type=5,
            )
            for r in cc_results:
                r['source_group'] = 'cc_general'
                r['source_url'] = r.get('link', '')
                r['thumbnail_url'] = r.get('thumbnail_link', '')
                r['license'] = r.get('license', 'CC')
                r['attribution'] = r.get('source_domain', r.get('displayLink', ''))
            all_results.extend(cc_results)
        except Exception as exc:
            logger.warning(f"CC image search failed: {exc}")

    # Normalize results for frontend
    normalized = []
    for r in all_results:
        normalized.append({
            'source_url': r.get('source_url') or r.get('link', ''),
            'thumbnail_url': r.get('thumbnail_url') or r.get('thumbnail_link', ''),
            'source_domain': r.get('source_domain', ''),
            'title': r.get('title', ''),
            'license': r.get('license', 'CC BY-NC-SA 3.0'),
            'attribution': r.get('attribution', ''),
            'source_group': r.get('source_group', 'other'),
        })

    return jsonify({'success': True, 'results': normalized})


# ==================== CONTENT REQUESTS ====================

@reporting_bp.route('/api/smart-reporter/content-request', methods=['POST'])
@login_required
def submit_content_request():
    """User submits a request for new content (template, algorithm, resource)."""
    data = request.get_json() or {}
    request_type = (data.get('request_type') or '').strip()
    title = (data.get('title') or '').strip()
    description = (data.get('description') or '').strip()
    body_section = (data.get('body_section') or '').strip()

    if not request_type or request_type not in ('template', 'algorithm', 'resource'):
        return jsonify({'error': 'Please select a request type.'}), 400
    if not title or len(title) < 3:
        return jsonify({'error': 'Please provide a title (at least 3 characters).'}), 400

    # Rate limit: max 5 pending requests per user
    pending_count = ContentRequest.query.filter_by(
        user_id=current_user.id, status='pending'
    ).count()
    if pending_count >= 5:
        return jsonify({'error': 'You already have 5 pending requests. Please wait for them to be reviewed.'}), 429

    cr = ContentRequest(
        user_id=current_user.id,
        request_type=request_type,
        title=title[:300],
        description=description[:2000] if description else None,
        body_section=body_section[:100] if body_section else None,
        status='pending',
    )
    db.session.add(cr)
    db.session.commit()

    return jsonify({'success': True, 'message': 'Content request submitted. Thank you!'})


@reporting_bp.route('/api/admin/content-requests', methods=['GET'])
@login_required
@require_admin
def list_content_requests():
    """Admin: list all content requests."""
    status_filter = request.args.get('status', '')
    query = ContentRequest.query.order_by(ContentRequest.created_at.desc())
    if status_filter:
        query = query.filter_by(status=status_filter)

    requests_list = query.limit(100).all()
    return jsonify({'requests': [{
        'id': r.id,
        'user_id': r.user_id,
        'username': r.user.username if r.user else 'Unknown',
        'request_type': r.request_type,
        'title': r.title,
        'description': r.description,
        'body_section': r.body_section,
        'status': r.status,
        'admin_notes': r.admin_notes,
        'created_at': r.created_at.isoformat() if r.created_at else None,
    } for r in requests_list]})


@reporting_bp.route('/api/admin/content-requests/<int:request_id>', methods=['PUT'])
@login_required
@require_admin
def update_content_request(request_id):
    """Admin: update content request status/notes."""
    cr = ContentRequest.query.get_or_404(request_id)
    data = request.get_json() or {}

    if 'status' in data and data['status'] in ('pending', 'completed', 'declined'):
        cr.status = data['status']
    if 'admin_notes' in data:
        cr.admin_notes = (data['admin_notes'] or '')[:2000]

    db.session.commit()
    return jsonify({'success': True, 'message': f'Request updated to {cr.status}.'})


# ==================== RADIOLOGY PEARLS ====================

@reporting_bp.route('/api/smart-reporter/save-pearl', methods=['POST'])
@login_required
def save_pearl():
    """Save a teaching point as a radiology pearl."""
    import hashlib
    data = request.get_json() or {}

    pearl_text = (data.get('pearl_text') or '').strip()
    if not pearl_text:
        return jsonify({'error': 'pearl_text is required'}), 400

    content_hash = hashlib.sha256(pearl_text.lower().encode('utf-8')).hexdigest()

    existing = RadiologyPearl.query.filter_by(content_hash=content_hash).first()
    if existing:
        return jsonify({
            'success': True,
            'message': 'Pearl already exists.',
            'pearl': _pearl_to_dict(existing),
            'duplicate': True,
        })

    # Sanitize HTML if pearl contains markup (from TinyMCE editor)
    if '<' in pearl_text:
        from app import sanitize_clinical_html
        pearl_text = sanitize_clinical_html(pearl_text)
        # Recalculate hash after sanitization
        content_hash = hashlib.sha256(pearl_text.lower().encode('utf-8')).hexdigest()
        existing = RadiologyPearl.query.filter_by(content_hash=content_hash).first()
        if existing:
            return jsonify({'success': True, 'message': 'Pearl already exists.', 'pearl': _pearl_to_dict(existing), 'duplicate': True})

    pearl = RadiologyPearl(
        content_hash=content_hash,
        pearl_text=pearl_text,
        body_section=data.get('body_section', '').strip() or None,
        modality=normalize_modality(data.get('modality', '')),
        tags=data.get('tags', '').strip() or None,
        source_report_context=data.get('source_report_context', '').strip() or None,
        created_by_user_id=current_user.id,
    )

    # Allow admin to save as pre-verified (for AI-generated pearls)
    from models import UserRole
    if data.get('is_verified') and current_user.role == UserRole.ADMIN:
        pearl.is_verified = True
        pearl.verified_by_user_id = current_user.id
        pearl.verified_at = datetime.utcnow()

    db.session.add(pearl)
    db.session.commit()

    return jsonify({
        'success': True,
        'message': 'Pearl saved successfully.',
        'pearl': _pearl_to_dict(pearl),
        'duplicate': False,
    })


@reporting_bp.route('/api/smart-reporter/pearls', methods=['GET'])
@login_required
def list_pearls():
    """List radiology pearls. All verified + own unverified."""
    q = request.args.get('q', '').strip()
    body_section = request.args.get('body_section', '').strip()
    modality = request.args.get('modality', '').strip()
    limit = request.args.get('limit', 50, type=int)

    query = RadiologyPearl.query.filter(
        db.or_(
            RadiologyPearl.is_verified == True,
            RadiologyPearl.created_by_user_id == current_user.id,
        )
    )

    if q:
        query = query.filter(
            db.or_(
                RadiologyPearl.pearl_text.ilike(f'%{q}%'),
                RadiologyPearl.tags.ilike(f'%{q}%'),
            )
        )
    if body_section:
        query = query.filter(RadiologyPearl.body_section.ilike(f'%{body_section}%'))
    if modality:
        query = query.filter(RadiologyPearl.modality.ilike(f'%{modality}%'))

    pearls = query.order_by(RadiologyPearl.created_at.desc()).limit(limit).all()
    return jsonify([_pearl_to_dict(p) for p in pearls])


@reporting_bp.route('/api/smart-reporter/pearls/<int:pearl_id>', methods=['GET'])
@login_required
def get_pearl(pearl_id):
    """Get a single radiology pearl."""
    pearl = RadiologyPearl.query.get_or_404(pearl_id)
    return jsonify(_pearl_to_dict(pearl))


@reporting_bp.route('/api/smart-reporter/pearls/<int:pearl_id>', methods=['PUT'])
@login_required
def update_pearl(pearl_id):
    """Edit a pearl (admin or creator)."""
    pearl = RadiologyPearl.query.get_or_404(pearl_id)

    from models import UserRole
    if current_user.role != UserRole.ADMIN and pearl.created_by_user_id != current_user.id:
        return jsonify({'error': 'Unauthorized'}), 403

    data = request.get_json() or {}

    if 'pearl_text' in data:
        import hashlib
        new_text = data['pearl_text'].strip()
        if not new_text:
            return jsonify({'error': 'pearl_text cannot be empty'}), 400
        # Sanitize HTML if pearl contains markup (from TinyMCE editor)
        if '<' in new_text:
            from app import sanitize_clinical_html
            new_text = sanitize_clinical_html(new_text)
        new_hash = hashlib.sha256(new_text.lower().encode('utf-8')).hexdigest()
        dup = RadiologyPearl.query.filter(
            RadiologyPearl.content_hash == new_hash,
            RadiologyPearl.id != pearl_id,
        ).first()
        if dup:
            return jsonify({'error': 'Another pearl with identical text already exists'}), 400
        pearl.pearl_text = new_text
        pearl.content_hash = new_hash

    if 'body_section' in data:
        pearl.body_section = data['body_section'].strip() or None
    if 'modality' in data:
        pearl.modality = normalize_modality(data['modality'])
    if 'tags' in data:
        pearl.tags = data['tags'].strip() or None

    pearl.updated_at = datetime.utcnow()
    db.session.commit()
    return jsonify({'success': True, 'pearl': _pearl_to_dict(pearl)})


@reporting_bp.route('/api/smart-reporter/pearls/<int:pearl_id>', methods=['DELETE'])
@login_required
@require_admin
def delete_pearl(pearl_id):
    """Delete a pearl (admin only)."""
    pearl = RadiologyPearl.query.get_or_404(pearl_id)
    db.session.delete(pearl)
    db.session.commit()
    return jsonify({'success': True, 'message': 'Pearl deleted.'})


@reporting_bp.route('/api/smart-reporter/pearls/<int:pearl_id>/verify', methods=['POST'])
@login_required
@require_admin
def verify_pearl(pearl_id):
    """Verify a pearl (admin only) — makes it visible to all users."""
    pearl = RadiologyPearl.query.get_or_404(pearl_id)
    pearl.is_verified = True
    pearl.verified_by_user_id = current_user.id
    pearl.verified_at = datetime.utcnow()
    db.session.commit()
    return jsonify({'success': True, 'message': 'Pearl verified.', 'pearl': _pearl_to_dict(pearl)})


def _pearl_to_dict(pearl):
    """Convert RadiologyPearl to JSON-serializable dict."""
    return {
        'id': pearl.id,
        'pearl_text': pearl.pearl_text,
        'body_section': pearl.body_section,
        'modality': pearl.modality,
        'tags': pearl.tags,
        'source_report_context': pearl.source_report_context,
        'is_verified': pearl.is_verified,
        'created_by_user_id': pearl.created_by_user_id,
        'created_by_name': pearl.created_by.get_display_name() if pearl.created_by else None,
        'verified_at': pearl.verified_at.isoformat() if pearl.verified_at else None,
        'created_at': pearl.created_at.isoformat() if pearl.created_at else None,
    }


# ── Shared helper: build context from admin inputs ─────────────────

def _build_generation_context(instructions='', reference_urls=None, pdf_files=None):
    """Build context string + extract reference images from optional admin inputs.

    Args:
        instructions: Free-text instructions string.
        reference_urls: A single URL string or list of URL strings.
        pdf_files: A single FileStorage or list of FileStorage objects.

    Returns:
        tuple (context_text: str, reference_images: list[dict])
        Each image dict has keys: url, title, case_url, source_domain, license, author
    """
    parts = []
    ref_images = []

    if instructions:
        parts.append(f"ADMIN INSTRUCTIONS:\n{instructions}")

    # Normalise to list (supports legacy single-string callers)
    if isinstance(reference_urls, str):
        reference_urls = [reference_urls] if reference_urls.strip() else []
    reference_urls = [u.strip() for u in (reference_urls or []) if u and u.strip()]

    for ref_url in reference_urls:
        try:
            from clinical_tool_generator import fetch_url_content
            content = fetch_url_content(ref_url, max_chars=4000)
            if content:
                parts.append(f"REFERENCE URL ({ref_url}):\n{content}")
        except Exception as exc:
            logger.warning("Failed to fetch reference URL %s: %s", ref_url, exc)
        try:
            from clinical_tool_generator import fetch_url_images
            url_imgs = fetch_url_images(ref_url, max_images=3)
            ref_images.extend(url_imgs)
        except Exception as exc:
            logger.warning("URL image extraction failed for %s: %s", ref_url, exc)

    # Normalise pdf_files to list
    if pdf_files and not isinstance(pdf_files, (list, tuple)):
        pdf_files = [pdf_files]
    pdf_files = pdf_files or []

    for pdf_file in pdf_files:
        _pdf_tmp_path = None
        try:
            import tempfile, os as _os
            from clinical_tool_generator import extract_pdf_text
            tmp = tempfile.NamedTemporaryFile(delete=False, suffix='.pdf')
            pdf_file.save(tmp.name)
            tmp.close()
            _pdf_tmp_path = tmp.name
            text = extract_pdf_text(_pdf_tmp_path)
            if text:
                parts.append(f"REFERENCE PDF ({pdf_file.filename}):\n{text[:6000]}")
        except Exception as exc:
            logger.warning("Failed to extract PDF text: %s", exc)
        if _pdf_tmp_path:
            try:
                from clinical_tool_generator import extract_pdf_images
                pdf_imgs = extract_pdf_images(_pdf_tmp_path, max_images=3)
                ref_images.extend(pdf_imgs)
            except Exception as exc:
                logger.warning("PDF image extraction failed: %s", exc)
            try:
                import os as _os
                _os.unlink(_pdf_tmp_path)
            except Exception:
                pass

    context_text = '\n\n'.join(parts) if parts else ''
    return (context_text, ref_images)


# ── Admin AI Pearl Generator ────────────────────────────────────────

@reporting_bp.route('/api/admin/generate-pearl', methods=['POST'])
@login_required
@require_admin
def admin_generate_pearl():
    """Generate a structured radiology pearl via AI (admin only)."""
    import time

    # Support both JSON and FormData (when PDFs are uploaded)
    if request.content_type and 'multipart/form-data' in request.content_type:
        data = request.form
    else:
        data = request.get_json() or {}

    topic = (data.get('topic') or '').strip()
    if not topic:
        return jsonify({'error': 'topic is required'}), 400

    modality_raw = (data.get('modality') or '').strip()
    modality = normalize_modality(modality_raw) if modality_raw else ''
    body_section = (data.get('body_section') or '').strip()
    include_image = data.get('include_image', True)
    if isinstance(include_image, str):
        include_image = include_image.lower() not in ('false', '0', '')

    # Build additional context + extract reference images from optional admin inputs
    instructions = (data.get('instructions') or '').strip()
    if request.content_type and 'multipart/form-data' in request.content_type:
        reference_urls = request.form.getlist('reference_url')
        pdf_files = request.files.getlist('pdf')
    else:
        reference_urls = data.get('reference_urls') or ([data['reference_url']] if data.get('reference_url') else [])
        pdf_files = []
    additional_context, ref_images = _build_generation_context(instructions, reference_urls, pdf_files)

    start = time.time()

    try:
        from ai_pearl_generator import (
            generate_pearl, fetch_radiopaedia_images, render_pearl_html,
            PearlGeneratorError,
        )

        result = generate_pearl(topic, modality=modality, body_section=body_section,
                                additional_context=additional_context)

        # Fetch Radiopaedia images + combine with reference images
        all_images = []
        if include_image:
            rp_images = fetch_radiopaedia_images(topic, modality=modality, max_images=3)
            all_images.extend(rp_images)
        all_images.extend(ref_images)
        all_images = all_images[:5]  # Limit total

        # Re-render HTML with images if any found
        if all_images:
            result['pearl_html'] = render_pearl_html(
                result['pearl_data'], reference_images=all_images,
            )

    except Exception as exc:
        logger.error("Pearl generation failed: %s", exc)
        return jsonify({'error': str(exc)}), 500

    duration_ms = int((time.time() - start) * 1000)

    try:
        from models import log_ai_usage
        log_ai_usage(
            user_id=current_user.id,
            action='generate_pearl',
            provider='anthropic',
            model=result.get('model'),
            output_tokens=result.get('token_count'),
            input_summary=f"topic={topic}, modality={modality}, body={body_section}",
            status='success',
            duration_ms=duration_ms,
        )
    except Exception:
        pass  # Audit logging never breaks main flow

    return jsonify({
        'success': True,
        'pearl_html': result['pearl_html'],
        'pearl_data': result['pearl_data'],
        'title': result['title'],
        'tags': result['tags'],
        'model': result.get('model'),
        'token_count': result.get('token_count'),
    })


# ==================== VOICE DICTATION (Groq Whisper) ====================

GROQ_WHISPER_URL = 'https://api.groq.com/openai/v1/audio/transcriptions'
GROQ_WHISPER_MODEL = 'whisper-large-v3-turbo'
GROQ_WHISPER_PROMPT = (
    'Radiology report dictation. Medical terms: carcinoma, adenocarcinoma, '
    'hepatocellular, metastasis, metastases, lymphadenopathy, cholangiocarcinoma, '
    'BI-RADS, PI-RADS, LI-RADS, TI-RADS, Fleischner, RECIST, Bosniak, '
    'peritoneal, retroperitoneal, mesenteric, parenchymal, hypodense, hyperdense, '
    'hyperintense, hypointense, T1-weighted, T2-weighted, FLAIR, DWI, ADC, '
    'pneumothorax, haemothorax, consolidation, atelectasis, bronchiectasis, '
    'IMPRESSION, FINDINGS, CLINICAL INFORMATION, TECHNIQUE, COMPARISON'
)
MAX_AUDIO_SIZE_MB = 25  # Groq limit


@reporting_bp.route('/api/smart-reporter/transcribe', methods=['POST'])
@login_required
def smart_reporter_transcribe():
    """Voice dictation: transcribe audio via Groq Whisper turbo."""
    # Subscription check — paid users only
    if current_user.subscription_status != SubscriptionStatus.PAID:
        return jsonify({
            'error': 'Voice dictation is available for paid subscribers. '
                     'Upgrade your plan to unlock this feature.'
        }), 403

    # Rate limit (shared with other AI features)
    ok, remaining, err = _check_ai_rate_limit()
    if not ok:
        return err

    # Validate audio file
    audio_file = request.files.get('audio')
    if not audio_file:
        return jsonify({'error': 'No audio file provided.'}), 400

    audio_data = audio_file.read()
    if len(audio_data) > MAX_AUDIO_SIZE_MB * 1024 * 1024:
        return jsonify({'error': f'Audio file too large (max {MAX_AUDIO_SIZE_MB}MB).'}), 400
    if len(audio_data) < 100:
        return jsonify({'error': 'Audio file is too small — no speech detected.'}), 400

    groq_api_key = os.environ.get('GROQ_API_KEY')
    if not groq_api_key:
        logger.error('GROQ_API_KEY not configured')
        return jsonify({'error': 'Voice dictation is not configured on this server.'}), 503

    # Determine filename/content-type from upload
    filename = audio_file.filename or 'dictation.webm'
    content_type = audio_file.content_type or 'audio/webm'

    start_time = time.time()
    try:
        resp = http_requests.post(
            GROQ_WHISPER_URL,
            headers={'Authorization': f'Bearer {groq_api_key}'},
            files={'file': (filename, audio_data, content_type)},
            data={
                'model': GROQ_WHISPER_MODEL,
                'language': 'en',
                'response_format': 'text',
                'prompt': GROQ_WHISPER_PROMPT,
            },
            timeout=30,
        )
        duration_ms = int((time.time() - start_time) * 1000)

        if resp.status_code != 200:
            logger.error(f'Groq Whisper error {resp.status_code}: {resp.text[:500]}')
            return jsonify({'error': 'Transcription service returned an error. Please try again.'}), 502

        transcribed_text = resp.text.strip()

    except http_requests.exceptions.Timeout:
        logger.error('Groq Whisper request timed out')
        return jsonify({'error': 'Transcription timed out. Try a shorter recording.'}), 504
    except Exception as exc:
        logger.error(f'Groq Whisper request failed: {exc}')
        return jsonify({'error': 'Transcription failed. Please try again.'}), 500

    # Audit log
    try:
        from models import log_ai_usage
        log_ai_usage(
            user_id=current_user.id,
            action='voice_transcribe',
            provider='groq',
            model=GROQ_WHISPER_MODEL,
            input_summary=f'audio {len(audio_data)} bytes',
            status='success',
            duration_ms=duration_ms,
        )
    except Exception:
        pass

    return jsonify({
        'success': True,
        'text': transcribed_text,
        'remaining_requests': remaining,
    })
