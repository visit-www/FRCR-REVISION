"""
AI Protocol Helper Module

Provides clinical protocol search, AI-generated protocol content, and
curated source-traceable answers for on-call radiologists.
Mirrors ai_prelim.py patterns: Claude API call, error handling, response processing.

Architecture:
  1. User submits clinical query
  2. pg_trgm search matches against ClinicalProtocol table
  3. Matched protocol content injected as context into Claude system prompt
  4. Claude FORMATS (does not SOURCE) the answer
  5. Response returned with mandatory source citation + disclaimer
  6. Query + response logged to OnCallQueryLog (audit trail)

If no matching protocol found, system returns "No verified protocol found"
rather than generating from Claude's training data alone.
"""

import json
import os
import re
import logging
from datetime import datetime

import requests

from ai_client import AIClientError

logger = logging.getLogger(__name__)


class ProtocolHelperError(AIClientError):
    """Raised when protocol helper query or generation fails."""
    pass


# Backward-compatible alias
OnCallHelperError = ProtocolHelperError


# ==================== SYSTEM PROMPT ====================

SYSTEM_PROMPT = """You are a consultant radiologist answering an on-call clinical query.
You are part of a clinical decision support tool called RadInsight.

CRITICAL RULES:
1. Base your answer ONLY on the provided protocol data below. Do NOT use your training data to supplement clinical facts.
2. If the protocol data does not cover the question, say so explicitly: "The available protocols do not cover this specific query."
3. Format for quick reading — use bullet points, not paragraphs.
4. Always cite the source guideline at the end of your answer.
5. Include the guideline version/year when available.
6. Use clinical radiology language appropriate for a registrar/resident on call.
7. Prioritise actionable information: what to do, what to report, when to escalate.
8. If there are critical safety considerations, highlight them prominently.

OUTPUT FORMAT:
Return a JSON object with this structure:
{
  "answer_html": "<div class='oncall-answer'>Your formatted HTML answer here</div>",
  "summary": "One-line plain text summary of the answer",
  "citations": [{"source": "Guideline name", "version": "Year/version", "url": "optional URL"}],
  "confidence": "high|medium|low",
  "flags": ["any safety warnings or caveats"]
}

HTML FORMATTING RULES:
- Use <ul>/<li> for lists (not numbered unless order matters)
- Use <strong> for key values, thresholds, or critical findings
- Use <span class="text-danger fw-bold"> for red-flag items requiring urgent action
- Use <span class="text-warning fw-bold"> for caution items
- Use headings <h6> for subsections within the answer
- Keep answers concise — aim for screen-readable without scrolling
- Do NOT use markdown — output clean HTML only
"""


# ==================== PROTOCOL SEARCH ====================

def search_protocols(query_text, limit=5):
    """
    Search ClinicalProtocol table using pg_trgm similarity.
    Returns top matching published protocols.
    """
    from models import db, ClinicalProtocol
    from sqlalchemy import text

    if not query_text or not query_text.strip():
        return []

    query_text = query_text.strip()

    try:
        # Use pg_trgm similarity search against keywords and title
        sql = text("""
            SELECT id, title, category, keywords, source_citation, guideline_version,
                   similarity(keywords, :query) AS kw_sim,
                   similarity(title, :query) AS title_sim,
                   GREATEST(similarity(keywords, :query), similarity(title, :query)) AS best_sim
            FROM clinical_protocol
            WHERE is_published = TRUE
              AND (
                  similarity(keywords, :query) > 0.1
                  OR similarity(title, :query) > 0.15
                  OR keywords ILIKE :like_query
                  OR title ILIKE :like_query
              )
            ORDER BY best_sim DESC, title ASC
            LIMIT :limit
        """)

        results = db.session.execute(sql, {
            'query': query_text,
            'like_query': f'%{query_text}%',
            'limit': limit,
        }).fetchall()

        protocol_ids = [r.id for r in results]
        if not protocol_ids:
            return []

        # Fetch full protocol objects
        protocols = ClinicalProtocol.query.filter(
            ClinicalProtocol.id.in_(protocol_ids)
        ).all()

        # Maintain similarity ordering
        id_order = {pid: idx for idx, pid in enumerate(protocol_ids)}
        protocols.sort(key=lambda p: id_order.get(p.id, 999))

        return protocols

    except Exception as exc:
        logger.warning(f"pg_trgm search failed, falling back to ILIKE: {exc}")
        # Fallback: simple ILIKE search (works on SQLite too)
        return ClinicalProtocol.query.filter(
            ClinicalProtocol.is_published == True,
            db.or_(
                ClinicalProtocol.keywords.ilike(f'%{query_text}%'),
                ClinicalProtocol.title.ilike(f'%{query_text}%'),
            )
        ).limit(limit).all()


def search_protocols_autocomplete(query_text, limit=8):
    """
    Lightweight search for autocomplete suggestions.
    Returns protocol titles and categories without full content.
    """
    from models import db, ClinicalProtocol

    if not query_text or len(query_text.strip()) < 2:
        return []

    query_text = query_text.strip()

    try:
        from sqlalchemy import text
        sql = text("""
            SELECT id, title, category, source_citation,
                   GREATEST(similarity(keywords, :query), similarity(title, :query)) AS sim
            FROM clinical_protocol
            WHERE is_published = TRUE
              AND (
                  similarity(keywords, :query) > 0.1
                  OR similarity(title, :query) > 0.1
                  OR keywords ILIKE :like_query
                  OR title ILIKE :like_query
              )
            ORDER BY sim DESC
            LIMIT :limit
        """)
        results = db.session.execute(sql, {
            'query': query_text,
            'like_query': f'%{query_text}%',
            'limit': limit,
        }).fetchall()

        return [
            {'id': r.id, 'title': r.title, 'category': r.category, 'source': r.source_citation}
            for r in results
        ]
    except Exception:
        # Fallback for SQLite
        protocols = ClinicalProtocol.query.filter(
            ClinicalProtocol.is_published == True,
            db.or_(
                ClinicalProtocol.keywords.ilike(f'%{query_text}%'),
                ClinicalProtocol.title.ilike(f'%{query_text}%'),
            )
        ).limit(limit).all()
        return [
            {'id': p.id, 'title': p.title, 'category': p.category, 'source': p.source_citation}
            for p in protocols
        ]


# ==================== CONTEXT BUILDER ====================

def _build_protocol_context(protocols):
    """
    Build the protocol context block that gets injected into Claude's system prompt.
    Each protocol is formatted as a clearly delimited reference block.
    """
    if not protocols:
        return ""

    blocks = []
    for p in protocols:
        block = f"""
--- PROTOCOL: {p.title} ---
Category: {p.category}
Source: {p.source_citation}
Version: {p.guideline_version or 'Not specified'}
"""
        # Add structured content if available
        structured = p.get_content_structured()
        if structured:
            block += f"Structured Data:\n{json.dumps(structured, indent=2)}\n"

        # Add HTML content (strip tags for context, keep structure)
        if p.content_html:
            # Keep HTML as-is for Claude to interpret
            block += f"Reference Content:\n{p.content_html}\n"

        block += f"--- END PROTOCOL: {p.title} ---\n"
        blocks.append(block)

    return "\n".join(blocks)


# ==================== AI QUERY ====================

def generate_oncall_response(query_text, user_id, provider='claude', model=None):
    """
    Generate an on-call helper response for the given query.

    1. Search for matching protocols via pg_trgm
    2. If protocols found: inject as context, ask Claude to format
    3. If no protocols found: return "no verified protocol" message
    4. Log query + response to OnCallQueryLog

    Returns:
        dict with keys: answer_html, summary, citations, confidence, flags,
                        matched_protocols, model, response_source
    """
    from models import db, OnCallQueryLog

    api_key = os.getenv("CLAUDE_API_KEY")
    if not api_key:
        raise ProtocolHelperError("RadInsight Intelligence API key not configured.")

    effective_model = model or os.getenv("CLAUDE_MODEL", "claude-sonnet-4-20250514")

    # Step 1: Search for matching protocols
    matched_protocols = search_protocols(query_text, limit=5)
    matched_ids = [p.id for p in matched_protocols]

    # Step 2: Handle no-match case — DO NOT generate from training data
    if not matched_protocols:
        no_match_response = {
            'answer_html': (
                '<div class="oncall-answer">'
                '<div class="alert alert-warning">'
                '<i class="fas fa-exclamation-triangle me-2"></i>'
                '<strong>No verified protocol found</strong>'
                '</div>'
                '<p>No verified clinical protocol matches your query: '
                f'<em>"{query_text}"</em></p>'
                '<p>This tool only provides answers grounded in curated, verified protocols. '
                'Consider:</p>'
                '<ul>'
                '<li>Rephrasing your query with more specific clinical terms</li>'
                '<li>Consulting a senior colleague or published guidelines directly</li>'
                '<li>Requesting that an admin add this protocol to the knowledge base</li>'
                '</ul>'
                '</div>'
            ),
            'summary': 'No verified protocol found for this query.',
            'citations': [],
            'confidence': 'none',
            'flags': ['No matching protocol in knowledge base — answer NOT generated from AI training data.'],
            'matched_protocols': [],
            'model': None,
            'response_source': 'no_match',
        }

        # Log the no-match query
        log_entry = OnCallQueryLog(
            user_id=user_id,
            query_text=query_text,
            matched_protocol_ids=json.dumps([]),
            ai_response_text=no_match_response['answer_html'],
            model_used=None,
            token_count=0,
            response_source='no_match',
        )
        db.session.add(log_entry)
        db.session.commit()

        return no_match_response

    # Step 3: Build context from matched protocols
    protocol_context = _build_protocol_context(matched_protocols)

    # Build the full system prompt with protocol data
    system_with_context = SYSTEM_PROMPT + f"""

AVAILABLE PROTOCOL DATA:
{protocol_context}

Remember: Answer ONLY based on the protocol data above. If the user's question
goes beyond what the protocols cover, say so explicitly.
"""

    user_prompt = f"""Clinical on-call query: "{query_text}"

Based on the protocol data provided in the system prompt, provide a concise,
actionable answer formatted for a radiologist on call. Include source citations."""

    # Step 4: Call Claude API (mirrors ai_prelim.py pattern)
    payload = {
        "model": effective_model,
        "max_tokens": 4000,
        "temperature": 0.2,
        "system": system_with_context,
        "messages": [
            {"role": "user", "content": user_prompt}
        ],
    }

    try:
        response = requests.post(
            "https://api.anthropic.com/v1/messages",
            headers={
                "Content-Type": "application/json",
                "x-api-key": api_key,
                "anthropic-version": "2023-06-01",
            },
            json=payload,
            timeout=90,
        )
    except requests.exceptions.Timeout:
        raise ProtocolHelperError("RadInsight Intelligence request timed out. Please try again.")
    except requests.exceptions.RequestException as exc:
        raise ProtocolHelperError(f"Failed to connect to RadInsight Intelligence: {exc}")

    if response.status_code >= 300:
        detail = response.text[:500]
        raise ProtocolHelperError(f"RadInsight Intelligence error (HTTP {response.status_code}): {detail}")

    result = response.json()
    content = result.get("content", [])
    if not content:
        raise ProtocolHelperError("Empty response from RadInsight Intelligence.")

    text = content[0].get("text", "")
    if not text:
        raise ProtocolHelperError("No text in RadInsight Intelligence response.")

    token_count = result.get("usage", {}).get("output_tokens", 0)

    # Step 5: Parse JSON response
    parsed = _parse_response(text)

    # Inject matched protocol info
    parsed['matched_protocols'] = [
        {'id': p.id, 'title': p.title, 'category': p.category, 'source': p.source_citation}
        for p in matched_protocols
    ]
    parsed['model'] = effective_model
    parsed['response_source'] = 'protocol'

    # Step 6: Log to audit trail
    log_entry = OnCallQueryLog(
        user_id=user_id,
        query_text=query_text,
        matched_protocol_ids=json.dumps(matched_ids),
        ai_response_text=parsed.get('answer_html', ''),
        model_used=effective_model,
        token_count=token_count,
        response_source='protocol',
    )
    db.session.add(log_entry)
    db.session.commit()

    return parsed


def _parse_response(text):
    """Parse Claude's JSON response with fallback handling."""
    # Strip markdown code fences
    if text.strip().startswith("```"):
        lines = text.strip().split("\n")
        if lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        text = "\n".join(lines)

    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        # Fallback: regex extraction
        match = re.search(r'\{[\s\S]*\}', text)
        if match:
            try:
                parsed = json.loads(match.group())
            except json.JSONDecodeError:
                parsed = _fallback_response(text)
        else:
            parsed = _fallback_response(text)

    # Validate and ensure required fields
    parsed.setdefault('answer_html', '<p>Unable to format response.</p>')
    parsed.setdefault('summary', '')
    parsed.setdefault('citations', [])
    parsed.setdefault('confidence', 'medium')
    parsed.setdefault('flags', [])

    # Validate citations structure
    valid_citations = []
    for c in parsed.get('citations', []):
        if isinstance(c, dict) and 'source' in c:
            valid_citations.append({
                'source': c.get('source', ''),
                'version': c.get('version', ''),
                'url': c.get('url', ''),
            })
    parsed['citations'] = valid_citations

    return parsed


def _fallback_response(text):
    """Create a structured response from unstructured text."""
    return {
        'answer_html': f'<div class="oncall-answer"><p>{text}</p></div>',
        'summary': text[:200] if text else 'Response received.',
        'citations': [],
        'confidence': 'low',
        'flags': ['AI-supplemented — verify independently. Response could not be parsed into structured format.'],
    }


# ==================== QUERY HISTORY ====================

def get_query_history(user_id, limit=20):
    """Get recent on-call queries for a user."""
    from models import OnCallQueryLog

    return OnCallQueryLog.query.filter_by(
        user_id=user_id
    ).order_by(
        OnCallQueryLog.created_at.desc()
    ).limit(limit).all()


# ==================== PROTOCOL AI GENERATION ====================

PROTOCOL_GENERATION_PROMPT = """You are an expert consultant radiologist and clinical guideline editor.

Your task is to generate a quick-reference protocol card — the kind a radiologist pins to their
workstation or pulls up mid-report. This is NOT a textbook chapter or review article.

This protocol will be reviewed by a human admin before publication. If any uncertainty exists,
you MUST explicitly flag it.

INPUTS:
<title>{title}</title>
<category>{category}</category>
<source_citation>{source_citation}</source_citation>
<additional_context>{additional_context}</additional_context>

Category is one of: acute_emergency, diagnostic_algorithms, interventional, pre_procedural,
intra_procedural, post_procedural, contrast_safety, mri_safety, radiation_protection,
special_populations, medication_risk, adverse_events.

OUTPUT FORMAT (STRICT — valid JSON only, no markdown, no text outside JSON):
{{
  "content_html": "...",
  "content_structured": {{ ... }},
  "suggested_keywords": [],
  "guideline_version": "",
  "warnings": []
}}

CONTENT PRINCIPLES:
1. Clinical Accuracy First
   - Use widely accepted, peer-reviewed standards
   - Prefer international consensus systems (AAST, AJCC, Balthazar, Bosniak, LI-RADS, PI-RADS, etc.)
   - Do NOT invent cutoffs, thresholds, or criteria
   - If uncertain about a specific numerical threshold, append [verify] next to the value
   - If the title implies a specific version (e.g. AAST 2018), generate for that version only — do NOT merge multiple versions
   - If a newer version of this system exists, state in warnings which version you generated and that a newer one exists

2. Radiologist-Centric — No Filler
   - Focus on what is seen on imaging and how it affects the report
   - Do NOT include: history of the classification, epidemiology statistics, detailed pathophysiology, or literature review
   - Every grading/scoring row must answer "so what?" — include management implication
   - Explain why the grading matters for the report

3. Fast Cognitive Access
   - Tables over paragraphs where possible
   - Clear thresholds, unambiguous criteria
   - Minimal prose, maximum signal
   - Scale depth to complexity — simple protocols get concise output, multi-grade systems get full tables

4. Conceptual Understanding
   - Every grading/scoring system must include: what it measures, when to use it, how it influences management
   - Do NOT include a "why this is important" preamble — go straight to actionable content

5. No Overreach
   - This is a reference aid, not a treatment mandate
   - Use cautious language where appropriate

content_structured SCHEMA:
{{
  "overview": {{
    "clinical_context": "Brief clinical scenario where this protocol applies",
    "imaging_role": "What imaging modality and why",
    "when_to_use": "Specific situation where a radiologist would look this up"
  }},
  "grading_or_scoring_systems": [
    {{
      "name": "System name",
      "applies_to": "What condition/organ",
      "imaging_modality": ["CT", "MRI", etc.],
      "parameters": [
        {{
          "feature": "Finding name",
          "imaging_criteria": "Specific criteria WITHIN this grade (e.g. 'laceration >3cm')",
          "score_or_grade": "Grade/score value (numeric or categorical)",
          "management_implication": "What this grade means for patient management",
          "notes": "Optional qualifier"
        }}
      ],
      "interpretation": "How to read the overall score/grade",
      "clinical_implication": "What changes in management based on result"
    }}
  ],
  "key_imaging_features": ["General imaging features of the condition regardless of grade"],
  "reporting_recommendations": [
    {{
      "recommendation": "What to include in the report",
      "priority": "must_report | should_mention | consider_including"
    }}
  ],
  "common_pitfalls": ["Practical traps, mimics, overcalls"],
  "when_to_escalate_or_flag": ["Red flags requiring urgent action"]
}}

Note: key_imaging_features are GENERAL features of the condition. parameters.imaging_criteria are
SPECIFIC criteria within each grade/score level.

content_html REQUIREMENTS:
Use ONLY these CSS classes (pre-defined in the app):
- <div class="diagnosis-box"> — for protocol title/summary box
- <div class="key-finding"> — green border for key imaging findings
- <div class="staging-info"> — grey border for grading/staging tables
- <div class="clinical-note"> — teal border for clinical context
- <div class="pitfall"> — red border for pitfalls/traps
- <div class="teaching-pearl"> — amber border for practical tips
- <div class="image-finding"> — orange border for specific imaging features
- <span class="measurement"> — monospace for measurements/values
- <span class="anatomy-label"> — teal pill badge for anatomical structures
- <span class="important-text"> — bold red for critical items
- <table class="table table-sm table-bordered"> — for all grading/scoring tables

Structure:
1. <div class="diagnosis-box"> with protocol title and one-line summary
2. <div class="staging-info"> with grading/scoring table(s) — must include management column
3. <div class="key-finding"> for key imaging features to report
4. <div class="pitfall"> for common traps and mimics
5. <div class="clinical-note"> for when-to-escalate items

Do NOT include: <html>, <head>, <body> tags, inline styles, markdown, or any CSS class not listed above.

suggested_keywords:
8-15 concise terms a radiologist would type when searching for this protocol. Include: modality,
organ, condition name, grading system name, common synonyms, emergency flags.

guideline_version:
Specific version/year. Examples: "AJCC 8th Edition", "Revised Atlanta Classification (2012)".
If unclear, say "Not explicitly versioned".

warnings (populate when applicable):
- Evidence is evolving or contested
- Multiple versions exist
- Protocol is not standalone (requires clinical context)
- Borderline cases need MDT correlation
- Modality-specific limitations exist
If none needed, return empty array.

QUALITY CHECK — verify before responding:
- Is this safe to use as a draft reference?
- Would a radiologist trust it during reporting?
- Are grading tables precise with unambiguous criteria?
- Does every grade row have a management implication?
- Are limitations clearly stated?
- Is there any filler or textbook content? (Remove it)
If any answer is no, revise before output."""


def _format_resources_for_prompt(resources_json):
    """Parse unified resources JSON, fetch URL content, extract PDF text,
    and format for AI prompt context with preference instruction."""
    if not resources_json or not resources_json.strip():
        return 'Not specified'

    try:
        parsed = json.loads(resources_json)
    except (json.JSONDecodeError, TypeError):
        return resources_json.strip() or 'Not specified'

    if isinstance(parsed, str):
        return parsed

    if not isinstance(parsed, dict):
        return 'Not specified'

    sections = []

    # References — fetch URL content where available
    refs = parsed.get('references', [])
    if refs:
        ref_lines = []
        for i, ref in enumerate(refs, 1):
            line = f"  {i}. {ref.get('source', 'Unknown')}"
            if ref.get('version'):
                line += f" ({ref['version']})"
            if ref.get('url'):
                line += f" — {ref['url']}"
                try:
                    from clinical_tool_generator import fetch_url_content
                    fetched = fetch_url_content(ref['url'])
                    if fetched:
                        line += f"\n     Content:\n     {fetched[:4000]}"
                except Exception as exc:
                    logger.warning("Failed to fetch URL %s: %s", ref['url'], exc)
            ref_lines.append(line)
        if ref_lines:
            sections.append("REFERENCES:\n" + "\n".join(ref_lines))

    # Linked cases
    cases = parsed.get('linked_cases', [])
    if cases:
        case_lines = [f"  - Case {c.get('case_number', '')}: {c.get('diagnosis', '')}"
                      for c in cases if isinstance(c, dict)]
        if case_lines:
            sections.append("LINKED CASES:\n" + "\n".join(case_lines))

    # Linked TNM calculators
    tnm = parsed.get('linked_tnm', [])
    if tnm:
        tnm_lines = [f"  - {t.get('cancer_name', t.get('slug', ''))}"
                     for t in tnm if isinstance(t, dict)]
        if tnm_lines:
            sections.append("LINKED TNM CALCULATORS:\n" + "\n".join(tnm_lines))

    # PDFs — download from Cloudinary and extract text
    pdfs = parsed.get('pdfs', [])
    if pdfs:
        pdf_parts = []
        for pdf in pdfs:
            if not isinstance(pdf, dict) or not pdf.get('url'):
                continue
            pdf_name = pdf.get('name', 'uploaded document')
            try:
                import tempfile
                from clinical_tool_generator import extract_pdf_text
                resp = requests.get(pdf['url'], timeout=15)
                resp.raise_for_status()
                tmp = tempfile.NamedTemporaryFile(delete=False, suffix='.pdf')
                tmp.write(resp.content)
                tmp.close()
                text = extract_pdf_text(tmp.name)
                try:
                    os.unlink(tmp.name)
                except Exception:
                    pass
                if text:
                    pdf_parts.append(f"  [PDF: {pdf_name}]\n  {text[:6000]}")
                else:
                    pdf_parts.append(f"  [PDF: {pdf_name}] (text extraction unavailable)")
            except Exception as exc:
                logger.warning("Failed to extract PDF text from %s: %s", pdf_name, exc)
                pdf_parts.append(f"  [PDF: {pdf_name}] (download/extraction failed)")
        if pdf_parts:
            sections.append("REFERENCE PDFs:\n" + "\n\n".join(pdf_parts))

    if not sections:
        return 'Not specified'

    return (
        "\n\n=== REFERENCE MATERIALS ===\n"
        "Use the following references to ground your output in evidence. "
        "Where references conflict with general knowledge, prefer the references. "
        "However, also draw on your broader medical knowledge — do not limit "
        "your response exclusively to these references.\n\n"
        + "\n\n".join(sections)
        + "\n=== END REFERENCES ===\n"
    )


def generate_protocol_content(title, category, source_citation='', additional_context=''):
    """
    Generate structured clinical protocol content using Claude API.

    Returns dict with: content_html, content_structured, suggested_keywords,
    guideline_version, warnings. Does NOT save to DB.
    """
    api_key = os.getenv("CLAUDE_API_KEY")
    if not api_key:
        raise ProtocolHelperError("RadInsight Intelligence API key not configured.")

    effective_model = os.getenv("CLAUDE_MODEL", "claude-sonnet-4-20250514")

    formatted_resources = _format_resources_for_prompt(source_citation)

    user_prompt = PROTOCOL_GENERATION_PROMPT.format(
        title=title,
        category=category,
        source_citation=formatted_resources,
        additional_context=additional_context or 'None',
    )

    payload = {
        "model": effective_model,
        "max_tokens": 4000,
        "temperature": 0.2,
        "system": (
            "You are a clinical protocol generator for a radiology decision support app. "
            "When reference materials are provided, use them as your primary source of truth "
            "and cite specific details where relevant. Also draw on your broader medical "
            "knowledge to fill gaps — do not limit your output exclusively to the references. "
            "Output valid JSON only. No markdown. No text outside the JSON object."
        ),
        "messages": [
            {"role": "user", "content": user_prompt}
        ],
    }

    try:
        response = requests.post(
            "https://api.anthropic.com/v1/messages",
            headers={
                "Content-Type": "application/json",
                "x-api-key": api_key,
                "anthropic-version": "2023-06-01",
            },
            json=payload,
            timeout=120,
        )
    except requests.exceptions.Timeout:
        raise ProtocolHelperError("Protocol generation timed out. Please try again.")
    except requests.exceptions.RequestException as exc:
        raise ProtocolHelperError(f"Failed to connect to RadInsight Intelligence: {exc}")

    if response.status_code >= 300:
        detail = response.text[:500]
        raise ProtocolHelperError(f"RadInsight Intelligence error (HTTP {response.status_code}): {detail}")

    result = response.json()
    content = result.get("content", [])
    if not content:
        raise ProtocolHelperError("Empty response from RadInsight Intelligence.")

    text = content[0].get("text", "")
    if not text:
        raise ProtocolHelperError("No text in RadInsight Intelligence response.")

    # Parse JSON response
    parsed = _parse_protocol_response(text)

    parsed['model'] = effective_model
    parsed['token_count'] = result.get("usage", {}).get("output_tokens", 0)

    return parsed


def _parse_protocol_response(text):
    """Parse protocol generation JSON response with fallback."""
    # Strip markdown code fences
    if text.strip().startswith("```"):
        lines = text.strip().split("\n")
        if lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        text = "\n".join(lines)

    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        match = re.search(r'\{[\s\S]*\}', text)
        if match:
            try:
                parsed = json.loads(match.group())
            except json.JSONDecodeError:
                raise ProtocolHelperError("Failed to parse protocol generation response as JSON.")
        else:
            raise ProtocolHelperError("Protocol generation response was not valid JSON.")

    # Validate required fields
    parsed.setdefault('content_html', '')
    parsed.setdefault('content_structured', {})
    parsed.setdefault('suggested_keywords', [])
    parsed.setdefault('guideline_version', '')
    parsed.setdefault('warnings', [])

    # Ensure content_structured is a dict (not a string)
    if isinstance(parsed['content_structured'], str):
        try:
            parsed['content_structured'] = json.loads(parsed['content_structured'])
        except (json.JSONDecodeError, TypeError):
            parsed['content_structured'] = {}

    # Ensure suggested_keywords is a list of strings
    if not isinstance(parsed['suggested_keywords'], list):
        parsed['suggested_keywords'] = []
    parsed['suggested_keywords'] = [str(k) for k in parsed['suggested_keywords'] if k]

    return parsed
