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
  "anatomy_image": {},
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
  "anatomy_image": {
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

If staging/grading/classification exists (non-cancer):
• Do NOT give full TNM or full scoring tables
• Instead give only:
  - The 2-4 most important differentiating features
  - What specifically changes management

TNM CLASSIFICATION (CANCER ONLY):
• If the diagnosis contains the word "cancer", include AJCC TNM classification table in this section
• Format using pipe tables (|) for clear structure
• Include:
  - T Stage definitions (T1, T2, T3, T4, etc.)
  - N Stage definitions (N0, N1, N2, N3, etc.)
  - M Stage definitions (M0, M1, etc.)
  - Stage groupings (Stage I, II, III, IV with corresponding T N M combinations)
• Example format:
  | T Stage | Definition |
  |---------|------------|
  | T1      | ...        |
  | T2      | ...        |
  | N Stage | Definition |
  |---------|------------|
  | N0      | ...        |
  | M Stage | Definition |
  |---------|------------|
  | M0      | ...        |
  | Stage Grouping | T N M |
  |----------------|-------|
  | Stage I        | T1N0M0 |
• Only include TNM classification if diagnosis contains "cancer" keyword
• Keep the table concise - focus on the most clinically relevant stages"""

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
• Radiographics (https://pubs.rsna.org/journal/radiographics)
• Cancer staging atlases (https://www.cancernetwork.org/tool?tnm_version=v8)
• Musculoskeletal MRI anatomy from https://www.freitasrad.net
• Head and neck MRI anatomy from https://headandneckrad.com
• Radiology Gyan (https://radiogyan.com/radiological-anatomy/) - comprehensive anatomy links collection

If no suitable image is known, leave teaching_image as empty object {}"""

    # Section 5: Anatomy image (OPTIONAL - Normal anatomy reference)
    anatomy_image_section = """
───────────────────────────────────────────────────────────────────
5) anatomy_image — NORMAL ANATOMY REFERENCE (OPTIONAL)
───────────────────────────────────────────────────────────────────

OPTIONAL SUPPLEMENT: If you can find a DISTINCT image showing NORMAL 
radiological anatomy relevant to this diagnosis, provide it here.

This should be DIFFERENT from teaching_image and specifically show:
• Normal anatomical structures (not pathology)
• Cross-sectional anatomy (CT/MRI) for spatial reference
• Anatomical landmarks relevant to the diagnosis location
• Structures that help understand the pathology context

CRITICAL REQUIREMENTS:
• MUST be different from teaching_image (do not duplicate)
• MUST focus on NORMAL anatomy (not pathology)
• MUST be relevant to the diagnosis location/structures
• If uncertain or no suitable image exists, leave as empty object {}

This helps students compare normal vs. pathology anatomy.

Provide:
• title: Brief descriptive title
• link: URL to normal anatomy resource (MUST be valid, working URL)
• description: What normal anatomical structures are shown
• teaching_point: How this normal anatomy relates to the diagnosis
• source: Attribution/credit

Preferred sources for normal anatomy:
• Radiopaedia normal anatomy sections (radiopaedia.org)
• Radiology Assistant anatomy atlases (radiologyassistant.nl)
• Radiology Gyan (https://radiogyan.com/radiological-anatomy/) - comprehensive anatomy links
• Freitasrad (https://www.freitasrad.net) - MSK MRI anatomy
• Head and Neck Radiology (https://headandneckrad.com) - Head/neck MRI anatomy
• Medical Image Cafe normal anatomy sections (medicalimagecafe.com)
• Sectional anatomy resources (sectional-anatomy.org)
• Castlemountain imaging anatomy (castlemountain.dk)

If no suitable normal anatomy image is known, leave anatomy_image as empty object {}"""

    # Section 6: Sources
    sources_section = """
───────────────────────────────────────────────────────────────────
6) sources — REFERENCES
───────────────────────────────────────────────────────────────────

List 2-5 reputable sources for your information:
• Include title, url, and pmid (if applicable)
• Include pdf_url field when PDF version is available (for journal articles)

PREFERRED JOURNALS (prioritize these for high-quality pictorial essays and anatomical/pathological correlations):
• Radiographics (pictorial reviews, case-based learning) - https://pubs.rsna.org/journal/radiographics
• AJNR (American Journal of Neuroradiology) - pictorial essays and case reports
• IJR (Indian Journal of Radiology) - pictorial articles
• RadiologyAssistant (radiologyassistant.nl) - comprehensive pictorial reviews
• Radiopaedia (radiopaedia.org) - case-based learning
• ScienceDirect - peer-reviewed radiology articles with full-text access
• Clinical Key - comprehensive medical reference with imaging correlations

IMPORTANT GUIDELINES:
• PREFER pictorial articles and articles with anatomical/pathological correlations
• PREFER case reviews and teaching files over general review articles
• Include PDF links when available (especially for Radiographics, AJNR, ScienceDirect)
• DO NOT link to generic journal homepages or main pages (e.g., acr.org main page, journal index pages)
• DO NOT invent or guess URLs - only use URLs you can verify exist
• Only cite sources you are confident exist and ensure the URL and links are valid
• For Radiopaedia: Use exact case/article slugs from search results, not guessed URLs
• For journal articles: Link to specific article DOIs, not journal homepages"""

    # Section 7: Warnings
    warnings_section = """
───────────────────────────────────────────────────────────────────
7) warnings — IMPORTANT CAVEATS
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
        anatomy_image_section,
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
    parsed.setdefault("anatomy_image", {})  # Optional field - may be empty
    parsed.setdefault("sources", [])
    parsed.setdefault("warnings", [])
    
    # Fix URLs in sources (PMC, RadiologyAssistant, Radiopaedia, and journal articles)
    if isinstance(parsed.get("sources"), list):
        import re
        from urllib.parse import urlparse
        
        filtered_sources = []
        generic_urls = [
            "acr.org/clinical-resources/clinical-tools-and-reference/appropriateness-criteria",
            "acr.org/clinical-resources",
            "pubs.rsna.org/journal/radiographics",  # Journal homepage, not specific article
            "ajnr.org",  # Journal homepage
        ]
        
        for source in parsed["sources"]:
            if isinstance(source, dict) and "url" in source:
                url = source["url"]
                url_lower = url.lower()
                
                # Fix PMC URLs with duplicate prefix (e.g., PMCPMC10481713)
                if "pmc.ncbi.nlm.nih.gov" in url or "ncbi.nlm.nih.gov/pmc" in url:
                    # Extract PMC ID and reconstruct URL correctly
                    # Match patterns like PMCPMC123 or PMC123
                    pmc_match = re.search(r'PMC?PMC?(\d+)', url, re.IGNORECASE)
                    if pmc_match:
                        pmc_id_clean = pmc_match.group(1)
                        source["url"] = f"https://www.ncbi.nlm.nih.gov/pmc/articles/PMC{pmc_id_clean}/"
                
                # Fix RadiologyAssistant URLs (ensure correct domain and protocol)
                elif "radiologyassistant" in url.lower():
                    # Normalize domain: ensure it's radiologyassistant.nl (not .com or other)
                    url_lower = url.lower()
                    # Extract the path/query part
                    if "radiologyassistant.nl" in url_lower:
                        # Already correct domain, just ensure https://
                        if not url.startswith("http://") and not url.startswith("https://"):
                            # Reconstruct with https://
                            path_part = url.split("radiologyassistant.nl", 1)[1] if "radiologyassistant.nl" in url_lower else ""
                            source["url"] = f"https://radiologyassistant.nl{path_part}"
                        elif url.startswith("http://"):
                            # Upgrade http to https
                            source["url"] = url.replace("http://", "https://", 1)
                    elif "radiologyassistant.com" in url_lower or "radiology-assistant" in url_lower:
                        # Wrong domain, fix to .nl
                        path_part = ""
                        for domain in ["radiologyassistant.com", "radiology-assistant"]:
                            if domain in url_lower:
                                path_part = url.split(domain, 1)[1] if domain in url else ""
                                break
                        # Ensure protocol
                        if not path_part.startswith("/"):
                            path_part = "/" + path_part
                        source["url"] = f"https://radiologyassistant.nl{path_part}"
                    else:
                        # Just radiologyassistant mentioned, ensure full URL
                        if not url.startswith("http://") and not url.startswith("https://"):
                            source["url"] = f"https://radiologyassistant.nl{url if url.startswith('/') else '/' + url}"
                
                # Fix Radiopaedia URLs (detect truncation and validate)
                elif "radiopaedia.org" in url.lower():
                    url_lower = url.lower()
                    # Ensure proper protocol
                    if not url.startswith("http://") and not url.startswith("https://"):
                        source["url"] = f"https://{url}"
                    elif url.startswith("http://"):
                        source["url"] = url.replace("http://", "https://", 1)
                    # Note: We can't easily validate truncated URLs without making HTTP requests
                    # The model should be instructed to use exact URLs, and we'll add warnings if needed
                
                # Filter out generic/homepage URLs
                is_generic = any(generic in url_lower for generic in generic_urls)
                # Also check if it's just a domain or main page
                parsed_url = urlparse(url if url.startswith("http") else f"https://{url}")
                if is_generic or (parsed_url.path in ["/", ""] and not parsed_url.query and not parsed_url.fragment):
                    # Mark for removal - we'll filter these out
                    source["_should_remove"] = True
                    if "warnings" not in parsed:
                        parsed["warnings"] = []
                    parsed["warnings"].append(f"Removed generic URL: {url}")
                
                # Generate PDF links for journal articles
                if "pubs.rsna.org/doi/full" in url_lower or "pubs.rsna.org/doi/abs" in url_lower:
                    # Convert to PDF link
                    doi_match = re.search(r'10\.\d+/[^\s/]+', url)
                    if doi_match:
                        doi = doi_match.group(0)
                        pdf_url = f"https://pubs.rsna.org/doi/pdf/{doi}"
                        source["pdf_url"] = pdf_url
                elif "ajnr.org/content" in url_lower:
                    # AJNR article - try to generate PDF link
                    # AJNR PDF links typically follow pattern: ajnr.org/content/{vol}/{issue}/{page}.full.pdf
                    # We'll keep the article URL and note that PDF may be available
                    source["pdf_note"] = "PDF may be available on article page"
                elif "sciencedirect.com" in url_lower and "/article/" in url_lower:
                    # ScienceDirect article - PDF link typically available
                    # Format: sciencedirect.com/science/article/pii/{pii}/pdfft
                    pii_match = re.search(r'/pii/([A-Z0-9]+)', url_lower)
                    if pii_match:
                        pii = pii_match.group(1)
                        pdf_url = url.replace("/article/", "/article/pii/").replace("?via%3Dihub", "") + "/pdfft"
                        source["pdf_url"] = pdf_url
                
                # Only add source if not marked for removal
                if not source.get("_should_remove", False):
                    # Remove the temporary flag
                    source.pop("_should_remove", None)
                    filtered_sources.append(source)
            else:
                # Keep sources without URLs or invalid structure
                filtered_sources.append(source)
        
        # Update sources list with filtered results
        parsed["sources"] = filtered_sources

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
    # If oncologic diagnosis detected, add TNM metadata to output.
    # This does NOT call Claude for TNM - that's done separately via ai_tnm.py
    # when user explicitly requests it. Here we just add reference info.
    
    diagnosis = case_context.get("diagnosis", "").strip()
    module = case_context.get("module", "").strip()
    body_part = case_context.get("body_part", "").strip()
    case_id = case_context.get("case_id")  # Optional: for link generation
    
    # Initialize TNM metadata (will be populated if oncologic)
    parsed["tnm_metadata"] = None
    
    if diagnosis:
        try:
            from ai_tnm import is_oncologic_diagnosis, get_tnm_reference_only
            
            if is_oncologic_diagnosis(diagnosis):
                # Get TNM reference from internal database
                tnm_ref = get_tnm_reference_only(
                    diagnosis=diagnosis,
                    module=module,
                    body_part=body_part,
                    from_case_id=case_id
                )
                
                if tnm_ref:
                    # Add TNM metadata to output
                    parsed["tnm_metadata"] = {
                        "is_oncologic": True,
                        "has_staging_data": tnm_ref.get("has_staging_data", False),
                        "disease_name": tnm_ref["ajcc_match"].get("disease_name") if tnm_ref.get("ajcc_match") else None,
                        "section_name": tnm_ref["ajcc_match"].get("section_name") if tnm_ref.get("ajcc_match") else None,
                        "tnm_link": tnm_ref.get("tnm_link"),
                        "disease_site_id": tnm_ref["ajcc_match"].get("disease_site_id") if tnm_ref.get("ajcc_match") else None,
                    }
                    
                    # If TNM data exists, add reference to discussion
                    discussion = parsed.get("discussion", "")
                    if tnm_ref.get("has_staging_data") and tnm_ref.get("tnm_link"):
                        disease_name = tnm_ref["ajcc_match"].get("disease_name", "this cancer")
                        section_name = tnm_ref["ajcc_match"].get("section_name", "")
                        tnm_link = tnm_ref["tnm_link"]
                        
                        # Add internal TNM reference
                        tnm_ref_text = f"\n\n**TNM Staging Reference:** [View AJCC TNM staging for {disease_name}]({tnm_link}) - Detailed T/N/M definitions, stage groupings, and imaging-specific guidance available."
                        
                        if tnm_ref_text not in discussion:
                            parsed["discussion"] = discussion + tnm_ref_text
                else:
                    # Oncologic but no AJCC match found
                    parsed["tnm_metadata"] = {
                        "is_oncologic": True,
                        "has_staging_data": False,
                        "disease_name": None,
                        "tnm_link": None,
                        "message": "TNM staging data not yet available in database for this cancer type."
                    }
                    
        except ImportError:
            # ai_tnm not available, skip enhancement
            import sys
            print("[AI_PRELIM] ai_tnm module not available, skipping TNM enhancement", file=sys.stderr)
        except Exception as e:
            # Log error but don't break the flow
            import sys
            print(f"[AI_PRELIM] Error during TNM enhancement: {e}", file=sys.stderr)
            parsed["tnm_metadata"] = {
                "is_oncologic": True,
                "error": str(e)
            }

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
