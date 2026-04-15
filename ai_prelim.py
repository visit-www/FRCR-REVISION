"""
AI Preliminary Case Data Generator

This module provides the Claude API integration for generating FRCR-relevant
preliminary case data. Uses the detailed prompt structure from AI_INTEGRATION_REFERENCE.md.

Prompt Version: v2
Last Updated: January 2026
"""

import json
import os
from datetime import datetime

import requests

from ai_client import AIClientError


class AiPrelimError(AIClientError):
    """Raised when AI generation fails."""
    pass


# ============================================================================
# PROMPT TEMPLATES (v2 - from AI_INTEGRATION_REFERENCE.md)
# ============================================================================

SYSTEM_PROMPT = """You are a clinical radiology knowledge engine designed to help radiologists prepare, report, and teach from real clinical cases.
Your output must be clinically safe, FRCR-relevant, and radiology-focused.

You are given structured case data.
Your job is to generate high-yield preliminary case material that helps determine whether a candidate is safe to report independently.

CRITICAL RULES:
- Do NOT invent or hallucinate facts
- If you are not certain about something, omit it and add a warning
- Use the diagnosis as the anchor concept - do not replace or rephrase it
- Be concise but clinically powerful
- Prioritize safety, management-changing features, and anatomical danger points

This is NOT a textbook.
This is radiology survival knowledge.

Output JSON only. No markdown fences. No explanations outside the JSON structure."""


def _build_user_prompt(case_context):
    """Build the detailed user prompt from case context."""
    diagnosis = case_context.get("diagnosis", "").strip()
    modality = case_context.get("modality", "").strip()
    module = case_context.get("module", "").strip()
    body_part = case_context.get("body_part", "").strip()
    notes = case_context.get("notes", "").strip()
    existing_content = case_context.get("existing_summary", "").strip()
    
    additional_context = case_context.get("additional_context", "").strip()

    # Build input section
    input_section = f"""INPUT
═══════════════════════════════════════════════════════════════════

Case Diagnosis: {diagnosis if diagnosis else 'NOT PROVIDED'}
Modality: {modality if modality else 'Not specified'}
Module: {module if module else 'Not specified'}
Body Part: {body_part if body_part else 'Not specified'}
Notes: {notes if notes else 'None'}
Existing Content: {existing_content[:500] + '...' if len(existing_content) > 500 else existing_content if existing_content else 'None'}"""

    if additional_context:
        input_section += (
            f"\n\n=== ADDITIONAL CONTEXT PROVIDED BY USER ===\n"
            f"{additional_context}\n"
            f"=== END CONTEXT ===\n\n"
            f"Use the above as preferred references to enrich and ground your output. "
            f"Cite specific details from these sources where relevant, but also draw on "
            f"your broader medical knowledge — do not limit your response exclusively to "
            f"these references."
        )

    # Diagnosis handling instruction
    diagnosis_handling = """
═══════════════════════════════════════════════════════════════════
STEP 1 — DIAGNOSIS HANDLING
═══════════════════════════════════════════════════════════════════

If Case Diagnosis is 'NOT PROVIDED', return ONLY:
{
  "error": "Please enter the working radiological diagnosis before I can generate preliminary case data.",
  "qa_pairs": [],
  "discussion": "",
  "safety_checklist": [],
  "sources": [],
  "warnings": ["Diagnosis is required"]
}

If diagnosis exists:
• Use it as the anchor concept
• Do not rephrase or replace it
• Do not invent a new diagnosis"""

    # Output structure instruction
    output_structure = """
═══════════════════════════════════════════════════════════════════
OUTPUT STRUCTURE
═══════════════════════════════════════════════════════════════════

Return valid JSON with this exact structure:

{
  "qa_pairs": [
    {"question": "...", "answer": "..."}
  ],
  "discussion": {
    "diagnosis_summary": "Brief 1-2 sentence overview anchored to imaging.",
    "sections": [
      {
        "type": "key_findings|dangerous_anatomy|differentials|pitfalls|teaching_points|staging|classification|imaging_approach|complications|management_impact|anatomy|key_image|custom",
        "title": "Section heading (use your own if type is custom)",
        "content": "string OR array of strings OR array of objects — whatever fits the content best"
      }
    ]
  },
  "safety_checklist": ["..."],
  "sources": [
    {"title": "...", "url": "...", "pmid": "..."}
  ],
  "image_captions": [
    "Brief clinical description of the key imaging finding for this diagnosis (1-2 sentences). Describe the specific imaging appearance, modality, and diagnostic significance. Provide 1-3 captions."
  ],
  "warnings": ["..."]
}

IMPORTANT: The "discussion" field is a STRUCTURED OBJECT with a required "diagnosis_summary" string and a "sections" array.
Each section has a "type", "title", and "content" — you decide which sections are relevant.
Do NOT include teaching_image or anatomy_image fields.
The "image_captions" array should contain 1-3 brief descriptions of what key reference images for this diagnosis would show — these will be paired with automatically-fetched Radiopaedia images."""

    # Section 1: Q&A pairs
    qa_section = """
───────────────────────────────────────────────────────────────────
1) qa_pairs — HIGH-YIELD QUESTION & ANSWER PAIRS
───────────────────────────────────────────────────────────────────

Create 5-8 clinically realistic FRCR-style viva questions that test:
• Is this diagnosis life-threatening?
• What must not be missed?
• What changes management?
• What findings make this unsafe to ignore?
• What should be reported urgently?

Rules:
• Each question must be something a consultant would ask in real reporting
• Each answer must be short (1-3 sentences), precise, and clinically actionable
• Avoid trivia
• Prefer "what changes management" over rare facts
• Focus on imaging findings and their clinical significance"""

    # Section 2: Discussion
    discussion_section = """
───────────────────────────────────────────────────────────────────
2) discussion — RADIOLOGIST'S HIGH-YIELD NOTES (FLEXIBLE STRUCTURED JSON)
───────────────────────────────────────────────────────────────────

The discussion field is a JSON object with two parts:

"diagnosis_summary": (string, required)
  A punchy 1-3 sentence overview anchored to imaging. Set the scene — what is this,
  why does it matter, and what should a radiologist know before reading further.

"sections": (array of objects)
  YOU DECIDE which sections are relevant to this diagnosis. Each section is:
  {
    "type": "<one of the types below or 'custom'>",
    "title": "<your own heading — be specific to the diagnosis, not generic>",
    "content": <string, array of strings, or array of objects — whatever fits best>
  }

AVAILABLE SECTION TYPES (use what's relevant, skip what's not, add custom):

  "key_findings" — What you see on imaging. Content: array of objects
    [{"finding": "...", "description": "...", "measurement": "size/threshold or null"}]

  "dangerous_anatomy" — Critical structures at risk. Content: array of strings.

  "differentials" — How to tell this apart from mimics. Content: array of objects
    [{"name": "...", "distinguishing_feature": "..."}]

  "pitfalls" — What gets missed, what harms patients. Content: array of strings.

  "teaching_points" — Memorable facts, FRCR pearls. Content: array of strings.

  "staging" — Only for conditions with formal staging/grading. Content: object
    {"system": "...", "stages": [{"stage": "T1", "description": "...", "management": "..."}], "key_stages": "..."}

  "classification" — Named classification systems (e.g., Bosniak, LI-RADS, BI-RADS, Todani).
    Content: object with "system" and "grades" or description.

  "imaging_approach" — How to systematically read this study. Content: array of strings.

  "complications" — What can go wrong, what to look for on follow-up. Content: array of strings.

  "management_impact" — How imaging findings change clinical decisions. Content: array of strings.

  "anatomy" — Relevant anatomy for reporting. Content: array of strings.

  "key_image" — What the classic image looks like. Content: object
    {"modality": "...", "appearance": "...", "search_term": "..."}

  "custom" — Anything else that matters for this diagnosis. Use your own title.
    Content: string or array of strings.

GUIDELINES:
  • Aim for 4-8 sections — enough depth, not padding
  • Write titles specific to the diagnosis (e.g., "Bosniak Classification" not "Classification")
  • Be creative — if this diagnosis has a unique feature (e.g., a named sign, a classic
    triad, a measurement threshold), give it its own section
  • Include specific measurements, thresholds, and criteria where they exist
  • Each section should be self-contained
  • Plain text only in all fields — NO HTML tags, NO markdown
  • Prioritise what changes management over encyclopaedic completeness"""

    # Section 3: Safety checklist
    safety_section = """
───────────────────────────────────────────────────────────────────
3) safety_checklist — CLINICO-RADIOLOGICAL SAFETY FOCUS
───────────────────────────────────────────────────────────────────

Provide 4-8 bullet points explicitly stating:
• What makes this diagnosis dangerous
• What imaging features mean urgent action is needed
• What a junior radiologist must not miss
• What leads to legal or clinical harm if omitted from the report

This section answers: "Is the candidate safe to report this independently?"

Each item should be a complete, actionable statement."""

    # Section 4: Sources
    sources_section = """
───────────────────────────────────────────────────────────────────
4) sources — REFERENCES
───────────────────────────────────────────────────────────────────

Provide exactly 1-3 high-quality references. Each source object must have:
• "title" — the exact article title (required)
• "journal" — the journal or website name (required)
• "url" — leave as EMPTY STRING for ALL sources (URLs are auto-resolved)

RULES:
• Include exactly 1 Radiopaedia article — provide the exact article title and set journal to "Radiopaedia". Do NOT generate a URL.
• Include 1-2 journal articles from: Radiographics, AJR, AJNR, European Radiology, RadioGraphics, RadiologyAssistant
• PREFER pictorial essays, case reviews, and teaching articles
• The article title must be the REAL, EXACT title of a published article — do NOT invent titles
• Do NOT generate ANY URLs — all URLs will be auto-resolved from titles. Set url to ""
• Do NOT include pmid, pdf_url, or doi fields"""

    # Section 5: Warnings
    warnings_section = """
───────────────────────────────────────────────────────────────────
5) warnings — IMPORTANT CAVEATS
───────────────────────────────────────────────────────────────────

Include any warnings about:
• Information you were unsure about
• Areas where local protocols may vary
• Aspects that require senior review
• Limitations of the generated content

If no warnings, use empty array []"""

    # Quality bar
    quality_bar = """
═══════════════════════════════════════════════════════════════════
QUALITY BAR
═══════════════════════════════════════════════════════════════════

Your output should feel like:

A senior radiologist writing high-yield exam notes + safety checklist
for a trainee about to report this case alone.

If something is not relevant to reporting, do not include it.
Keep everything clinically relevant, radiology-focused, and easy to retain."""

    # Combine all sections
    full_prompt = "\n".join([
        input_section,
        diagnosis_handling,
        output_structure,
        qa_section,
        discussion_section,
        safety_section,
        sources_section,
        warnings_section,
        quality_bar
    ])
    
    return full_prompt


def _build_prompt(case_context):
    """Build system and user prompts for Claude API call."""
    return SYSTEM_PROMPT, _build_user_prompt(case_context)


def generate_prelim_case_data(case_context, provider="claude", model=None):
    """
    Generate preliminary case data using the specified AI provider.

    Args:
        case_context: dict with keys:
            - diagnosis (required)
            - modality (optional)
            - module (optional)
            - body_part (optional)
            - notes (optional)
            - existing_summary (optional)
        provider: str, currently only "claude" is supported
        model: str, Claude model to use (defaults to env CLAUDE_MODEL or sonnet)

    Returns:
        dict with keys:
            - provider
            - model
            - prompt_version
            - generated_at
            - output (the parsed JSON response)
            - raw_response

    Raises:
        AiPrelimError: If generation fails
    """
    if provider != "claude":
        raise AiPrelimError(f"Unsupported provider: {provider}")

    api_key = os.getenv("CLAUDE_API_KEY")
    if not api_key:
        raise AiPrelimError("CLAUDE_API_KEY is not configured. Please set this environment variable.")

    system_prompt, user_prompt = _build_prompt(case_context)
    # Use provided model or fall back to environment/default
    if model is None:
        model = os.getenv("CLAUDE_MODEL", "claude-sonnet-4-6")

    # Prepend shared ABC preamble for consistency with ai_client.py
    from ai_client import ABC_PREAMBLE
    effective_system = ABC_PREAMBLE + system_prompt

    payload = {
        "model": model,
        "max_tokens": 12000,  # Flexible sections format needs more room than rigid fields
        "temperature": 0.3,  # Slightly higher for more natural language
        "system": effective_system,
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
            data=json.dumps(payload),
            timeout=180,  # Generous timeout for flexible structured responses
        )
    except requests.exceptions.Timeout:
        raise AiPrelimError("RadInsights Intelligence request timed out. Please try again.")
    except requests.exceptions.RequestException as exc:
        raise AiPrelimError(f"Failed to connect to RadInsights Intelligence: {exc}")

    if response.status_code >= 300:
        error_detail = response.text[:500] if response.text else "No details"
        raise AiPrelimError(
            f"RadInsights Intelligence error (HTTP {response.status_code}): {error_detail}"
        )

    data = response.json()
    usage = data.get("usage", {})
    content = data.get("content", [])
    if not content:
        raise AiPrelimError("RadInsights Intelligence response missing content block")

    text = content[0].get("text", "").strip()
    if not text:
        raise AiPrelimError("RadInsights Intelligence response was empty")

    # Clean up potential markdown fences
    if text.startswith("```"):
        lines = text.split("\n")
        # Remove first line (```json or ```)
        lines = lines[1:]
        # Remove last line if it's ```
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        text = "\n".join(lines)

    try:
        parsed = json.loads(text)
    except json.JSONDecodeError as exc:
        # Try to extract JSON from the response
        import re
        json_match = re.search(r'\{[\s\S]*\}', text)
        if json_match:
            try:
                parsed = json.loads(json_match.group())
            except json.JSONDecodeError:
                raise AiPrelimError(
                    f"RadInsights Intelligence response was not valid JSON: {exc}. "
                    f"Response preview: {text[:200]}..."
                ) from exc
        else:
            raise AiPrelimError(
                f"RadInsights Intelligence response was not valid JSON: {exc}. "
                f"Response preview: {text[:200]}..."
            ) from exc

    # Check for error response (diagnosis missing)
    if parsed.get("error"):
        raise AiPrelimError(parsed["error"])

    # Ensure all expected fields exist with defaults
    parsed.setdefault("qa_pairs", [])
    parsed.setdefault("discussion", "")
    parsed.setdefault("safety_checklist", [])
    parsed.setdefault("teaching_image", {})
    parsed.setdefault("anatomy_image", {})  # Optional field - may be empty
    parsed.setdefault("sources", [])
    parsed.setdefault("image_captions", [])
    parsed.setdefault("warnings", [])
    
    # Process sources: keep Radiopaedia URLs, generate Google Scholar search links for others
    if isinstance(parsed.get("sources"), list):
        from urllib.parse import quote_plus

        processed_sources = []
        for source in parsed["sources"]:
            if not isinstance(source, dict):
                continue
            title = source.get("title", "").strip()
            if not title:
                continue
            url = source.get("url", "").strip()
            journal = source.get("journal", "").strip()

            # Radiopaedia: keep URL (fix protocol if needed)
            if url and "radiopaedia.org" in url.lower():
                if url.startswith("http://"):
                    url = url.replace("http://", "https://", 1)
                elif not url.startswith("https://"):
                    url = f"https://{url}"
                source["url"] = url
            elif url and "radiologyassistant.nl" in url.lower():
                # RadiologyAssistant also has predictable URLs — keep them
                if url.startswith("http://"):
                    url = url.replace("http://", "https://", 1)
                elif not url.startswith("https://"):
                    url = f"https://{url}"
                source["url"] = url
            else:
                # All other sources: generate Google Scholar search link from title
                search_query = title
                if journal:
                    search_query = f"{title} {journal}"
                source["url"] = f"https://scholar.google.com/scholar?q={quote_plus(search_query)}"
                # Remove any hallucinated fields
                source.pop("pmid", None)
                source.pop("pdf_url", None)
                source.pop("doi", None)

            processed_sources.append(source)

        # Limit to 3 sources max
        parsed["sources"] = processed_sources[:3]

    # Validate qa_pairs structure
    validated_pairs = []
    for pair in parsed.get("qa_pairs", []):
        if isinstance(pair, dict):
            q = pair.get("question", "").strip()
            a = pair.get("answer", "").strip()
            if q or a:
                validated_pairs.append({"question": q, "answer": a})
    parsed["qa_pairs"] = validated_pairs

    # Validate safety_checklist
    if isinstance(parsed.get("safety_checklist"), list):
        parsed["safety_checklist"] = [
            item.strip() for item in parsed["safety_checklist"]
            if isinstance(item, str) and item.strip()
        ]
    
    # =========================================================================
    # TNM INTELLIGENCE ENHANCEMENT (uses internal AJCC database)
    # =========================================================================
    # Check if oncologic diagnosis (for metadata only - no link injection)
    # TNM intelligence is generated separately via ai_tnm.py when user requests it.
    
    diagnosis = case_context.get("diagnosis", "").strip()
    parsed["tnm_metadata"] = None
    
    if diagnosis:
        try:
            from ai_tnm import is_oncologic_diagnosis
            
            if is_oncologic_diagnosis(diagnosis):
                parsed["tnm_metadata"] = {"is_oncologic": True}
                    
        except ImportError:
            pass  # ai_tnm not available, skip
        except Exception:
            pass  # Don't break the flow for metadata

    return {
        "provider": provider,
        "model": model,
        "prompt_version": "v2",
        "generated_at": datetime.utcnow().isoformat(),
        "output": parsed,
        "raw_response": text,
        "usage": {
            "input_tokens": usage.get("input_tokens", 0),
            "output_tokens": usage.get("output_tokens", 0),
        },
    }


# ============================================================================
# FUTURE: Alternative Providers (PubMed, Semantic Scholar)
# ============================================================================
# 
# When Consensus API is unavailable, these can be used for evidence retrieval:
#
# def search_pubmed(query, max_results=10):
#     """
#     Search PubMed E-utilities for relevant papers.
#     API Docs: https://www.ncbi.nlm.nih.gov/books/NBK25501/
#     """
#     # TODO: Implement when needed
#     pass
#
# def search_semantic_scholar(query, max_results=10):
#     """
#     Search Semantic Scholar API for relevant papers.
#     API Docs: https://api.semanticscholar.org/
#     """
#     # TODO: Implement when needed
#     pass
