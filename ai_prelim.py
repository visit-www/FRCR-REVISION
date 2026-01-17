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


class AiPrelimError(Exception):
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
    
    # Build input section
    input_section = f"""INPUT
═══════════════════════════════════════════════════════════════════

Case Diagnosis: {diagnosis if diagnosis else 'NOT PROVIDED'}
Modality: {modality if modality else 'Not specified'}
Module: {module if module else 'Not specified'}
Body Part: {body_part if body_part else 'Not specified'}
Notes: {notes if notes else 'None'}
Existing Content: {existing_content[:500] + '...' if len(existing_content) > 500 else existing_content if existing_content else 'None'}"""

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
  "teaching_image": {},
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
  "discussion": "...",
  "safety_checklist": ["..."],
  "teaching_image": {
    "title": "...",
    "link": "...",
    "description": "...",
    "teaching_point": "...",
    "source": "..."
  },
  "sources": [
    {"title": "...", "url": "...", "pmid": "..."}
  ],
  "warnings": ["..."]
}"""

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
2) discussion — RADIOLOGIST'S HIGH-YIELD NOTES
───────────────────────────────────────────────────────────────────

Provide a concise discussion using:
• Short paragraphs
• Bullet lists (use • or -)
• Simple pipe tables where helpful

Focus on:
• Dangerous anatomy relevant to this diagnosis
• Spread patterns and routes of involvement
• Complications and what to look for
• Key imaging signs and how they appear
• What differentiates mild vs severe
• What differentiates stable vs unstable
• What MUST be mentioned in a report

If staging/grading/classification exists:
• Do NOT give full TNM or full scoring tables
• Instead give only:
  - The 2-4 most important differentiating features
  - What specifically changes management"""

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

    # Section 4: Teaching image
    image_section = """
───────────────────────────────────────────────────────────────────
4) teaching_image — TEACHING IMAGE WITH CREDITS
───────────────────────────────────────────────────────────────────

Suggest ONE teaching image that explains a key concept of this diagnosis:
• CT, MRI, X-ray, or explanatory diagram
• Something that shows anatomy, spread pattern, or a classic sign

Provide:
• title: Brief descriptive title
• link: URL to a reputable medical image source
• description: What the image shows
• teaching_point: What it teaches the learner
• source: Attribution/credit (e.g., "Radiopaedia - Dr. X")

Use sources such as:
• Radiopaedia (radiopaedia.org)
• Radiology Assistant (radiologyassistant.nl)
• ACR (acr.org)
• NICE guidelines (nice.org.uk)
• Radiology key (radiologykey.com)
• Rdiographics (https://pubs.rsna.org/journal/radiographics)
• Cancer staging atlases (https://www.cancernetwork.org/tool?tnm_version=v8)
.Msucoskeliton MRI anatomy from https://www.freitasrad.net
. Head and neck MRI anatomy from https://headandneckrad.com

If no suitable image is known, leave teaching_image as empty object {}"""

    # Section 5: Sources
    sources_section = """
───────────────────────────────────────────────────────────────────
5) sources — REFERENCES
───────────────────────────────────────────────────────────────────

List 2-5 reputable sources for your information:
• Include title, url, and pmid (if applicable)
• Prefer: Radiopaedia, Radiology Assistant, ACR, NICE guidelines
• Only cite sources you are confident exist"""

    # Section 6: Warnings
    warnings_section = """
───────────────────────────────────────────────────────────────────
6) warnings — IMPORTANT CAVEATS
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
        image_section,
        sources_section,
        warnings_section,
        quality_bar
    ])
    
    return full_prompt


def _build_prompt(case_context):
    """Build system and user prompts for Claude API call."""
    return SYSTEM_PROMPT, _build_user_prompt(case_context)


def generate_prelim_case_data(case_context, provider="claude"):
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
    model = os.getenv("CLAUDE_MODEL", "claude-sonnet-4-20250514")

    payload = {
        "model": model,
        "max_tokens": 4000,  # Increased for more comprehensive output
        "temperature": 0.3,  # Slightly higher for more natural language
        "system": system_prompt,
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
            timeout=90,  # Increased timeout for longer responses
        )
    except requests.exceptions.Timeout:
        raise AiPrelimError("Claude API request timed out. Please try again.")
    except requests.exceptions.RequestException as exc:
        raise AiPrelimError(f"Failed to connect to Claude API: {exc}")

    if response.status_code >= 300:
        error_detail = response.text[:500] if response.text else "No details"
        raise AiPrelimError(
            f"Claude API error (HTTP {response.status_code}): {error_detail}"
        )

    data = response.json()
    content = data.get("content", [])
    if not content:
        raise AiPrelimError("Claude response missing content block")

    text = content[0].get("text", "").strip()
    if not text:
        raise AiPrelimError("Claude response was empty")

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
                    f"Claude response was not valid JSON: {exc}. "
                    f"Response preview: {text[:200]}..."
                ) from exc
        else:
            raise AiPrelimError(
                f"Claude response was not valid JSON: {exc}. "
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
    parsed.setdefault("sources", [])
    parsed.setdefault("warnings", [])

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

    return {
        "provider": provider,
        "model": model,
        "prompt_version": "v2",
        "generated_at": datetime.utcnow().isoformat(),
        "output": parsed,
        "raw_response": text,
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
