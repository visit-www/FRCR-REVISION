"""
RadInsight Peer Review — AI output verification module.

Post-processes AI-generated medical content to:
1. Extract numerical claims (measurements, percentages, thresholds, doses)
2. Verify claims against PubMed indexed literature
3. Verify Radiopaedia article URLs via HEAD request
4. Annotate claims with trust tiers (verified / unverified)
5. Render verification badges, reference sections, and disclaimers

Usage:
    from radinsight_peer_review import peer_review

    result = peer_review(ai_output_dict, topic="circle of Willis", context="anatomy")
    # result['claims']             — list of extracted + annotated claims
    # result['references_html']    — rendered reference section HTML
    # result['disclaimer_html']    — rendered disclaimer banner HTML
    # result['verification_summary'] — {verified: N, unverified: N, total: N}
    # result['radiopaedia_url']    — verified article URL or None
    # result['pubmed_articles']    — list of matched PubMed articles
"""

import re
import os
import json
import time
import logging
import hashlib
from datetime import datetime, timedelta
from html import escape as html_escape
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Optional

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Cache configuration (mirrors pubmed_service.py pattern)
# ---------------------------------------------------------------------------
CACHE_DIR = os.path.join('/tmp' if os.environ.get('VERCEL') else os.path.dirname(__file__), 'cache', 'peer_review')
CACHE_DURATION_HOURS = 24


def _ensure_cache_dir():
    os.makedirs(CACHE_DIR, exist_ok=True)


def _cache_key(topic: str, context: str) -> str:
    raw = f"pr_{topic}_{context}"
    return hashlib.md5(raw.encode()).hexdigest()


def _get_cached(key: str) -> Optional[dict]:
    _ensure_cache_dir()
    path = os.path.join(CACHE_DIR, f"{key}.json")
    if not os.path.exists(path):
        return None
    try:
        with open(path, 'r') as f:
            data = json.load(f)
        ts = datetime.fromisoformat(data.get('timestamp', ''))
        if datetime.now() - ts < timedelta(hours=CACHE_DURATION_HOURS):
            return data.get('result')
    except Exception:
        pass
    return None


def _set_cached(key: str, result: dict):
    _ensure_cache_dir()
    path = os.path.join(CACHE_DIR, f"{key}.json")
    try:
        with open(path, 'w') as f:
            json.dump({'timestamp': datetime.now().isoformat(), 'result': result}, f)
    except Exception as exc:
        logger.debug("Peer review cache write error: %s", exc)


# ---------------------------------------------------------------------------
# Claim extraction — regex patterns for medical numerical values
# ---------------------------------------------------------------------------
_NUM_PATTERNS = [
    # Ranges: 20-32%, 3-5 mm, 10–15 cm
    re.compile(r'(\d+(?:\.\d+)?)\s*[\-–]\s*(\d+(?:\.\d+)?)\s*(%|mm|cm|mL|mg|Gy|HU|L|g|kg|mGy|mSv)', re.IGNORECASE),
    # Single values with units: 40 mm, 3.5 cm, 150 HU
    re.compile(r'(\d+(?:\.\d+)?)\s*(mm|cm|mL|mg|Gy|HU|L|g|kg|mGy|mSv)\b', re.IGNORECASE),
    # Percentages: 20%, ~30%, approximately 15%
    re.compile(r'(?:approximately |~|about |circa )?(\d+(?:\.\d+)?)\s*%', re.IGNORECASE),
    # Threshold patterns: > 3 mm, < 40 mm, ≥ 10 mm
    re.compile(r'[>≥<≤]\s*(\d+(?:\.\d+)?)\s*(mm|cm|mL|mg|Gy|HU|mGy|mSv|%)?', re.IGNORECASE),
    # Prevalence phrases: prevalence of 20-32%, found in 10% of
    re.compile(r'(?:prevalence|incidence|frequency|found in|occurs in|seen in)\s+(?:of\s+)?(?:approximately |~|about )?(\d+(?:\.\d+)?)\s*[\-–]?\s*(\d+(?:\.\d+)?)?\s*%', re.IGNORECASE),
]

# Fields in structured anatomy JSON that contain verifiable claims
_ANATOMY_CLAIM_FIELDS = [
    ('normal_variants', 'prevalence'),
    ('normal_variants', 'imaging_pitfall'),
    ('measurements', 'normal'),
    ('measurements', 'abnormal_threshold'),
    ('diagnostic_appearances', 'significance'),
    ('pathology_at_this_site', 'key_finding'),
]

# Fields in other AI outputs
_GENERAL_CLAIM_FIELDS = [
    'answer',
    'teaching_point',
    'guideline_citation',
    'key_points',
]


def _has_numerical_claim(text: str) -> bool:
    """Check if text contains a numerical medical claim."""
    if not text:
        return False
    for pattern in _NUM_PATTERNS:
        if pattern.search(text):
            return True
    return False


def _extract_llm_claims(data: dict) -> list[dict]:
    """Extract claims from LLM self-reported verifiable_claims field.

    The model provides claims with optimised search terms, which gives
    much better PubMed matches than regex extraction. This is the preferred
    extraction method for structured JSON outputs.

    Looks for verifiable_claims at top-level and inside nested 'insights' dict.
    Returns empty list if field is absent or empty.
    """
    raw_claims = []

    # Top-level verifiable_claims
    top = data.get('verifiable_claims', [])
    if isinstance(top, list):
        raw_claims.extend(top)

    # Nested inside insights (Smart Reporter unified assist)
    insights = data.get('insights', {})
    if isinstance(insights, dict):
        nested = insights.get('verifiable_claims', [])
        if isinstance(nested, list):
            raw_claims.extend(nested)

    if not raw_claims:
        return []

    claims = []
    for i, rc in enumerate(raw_claims):
        if not isinstance(rc, dict):
            continue
        claim_text = (rc.get('claim') or '').strip()
        if not claim_text:
            continue
        claims.append({
            'text': claim_text,
            'field': f"verifiable_claims[{i}]",
            'context_name': rc.get('search_terms', ''),  # LLM-provided search terms
            'section': 'verifiable_claims',
            'index': i,
            'field_key': rc.get('type', 'unknown'),
            'status': 'pending',
            'pubmed_match': None,
            '_llm_search_terms': rc.get('search_terms', ''),  # Preserved for PubMed query
        })

    return claims


def _extract_claims_from_anatomy(data: dict) -> list[dict]:
    """Extract verifiable numerical claims from anatomy snippet JSON.

    Uses BOTH methods and merges results:
    1. LLM self-extracted claims (verifiable_claims field) — best search terms
    2. Regex extraction from structured fields — catches what the LLM missed

    Deduplicates by checking if a regex-found claim's text is already
    covered by an LLM claim (substring match).
    """
    # Method 1: LLM self-extracted claims
    llm_claims = _extract_llm_claims(data)

    # Method 2: Regex extraction from structured fields (always runs)
    regex_claims = []

    for section_key, field_key in _ANATOMY_CLAIM_FIELDS:
        items = data.get(section_key, [])
        if not isinstance(items, list):
            continue
        for i, item in enumerate(items):
            if not isinstance(item, dict):
                continue
            value = item.get(field_key, '')
            if value and _has_numerical_claim(str(value)):
                name = item.get('name') or item.get('variant') or item.get('what') or item.get('finding') or item.get('pathology') or ''
                regex_claims.append({
                    'text': str(value),
                    'field': f"{section_key}[{i}].{field_key}",
                    'context_name': str(name),
                    'section': section_key,
                    'index': i,
                    'field_key': field_key,
                    'status': 'pending',
                    'pubmed_match': None,
                })

    # Also check overview for numerical claims
    overview = data.get('overview', '')
    if overview and _has_numerical_claim(overview):
        regex_claims.append({
            'text': overview,
            'field': 'overview',
            'context_name': data.get('title', ''),
            'section': 'overview',
            'index': 0,
            'field_key': 'overview',
            'status': 'pending',
            'pubmed_match': None,
        })

    # Merge: start with LLM claims, add regex claims not already covered
    if not llm_claims:
        return regex_claims
    if not regex_claims:
        return llm_claims

    # Deduplicate: check if each regex claim's key numbers are already
    # mentioned in an LLM claim (prevents double-flagging same measurement)
    llm_texts_lower = ' '.join(c['text'].lower() for c in llm_claims)
    merged = list(llm_claims)
    for rc in regex_claims:
        # Extract numbers from the regex claim
        nums = re.findall(r'\d+(?:\.\d+)?', rc['text'])
        # If at least one number is NOT in any LLM claim, this is a new claim
        if nums and not any(n in llm_texts_lower for n in nums):
            merged.append(rc)

    return merged


def _extract_claims_from_text(text: str, field_name: str = 'text') -> list[dict]:
    """Extract verifiable numerical claims from free-text AI output."""
    if not text or not _has_numerical_claim(text):
        return []

    # Split into sentences and check each
    claims = []
    sentences = re.split(r'(?<=[.!?])\s+', text)
    for i, sentence in enumerate(sentences):
        if _has_numerical_claim(sentence):
            claims.append({
                'text': sentence.strip(),
                'field': f"{field_name}[sentence_{i}]",
                'context_name': '',
                'section': field_name,
                'index': i,
                'field_key': field_name,
                'status': 'pending',
                'pubmed_match': None,
            })
    return claims


def _extract_claims_from_html(html: str, field_name: str = 'html') -> list[dict]:
    """Extract verifiable numerical claims from HTML content (SBA, Viva, etc)."""
    if not html:
        return []
    # Strip HTML tags to get plain text
    plain = re.sub(r'<[^>]+>', ' ', html)
    plain = re.sub(r'\s+', ' ', plain).strip()
    return _extract_claims_from_text(plain, field_name)


# ---------------------------------------------------------------------------
# PubMed verification
# ---------------------------------------------------------------------------
def _verify_claim_pubmed(claim: dict, topic: str) -> dict:
    """Search PubMed for a claim and check if abstract contains matching numbers."""
    try:
        from pubmed_service import search_pubmed
    except ImportError:
        logger.warning("pubmed_service not available for peer review")
        claim['status'] = 'unverified'
        return claim

    # Prefer LLM-provided search terms (much better than regex-derived queries)
    llm_terms = claim.get('_llm_search_terms', '')
    if llm_terms:
        query = llm_terms
    else:
        # Fallback: build search query from topic + context
        search_terms = []
        if topic:
            search_terms.append(topic)
        if claim.get('context_name'):
            search_terms.append(claim['context_name'])
        query = ' '.join(search_terms)
        if not query.strip():
            query = claim['text'][:80]

    # Extract the key numbers from the claim text
    numbers = re.findall(r'\d+(?:\.\d+)?', claim['text'])

    try:
        articles = search_pubmed(query, max_results=5)
    except Exception as exc:
        logger.debug("PubMed search failed for claim '%s': %s", claim['text'][:50], exc)
        claim['status'] = 'unverified'
        return claim

    if not articles:
        claim['status'] = 'unverified'
        return claim

    # Check if any article abstract contains matching numbers
    for article in articles:
        abstract = (article.get('abstract') or '').lower()
        title = (article.get('title') or '').lower()
        combined = f"{title} {abstract}"

        # Check if at least one key number appears in the abstract/title
        match_count = 0
        for num in numbers:
            if num in combined:
                match_count += 1

        # Require at least one number match AND topic relevance
        topic_words = [w.lower() for w in topic.split() if len(w) > 3] if topic else []
        topic_relevant = any(w in combined for w in topic_words) if topic_words else True

        if match_count >= 1 and topic_relevant:
            claim['status'] = 'verified'
            claim['pubmed_match'] = {
                'title': article.get('title', ''),
                'authors': article.get('authors', []),
                'journal': article.get('journal', ''),
                'journal_iso': article.get('journal_iso', ''),
                'year': article.get('year', ''),
                'doi': article.get('doi'),
                'pmid': article.get('pmid', ''),
                'pubmed_link': article.get('pubmed_link', ''),
            }
            return claim

    claim['status'] = 'unverified'
    return claim


def _verify_claims_parallel(claims: list[dict], topic: str, max_workers: int = 4) -> list[dict]:
    """Verify multiple claims against PubMed in parallel."""
    if not claims:
        return []

    # Deduplicate searches — group claims by context_name to avoid redundant PubMed calls
    context_groups: dict[str, list[int]] = {}
    for i, c in enumerate(claims):
        key = (c.get('context_name', '') or c['text'][:40]).lower().strip()
        context_groups.setdefault(key, []).append(i)

    # Build unique search tasks (one per context group)
    search_tasks = []
    for key, indices in context_groups.items():
        representative = claims[indices[0]]
        search_tasks.append((key, representative, indices))

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {}
        for key, rep_claim, indices in search_tasks:
            # Deep copy so parallel writes don't collide
            claim_copy = dict(rep_claim)
            future = executor.submit(_verify_claim_pubmed, claim_copy, topic)
            futures[future] = (key, indices)

        for future in as_completed(futures):
            key, indices = futures[future]
            try:
                verified_claim = future.result()
                # Apply result to all claims in this group
                for idx in indices:
                    claims[idx]['status'] = verified_claim['status']
                    claims[idx]['pubmed_match'] = verified_claim.get('pubmed_match')
            except Exception as exc:
                logger.debug("Claim verification failed for '%s': %s", key, exc)
                for idx in indices:
                    claims[idx]['status'] = 'unverified'

    return claims


# ---------------------------------------------------------------------------
# Radiopaedia article verification
# ---------------------------------------------------------------------------
_radiopaedia_cache: dict[str, Optional[str]] = {}


def verify_radiopaedia_article(topic: str) -> Optional[str]:
    """Check if a Radiopaedia article page exists for the given topic.

    Returns the verified URL if it exists (HTTP 200), else None.
    Results are cached in-memory.
    """
    import requests as req

    slug = re.sub(r'[^a-z0-9]+', '-', topic.lower()).strip('-')
    url = f"https://radiopaedia.org/articles/{slug}"

    if url in _radiopaedia_cache:
        return _radiopaedia_cache[url]

    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                          "AppleWebKit/537.36 (KHTML, like Gecko) "
                          "Chrome/120.0.0.0 Safari/537.36",
        }
        r = req.head(url, headers=headers, timeout=5, allow_redirects=True)
        if r.status_code == 200:
            # Use the final URL after redirects (Radiopaedia may normalise slugs)
            final_url = r.url if r.url else url
            _radiopaedia_cache[url] = final_url
            return final_url
    except Exception as exc:
        logger.debug("Radiopaedia HEAD check failed for '%s': %s", url, exc)

    _radiopaedia_cache[url] = None
    return None


# ---------------------------------------------------------------------------
# HTML rendering
# ---------------------------------------------------------------------------
def _esc(text) -> str:
    """HTML-escape a string."""
    if not text:
        return ''
    return html_escape(str(text))


def render_verification_badge(claim: dict) -> str:
    """Render inline badge for a single claim."""
    if claim['status'] == 'verified':
        match = claim.get('pubmed_match') or {}
        doi = match.get('doi')
        pmid = match.get('pmid', '')
        link = f"https://doi.org/{doi}" if doi else match.get('pubmed_link', f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/")
        short_ref = match.get('journal_iso') or match.get('journal', '')
        year = match.get('year', '')
        tooltip = f"Verified: {short_ref} {year}".strip()
        return (
            f'<a href="{_esc(link)}" target="_blank" rel="noopener noreferrer" '
            f'class="peer-review-badge verified" title="{_esc(tooltip)}">'
            f'<i class="fas fa-check-circle"></i></a>'
        )
    else:
        return (
            '<span class="peer-review-badge unverified" '
            'data-bs-toggle="tooltip" data-bs-placement="top" '
            'title="This number came from the AI. We couldn\'t find a paper to back it. '
            'Treat with caution.">'
            '<i class="fas fa-exclamation-triangle"></i></span>'
        )


def render_disclaimer_html(summary: dict) -> str:
    """Render the peer review disclaimer banner."""
    verified = summary.get('verified', 0)
    unverified = summary.get('unverified', 0)
    total = summary.get('total', 0)

    badges = ''
    if total > 0:
        if verified > 0:
            badges += f' <span class="badge bg-success ms-1">{verified} verified</span>'
        if unverified > 0:
            badges += f' <span class="badge bg-warning text-dark ms-1">{unverified} unverified</span>'

    return (
        '<div class="peer-review-disclaimer mt-2 mb-2">'
        '<i class="fas fa-shield-alt me-1"></i>'
        '<strong>AI-Generated Revision Aid</strong> &mdash; '
        'Verify critical measurements against your textbook before clinical use.'
        f'{badges}'
        '</div>'
    )


def render_references_html(
    pubmed_articles: list[dict],
    radiopaedia_url: Optional[str] = None,
    topic: str = '',
) -> str:
    """Render the verified references section."""
    if not pubmed_articles and not radiopaedia_url:
        return ''

    parts = [
        '<div class="peer-review-references mt-3">',
        '<div class="card border">',
        '<div class="card-header bg-light py-2">',
        '<i class="fas fa-book-medical me-2 text-muted"></i>',
        '<strong class="text-muted">Verified References</strong>',
        '</div>',
        '<div class="card-body p-3">',
        '<ul class="list-unstyled mb-0">',
    ]

    # Radiopaedia article (verified, clickable)
    if radiopaedia_url:
        parts.append(
            f'<li class="mb-2">'
            f'<i class="fas fa-globe me-1 text-info"></i>'
            f'<a href="{_esc(radiopaedia_url)}" target="_blank" rel="noopener noreferrer">'
            f'{_esc(topic.title())} &mdash; Radiopaedia.org</a>'
            f' <span class="badge bg-info text-white" style="font-size:0.6rem;">Radiopaedia</span>'
            f'</li>'
        )

    # PubMed articles (deduplicated by PMID)
    seen_pmids = set()
    for article in pubmed_articles:
        pmid = article.get('pmid', '')
        if pmid in seen_pmids:
            continue
        seen_pmids.add(pmid)

        doi = article.get('doi')
        link = f"https://doi.org/{doi}" if doi else article.get('pubmed_link', '')
        authors = article.get('authors', [])
        first_author = authors[0] if authors else ''
        if isinstance(first_author, dict):
            first_author = first_author.get('name', str(first_author))
        et_al = ' et al.' if len(authors) > 1 else ''
        year = article.get('year', '')
        journal = article.get('journal_iso') or article.get('journal', '')
        title = article.get('title', '')

        parts.append(
            f'<li class="mb-2">'
            f'<i class="fas fa-file-medical me-1 text-success"></i>'
            f'<a href="{_esc(link)}" target="_blank" rel="noopener noreferrer">'
            f'{_esc(title)}</a>'
            f'<br><small class="text-muted">'
            f'{_esc(first_author)}{_esc(et_al)} '
            f'<em>{_esc(journal)}</em> ({_esc(year)})'
            f' &mdash; <span class="badge bg-success" style="font-size:0.6rem;">PubMed</span>'
            f'</small></li>'
        )

    parts.extend(['</ul>', '</div>', '</div>', '</div>'])
    return '\n'.join(parts)


def render_flag_button_html(content_type: str = '', content_id: str = '') -> str:
    """Render the 'Flag Inaccuracy' button."""
    return (
        f'<button class="btn btn-sm btn-outline-danger peer-review-flag mt-2" '
        f'data-content-type="{_esc(content_type)}" '
        f'data-content-id="{_esc(content_id)}" '
        f'onclick="openPeerReviewFlagModal(this)">'
        f'<i class="fas fa-flag me-1"></i>Flag Inaccuracy'
        f'</button>'
    )


# ---------------------------------------------------------------------------
# Anatomy-specific: inject badges into rendered HTML
# ---------------------------------------------------------------------------
def _inject_badges_into_anatomy_html(html: str, claims: list[dict]) -> str:
    """Inject verification badges into already-rendered anatomy HTML.

    Strategy: for each claim, find the key numerical value in the HTML
    and append the verification badge after it. Falls back to full
    sentence match if numerical match fails.
    """
    for claim in claims:
        badge = render_verification_badge(claim)
        raw_text = claim['text']
        escaped_full = _esc(raw_text)

        # Try 1: full sentence match (works for inline text)
        if escaped_full in html:
            html = html.replace(escaped_full, escaped_full + ' ' + badge, 1)
            continue

        # Try 2: match the numerical portion (e.g., "0.6-5%", "15-20%")
        # This handles text split across HTML tags (table cells, list items)
        numbers = re.findall(r'\d+(?:\.\d+)?(?:\s*[-–]\s*\d+(?:\.\d+)?)?%?(?:\s*(?:mm|cm|m[Ll]|mg|g|Hz|kHz))?', raw_text)
        injected = False
        for num in numbers:
            escaped_num = _esc(num)
            # Find it inside tag content (not inside attributes)
            pattern = r'(>[^<]*?)(' + re.escape(escaped_num) + r')([^<]*?<)'
            match = re.search(pattern, html)
            if match:
                replacement = match.group(1) + match.group(2) + ' ' + badge + match.group(3)
                html = html[:match.start()] + replacement + html[match.end():]
                injected = True
                break
        if injected:
            continue

        # Try 3: find a short distinctive phrase (first 40 chars)
        short = _esc(raw_text[:40].strip())
        if short and short in html:
            html = html.replace(short, short + ' ' + badge, 1)

    return html


# ---------------------------------------------------------------------------
# Main public API
# ---------------------------------------------------------------------------
def peer_review(
    ai_output: dict | str,
    topic: str = '',
    context: str = 'anatomy',
    content_type: str = '',
    content_id: str = '',
    skip_pubmed: bool = False,
) -> dict:
    """Run RadInsight Peer Review on AI-generated content.

    Args:
        ai_output: Structured dict (anatomy JSON, insights dict) or
                   raw text/HTML string from AI.
        topic: The anatomy/medical topic (used for PubMed search context).
        context: One of 'anatomy', 'radiq', 'vetting', 'teaching',
                 'sba', 'viva', 'admin', 'general'.
        content_type: For flag button (e.g., 'anatomy_snippet', 'radiq_answer').
        content_id: For flag button (e.g., snippet DB id).
        skip_pubmed: If True, skip PubMed verification (useful for testing).

    Returns:
        dict with keys: claims, references_html, disclaimer_html,
        flag_button_html, verification_summary, radiopaedia_url,
        pubmed_articles, annotated_html (if HTML input).
    """
    start_time = time.time()

    # Check cache
    cache_k = _cache_key(topic or str(ai_output)[:100], context)
    cached = _get_cached(cache_k)
    if cached:
        logger.debug("Peer review cache hit for '%s' (%s)", topic, context)
        return cached

    # --- 1. Extract claims ---
    claims = []
    if isinstance(ai_output, dict):
        if context == 'anatomy':
            claims = _extract_claims_from_anatomy(ai_output)
        else:
            # LLM self-extracted claims + regex fallback (merged, not either-or)
            llm_claims = _extract_llm_claims(ai_output)

            # Regex extraction from common text fields (always runs)
            regex_claims = []
            for field in _GENERAL_CLAIM_FIELDS:
                value = ai_output.get(field, '')
                if isinstance(value, str):
                    regex_claims.extend(_extract_claims_from_text(value, field))
                elif isinstance(value, list):
                    for j, item in enumerate(value):
                        if isinstance(item, str) and _has_numerical_claim(item):
                            regex_claims.append({
                                'text': item,
                                'field': f"{field}[{j}]",
                                'context_name': '',
                                'section': field,
                                'index': j,
                                'field_key': field,
                                'status': 'pending',
                                'pubmed_match': None,
                            })

            # Also check nested insights dict
            insights = ai_output.get('insights', {})
            if isinstance(insights, dict):
                for k, v in insights.items():
                    if isinstance(v, str) and k != 'verifiable_claims':
                        regex_claims.extend(_extract_claims_from_text(v, f"insights.{k}"))

            # Merge LLM + regex claims (deduplicate by number overlap)
            if llm_claims and regex_claims:
                llm_texts_lower = ' '.join(c['text'].lower() for c in llm_claims)
                claims = list(llm_claims)
                for rc in regex_claims:
                    nums = re.findall(r'\d+(?:\.\d+)?', rc['text'])
                    if nums and not any(n in llm_texts_lower for n in nums):
                        claims.append(rc)
            elif llm_claims:
                claims = llm_claims
            else:
                claims = regex_claims

    elif isinstance(ai_output, str):
        # Raw HTML or text
        if '<' in ai_output and '>' in ai_output:
            claims = _extract_claims_from_html(ai_output, context)
        else:
            claims = _extract_claims_from_text(ai_output, context)

    # --- 2. Verify claims via PubMed ---
    if claims and not skip_pubmed:
        claims = _verify_claims_parallel(claims, topic)

    # --- 3. Verify Radiopaedia article ---
    radiopaedia_url = None
    if topic:
        radiopaedia_url = verify_radiopaedia_article(topic)

    # --- 4. Collect unique PubMed articles from verified claims ---
    pubmed_articles = []
    seen_pmids = set()
    for c in claims:
        match = c.get('pubmed_match')
        if match and match.get('pmid') and match['pmid'] not in seen_pmids:
            seen_pmids.add(match['pmid'])
            pubmed_articles.append(match)

    # --- 5. Build summary ---
    verified_count = sum(1 for c in claims if c['status'] == 'verified')
    unverified_count = sum(1 for c in claims if c['status'] == 'unverified')
    summary = {
        'verified': verified_count,
        'unverified': unverified_count,
        'total': len(claims),
    }

    # --- 6. Render HTML ---
    disclaimer_html = render_disclaimer_html(summary)
    references_html = render_references_html(pubmed_articles, radiopaedia_url, topic)
    flag_html = render_flag_button_html(content_type, content_id)

    # --- 7. If input was HTML string, annotate it ---
    annotated_html = None
    if isinstance(ai_output, str) and claims:
        annotated_html = ai_output
        for claim in claims:
            badge = render_verification_badge(claim)
            # Find numerical patterns in the HTML and append badge
            for pattern in _NUM_PATTERNS:
                match_obj = pattern.search(claim['text'])
                if match_obj:
                    num_str = match_obj.group(0)
                    esc_num = _esc(num_str)
                    if esc_num in annotated_html:
                        annotated_html = annotated_html.replace(
                            esc_num, esc_num + ' ' + badge, 1
                        )
                    break

    elapsed_ms = int((time.time() - start_time) * 1000)
    logger.info(
        "Peer review for '%s' (%s): %d claims, %d verified, %d unverified, %dms",
        topic, context, len(claims), verified_count, unverified_count, elapsed_ms
    )

    result = {
        'claims': claims,
        'references_html': references_html,
        'disclaimer_html': disclaimer_html,
        'flag_button_html': flag_html,
        'verification_summary': summary,
        'radiopaedia_url': radiopaedia_url,
        'pubmed_articles': pubmed_articles,
        'annotated_html': annotated_html,
        'elapsed_ms': elapsed_ms,
    }

    # Cache result
    _set_cached(cache_k, result)

    return result


def peer_review_anatomy(
    parsed_json: dict,
    rendered_html: str,
    topic: str = '',
    content_id: str = '',
) -> dict:
    """Convenience wrapper for anatomy snippets.

    Returns the same dict as peer_review() plus 'content_html' which is
    the original rendered HTML with injected badges, disclaimer, references,
    and flag button appended.
    """
    pr = peer_review(
        parsed_json,
        topic=topic,
        context='anatomy',
        content_type='anatomy_snippet',
        content_id=content_id,
    )

    # Inject inline badges into the rendered HTML
    if pr['claims']:
        rendered_html = _inject_badges_into_anatomy_html(rendered_html, pr['claims'])

    # Append disclaimer + references + flag button
    rendered_html = (
        pr['disclaimer_html']
        + rendered_html
        + pr['references_html']
        + pr['flag_button_html']
    )

    pr['content_html'] = rendered_html
    return pr


# ---------------------------------------------------------------------------
# Stale badge handling: strip automated badges on content edit
# ---------------------------------------------------------------------------

def strip_automated_badges(html: str) -> str:
    """Remove all automated peer review elements from HTML.

    Strips: inline badges (verified/unverified), disclaimer banner,
    references section, and flag button. Preserves manual-verified badges.
    """
    if not html:
        return html
    # Remove inline badges: <a class="peer-review-badge verified"...>...</a>
    # and <span class="peer-review-badge unverified"...>...</span>
    html = re.sub(r'<a[^>]*class="peer-review-badge[^"]*"[^>]*>.*?</a>', '', html, flags=re.DOTALL)
    html = re.sub(r'<span[^>]*class="peer-review-badge[^"]*"[^>]*>.*?</span>', '', html, flags=re.DOTALL)
    # Remove disclaimer banner
    html = re.sub(r'<div[^>]*class="peer-review-disclaimer[^"]*"[^>]*>.*?</div>', '', html, flags=re.DOTALL)
    # Remove references section
    html = re.sub(r'<div[^>]*class="peer-review-references[^"]*"[^>]*>.*?</div>\s*</div>', '', html, flags=re.DOTALL)
    # Remove flag button
    html = re.sub(r'<button[^>]*class="[^"]*peer-review-flag[^"]*"[^>]*>.*?</button>', '', html, flags=re.DOTALL)
    # Clean up leftover whitespace
    html = re.sub(r'\n\s*\n\s*\n', '\n\n', html)
    return html.strip()
