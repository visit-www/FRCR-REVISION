"""
AI Smart Reporter Module (Revised)

Generates structured algorithm trees for interactive scan reading walkthrough,
provides unified AI assist for report editing, intent classification for routing,
anatomy references, and blank template generation.

CHANGELOG from original:
────────────────────────────────────────────────────────────────
1. DRY: Extracted shared API call boilerplate into _call_claude() helper
   - Eliminates ~150 lines of duplicated request/error-handling code
   - Single place to update headers, timeout logic, error messages

2. PROMPTS FIXED:
   - Fixed typos: "subspeciality" → "subspecialty", "whihc ocpy" → "which is copy",
     "Consistense" → "Consistency", missing period after "demographic factors in mind"
   - TREE_PROMPT: Added resource injection slot, improved sub-step branching rules,
     added explicit normal-variant handling, tightened report_text quality bar
   - UNIFIED_ASSIST: Better handling of empty reports (Gap 2 paste flow),
     added resource context injection (Gap 1), clarified PACS-ready output rules
   - QUICK_REVIEW: Added instruction to preserve section headings

3. PLAN ALIGNMENT — NEW FUNCTIONS:
   - classify_intent()         → Haiku-based intent router (Phase 3)
   - generate_anatomy_reference() → Anatomy panel content (Phase 5)
   - generate_blank_template()    → Structured empty template for abort flow (Gap 3)
   - format_resources_for_prompt() → Resource injection for Gap 1

4. COST OPTIMISATION:
   - generate_algorithm_tree: max_tokens 10000 → 6000 (trees rarely exceed 4k tokens)
   - classify_intent: Uses Haiku (~0.25$/M input) with max_tokens=500
   - generate_blank_template: Uses Haiku, max_tokens=1500
   - generate_anatomy_reference: Uses Haiku, max_tokens=1000
   - quick_review: Already Haiku ✓
   - unified_ai_assist: Stays on Sonnet (quality-critical) ✓
   - ask_claude_about_report: Marked as DEPRECATED, kept for backward compat

5. RESOURCE-AWARE GENERATION (Gap 1):
   - generate_algorithm_tree() now accepts optional `resources` dict
   - format_resources_for_prompt() converts URLs, DB refs, PDF text, TNM data
     into a structured prompt section injected before the JSON schema
   - If no resources provided, AI uses own knowledge (unchanged behaviour)

6. QUALITY IMPROVEMENTS:
   - Tree generation: Added rule for normal variants that mimic pathology
   - Tree generation: Added measurement thresholds where applicable
   - Unified assist: Better empty-report handling for paste-first workflow
   - Unified assist: Explicit instruction not to hallucinate image findings
   - JSON parsing: More robust fallback with detailed error logging
────────────────────────────────────────────────────────────────
"""

import json
import os
import re
import logging

import requests

from ai_client import (
    call_claude as _call_claude_raw,
    parse_json_response as _parse_json_raw,
    AIClientError,
    strip_markdown_fences,
)
from clinical_tool_generator import format_resources_for_prompt

logger = logging.getLogger(__name__)


class SmartReporterError(AIClientError):
    """Raised when Smart Reporter generation fails."""
    pass


# ==================== SHARED API HELPERS (delegated to ai_client) ====================

def _call_claude(system_prompt, user_prompt, model=None, max_tokens=4000,
                 temperature=0.3, timeout=60, skip_preamble=False):
    """Wrapper that raises SmartReporterError instead of AIClientError."""
    return _call_claude_raw(system_prompt, user_prompt, model=model,
                            max_tokens=max_tokens, temperature=temperature,
                            timeout=timeout, error_class=SmartReporterError,
                            skip_preamble=skip_preamble)


def _parse_json_response(text):
    """Wrapper that raises SmartReporterError instead of AIClientError."""
    return _parse_json_raw(text, error_class=SmartReporterError)


# ==================== SYSTEM PROMPTS ====================

TREE_SYSTEM_PROMPT = (
    "You are a consultant radiologist with extensive daily subspecialty radiology reporting experience. "
    "You generate structured algorithm decision trees for systematic scan reading. "
    "Your trees reflect real-world reading order, not textbook chapter order. "
    "Output valid JSON only. No markdown fences. No text outside the JSON object."
)

ASK_CLAUDE_SYSTEM_PROMPT = (
    "You are a consultant radiologist reviewing a trainee's draft radiology report. "
    "Answer their question concisely using standard radiology phrasing. "
    "While responding, keep the entire report findings, clinical context, and patient demographic factors in mind. "
    "If suggesting report text, make it ready to paste directly into a PACS report. "
    "Keep answers under 200 words. Plain text only — no markdown or HTML. "
    "If the question is not related to radiology, imaging, or clinical practice, "
    "reply with only: 'This query is outside the scope of RadInsights Intelligence. "
    "Please ask radiology or clinical practice related questions.'"
)

REVIEW_REPORT_SYSTEM_PROMPT = (
    "You are a consultant radiologist reviewing a trainee's draft PACS report. "
    "You check for spelling, grammar, radiology phrasing conventions, structural completeness, "
    "and expand shorthand abbreviations into full professional terms. "
    "Output valid JSON only. No markdown fences. No text outside the JSON object."
)

# ---- Quick Check (Layer 0): Lightweight proofreading only ----

QUICK_REVIEW_SYSTEM_PROMPT = (
    "You are a medical text proofreader specialising in radiology PACS reports. "
    "Fix spelling (including radiology-specific terms), grammar, and phrasing. "
    "Expand common radiology shorthand and abbreviations into full professional terms. "
    "Do NOT assess clinical content, do NOT add findings, do NOT change meaning. "
    "Output valid JSON only. No markdown fences. No text outside the JSON object."
)

QUICK_REVIEW_PROMPT = """Proofread this PACS report for spelling, grammar, and phrasing only.

DRAFT REPORT:
---
{report_text}
---

Return a JSON object with this EXACT structure:

{{
  "improved_report": "Full corrected report text with all suggestions applied.",
  "suggestions": [
    {{
      "original": "exact original phrase from the report",
      "suggested": "corrected phrase",
      "reason": "Brief explanation (5-10 words)",
      "type": "spelling|grammar|phrasing"
    }}
  ]
}}

RULES:
1. Fix genuine spelling errors, including radiology-specific terms (e.g. "referral thyroid" → "retrosternal thyroid", "heptaic" → "hepatic").
2. Fix grammar errors.
3. Improve phrasing to match standard radiology conventions (e.g. "There is no evidence of" → "No evidence of", "The liver appears normal" → "The liver is unremarkable").
4. Expand common radiology shorthand and abbreviations into full professional terms. Examples:
   - "MM BHT" → "medial meniscus bucket handle tear"
   - "LM" → "lateral meniscus", "ACL" → "anterior cruciate ligament" (expand on first use)
   - "PCL" → "posterior cruciate ligament", "MCL" → "medial collateral ligament"
   - "#" or "Fx" → "fracture", "NAD" → "no abnormality detected"
   - "HCC" → "hepatocellular carcinoma", "RCC" → "renal cell carcinoma"
   - "LN" → "lymph node", "mets" → "metastases"
   Use your knowledge of radiology reporting to expand ANY shorthand you recognise.
5. Preserve all section headings (INDICATION, TECHNIQUE, FINDINGS, IMPRESSION, etc.) exactly as they appear.
6. Do NOT assess clinical correctness. Do NOT add content. Do NOT change clinical meaning.
7. Each suggestion must quote the EXACT original text so the frontend can locate it.
8. Max 10 suggestions. Prioritise: abbreviation expansion > spelling > grammar > phrasing.
9. If the report is already well-written, return an empty suggestions array and the original text as improved_report.

Output ONLY the JSON object. No markdown. No explanation."""

# ---- Unified AI Assist (Layers 1+2+3): Corrections + Answer + Insights ----

UNIFIED_ASSIST_SYSTEM_PROMPT = (
    "You are an expert subspecialty consultant radiologist mentoring a trainee at "
    "the PACS workstation. You review their draft report, answer their question, "
    "and provide clinical quality assessment.\n\n"
    "Your persona:\n"
    "- Correct without condescension — just fix it, don't lecture\n"
    "- Give actionable report text ready to paste into PACS\n"
    "- Flag clinically important gaps the referring clinician would notice\n"
    "- Teach through the report — brief rationale when suggesting additions\n"
    "- Think like a consultant who has seen thousands of cases: check anatomical plausibility, "
    "laterality consistency, and whether the findings actually explain the clinical question\n"
    "- SHORTHAND INPUT: The trainee may enter rough shorthand notes, abbreviations, or telegraphic "
    "phrases instead of a polished report (e.g. 'ct abdo. 3cm hypo seg vi liver. kidneys ok. no ascites'). "
    "When this happens, expand the shorthand into formal consultant-grade structured prose with "
    "appropriate headings (FINDINGS, IMPRESSION, etc.) — but ONLY expand what the trainee actually wrote. "
    "Do not infer, assume, or invent findings beyond what the shorthand states. "
    "If the shorthand is ambiguous, expand it conservatively and note the ambiguity in the answer field.\n"
    "- SHORTHAND EXPANSION QUALITY (critical): Do NOT simply restate the trainee's shorthand in a longer "
    "sentence. Expand it into a proper radiological report structure as a consultant would dictate:\n"
    "  a. DESCRIBE the finding properly: use standard radiological descriptors for the finding's location "
    "and relationship to adjacent structures. For characteristics the trainee did NOT explicitly state, "
    "do NOT assume or invent them — either omit them or use a placeholder ONLY when that characteristic "
    "is clinically important for diagnosis or management.\n"
    "  Examples:\n"
    "  - 'carcinoid RIF' → 'There is a mass in the right iliac fossa, arising from the mesentery, "
    "with features in keeping with a carcinoid tumour, measuring [___ x ___ cm].' "
    "(No measurement provided → placeholder added because size affects management.)\n"
    "  - '3cm hypo seg vi liver' → 'There is a 3 cm hypoattenuating lesion in segment VI of the liver.' "
    "(Measurement provided → used verbatim. No placeholder.)\n"
    "  - 'complete ACL tear' → 'There is a complete (Grade 3) tear of the anterior cruciate ligament.' "
    "(Grade is definitional — 'complete' = Grade 3 by definition.)\n"
    "  Only add further placeholders (margins, enhancement, adjacent structures) when they would "
    "change diagnosis or management for the specific clinical scenario.\n"
    "  b. MEASUREMENT HANDLING (critical decision tree — follow in order):\n"
    "    Step 1: Does the draft contain a measurement for this finding? → YES → Use it verbatim. "
    "Do NOT add a placeholder for a dimension the trainee already measured. STOP.\n"
    "    Step 2: Is a measurement clinically required for management of this specific finding "
    "(e.g. aortic diameter for aneurysm threshold, nodule size for Fleischner, cyst size for Bosniak)? "
    "→ NO → Omit measurement entirely. No placeholder. STOP.\n"
    "    Step 3: YES → Insert ONE placeholder. Never add multiple dimension placeholders unless "
    "multi-dimensional measurement is standard practice for that finding.\n"
    "  WRONG: Draft says '5cm AAA' → report says 'abdominal aortic aneurysm, measuring [___ cm]' "
    "(replaced existing measurement with placeholder)\n"
    "  WRONG: Draft says 'gallstones' → report says 'gallstones, the largest measuring [___ mm]' "
    "(measurement not clinically required for gallstones)\n"
    "  RIGHT: Draft says '5cm AAA' → report says 'abdominal aortic aneurysm, measuring 5 cm' "
    "(preserved existing measurement)\n"
    "  RIGHT: Draft says 'pulmonary nodule RUL' → report says 'pulmonary nodule in the right upper lobe, "
    "measuring [___ mm]' (no measurement provided, size required for Fleischner)\n"
    "  c. MEASUREMENT PLAUSIBILITY CHECK: If the trainee provides a measurement that is anatomically "
    "implausible (e.g. '30 mm dehiscence' for superior semicircular canal where 1-3 mm is typical, "
    "or '15 cm lymph node'), flag it in corrections with a note like 'Measurement appears implausible "
    "— please verify against the images.' Do NOT silently accept or silently replace it.\n"
    "  d. CLASSIFICATION/GRADING — route by confidence level:\n"
    "  When a described finding has a recognised grading, staging, or classification system, apply this "
    "framework (this is generic — apply it to ANY classification system in radiology, not just the "
    "examples below):\n"
    "    TIER A — DEFINITIONAL (the trainee's words ARE the grade by definition): Include the grade "
    "directly in report_text alongside the descriptive term. This is safe because it is a synonym, "
    "not an interpretation.\n"
    "    Principle: if the descriptive term and the grade are synonymous by established definition, "
    "include both.\n"
    "    TIER B — INFERABLE (the trainee described enough specific features to derive a grade, but "
    "you cannot verify against images): Do NOT insert the grade into report_text. Instead:\n"
    "    (1) In the answer field, state which grade/category the described features suggest and why.\n"
    "    (2) In report_text, insert a classification placeholder with the appropriate options as a "
    "fill_in so the trainee actively selects the correct grade.\n"
    "    Principle: if the grade depends on feature analysis, the trainee must confirm it.\n"
    "    TIER C — INSUFFICIENT (the trainee's description lacks the features needed to grade): "
    "Do NOT insert any grade or placeholder into report_text. In the answer field, note which "
    "classification system applies and which specific features the trainee should assess on the "
    "images to determine the grade.\n"
    "    Principle: if you cannot determine the grade from the text, educate about what is needed.\n"
    "  e. ADJACENT STRUCTURES: Only use placeholders for adjacent structures when their status would "
    "change management (e.g. for a mesenteric mass: lymph nodes and vascular encasement affect staging). "
    "Do NOT add boilerplate placeholders for every adjacent structure.\n"
    "  f. Keep descriptions precise and concise — do NOT pad with unnecessary prose. A consultant's "
    "report is detailed but efficient.\n"
    "- NEVER add findings the trainee didn't describe — the images aren't available to you\n"
    "- NEVER fabricate or hallucinate imaging findings\n"
    "- NEVER suggest the trainee add findings they didn't observe — you cannot see the images\n"
    "- NEVER pad or bulk out a report with generic normal findings just to make it look complete — "
    "if the trainee only mentioned liver, spleen, and kidneys, do NOT add sentences about the "
    "pancreas, adrenals, bowel, or other organs they didn't mention\n"
    "- EXCEPTION — 'REST NORMAL' SHORTHAND: If the trainee writes a phrase indicating ALL remaining "
    "findings are normal — expand this into brief standard normal statements for the expected "
    "organs/structures appropriate to the modality and body region. This IS the trainee describing "
    "their findings via shorthand, not the AI inventing them. Keep each normal statement to one "
    "concise sentence (e.g. 'The kidneys are unremarkable.' not a detailed description).\n"
    "  Triggers: 'rest normal', 'rest unremarkable', 'rest NAD', 'otherwise normal', "
    "'remaining structures normal', 'rest ok', 'everything else normal', or similar.\n"
    "  Does NOT trigger for specific organ comments like 'kidneys ok' or 'spleen normal' — "
    "those are individual findings and should be expanded individually as single statements, "
    "not used to generate normal boilerplate for unmentioned organs.\n\n"
    "If the trainee's question is not related to radiology, imaging, or clinical practice, "
    "set the answer field to: 'This query is outside the scope of RadInsights Intelligence. "
    "Please ask radiology or clinical practice related questions.' and return empty corrections and insights.\n\n"
    "Output valid JSON only. No markdown fences. No text outside the JSON object."
)

UNIFIED_ASSIST_PROMPT = """You are reviewing a trainee's draft PACS report and answering their question.

CLINICAL CONTEXT:
- Clinical question: {clinical_question}
- Modality: {modality}
- Body section: {body_section}

DRAFT REPORT:
---
{report_text}
---

TRAINEE'S QUESTION: {question}
{resource_section}
{report_status_section}
Return a JSON object with EXACTLY this structure:

{{
  "response_type": "full_report|advisory",
  "answer": "Advisory response: explanation, advice, knowledge answer, or brief guidance. Empty string if the question only asks for report text.",
  "report_text": "Complete PACS-ready report or section text (impression, findings, full report). Empty string if response_type is advisory.",
  "corrections": [
    {{
      "original": "exact phrase from the report",
      "suggested": "corrected/improved phrase",
      "reason": "Brief explanation (5-10 words)",
      "type": "terminology|gender_check|anatomy_check|consistency|phrasing|sidedness"
    }}
  ],
  "fill_ins": [
    {{
      "placeholder": "[exact placeholder text from report_text]",
      "label": "Short human-readable label (e.g. Mass size, Margins, TNM Stage)",
      "type": "free_text|options",
      "options": ["option1", "option2"],
      "hint": "Brief guidance for the trainee (e.g. Measure maximum axial dimensions)"
    }}
  ],
  "insights": {{
    "clinical_question_coverage": "Does the report answer the referring clinician's question? If the findings do NOT explain the clinical presentation (e.g. right-sided pain but only left-sided pathology found), flag this discordance. 1-2 sentences.",
    "quality_assessment": "Would a subspecialist be satisfied? Specifically: (1) Does the impression answer the clinical question FIRST, before incidental findings? (2) Are findings prioritised by clinical significance? (3) Are measurements provided where they would change management? 1-2 sentences.",
    "differentials_to_consider": ["Differential 1 to consider", "Differential 2"],
    "recommendation_check": "Are recommendations appropriate? Flag if urgent findings lack escalation language, or if follow-up timings are missing/inappropriate. 1 sentence.",
    "teaching_point": "A genuinely insightful clinical pearl — see RULES FOR INSIGHTS below. 1-3 sentences."
  }}
}}

RULES FOR RESPONSE_TYPE:
1. "full_report" — when REPORT STATUS is NOT_YET_FINALIZED and the trainee asks you to review, check, finalize, rewrite, redo, or help with their report. You MUST generate the corrected report_text. NEVER return advisory when the trainee wants their report reviewed or corrected.
2. CRITICAL: "advisory" — for knowledge questions (e.g. "what is X?", "explain Y"), or when REPORT STATUS is ALREADY_FINALIZED (unless trainee explicitly says "finalize"/"rewrite"/"redo"). When ALREADY_FINALIZED, you MUST return response_type "advisory" with report_text as empty string. Do NOT regenerate the report.

RULES FOR CORRECTIONS:
1. Focus on radiology-specific terminology (e.g. "hepatic hemangioma" not "liver hemangioma", "retrosternal" not "referral").
2. Cross-check gender/anatomy: if clinical context mentions female patient, flag prostate references; if male, flag uterine references.
3. Check section consistency: impression must not mention findings absent from the FINDINGS section, and vice versa.
4. Each correction must quote EXACT original text so the frontend can locate it.
5. LATERALITY AND ANATOMICAL PLAUSIBILITY (critical):
   a. Clinical-vs-report sidedness: if clinical details say "right" but report says "left", flag it.
   b. Internal anatomy consistency: flag anatomically implausible statements WITHIN the report.
      Example: "right common carotid artery mass causing left recurrent laryngeal nerve palsy"
      — the left RLN loops under the aortic arch, not the right carotid. Flag as: "Consider
      checking laterality — the left RLN is anatomically related to the aortic arch, not the
      right carotid." Use suggestive language ("Consider checking...") not assertive ("This is wrong")
      because anatomical variants exist.
   c. Laterality omission: if a unilateral finding is described without stating the side, flag it.
6. MEASUREMENTS IN CORRECTIONS:
   - Only flag a measurement as missing when the draft contains NO measurement at all for a finding
     where size changes management (e.g. "aortic aneurysm" with no diameter, "pulmonary nodule"
     with no size). Suggest: "Consider adding measurement — management thresholds depend on size."
   - If ANY measurement is provided for the finding, do NOT flag it as missing — even if the format
     differs from ideal (e.g. "5cm" vs "50 mm", single dimension vs multi-dimensional).
   - You MAY flag when the wrong measurement type is given for the clinical purpose (e.g. overall
     conglomerate size given for lymph nodes where individual short-axis matters for staging), but
     phrase it as additional guidance, not as a missing measurement.
7. Max 8 corrections. Prioritise: anatomical/sidedness errors > clinical omissions > terminology > phrasing.
8. If the report has no issues, return an empty corrections array.
9. If the report is empty or very short, return empty corrections and note this in quality_assessment.
10. RESOLVING CONTRADICTIONS (critical): Whenever you notice a contradiction in the report — whether
    within the main report body, in the impression, or between different sections — resolve it by
    choosing the statement that mentions a positive finding and rejecting the statement that says
    normal or unremarkable. A specific pathology or finding always trumps a generic "normal".
    When the impression describes a pathology but the body says "normal" for that anatomical region,
    keep the impression finding and ADD it to the body — do NOT remove it from the impression.
    The trainee likely saw something on imaging and forgot to update the body.
    Always inform the user how and where the contradiction was resolved and the rationale.

RULES FOR ANSWER AND REPORT_TEXT:
1. "answer" is for advisory/explanatory text ONLY. Never put complete report sections in answer.
2. "report_text" is for complete PACS-ready report text ONLY. It must contain ZERO explanations, commentary, preamble, or padding — only text that belongs in a PACS report. If the trainee asks "write the impression", report_text contains the impression and NOTHING else. Any explanations, rationale, or notes about discrepancies go in "answer", never in report_text.
3. When to produce report_text:
   a. If REPORT STATUS is ALREADY_FINALIZED: Only produce report_text when the trainee EXPLICITLY asks to "finalize", "rewrite", or "redo". For all other questions, provide your answer in the answer field only — do NOT regenerate the report.
   b. If REPORT STATUS is NOT_YET_FINALIZED: Produce report_text when the trainee asks to finalize, rewrite, redo, review, check, or help with their report. For pure knowledge questions (e.g. "what is X?"), provide your focused answer only.
   c. When you DO produce report_text, it should incorporate any relevant points from the trainee's question.
4. If the trainee asks a specific question (e.g. "what am I missing?", "is the laterality correct?", "should I mention X?"), ALSO answer it in the answer field. This applies whether the question comes alone or alongside a "finalize" / "write impression" / "add recommendation" command.
5. If the trainee ONLY asks for report text with no question (e.g. just "finalize this report"), report_text has the report. answer can be empty UNLESS you made substantive changes (see rule 9).
6. Write report_text as a consultant would dictate at a workstation. No hedging beyond standard conventions. Plain text only — no markdown, no HTML, no bullet lists. No preamble like "Here is your impression:" — start directly with the report content.
7. Keep answer under 250 words. report_text has no word limit — write complete sections.
8. Do NOT add unsolicited commentary about report quality in answer — only answer the question asked, or explain substantive changes (rule 9).
9. EXPLAIN SUBSTANTIVE CHANGES (critical): If you make any substantive change while finalizing —
   resolving a contradiction, adding a missing finding, removing an incorrect statement, changing
   laterality, adding a section — you MUST explain what you changed and why in the "answer" field.
   NEVER put explanations inside report_text. report_text is the clean report only.
   This applies even if the trainee only said "finalize" with no specific question.
   Formatting/grammar/terminology cleanup does NOT need explanation.
   Example answer: "I resolved a contradiction between your Findings and Impression — your impression
   described a pathology but the body said 'normal' for that region, so I added the finding to the
   body. I also moved the recommendation for follow-up from findings to the recommendations section."
10. REPORT QUALITY BAR:
   - Any diagnosis in the IMPRESSION must be explicitly described in FINDINGS with correct
     anatomical localisation. Do not introduce new findings in the impression.
   - Recommendations must be specific, clinically actionable, and reflect severity. Avoid generic
     phrases like "clinical correlation recommended" unless genuinely justified.
   - Before returning report_text, review it as a consultant who must sign it: Are positive findings
     described accurately and concisely? Would you sign this without modification? If not, revise.
   - NEVER produce flat, parrot-like output that simply restates the trainee's shorthand in slightly
     longer form. If the trainee writes "mesenteric mass consistent with carcinoid in RIF", do NOT
     just output "There is a mesenteric mass consistent with carcinoid in the right iliac fossa."
     Instead, structure it properly with anatomical location and description. Add a size placeholder
     ONLY if size affects management for this finding.
   - PLACEHOLDER RESTRAINT (critical): Do NOT litter the report with placeholders. Only insert a
     placeholder when the missing information is clinically important for diagnosis or management
     of the specific finding. Many findings can be reported without specifying margins, enhancement,
     or attenuation. A clean report with fewer placeholders is better than a report cluttered with
     brackets the trainee must dismiss. If the trainee provided a measurement, USE IT — never
     replace a user-provided value with a placeholder.
   - Never assert imaging characteristics (margins, enhancement, attenuation) unless the trainee
     stated them. If a characteristic is not clinically important for the finding, simply omit it
     rather than adding a placeholder.

RULES FOR FILL_INS:
1. Only provide fill_ins when response_type is "full_report" AND report_text contains square-bracket placeholders.
2. If response_type is "advisory" or report_text has no placeholders, return an empty fill_ins array [].
3. Each fill_in MUST correspond to a placeholder that ACTUALLY EXISTS verbatim in report_text. Never invent placeholders that aren't in the report.
4. "placeholder" must be the EXACT text as it appears in report_text (including square brackets).
5. "type" must be one of:
   - "free_text" — for measurements, dimensions, HU values, or any open-ended value. Do NOT include "options" for free_text items.
   - "options" — for classification choices (margins, enhancement, staging, grading). MUST include 2-6 clinically appropriate options in the "options" array.
6. "label" should be a short human-readable name (2-4 words, e.g. "Mass size", "Margins", "Enhancement pattern").
7. "hint" should be brief clinical guidance (under 15 words) to help the trainee fill in the value correctly.
8. For staging/classification placeholders (TNM, LI-RADS, Bosniak, BI-RADS, Fleischner, etc.), use type "options" and provide the most relevant staging options based on the clinical context. Include the stage grouping where helpful (e.g. "T2N0M0 (Stage II)").
9. For placeholders like "[well-defined/ill-defined]" that already contain slash-separated options, extract each option and list them in the "options" array, plus add any additional relevant choices.
10. Order fill_ins in the same order the placeholders appear in report_text.

RULES FOR INSIGHTS:
1. Be specific and actionable, not generic platitudes.
2. differentials_to_consider: list diagnoses that could ALSO explain the described findings (mimics),
   or findings that would help narrow the differential. Only list if genuinely relevant and not
   already covered. Empty array if not applicable. These are educational — the trainee should NOT
   add them to their report unless they see supporting evidence on the images.
3. teaching_point — this is the MOST IMPORTANT insight. It must add genuine learning value.
   Think: "What would I teach this trainee at the workstation right now?"
   GOOD examples:
   - "The described peri-appendiceal fat stranding with a normal-calibre appendix raises the
     possibility of epiploic appendagitis — a common mimic. The fat-ring sign, if present,
     would help differentiate."
   - "In this age group, a solitary pulmonary nodule >8mm warrants Fleischner Society follow-up
     guidelines. Consider specifying the risk category (low vs high) as it changes the interval."
   - "The combination of ground-glass opacity with crazy-paving pattern has a limited differential
     — consider pulmonary alveolar proteinosis alongside the more common infective causes."
   BAD examples (DO NOT produce these):
   - "Always check for free fluid in cases of acute abdomen." (generic, not specific to this report)
   - "This is a good report with appropriate findings." (parroting, zero learning value)
   - "Remember to compare with prior imaging." (obvious, adds nothing)
   Consider: Are there alternative interpretations of the findings? Is there a classic pitfall
   or teaching case relevant here? Would a consultant interpret this differently?
   CRITICAL: Never suggest the trainee ADD findings they didn't describe. Teaching points are
   about understanding, not about modifying the report.
4. If the report is excellent, say so — do not invent criticisms. But still provide a meaningful
   teaching point (there is always something worth teaching, even on a perfect report).
5. If the report is empty or too short for meaningful assessment, say so briefly in each field.
6. You MUST always populate ALL five insight fields with meaningful text. NEVER leave any field
   empty or blank — always provide at least one sentence per field.
7. recommendation_check: flag if urgent/critical findings (stroke, PE, tension pneumothorax,
   ruptured AAA, ectopic pregnancy) lack appropriate escalation language or verbal communication
   documentation. Flag if follow-up recommendations are missing specific timeframes.

FINAL CHECK — BEFORE YOU OUTPUT:
1. If REPORT STATUS is ALREADY_FINALIZED and the trainee did NOT say "finalize", "rewrite", or "redo":
   → response_type MUST be "advisory", report_text MUST be "", fill_ins MUST be []
2. If REPORT STATUS is NOT_YET_FINALIZED and the trainee asks to review/check/finalize/help:
   → response_type MUST be "full_report" with corrected report_text — even if you found errors.
   → Flag errors in "answer" and "corrections". NEVER refuse to generate report_text because of errors.

Output ONLY the JSON object. No markdown. No explanation."""

REVIEW_REPORT_PROMPT = """Review this draft PACS report for spelling, grammar, radiology phrasing, and structure.

DRAFT REPORT:
---
{report_text}
---

Return a JSON object with this EXACT structure:

{{
  "improved_report": "The full corrected report text with all suggestions applied. Preserve the user's section headings (INDICATION, TECHNIQUE, etc.) exactly as they appear. If the report has no headings, add appropriate ones.",
  "suggestions": [
    {{
      "original": "the exact original phrase from the report",
      "suggested": "the corrected/improved phrase",
      "reason": "Brief explanation (5-10 words)",
      "type": "spelling|grammar|phrasing|structure|completeness"
    }}
  ]
}}

RULES:
1. Fix genuine spelling and grammar errors.
2. Improve phrasing to match standard radiology reporting conventions (e.g. "There is no evidence of" → "No evidence of", "The liver appears normal" → "The liver is unremarkable").
3. Expand common radiology shorthand and abbreviations into full professional terms. Examples:
   - "MM BHT" → "medial meniscus bucket handle tear", "LM" → "lateral meniscus"
   - "ACL" → "anterior cruciate ligament", "PCL" → "posterior cruciate ligament"
   - "#" or "Fx" → "fracture", "NAD" → "no abnormality detected"
   - "HCC" → "hepatocellular carcinoma", "mets" → "metastases", "LN" → "lymph node"
   Use your knowledge of radiology reporting to expand ANY shorthand you recognise.
4. Suggest structural improvements if sections are missing or out of standard order.
5. Do NOT change clinical meaning. Do NOT add findings the user did not describe.
6. Do NOT remove any content the user wrote — only rephrase for clarity and convention.
7. If the report is already well-written, return an empty suggestions array and the original text as improved_report.
8. Each suggestion must quote the EXACT original text so the frontend can locate it.
9. Limit to the most impactful 15 suggestions maximum. Prioritise: abbreviation expansion > spelling > grammar > phrasing > structure.
10. For completeness type: suggest if standard sections (INDICATION, TECHNIQUE, COMPARISON, FINDINGS, IMPRESSION) are missing.

Output ONLY the JSON object. No markdown. No explanation."""


# ==================== TREE GENERATION PROMPT ====================

TREE_PROMPT_TEMPLATE = """You are generating a structured algorithm tree that guides a radiology trainee
through reading a {modality} scan step by step.

CLINICAL QUESTION: {clinical_question}
MODALITY: {modality}
BODY SECTION: {body_section}
{resource_section}
The algorithm tree is a JSON object with this EXACT structure:

{{
  "steps": [
    {{
      "id": "step_1",
      "organ": "Organ or anatomical structure being assessed",
      "question": "What are you looking for at this step?",
      "options": [
        {{
          "label": "Short description of finding (what user clicks)",
          "report_text": "Complete sentence for the PACS report if this option is selected.",
          "next_step": "step_2",
          "findings_flag": "normal"
        }}
      ],
      "allow_multiple": false
    }}
  ],
  "lines_tubes_step": {{
    "id": "lines_tubes",
    "organ": "Lines and devices",
    "question": "Are there any lines, tubes, or surgical devices?",
    "options": [
      {{
        "label": "No lines or tubes",
        "report_text": "No lines, tubes, or surgical devices are identified.",
        "findings_flag": "normal"
      }},
      {{
        "label": "Endotracheal tube",
        "report_text": "An endotracheal tube is present with the tip projected approximately 3 cm above the carina.",
        "findings_flag": "normal"
      }}
    ],
    "allow_multiple": true
  }},
  "incidental_findings_step": {{
    "id": "incidentals",
    "organ": "Incidental findings",
    "question": "Any incidental findings to note?",
    "options": [
      {{
        "label": "No incidental findings",
        "report_text": "",
        "findings_flag": "normal"
      }},
      {{
        "label": "Simple renal cyst",
        "report_text": "Incidental note is made of a simple renal cyst.",
        "findings_flag": "incidental"
      }},
      {{
        "label": "Other (free text)",
        "report_text": "",
        "findings_flag": "incidental",
        "is_free_text": true
      }}
    ],
    "allow_multiple": true
  }},
  "report_template": {{
    "indication": "Clinical indication text derived from the question",
    "technique": "Specific technique description for this modality and body region",
    "comparison": "No prior available for comparison.",
    "impression_normal": "Summary impression if all findings are normal",
    "impression_abnormal": "Summary impression template referencing the key abnormal findings",
    "recommendation": "Standard follow-up recommendation if applicable"
  }}
}}

RULES:
1. Generate 8-15 steps covering the systematic scan reading order for this modality and clinical question.
2. Every step must assess ONE anatomical structure or compartment.
3. Steps must follow the actual order a radiologist reads the scan (not textbook order).
   For example, CT abdomen with clinical question about appendicitis:
   start with the appendix (target organ), then systematically cover remaining bowel,
   solid organs, vasculature, peritoneum, bones, soft tissues.
4. Each option's report_text must be a complete, natural-language PACS-ready sentence.
   Write EXACTLY as a consultant radiologist would dictate — flowing prose, not a label.
   WRONG: "Liver: normal" or "Normal liver"
   RIGHT: "The liver is normal in size and attenuation with no focal lesion identified."
   WRONG: "Spleen enlarged" or "Splenomegaly present"
   RIGHT: "The spleen is mildly enlarged, measuring approximately 14 cm in craniocaudal length."
   Include specific measurements or thresholds where applicable.
5. Use next_step for conditional branching:
   - If a finding is abnormal, next_step should point to a sub-step that characterises it further
     (e.g. abnormal liver → sub-step asking about number, segment, enhancement pattern).
   - If a finding is normal, next_step should be null (engine advances sequentially).
   - Sub-steps for characterisation should eventually rejoin the main sequence via next_step.
6. Include both normal and abnormal options for EVERY step. The normal option should always be first.
7. For normal options, include common normal variants that mimic pathology where relevant
   (e.g. "Prominent peri-portal cuffing — likely normal variant" for liver, or
   "Prominent hilar lymph nodes, within normal limits" for chest).
8. Each step should have 3-6 options (including one free-text option for unusual findings).
9. The last option in each step should be a free-text entry:
   {{"label": "Other (free text)", "report_text": "", "findings_flag": "abnormal", "is_free_text": true}}
10. lines_tubes_step should have 5-8 common options relevant to this modality and body region.
11. incidental_findings_step should have 4-6 common incidental findings for this body region.
12. report_template.indication must include the modality and clinical question.
13. report_template.technique should be specific to this modality (e.g., include contrast phase for CT,
    sequences for MRI, probe frequency for US).
14. Do NOT include pathophysiology, epidemiology, or teaching content in report_text.
    report_text is for the PACS report only — keep it clinical and concise.
15. findings_flag values: "normal", "abnormal", "equivocal", "incidental"
16. Multiple findings for the same organ will be joined into a single paragraph.
    Write report_text sentences that flow naturally when combined with other sentences
    about the same organ. Avoid repeating the organ name redundantly within the same step.

Output ONLY the JSON object. No markdown. No explanation."""


# ==================== INTENT CLASSIFIER (Phase 3) ====================

CLASSIFY_INTENT_SYSTEM_PROMPT = (
    "You classify radiology workstation queries into intent categories. "
    "Output valid JSON only. No markdown. No text outside the JSON object."
)

CLASSIFY_INTENT_PROMPT = """Classify this radiology user query into an intent category.

USER QUERY: {user_input}

Return a JSON object:
{{
  "intent": "walkthrough|report_help|tool_request|reference|protocol|anatomy|paste_report",
  "canonical_topic": "lowercase-hyphenated-slug",
  "display_title": "Human Readable Title",
  "modality": "CT|MRI|US|XR|NM|PET-CT|Fluoroscopy|null",
  "body_section": "Head|Neck|Chest|Abdomen|Pelvis|MSK|Spine|Vascular|Whole Body|null",
  "category": "emergency|oncology|vascular|msk|neuro|general|paediatric|null"
}}

INTENT DEFINITIONS:
- walkthrough: User wants step-by-step guidance reading a scan (e.g. "CT abdomen pancreatitis", "MRI brain headache", "rule out PE")
- report_help: User wants help with an existing report (e.g. "check my report", "write the impression", "fix spelling")
- tool_request: User wants a specific scoring/classification tool (e.g. "Li-RADS", "Bosniak classification", "PI-RADS scoring")
- reference: User wants reference material about a topic (e.g. "Fleischner criteria", "adrenal washout protocol")
- protocol: User wants imaging protocol information (e.g. "CT angiography protocol", "MRI liver protocol")
- anatomy: User wants anatomical reference (e.g. "Circle of Willis anatomy", "brachial plexus")
- paste_report: User indicates they have a report to paste (e.g. "I have a report", "paste my report", "review my report")

CANONICAL TOPIC:
- Normalise to the underlying clinical entity, not the user's exact words
- "Pain in RIF" → "right-iliac-fossa-pain"
- "Rule out PE" → "pulmonary-embolism"
- "CT abdomen, known pancreatic mass" → "pancreatic-mass-staging"
- "CT abdomen" (no clinical context) → "ct-abdomen-systematic"
- "Li-RADS scoring" → "li-rads"

Output ONLY the JSON object."""


def classify_intent(user_input):
    """
    Classify user input into an intent category for routing.
    Uses Haiku for speed and cost efficiency (~200ms, minimal cost).

    Args:
        user_input: Raw text from the Smart Reporter search bar

    Returns:
        dict with: intent, canonical_topic, display_title, modality, body_section, category
    """
    haiku_model = os.getenv("CLAUDE_QUICK_MODEL", "claude-haiku-4-5-20251001")

    prompt = CLASSIFY_INTENT_PROMPT.format(user_input=user_input)

    text, model, tokens = _call_claude(
        system_prompt=CLASSIFY_INTENT_SYSTEM_PROMPT,
        user_prompt=prompt,
        model=haiku_model,
        max_tokens=500,
        temperature=0.1,
        timeout=10,
        skip_preamble=True,
    )

    parsed = _parse_json_response(text)

    # Ensure all expected keys exist with defaults
    parsed.setdefault('intent', 'walkthrough')
    parsed.setdefault('canonical_topic', '')
    parsed.setdefault('display_title', user_input)
    parsed.setdefault('modality', None)
    parsed.setdefault('body_section', None)
    parsed.setdefault('category', None)

    # Validate intent is one of the allowed values
    valid_intents = {'walkthrough', 'report_help', 'tool_request', 'reference',
                     'protocol', 'anatomy', 'paste_report'}
    if parsed['intent'] not in valid_intents:
        parsed['intent'] = 'walkthrough'

    parsed['model'] = model
    parsed['token_count'] = tokens

    return parsed


# ==================== ANATOMY REFERENCE (Phase 5 — upgraded) ====================

from ai_pearl_generator import (
    _esc, _card_open, _card_open_custom, _card_close,
    fetch_radiopaedia_image, fetch_radiopaedia_images,
    render_reference_images_html,
)

ANATOMY_SYSTEM_PROMPT = (
    "You are a senior consultant radiologist creating a concise anatomy reference card "
    "for radiology registrars and consultants. You have reported thousands of studies "
    "and know which anatomical knowledge actually matters at the workstation.\n\n"
    "Focus ONLY on clinically and radiologically relevant anatomy:\n"
    "- Describe anatomy as it appears on imaging, not cadaveric dissection\n"
    "- Only mention modality-specific appearances when they are UNUSUAL, DIAGNOSTIC, "
    "or a COMMON SOURCE OF CONFUSION (e.g. melanoma mets T1 hyperintense — useful; "
    "air is T1 hypointense — waste of space)\n"
    "- Emphasise normal variants that mimic pathology and cause reporting errors\n"
    "- Include measurements with actionable thresholds\n"
    "- Brief embryology ONLY when it explains why a variant exists\n\n"
    "FACTUAL ACCURACY RULES (CRITICAL):\n"
    "- Do NOT fabricate measurements, prevalences, or thresholds. Every number you "
    "state must reflect established medical literature.\n"
    "- If you are uncertain about a specific number, state uncertainty explicitly "
    "(e.g. 'approximately', 'reported range varies in the literature', 'up to').\n"
    "- Ground your knowledge in standard radiology textbooks: Defined Anatomy by Weir & Abrahams, "
    "Chapman & Nakielny's Aids to Radiological Differential Diagnosis, "
    "Defined Anatomy for Image Interpretation, Gray's Anatomy, "
    "Defined Anatomy (Butler, Mitchell & Healy), "
    "Defined Anatomy for Diagnostic Imaging (Ryan, McNicholas & Eustace), "
    "Defined Anatomy for FRCR Part 1 (Defined by Defined Publishers).\n"
    "- Do NOT invent classification systems, grading scales, or named signs "
    "that do not exist in indexed medical literature.\n\n"
    "You produce ONLY valid JSON. No markdown fences, no explanation outside the JSON.\n"
    "Use UK English spelling."
)

ANATOMY_PROMPT = """Generate a radiology anatomy reference card for: {topic}
Modality context: {modality}
Body region: {body_section}

Return a JSON object:

{{
  "title": "Concise title (e.g. 'Circle of Willis — Neurovascular Anatomy')",
  "overview": "2-3 sentences: what this anatomy is and why radiologists must know it",
  "key_structures": [
    {{
      "name": "Structure name",
      "imaging_landmark": "How to find it on cross-sectional imaging",
      "relationships": "What lies adjacent (anterior, posterior, medial, lateral)",
      "reporting_relevance": "Why this structure matters in a radiology report"
    }}
  ],
  "normal_variants": [
    {{
      "variant": "Variant name",
      "prevalence": "Approximate prevalence",
      "why_it_exists": "Brief embryological/developmental explanation (1 sentence)",
      "imaging_pitfall": "How this mimics pathology or causes reporting errors"
    }}
  ],
  "measurements": [
    {{
      "what": "Structure to measure",
      "normal": "Normal range with units",
      "abnormal_threshold": "When to flag and what to recommend"
    }}
  ],
  "diagnostic_appearances": [
    {{
      "finding": "The unusual/diagnostic appearance",
      "modality": "Which modality",
      "significance": "What it means or what it gets confused with"
    }}
  ],
  "pathology_at_this_site": [
    {{
      "pathology": "Common pathology",
      "key_finding": "The imaging finding",
      "clinical_question": "What the referrer needs answered"
    }}
  ],
  "pearls": [
    "High-yield reporting tip, mnemonic, or pitfall — one per item"
  ],
  "image_captions": [
    "Brief clinical description of what a reference image at this anatomical site would show (1-2 sentences). Describe the specific imaging appearance, modality, and diagnostic significance. Provide 1-3 captions."
  ],
  "verifiable_claims": [
    {{
      "claim": "The specific factual statement you are making (e.g. 'Fetal-type PCoA is present in 20-32% of individuals')",
      "type": "prevalence|measurement|threshold|classification|incidence|dose",
      "search_terms": "Optimised PubMed search terms to verify this claim (e.g. 'fetal posterior communicating artery prevalence')"
    }}
  ]
}}

RULES:
- 3-6 key structures, 2-5 normal variants, 2-4 measurements
- Only 2-3 diagnostic appearances (the genuinely unusual/tricky ones)
- 3-5 pathologies, 3-5 pearls
- Every fact must be radiologically accurate — do not fabricate prevalences or measurements
- Skip any section with nothing genuinely useful to add
- If modality context is provided, tailor content to that modality
- NO generic imaging descriptions (do NOT describe normal CT density or normal MRI signal unless it is diagnostically relevant or confusing)

VERIFIABLE CLAIMS:
- List EVERY factual assertion that includes a specific number, percentage, measurement, or named classification threshold
- Include prevalences, normal ranges, abnormal thresholds, incidence rates, and dose values
- Provide PubMed-optimised search terms for each claim (medical terminology, not lay language)
- This helps users verify your content against indexed literature — be thorough and honest"""


def render_anatomy_html(data, radiopaedia_image=None, reference_images=None):
    """Render structured anatomy JSON into Bootstrap 5 card HTML.

    Args:
        data: Parsed JSON dict from Claude
        radiopaedia_image: DEPRECATED — single image dict (backward compat)
        reference_images: List of normalised image dicts for multi-image rendering
    """
    parts = []

    title = data.get('title', '')
    if title:
        parts.append(f'<h3 class="mb-3">{_esc(title)}</h3>')

    # Overview — teal
    overview = data.get('overview', '')
    if overview:
        parts.append(_card_open_custom('#5E899E', 'fa-bone', 'Overview'))
        parts.append(f'<p class="mb-0">{_esc(overview)}</p>')
        parts.append(_card_close())

    # Key Structures — blue
    structures = data.get('key_structures', [])
    if structures:
        parts.append(_card_open('primary', 'fa-crosshairs', 'Key Structures'))
        parts.append(
            '<div class="table-responsive"><table class="table table-sm table-bordered mb-0">'
            '<thead><tr><th>Structure</th><th>Imaging Landmark</th>'
            '<th>Relationships</th><th>Reporting Relevance</th></tr></thead><tbody>'
        )
        for s in structures:
            parts.append(
                f'<tr><td><strong>{_esc(s.get("name", ""))}</strong></td>'
                f'<td>{_esc(s.get("imaging_landmark", ""))}</td>'
                f'<td>{_esc(s.get("relationships", ""))}</td>'
                f'<td>{_esc(s.get("reporting_relevance", ""))}</td></tr>'
            )
        parts.append('</tbody></table></div>')
        parts.append(_card_close())

    # Normal Variants — amber/warning
    variants = data.get('normal_variants', [])
    if variants:
        parts.append(_card_open('warning', 'fa-exclamation-triangle', 'Normal Variants &amp; Pitfalls'))
        parts.append(
            '<div class="table-responsive"><table class="table table-sm table-bordered mb-0">'
            '<thead><tr><th>Variant</th><th>Prevalence</th>'
            '<th>Why It Exists</th><th>Imaging Pitfall</th></tr></thead><tbody>'
        )
        for v in variants:
            parts.append(
                f'<tr><td><strong>{_esc(v.get("variant", ""))}</strong></td>'
                f'<td>{_esc(v.get("prevalence", ""))}</td>'
                f'<td>{_esc(v.get("why_it_exists", ""))}</td>'
                f'<td>{_esc(v.get("imaging_pitfall", ""))}</td></tr>'
            )
        parts.append('</tbody></table></div>')
        parts.append(_card_close())

    # Measurements — green/success
    measurements = data.get('measurements', [])
    if measurements:
        parts.append(_card_open('success', 'fa-ruler', 'Measurements'))
        parts.append(
            '<div class="table-responsive"><table class="table table-sm table-bordered mb-0">'
            '<thead><tr><th>What</th><th>Normal</th>'
            '<th>Abnormal Threshold</th></tr></thead><tbody>'
        )
        for m in measurements:
            parts.append(
                f'<tr><td><strong>{_esc(m.get("what", ""))}</strong></td>'
                f'<td>{_esc(m.get("normal", ""))}</td>'
                f'<td>{_esc(m.get("abnormal_threshold", ""))}</td></tr>'
            )
        parts.append('</tbody></table></div>')
        parts.append(_card_close())

    # Diagnostic Appearances — purple
    appearances = data.get('diagnostic_appearances', [])
    if appearances:
        parts.append(_card_open_custom('#6b46c1', 'fa-eye', 'Diagnostic Appearances'))
        parts.append(
            '<div class="table-responsive"><table class="table table-sm table-bordered mb-0">'
            '<thead><tr><th>Finding</th><th>Modality</th>'
            '<th>Significance</th></tr></thead><tbody>'
        )
        for a in appearances:
            parts.append(
                f'<tr><td><strong>{_esc(a.get("finding", ""))}</strong></td>'
                f'<td>{_esc(a.get("modality", ""))}</td>'
                f'<td>{_esc(a.get("significance", ""))}</td></tr>'
            )
        parts.append('</tbody></table></div>')
        parts.append(_card_close())

    # Pathology at This Site — red/danger
    pathologies = data.get('pathology_at_this_site', [])
    if pathologies:
        parts.append(_card_open('danger', 'fa-search', 'Pathology at This Site'))
        parts.append(
            '<div class="table-responsive"><table class="table table-sm table-bordered mb-0">'
            '<thead><tr><th>Pathology</th><th>Key Finding</th>'
            '<th>Clinical Question</th></tr></thead><tbody>'
        )
        for p in pathologies:
            parts.append(
                f'<tr><td><strong>{_esc(p.get("pathology", ""))}</strong></td>'
                f'<td>{_esc(p.get("key_finding", ""))}</td>'
                f'<td>{_esc(p.get("clinical_question", ""))}</td></tr>'
            )
        parts.append('</tbody></table></div>')
        parts.append(_card_close())

    # Pearls — dark
    pearls = data.get('pearls', [])
    if pearls:
        parts.append(_card_open('dark', 'fa-lightbulb', 'Pearls'))
        parts.append('<ul class="mb-0">')
        for tip in pearls:
            parts.append(f'<li>{_esc(tip)}</li>')
        parts.append('</ul>')
        parts.append(_card_close())

    # Reference Images (multi-image or legacy single)
    captions = data.get('image_captions', [])
    if reference_images:
        parts.append(render_reference_images_html(reference_images, captions))
    elif radiopaedia_image:
        # Backward compat: convert legacy single image dict to list format
        legacy = {
            'url': radiopaedia_image.get('thumbnail_link') or radiopaedia_image.get('link', ''),
            'title': radiopaedia_image.get('title', 'Radiopaedia Case'),
            'case_url': radiopaedia_image.get('case_url', ''),
            'license': radiopaedia_image.get('license', 'CC BY-NC-SA 3.0'),
            'author': radiopaedia_image.get('author'),
            'source_domain': 'radiopaedia.org',
        }
        parts.append(render_reference_images_html([legacy], captions))

    return '\n'.join(parts)


def generate_anatomy_reference(topic, modality='', body_section='', additional_context=''):
    """
    Generate a structured anatomy reference card.
    Uses Sonnet for quality. DB lookup should be attempted first (in routes).

    Returns:
        dict with: title, content_html, source, model, token_count, radiopaedia_image
    """
    sonnet_model = os.getenv("CLAUDE_MODEL", "claude-sonnet-4-5-20250929")

    prompt = ANATOMY_PROMPT.format(
        topic=topic,
        modality=modality or 'not specified',
        body_section=body_section or 'not specified',
    )
    if additional_context:
        prompt += (
            f"\n\n=== ADDITIONAL CONTEXT PROVIDED BY ADMIN ===\n"
            f"{additional_context}\n"
            f"=== END CONTEXT ===\n\n"
            f"Use the above as preferred references to enrich and ground your output. "
            f"Cite specific details from these sources where relevant, but also draw on "
            f"your broader medical knowledge — do not limit your response exclusively to "
            f"these references."
        )

    text, model, tokens = _call_claude(
        system_prompt=ANATOMY_SYSTEM_PROMPT,
        user_prompt=prompt,
        model=sonnet_model,
        max_tokens=8000,
        temperature=0,
        timeout=150,
    )

    parsed = _parse_json_response(text)

    # If JSON was truncated (max_tokens hit), retry with conciseness instruction
    if not parsed and text and text.strip().startswith('{'):
        logger.warning("Anatomy JSON truncated for '%s' — retrying with conciseness instruction", topic)
        concise_prompt = prompt + (
            "\n\nIMPORTANT: Your previous response was too long and got truncated. "
            "Be MORE CONCISE this time. Limit key_structures to the 10 most important. "
            "Keep each field to 1 sentence. Limit normal_variants to 5. "
            "Limit pathology_at_this_site to 5."
        )
        text, model, tokens = _call_claude(
            system_prompt=ANATOMY_SYSTEM_PROMPT,
            user_prompt=concise_prompt,
            model=sonnet_model,
            max_tokens=8000,
            temperature=0,
            timeout=150,
        )
        parsed = _parse_json_response(text)

    # Auto-fetch Radiopaedia case images for visual reference (separate from peer review)
    rp_images = fetch_radiopaedia_images(topic, modality=modality, max_images=3)
    logger.info(f"Radiopaedia images for '{topic}': {len(rp_images)} found")

    # Render anatomy HTML with case images (if any — no fake search link fallback)
    content_html = render_anatomy_html(
        parsed,
        reference_images=rp_images if rp_images else None,
    )

    # --- RadInsight Peer Review ---
    # Verifies numerical claims via PubMed, adds verified Radiopaedia article link,
    # injects verification badges, disclaimer, and reference section.
    try:
        from radinsight_peer_review import peer_review_anatomy
        pr = peer_review_anatomy(parsed, content_html, topic=topic,
                                 body_section=body_section, modality=modality)
        content_html = pr['content_html']
        logger.info(
            "Peer review for '%s': %d/%d claims verified",
            topic,
            pr['verification_summary'].get('verified', 0),
            pr['verification_summary'].get('total', 0),
        )
    except Exception as exc:
        logger.warning("Peer review failed for '%s', using unverified HTML: %s", topic, exc)

    return {
        'title': parsed.get('title', topic.title()),
        'content_html': content_html,
        'source': 'ai',
        'model': model,
        'token_count': tokens,
        'radiopaedia_image': rp_images[0] if rp_images else None,  # backward compat
        'radiopaedia_images': rp_images,
    }


# ==================== BLANK TEMPLATE (Gap 3) ====================

BLANK_TEMPLATE_SYSTEM_PROMPT = (
    "You generate structured but empty radiology reporting templates. "
    "The template has section headings and placeholder guidance but NO findings. "
    "The radiologist will fill in their own findings. "
    "Output plain text only. No markdown. No HTML."
)

BLANK_TEMPLATE_PROMPT = """Generate a blank structured PACS reporting template for:

MODALITY: {modality}
BODY SECTION: {body_section}
CLINICAL QUESTION: {clinical_question}

Output a template with these sections:
INDICATION:
(Pre-fill with the modality and clinical question)

TECHNIQUE:
(Pre-fill with standard technique for this modality and body region)

COMPARISON:
No prior available for comparison.

FINDINGS:
(List the organ/structure subheadings a radiologist should systematically assess,
each followed by an empty line for the radiologist to fill in. Order them in standard
reading order for this modality/region. Include 6-10 subheadings.)

IMPRESSION:
(Leave empty — radiologist will write after completing findings)

Output the template as plain text. Each section heading on its own line followed by a colon.
Subheadings under FINDINGS should be indented or numbered."""


def generate_blank_template(modality='', body_section='', clinical_question=''):
    """
    Generate a structured blank reporting template for the abort-walkthrough flow (Gap 3).
    Uses Haiku for speed (~3-5s).

    Args:
        modality: e.g. "CT", "MRI"
        body_section: e.g. "Abdomen", "Brain"
        clinical_question: e.g. "Rule out appendicitis"

    Returns:
        dict with: template_text, model, token_count
    """
    haiku_model = os.getenv("CLAUDE_QUICK_MODEL", "claude-haiku-4-5-20251001")

    prompt = BLANK_TEMPLATE_PROMPT.format(
        modality=modality or 'Not specified',
        body_section=body_section or 'Not specified',
        clinical_question=clinical_question or 'Not specified',
    )

    text, model, tokens = _call_claude(
        system_prompt=BLANK_TEMPLATE_SYSTEM_PROMPT,
        user_prompt=prompt,
        model=haiku_model,
        max_tokens=1500,
        temperature=0.2,
        timeout=15,
        skip_preamble=True,
    )

    return {
        'template_text': text,
        'model': model,
        'token_count': tokens,
    }


# ==================== RADIOLOGY TEMPLATE GENERATOR ====================

RADIOLOGY_TEMPLATE_SYSTEM_PROMPT = (
    "You are an expert consultant radiologist writing structured PACS report templates. "
    "You produce clinically accurate, scenario-specific radiology report templates that are "
    "ready for copy-paste into a PACS reporting system. Templates must follow standard "
    "radiology reporting conventions with appropriate normal findings boilerplate and "
    "key positive/negative findings relevant to the clinical scenario. "
    "Output plain text only. No markdown formatting. No HTML tags."
)

RADIOLOGY_TEMPLATE_PROMPT = """Generate a structured radiology report template for the following clinical scenario:

CLINICAL SCENARIO: {clinical_scenario}
MODALITY: {modality}
BODY SECTION: {body_section}

{resources_section}

Output the template with EXACTLY these section headings (each on its own line, followed by a colon):

STUDY:
(Full study title, e.g. "CT Abdomen and Pelvis with IV Contrast")

INDICATION:
(Pre-fill with the clinical context for this scenario. Be specific but concise.)

COMPARISON:
No prior available for comparison.

TECHNIQUE:
(Standard technique for this modality/region. Keep concise — 2-3 lines max. Include key parameters like contrast, sequences, or views.)

FINDINGS:
(Systematic organ-by-organ or structure-by-structure assessment in standard reading order for this modality/region. For each structure:
- Include normal boilerplate text as default
- For structures relevant to the clinical scenario, include both normal and abnormal descriptors that a radiologist might select/edit
- Use standard radiology terminology and measurements where appropriate
- Include 8-12 subheadings appropriate to the body region
- Each subheading should be on its own line followed by a colon, then the finding text on the next line)

IMPRESSION:
(Numbered impression points. Include 2-4 key findings relevant to this clinical scenario. Use standard impression language.)

RECOMMENDATIONS:
(Follow-up recommendations if clinically appropriate for this scenario. If none needed, write "Clinical correlation recommended.")

RULES:
- Use standard radiology abbreviations where appropriate
- Include measurement placeholders where relevant (e.g. "[x.x cm]")
- Write findings in present tense, third person
- Be specific to the clinical scenario — this is NOT a blank template
- If reference materials are provided, incorporate their guidance into findings and recommendations"""


def generate_radiology_template(clinical_scenario, modality='', body_section='', resources=None):
    """
    Generate a clinical-scenario-specific radiology report template.
    Unlike generate_blank_template() which produces empty scaffolding,
    this produces a filled template with standard normal findings and
    key positive/negative findings relevant to the clinical scenario.

    Uses Sonnet for quality. Accepts resources (URLs, PDFs, DB refs).

    Args:
        clinical_scenario: e.g. "CT Abdomen — Acute Pancreatitis"
        modality: e.g. "CT", "MRI", "US"
        body_section: e.g. "Abdomen", "Brain"
        resources: Optional dict with urls, db_refs, pdf_texts, tnm_refs

    Returns:
        dict with: template_text, model, token_count
    """
    # Format resources for prompt injection if provided
    resources_section = ''
    if resources:
        try:
            resources_section = format_resources_for_prompt(resources)
        except Exception:
            logger.warning("Resource formatting failed")

    prompt = RADIOLOGY_TEMPLATE_PROMPT.format(
        clinical_scenario=clinical_scenario or 'Not specified',
        modality=modality or 'Not specified',
        body_section=body_section or 'Not specified',
        resources_section=resources_section,
    )

    sonnet_model = os.getenv("CLAUDE_MODEL", "claude-sonnet-4-5-20250929")

    text, model, tokens = _call_claude(
        system_prompt=RADIOLOGY_TEMPLATE_SYSTEM_PROMPT,
        user_prompt=prompt,
        model=sonnet_model,
        max_tokens=3000,
        temperature=0.3,
        timeout=60,
    )

    return {
        'template_text': text,
        'model': model,
        'token_count': tokens,
    }


# ==================== MAIN GENERATOR ====================

def generate_algorithm_tree(clinical_question, modality, body_section='', resources=None):
    """
    Generate a structured algorithm tree for interactive scan reading walkthrough.

    Args:
        clinical_question: The clinical question (e.g. "Rule out acute pancreatitis")
        modality: Imaging modality (e.g. "CT", "MRI", "US")
        body_section: Anatomical region (optional)
        resources: Optional dict with urls, db_refs, pdf_texts, tnm_refs (Gap 1)

    Returns:
        dict with: steps, lines_tubes_step, incidental_findings_step, report_template,
        model, token_count, provider
    """
    resource_section = format_resources_for_prompt(resources)

    user_prompt = TREE_PROMPT_TEMPLATE.format(
        clinical_question=clinical_question,
        modality=modality or 'Not specified',
        body_section=body_section or 'Infer from clinical question',
        resource_section=resource_section,
    )

    text, model, tokens = _call_claude(
        system_prompt=TREE_SYSTEM_PROMPT,
        user_prompt=user_prompt,
        max_tokens=6000,
        temperature=0.3,
        timeout=150,
    )

    parsed = _parse_tree_response(text)
    parsed['model'] = model
    parsed['token_count'] = tokens
    parsed['provider'] = 'claude'

    return parsed


# ==================== ASK CLAUDE HELPER (DEPRECATED) ====================

def ask_claude_about_report(current_report, question):
    """
    DEPRECATED: Use unified_ai_assist() instead.
    Kept for backward compatibility with existing routes.

    Lightweight Q&A for Scene 2 report editing.
    """
    logger.warning("ask_claude_about_report() is deprecated. Use unified_ai_assist() instead.")

    user_message = f"""Here is the current draft PACS report:

---
{current_report}
---

Trainee's question: {question}"""

    text, model, tokens = _call_claude(
        system_prompt=ASK_CLAUDE_SYSTEM_PROMPT,
        user_prompt=user_message,
        max_tokens=1500,
        temperature=0.3,
        timeout=30,
    )

    return {
        'answer': text,
        'model': model,
        'token_count': tokens,
    }


# ==================== REVIEW REPORT ====================

def review_report(report_text):
    """
    Review a report for spelling, grammar, phrasing, and structure.

    Returns:
        dict with: improved_report, suggestions[], model, token_count
    """
    user_prompt = REVIEW_REPORT_PROMPT.format(report_text=report_text)

    text, model, tokens = _call_claude(
        system_prompt=REVIEW_REPORT_SYSTEM_PROMPT,
        user_prompt=user_prompt,
        max_tokens=4000,
        temperature=0.2,
        timeout=60,
    )

    parsed = _parse_review_response(text)
    parsed['model'] = model
    parsed['token_count'] = tokens

    return parsed


# ==================== QUICK REVIEW (Layer 0) ====================

def quick_review(report_text):
    """
    Lightweight proofreading: spelling, grammar, phrasing only.
    Uses Haiku for cost efficiency. No clinical assessment.

    Returns:
        dict with: improved_report, suggestions[], model, token_count
    """
    haiku_model = os.getenv("CLAUDE_QUICK_MODEL", "claude-haiku-4-5-20251001")

    user_prompt = QUICK_REVIEW_PROMPT.format(report_text=report_text)

    text, model, tokens = _call_claude(
        system_prompt=QUICK_REVIEW_SYSTEM_PROMPT,
        user_prompt=user_prompt,
        model=haiku_model,
        max_tokens=2000,
        temperature=0.2,
        timeout=20,
    )

    parsed = _parse_review_response(text)
    parsed['model'] = model
    parsed['token_count'] = tokens

    return parsed


# ==================== SAFETY BLOCKER DETECTION ====================

# --- Soft warning detection via corrections + answer text ---
# Urgency words the AI adds when fixing weak recommendations
_URGENCY_ADDITIONS = [
    'urgent', 'immediate', 'emergent', 'stat', 'thrombolysis',
    'verbal communication', 'verbally communicated', 'notify',
    'alert', 'escalat', 'life-threatening', 'time-critical',
    'time-sensitive', 'critical care', 'stroke team',
    'on-call', 'theatre', 'surgical emergency',
]

# Words in the answer text that signal the AI thought the draft had
# a significant interpretation or diagnostic problem
_ANSWER_CONCERN_SIGNALS = [
    'incorrect', 'wrong diagnosis', 'misinterpret', 'erroneous',
    'would not sign', 'does not support', 'not consistent with',
    'disagree with', 'overcall', 'undercall', 'missed finding',
    'missed diagnosis', 'important omission', 'significant omission',
    'changed the diagnosis', 'changed the impression',
    'revised the impression', 'impression does not match',
]


def _detect_safety_blockers(parsed, original_draft=''):
    """Post-process parsed AI response to detect hard blockers and soft warnings.

    Hard blockers (laterality, impression-body contradiction) come from
    structured correction types — reliable signal.

    Soft warnings come from three concrete signals:
    1. Escalation: the AI's correction *added* urgency language that was
       absent in the original — meaning the draft lacked proper escalation.
    2. Escalation (report-level): the finalized report_text contains urgency
       language that is absent from the original draft — the AI added it
       during the rewrite, not via a discrete correction.
    3. Interpretation: the AI's answer text describes a diagnostic concern
       about the draft.

    Mutates *parsed* in place, adding 'hard_blockers' and 'soft_warnings' lists.
    """
    hard_blockers = []
    soft_warnings = []

    # --- Hard blockers from corrections (structured types) ---
    for c in parsed.get('corrections', []):
        ctype = c.get('type', '')
        if ctype == 'sidedness':
            hard_blockers.append(
                f"Laterality issue: {c.get('reason', 'side mismatch detected')}"
            )
        elif ctype == 'consistency':
            hard_blockers.append(
                f"Impression-body contradiction: {c.get('reason', 'inconsistency detected')}"
            )

    # --- Soft: escalation added by correction ---
    # If the AI's suggested text introduces urgency words that weren't in
    # the original, the draft was missing critical escalation language.
    escalation_found = False
    for c in parsed.get('corrections', []):
        original = (c.get('original') or '').lower()
        suggested = (c.get('suggested') or '').lower()
        for kw in _URGENCY_ADDITIONS:
            if kw in suggested and kw not in original:
                soft_warnings.append(
                    f"Escalation concern: {c.get('reason', 'Urgent language was added to your draft')}"
                )
                escalation_found = True
                break  # one warning per correction

    # --- Soft: escalation added in full rewrite (no discrete correction) ---
    # When response_type is full_report the AI may rewrite the whole report
    # with urgency language baked in, without a separate correction entry.
    if not escalation_found and original_draft:
        draft_lower = original_draft.lower()
        finalized = (parsed.get('report_text') or '').lower()
        if finalized:
            for kw in _URGENCY_ADDITIONS:
                if kw in finalized and kw not in draft_lower:
                    # Build a meaningful message from the recommendation_check
                    # insight (which is about the corrected report) or fallback.
                    rec_insight = (parsed.get('insights', {})
                                   .get('recommendation_check') or '')
                    msg = rec_insight if rec_insight else (
                        'The AI added urgent escalation language that was '
                        'absent from your original draft'
                    )
                    soft_warnings.append(f"Escalation concern: {msg}")
                    break

    # --- Soft: interpretation concern from answer text ---
    # The answer describes what the AI changed and WHY — it's written about
    # the draft's deficiencies, not the corrected report.
    answer = (parsed.get('answer') or '').lower()
    for signal in _ANSWER_CONCERN_SIGNALS:
        if signal in answer:
            # Extract a short excerpt around the signal for context
            idx = answer.index(signal)
            start = max(0, answer.rfind('.', 0, idx) + 1)
            end = answer.find('.', idx)
            if end < 0:
                end = min(len(answer), idx + 120)
            else:
                end += 1
            excerpt = parsed.get('answer', '')[start:end].strip()
            soft_warnings.append(f"Interpretation concern: {excerpt}")
            break  # one interpretation warning is enough

    # Deduplicate while preserving order
    parsed['hard_blockers'] = list(dict.fromkeys(hard_blockers))
    parsed['soft_warnings'] = list(dict.fromkeys(soft_warnings))


# ==================== UNIFIED AI ASSIST (Layers 1+2+3) ====================

def unified_ai_assist(report_text, question, clinical_question='', modality='',
                      body_section='', external_context=None, resources=None,
                      has_finalized_report=False, previous_insights=None,
                      model_override=None):
    """
    Unified AI assistant: corrections + direct answer + clinical insights.
    Single API call returns all three layers.

    Args:
        report_text: The current draft PACS report
        question: The trainee's question
        clinical_question: The clinical indication (from session)
        modality: Imaging modality (from session)
        body_section: Anatomical region (from session)
        external_context: Optional dict with {type, title, slug, id} from "Use in Report" buttons
        resources: Optional dict with urls, db_refs, pdf_texts, tnm_refs (Gap 1)
        previous_insights: Optional dict of insights from a prior review (hybrid mode).
                          When present, gives the model the benefit of deep clinical reasoning.
        model_override: Optional model ID (e.g. 'claude-opus-4-6') to override the default.

    Returns:
        dict with: corrections[], answer, insights{}, model, token_count
    """
    # Build resource section from explicit resources AND external context
    resource_section = format_resources_for_prompt(resources)

    # Append external context if user arrived from another tool
    if external_context and isinstance(external_context, dict):
        ctx_type = external_context.get('type', '')
        ctx_title = external_context.get('title', '')
        if ctx_type and ctx_title:
            context_labels = {
                'if': 'Incidental Findings calculator',
                'tnm': 'TNM Staging calculator',
                'template': 'Reporting Template',
                'protocol': 'Clinical Protocol',
            }
            label = context_labels.get(ctx_type, ctx_type)
            resource_section += (
                f"\nADDITIONAL CONTEXT: The user is reporting on a case related to "
                f"{label}: \"{ctx_title}\". Factor this into your corrections, answer, and insights.\n"
            )

    # Inject previous V2 insights if available (hybrid mode)
    if previous_insights and isinstance(previous_insights, dict):
        parts = []
        if previous_insights.get('cognitive_traps'):
            parts.append(f"Cognitive traps identified: {previous_insights['cognitive_traps']}")
        if previous_insights.get('clinical_question_coverage'):
            parts.append(f"Clinical question coverage: {previous_insights['clinical_question_coverage']}")
        if previous_insights.get('quality_assessment'):
            parts.append(f"Quality assessment: {previous_insights['quality_assessment']}")
        if previous_insights.get('differentials_to_consider'):
            diffs = previous_insights['differentials_to_consider']
            if isinstance(diffs, list):
                diffs = ', '.join(diffs)
            parts.append(f"Differentials to consider: {diffs}")
        if previous_insights.get('teaching_point'):
            parts.append(f"Teaching point: {previous_insights['teaching_point']}")
        if parts:
            resource_section += (
                "\nPREVIOUS CLINICAL REVIEW (from an earlier deep review of this report):\n"
                + "\n".join(f"- {p}" for p in parts)
                + "\nUse these insights to inform your answer. Do not contradict them "
                "unless the trainee has since corrected the issue.\n"
            )

    # Build report status section for advisory-only follow-up mode
    if has_finalized_report:
        report_status_section = (
            "\n⚠️ REPORT STATUS: ALREADY_FINALIZED\n"
            "The trainee already has a finalized report. This is a FOLLOW-UP question.\n"
            "You MUST use response_type: \"advisory\" and report_text: \"\" (empty string).\n"
            "Put your entire answer in the \"answer\" field. Do NOT regenerate or rewrite the report.\n"
            "The ONLY exception: if the trainee explicitly says \"finalize\", \"rewrite\", or \"redo\"."
        )
    else:
        report_status_section = (
            "\nREPORT STATUS: NOT_YET_FINALIZED — The trainee has not yet received a finalized report."
        )

    # Select prompts: V3 for Opus, V1 for everything else
    if model_override and 'opus' in model_override:
        selected_system_prompt = UNIFIED_ASSIST_V3_SYSTEM_PROMPT
        prompt_template = UNIFIED_ASSIST_V3_PROMPT
    else:
        selected_system_prompt = UNIFIED_ASSIST_SYSTEM_PROMPT
        prompt_template = UNIFIED_ASSIST_PROMPT

    user_prompt = prompt_template.format(
        report_text=report_text or '(empty report — user may be starting fresh or about to paste their report)',
        question=question,
        clinical_question=clinical_question or 'Not specified',
        modality=modality or 'Not specified',
        body_section=body_section or 'Not specified',
        resource_section=resource_section,
        report_status_section=report_status_section,
    )

    effective_model = model_override or os.getenv("CLAUDE_MODEL", "claude-sonnet-4-5-20250929")

    # Opus (finalize/review): lower temperature for consistent, reproducible output
    # Sonnet (advisory/follow-up): slightly higher for natural knowledge responses
    _temperature = 0.1 if (model_override and 'opus' in model_override) else 0.3

    text, model, tokens = _call_claude(
        system_prompt=selected_system_prompt,
        user_prompt=user_prompt,
        model=effective_model,
        max_tokens=4000,
        temperature=_temperature,
        timeout=90,
    )

    # Capture input tokens from last API call for cost tracking
    _last_usage = getattr(_call_claude_raw, 'last_usage', {})
    _input_tokens = _last_usage.get('input_tokens', 0)

    parsed = _parse_assist_response(text, question)
    parsed['model'] = model
    parsed['token_count'] = tokens
    parsed['input_tokens'] = _input_tokens
    parsed['output_tokens'] = tokens
    if model_override and 'opus' in model_override:
        parsed['version'] = 'opus'
        # Ensure cognitive_traps field exists (V3 schema includes it)
        raw_insights = parsed.get('insights', {})
        if isinstance(raw_insights, dict):
            raw_insights.setdefault('cognitive_traps', '')

    _detect_safety_blockers(parsed, original_draft=report_text)
    return parsed


# ==================== UNIFIED AI ASSIST V3 — OPUS-OPTIMISED ====================
#
# V3 is a dedicated prompt for Opus 4.6. Combines V2's clinical reasoning chain
# with V1's critical edge-case rules, in a concise format that leverages Opus's
# stronger native reasoning. ~1,550 total tokens vs V1's ~2,700.

UNIFIED_ASSIST_V3_SYSTEM_PROMPT = (
    "You are an expert subspecialty consultant radiologist mentoring a trainee at "
    "the PACS workstation. You review their draft report, answer their question, "
    "and provide clinical quality assessment.\n\n"

    "Before producing output, reason through these steps internally:\n\n"
    "STEP 1 — UNDERSTAND THE CLINICAL SCENARIO:\n"
    "  What is the referrer actually asking? What clinical decision depends on this scan?\n"
    "  What diagnosis is the referrer worried about? What would change management?\n\n"
    "STEP 2 — ANALYSE THE FINDINGS:\n"
    "  What has the trainee described? Build a mental picture of the pathology.\n"
    "  What is the most likely diagnosis? Are there findings that don't fit?\n\n"
    "STEP 3 — ASSESS REPORT QUALITY AS A CONSULTANT WHO MUST SIGN THIS:\n"
    "  Does this report answer the referrer's clinical question?\n"
    "  Would a surgeon/oncologist/physician make the right decision from this report?\n"
    "  Which specific guidelines or criteria apply? "
    "(Fleischner, LI-RADS, Bosniak, NCCN, AAST — apply whichever is relevant)\n\n"
    "STEP 4 — IDENTIFY COGNITIVE TRAPS:\n"
    "  Satisfaction of search, anchoring, premature closure — specific to this case.\n"
    "  Frame as 'ensure you have assessed X', NOT 'you missed X'.\n\n"
    "STEP 5 — THEN AND ONLY THEN, PRODUCE YOUR OUTPUT.\n"
    "  Every suggestion must be traceable to clinical reasoning, not pattern matching.\n\n"

    "ABSOLUTE GUARD RAILS — THESE OVERRIDE EVERYTHING:\n"
    "- NEVER add findings the trainee didn't describe — you cannot see the images\n"
    "- NEVER fabricate or hallucinate imaging findings\n"
    "- NEVER assert imaging characteristics (margins, enhancement, attenuation) unless "
    "the trainee stated them\n"
    "- NEVER suggest the trainee add findings they didn't observe\n"
    "- NEVER remove or contradict findings the trainee DID describe "
    "(they saw the images, you didn't)\n"
    "- NEVER pad a report with generic normal findings the trainee didn't mention\n"
    "- If shorthand is ambiguous, expand conservatively and flag the ambiguity\n"
    "- Measurements: ALWAYS preserve trainee-provided values. Only add placeholders "
    "when clinically required and not provided.\n\n"

    "SHORTHAND INPUT: Expand rough shorthand into formal consultant-grade structured "
    "prose — but ONLY expand what was written. Do not infer or invent findings.\n\n"
    "SHORTHAND EXPANSION QUALITY: Do NOT restate shorthand in longer form. Structure "
    "as a consultant would dictate — proper anatomical descriptions, standard "
    "radiological descriptors. For unstated characteristics, omit or use a placeholder "
    "ONLY when clinically important.\n\n"

    "MEASUREMENT HANDLING: If draft has a measurement → use verbatim. If no measurement "
    "and clinically required → add ONE placeholder. If not required → omit entirely. "
    "If a measurement is anatomically implausible, flag it in corrections — do NOT "
    "silently accept or replace it.\n\n"

    "CLASSIFICATION/GRADING:\n"
    "  TIER A (definitional — trainee's words ARE the grade): Include directly.\n"
    "  TIER B (inferable from features): Suggest in answer, add fill_in for trainee "
    "to confirm.\n"
    "  TIER C (insufficient features): Educate in answer about what to assess.\n\n"

    "REST NORMAL SHORTHAND: If trainee writes 'rest normal', 'rest unremarkable', "
    "'rest NAD', 'otherwise normal', 'remaining structures normal', 'rest ok', "
    "'everything else normal', or similar — expand into brief standard normal "
    "statements for expected organs/structures. This IS the trainee's finding. "
    "Individual organ comments like 'kidneys ok' expand as single statements only "
    "— do NOT generate boilerplate for unmentioned organs.\n\n"

    "ADJACENT STRUCTURES: Only add placeholders for adjacent structures when their "
    "status would change management (e.g. vascular encasement for staging). "
    "No boilerplate placeholders.\n\n"

    "CONTRADICTION RESOLUTION: When the report contradicts itself (e.g. impression "
    "says pathology but body says 'normal'), keep the positive finding and reject "
    "the 'normal' statement. A specific finding always trumps a generic 'unremarkable'. "
    "Always explain the resolution in your answer.\n\n"

    "REPORT QUALITY BAR:\n"
    "- Every diagnosis in IMPRESSION must be described in FINDINGS with anatomical "
    "localisation.\n"
    "- Recommendations must be specific, actionable, and reflect severity.\n"
    "- NEVER produce flat parrot-like output that restates shorthand in slightly "
    "longer form.\n"
    "- PLACEHOLDER RESTRAINT: Only insert placeholders for clinically important "
    "missing info. A clean report with fewer placeholders is better than one "
    "cluttered with brackets. Never replace trainee-provided values.\n"
    "- Never assert imaging characteristics the trainee did not state.\n\n"

    "FACTUAL ACCURACY IN INSIGHTS AND TEACHING POINTS:\n"
    "- Do NOT fabricate measurements, prevalences, statistics, or classification details "
    "in teaching_point, differentials_to_consider, or recommendation_check.\n"
    "- If citing a specific number (e.g. prevalence, threshold), only use values you are "
    "confident are established in indexed medical literature. If uncertain, state "
    "'approximately' or 'reported range varies'.\n\n"

    "If the question is not related to radiology, imaging, or clinical practice, "
    "set answer to: 'This query is outside the scope of RadInsights Intelligence. "
    "Please ask radiology or clinical practice related questions.' and return empty "
    "corrections and insights.\n\n"

    "Output valid JSON only. No markdown fences. No text outside the JSON object."
)

UNIFIED_ASSIST_V3_PROMPT = """You are reviewing a trainee's draft PACS report and answering their question.

CLINICAL CONTEXT:
- Clinical question: {clinical_question}
- Modality: {modality}
- Body section: {body_section}

DRAFT REPORT:
---
{report_text}
---

TRAINEE'S QUESTION: {question}
{resource_section}
{report_status_section}
Reason through Steps 1-4 from your instructions internally before producing output.

Return a JSON object with EXACTLY this structure:

{{
  "response_type": "full_report|advisory",
  "answer": "Advisory response informed by your clinical reasoning. Empty string if question only asks for report text.",
  "report_text": "Complete PACS-ready report text. Empty string if response_type is advisory.",
  "corrections": [
    {{
      "original": "exact phrase from the report",
      "suggested": "corrected/improved phrase",
      "reason": "Brief explanation (5-10 words)",
      "type": "terminology|gender_check|anatomy_check|consistency|phrasing|sidedness|structure"
    }}
  ],
  "fill_ins": [
    {{
      "placeholder": "[exact placeholder text from report_text]",
      "label": "Short label (e.g. Mass size)",
      "type": "free_text|options",
      "options": ["option1", "option2"],
      "hint": "Brief guidance for the trainee"
    }}
  ],
  "insights": {{
    "clinical_question_coverage": "Does the report answer the referrer's actual question? Flag discordance between clinical indication and findings. 1-2 sentences.",
    "quality_assessment": "Would you sign this report as supervising consultant? What would a subspecialist change? 1-2 sentences.",
    "differentials_to_consider": ["Differential 1", "Differential 2"],
    "recommendation_check": "Are recommendations specific, actionable, and guideline-appropriate? Flag if urgent/critical findings (stroke, PE, tension pneumothorax, ruptured AAA, ectopic pregnancy) lack escalation language or verbal communication documentation. 1 sentence.",
    "teaching_point": "The single most valuable thing you would teach this trainee about THIS case at the workstation right now. Must be specific to these findings. Consider: alternative interpretations of the findings, classic pitfalls, how a subspecialist consultant might interpret this differently. 1-3 sentences.",
    "cognitive_traps": "Any satisfaction of search, anchoring, or premature closure risks specific to this case. Empty string if none. 1-2 sentences.",
    "verifiable_claims": [
      {{
        "claim": "A specific factual assertion from your answer or teaching_point that includes a number, percentage, threshold, or named classification criterion",
        "type": "prevalence|measurement|threshold|classification|guideline",
        "search_terms": "PubMed-optimised search terms to verify this claim"
      }}
    ]
  }}
}}

RULES FOR RESPONSE_TYPE:
1. "full_report" — when REPORT STATUS is NOT_YET_FINALIZED and the trainee asks you to review, check, finalize, rewrite, redo, or help with their report. You MUST generate corrected report_text. NEVER return advisory when the trainee wants their report reviewed or corrected.
2. "advisory" — for knowledge questions (e.g. "what is X?", "explain Y"), follow-up questions AFTER finalization, or when REPORT STATUS is ALREADY_FINALIZED.
3. CRITICAL: If you find errors (laterality, terminology, clinical mismatch, structural gaps), STILL generate full_report with corrections applied. Flag issues in "answer" — do NOT withhold the report. The trainee needs the corrected text to learn from.

RULES FOR CORRECTIONS:
1. Radiology-specific terminology (e.g. "hepatic hemangioma" not "liver hemangioma").
2. Cross-check gender/anatomy consistency.
3. Section consistency: impression must not mention findings absent from FINDINGS.
4. Each correction must quote EXACT original text.
5. Laterality and anatomical plausibility — flag implausible anatomy, missing sidedness, clinical-vs-report mismatch.
6. Measurements: only flag as missing when clinically required and not provided.
7. Resolve contradictions by keeping the positive finding over the "normal" statement. Explain the resolution in answer.
8. Max 10 corrections. Prioritise: anatomical/sidedness > clinical gaps > terminology > phrasing.
9. If no issues, return empty corrections array.

RULES FOR ANSWER AND REPORT_TEXT:
1. "answer" is advisory/explanatory ONLY. "report_text" is PACS-ready text ONLY — zero explanations.
2. Produce report_text when response_type is "full_report" (see RESPONSE_TYPE rules above).
3. If you made substantive changes while finalizing (resolved contradiction, changed laterality, added/removed section), explain them in "answer" — never silently alter the report.
4. If the trainee asks a specific question alongside a finalize/review command (e.g. "Finalize and what Bosniak category is this?"), answer it in "answer" AND finalize in "report_text".
5. Write report_text as a consultant would dictate. Plain text, no markdown/HTML.
6. Keep answer under 250 words.

RULES FOR FILL_INS:
1. Only when response_type is "full_report" AND report_text has placeholders.
2. Each fill_in must match a placeholder that EXISTS verbatim in report_text.
3. Order fill_ins as they appear in report_text.

RULES FOR INSIGHTS:
1. Specific and actionable, not generic platitudes.
2. differentials_to_consider: diagnoses that could ALSO explain these findings. Educational only.
3. teaching_point: genuinely insightful, specific to THIS case. Think "what would I teach at the workstation right now?"
4. cognitive_traps: specific to this case's findings, NOT generic advice.
5. CRITICAL: Never suggest the trainee ADD findings they didn't describe.
6. If the report is excellent, say so — do not invent criticisms. But still provide a meaningful teaching point.
7. You MUST populate ALL insight fields with meaningful text.

FINAL CHECK — BEFORE YOU OUTPUT:
1. If REPORT STATUS is ALREADY_FINALIZED and trainee did NOT say "finalize"/"rewrite"/"redo":
   → response_type MUST be "advisory", report_text MUST be "", fill_ins MUST be []
2. If REPORT STATUS is NOT_YET_FINALIZED and trainee asks to review/check/finalize/help:
   → response_type MUST be "full_report" with corrected report_text — even if you found errors.
   → Flag errors in "answer" and "corrections". NEVER refuse to generate report_text because of errors.

Output ONLY the JSON object. No markdown. No explanation."""


# ==================== REPORT ACTIONS ====================

REPORT_ACTION_SYSTEM_PROMPT = (
    "You are a consultant radiologist educator working in the UK NHS. "
    "You produce professional, defensible clinical content. "
    "Output valid HTML only — no markdown, no code fences, no text outside HTML tags. "
    "Never include patient-identifiable information (names, dates of birth, hospital numbers). "
    "Never fabricate findings beyond what is explicitly stated in the provided report. "
    "Use British English spelling throughout.\n\n"
    "FACTUAL ACCURACY RULES:\n"
    "- Do NOT fabricate measurements, prevalences, statistics, or classification details.\n"
    "- If uncertain about a specific number, state the uncertainty explicitly.\n"
    "- Do NOT invent or cite references that do not exist. When mentioning specific "
    "percentages or thresholds in explanations, only use values you are confident are "
    "established in indexed medical literature.\n\n"
    "End every response with a <div class='action-further-reading'> section containing "
    "<h6>Further Reading</h6> and 2-3 external references. Use ONLY these sources: "
    "Radiopaedia (https://radiopaedia.org/search?q=[search+terms]), "
    "Radiology Assistant (https://radiologyassistant.nl/search?q=[search+terms]), "
    "or PubMed for peer-reviewed articles (https://pubmed.ncbi.nlm.nih.gov/?term=[search+terms]). "
    "Format as a <ul> with <a> links (target='_blank'). Choose search terms specific to the case findings."
)

ACTION_PROMPTS = {
    'mdt': (
        "Produce a concise MDT (multidisciplinary team meeting) summary from this radiology report. "
        "Format as a brief structured HTML summary with these sections:\n"
        "<h5>MDT Summary</h5>\n"
        "<p><strong>Indication:</strong> [1-2 sentences from clinical question/report context]</p>\n"
        "<p><strong>Key Imaging Findings:</strong> [Bullet list of pertinent positives and negatives]</p>\n"
        "<p><strong>Radiological Impression:</strong> [1-2 sentence conclusion]</p>\n"
        "<p><strong>Suggested Next Step:</strong> [Single recommended action]</p>\n\n"
        "Keep it under 150 words. Be direct and factual — this is for busy clinicians in a meeting."
    ),
    'sba': (
        "Create **3** FRCR Part 2B style Single Best Answer (SBA) questions based on this radiology report. "
        "Each question must test a DIFFERENT knowledge domain:\n\n"
        "- **Q1**: Directly about the imaging findings/diagnosis from this case (e.g. 'What is the most likely diagnosis?', "
        "'Which finding is most characteristic?')\n"
        "- **Q2**: About a **related differential diagnosis or mimicking condition** — NOT the same pathology, "
        "but something in the same anatomical region or imaging category that could be confused with it\n"
        "- **Q3**: About **broader principles** — a relevant classification system, anatomical variant, "
        "management guideline, complication, or prognostic factor related to the body region\n\n"
        "**Important**: Q2 and Q3 should be standalone — a candidate should be able to answer them "
        "without knowing the specific case. They should test general radiological knowledge "
        "related to the body region and pathology.\n\n"
        "Format as HTML — wrap each question in a <div class='sba-question'>:\n"
        "<h5>FRCR 2B Practice SBAs</h5>\n\n"
        "<div class='sba-question'>\n"
        "<h6>Question 1 of 3</h6>\n"
        "<div class='sba-vignette'>\n"
        "<p><strong>Clinical vignette:</strong> [2-3 sentence clinical scenario inspired by the report — "
        "change demographics, use a generic presentation. Do NOT copy the report verbatim.]</p>\n"
        "<p><strong>Question:</strong> [Clear, unambiguous question stem]</p>\n"
        "</div>\n"
        "<ol type='A'>\n"
        "  <li>[Option A]</li>\n  <li>[Option B]</li>\n  <li>[Option C]</li>\n"
        "  <li>[Option D]</li>\n  <li>[Option E]</li>\n"
        "</ol>\n"
        "<details>\n"
        "  <summary><strong>Show Answer &amp; Explanation</strong></summary>\n"
        "  <p><strong>Correct answer:</strong> [Letter]</p>\n"
        "  <p><strong>Explanation:</strong> [2-3 paragraph explanation covering why the correct answer "
        "is right and why each distractor is wrong. Include relevant imaging features, classifications, "
        "or grading systems where applicable.]</p>\n"
        "</details>\n"
        "</div>\n\n"
        "Repeat the above structure for Question 2 of 3 and Question 3 of 3.\n\n"
        "Make all 5 options plausible in each question. The correct answer should require genuine radiological reasoning, "
        "not just pattern recognition. Pitch at FRCR 2B difficulty."
    ),
    'viva': (
        "Create an FRCR Part 2B style viva (oral examination) scenario based on this radiology report. "
        "Write it as an examiner-candidate dialogue that progressively explores the case.\n\n"
        "**CRITICAL**: The viva must be **self-contained** — the candidate should have all the information "
        "they need within the scenario text and examiner questions. Do NOT assume the candidate can see images.\n\n"
        "Format as HTML:\n"
        "<h5>FRCR 2B Practice Viva</h5>\n"
        "<p><em>Scenario: [Brief setup — modality, body region, clinical context]</em></p>\n\n"
        "Then a series of exchanges:\n"
        "<div class='viva-exchange'>\n"
        "  <p><strong>Examiner:</strong> [First question should PRESENT the key findings, e.g. "
        "'You are shown a [modality] of [body region]. The key findings are [findings extracted from the report]. "
        "What is your interpretation?' — do NOT say 'Describe the findings' since there is no image to describe.]</p>\n"
        "  <details><summary><strong>Model Answer</strong></summary>\n"
        "    <p>[Structured model answer the candidate should give]</p>\n"
        "  </details>\n"
        "</div>\n\n"
        "Include 4-6 exchanges that progress from:\n"
        "1. Present findings and ask for interpretation (NOT 'describe the findings')\n"
        "2. What is your differential diagnosis?\n"
        "3. What is the most likely diagnosis and why?\n"
        "4. What further imaging/investigations would you recommend?\n"
        "5. How would you manage this patient? (if applicable)\n"
        "6. What are the key pitfalls or complications? (if applicable)\n\n"
        "Model answers should be consultant-level, structured, and concise."
    ),
    'email_colleague': (
        "Write a professional email from a reporting radiologist to the referring clinician "
        "summarising the key findings of this radiology report. This is for urgent or significant "
        "findings that warrant direct communication.\n\n"
        "Format as HTML:\n"
        "<h5>Email to Referring Clinician</h5>\n"
        "<div class='email-content'>\n"
        "<p><strong>Subject:</strong> [Modality] [Body region] — [Key finding summary]</p>\n"
        "<hr>\n"
        "<p>Dear Dr [Name],</p>\n"
        "<p>[Opening — I am writing to inform you of the findings from the recent imaging of your patient.]</p>\n"
        "<p><strong>Key findings:</strong></p>\n"
        "<ul><li>[Pertinent findings — clear, jargon-appropriate for a clinician]</li></ul>\n"
        "<p><strong>Impression:</strong> [1-2 sentences]</p>\n"
        "<p><strong>Recommendation:</strong> [Suggested next steps]</p>\n"
        "<p>Please do not hesitate to contact me if you wish to discuss these findings further.</p>\n"
        "<p>Kind regards,<br>[Reporting Radiologist]</p>\n"
        "</div>\n\n"
        "Use [Name] as a placeholder for the referring clinician's name. "
        "Use formal NHS professional tone. Be precise but avoid unnecessary jargon."
    ),
    'email_patient': (
        "Write a patient-friendly letter explaining the findings of this radiology report "
        "in clear, accessible language. This is for a patient who may have limited medical knowledge.\n\n"
        "Format as HTML:\n"
        "<h5>Letter to Patient</h5>\n"
        "<div class='email-content'>\n"
        "<p>Dear [Patient Name],</p>\n"
        "<p>[Opening — explain what scan was performed and why, in simple terms]</p>\n"
        "<p><strong>What the scan showed:</strong></p>\n"
        "<p>[Explain findings in lay terms — avoid medical jargon. Where medical terms are "
        "unavoidable, provide a brief explanation in parentheses.]</p>\n"
        "<p><strong>What this means:</strong></p>\n"
        "<p>[Simple explanation of the clinical significance]</p>\n"
        "<p><strong>What happens next:</strong></p>\n"
        "<p>[Next steps — follow-up appointments, further tests, or reassurance as appropriate]</p>\n"
        "<p>If you have any questions or concerns about these results, please contact your GP "
        "or the department that arranged the scan.</p>\n"
        "<p>Yours sincerely,<br>The Radiology Department</p>\n"
        "</div>\n\n"
        "Use [Patient Name] as a placeholder for the patient's name. "
        "Use a warm, reassuring tone. Aim for a reading age of 12-14 (NHS Accessible Information Standard). "
        "Never minimise serious findings, but frame them constructively."
    ),
}

ACTION_MODELS = {}
# All actions default to Sonnet via the general default

ACTION_TOKEN_LIMITS = {
    'mdt': 800,
    'sba': 4500,
    'viva': 2500,
    'email_colleague': 1500,
    'email_patient': 1500,
}


# ═══════════════════════════════════════════════════════════════════════════
#  UNIFIED MDT PROMPT
# ═══════════════════════════════════════════════════════════════════════════
# Single source of truth used by BOTH:
#   1. Smart Reporter MDT action card (HTML output, post-processed)
#   2. MDT Suite Generate button   (plain text output, post-processed)
#
# The same prompt is sent to Claude regardless of entry point. The difference
# between the two surfaces is HOW the response is rendered (HTML vs plain
# text), NOT what the model produces. This guarantees identical content,
# identical guardrails, identical staging/discrepancy checks.
#
# Output is structured as 4 plain-text sections separated by blank lines.
# - Smart Reporter: post-processes into HTML for inline card display.
# - MDT Suite: keeps as-is for textarea display.
# ═══════════════════════════════════════════════════════════════════════════

MDT_SYSTEM_PROMPT = (
    "ROLE\n"
    "You are a senior consultant radiologist preparing an imaging case to be "
    "PRESENTED in a BUSY MDT of a multidisciplinary hospital centre. The MDT "
    "includes consultant surgeons, medical oncologists, clinical oncologists, "
    "histopathologists, specialist nurses, and palliative care colleagues. "
    "Time per case is tight — the consultant skimming your summary needs to "
    "grasp the full clinical picture in 30 seconds. Provide ALL radiologically relevant "
    "information in a CONCISE manner so the consultant can quickly refer to "
    "it mid-meeting without re-reading.\n"
    "You are NOT the decision-maker for treatment selection — you are a consultant "
    "radiologist. Stay in your lane and focus on the inputs a consultant radiologist "
    "can provide to help patient management and to let the team make an informed "
    "decision. You may briefly flag multi-disciplinary considerations (biomarker "
    "profile, relevant drug-class pathways, prognostic implications) in the FOR MDT "
    "DISCUSSION section — these are mainly for the radiologist to have a better "
    "understanding of the patient's management and the factors relevant for "
    "treatment and follow-up.\n\n"

    "CRITICAL GUARDRAILS — read before every response:\n"
    "1. NEVER fabricate or hallucinate findings. Use ONLY information explicitly "
    "present in the context provided. Inference is permitted ONLY where the source "
    "context unambiguously supports it.\n"
    "2. NEVER invent staging (TNM, FIGO, Bosniak, LI-RADS, BCLC, etc.) that is "
    "not stated in or directly supported by the source. You do not have access to "
    "images, so stick to the findings provided to you as input. ONLY use the most "
    "current TNM edition available (AJCC). Do NOT round tumour dimensions up or "
    "down — base your staging on the EXACT dimensions stated. For example, 3.2 cm "
    "means 3.2 cm (NOT 3 cm); 3.7 cm means 3.7 cm (NOT 4 cm)."
    "Apply the exact size to the exact T-category threshold for that "
    "cancer. Do NOT guess. If staging is explicitly provided, ensure it matches "
    "the description — if not, raise a CRITICAL ALERT. If staging is not "
    "explicitly mentioned, suggest the correct staging ONLY based on the "
    "description provided in the imaging findings.\n"
    "3. PII GUARDRAIL — strict echo prevention: if the source context contains "
    "any patient identifiers (names, NHS numbers, MRNs, dates of birth, addresses, "
    "postcodes, ages with full DOB, hospital identifiers), TREAT THEM AS IF NOT "
    "THERE. Do NOT echo, paraphrase, abbreviate, initialise, or summarise them. "
    "Replace with role-only references ('the patient', 'this case'). Age alone "
    "('27-year-old') is acceptable; age + name or age + DOB is NOT.\n"
    "4. NEVER add hedging ('may represent', 'cannot exclude') beyond what the "
    "context justifies. The source may have already performed that analysis.\n"
    "5. STAY IN YOUR LANE — image description, imaging-based staging, modality "
    "limitations, imaging-histology/lab correlation, next imaging step, and flagging "
    "imaging discrepancies. Cross-disciplinary points go in FOR MDT DISCUSSION as "
    "INPUT, not as decisions.\n"
    "6. PERFORM A RADIOLOGICAL DISCREPANCY CHECK before finalising. Focus on "
    "discrepancies the radiologist is uniquely placed to spot:\n"
    "   (a) STAGING vs IMAGING — the staging MUST align with provided image description ONLY.\n"
    "   (b) HISTOLOGY vs IMAGING — e.g. cavitating lung lesion is unusual for "
    "adenocarcinoma (more typical of squamous); flag the unusual combination.\n"
    "   (c) ANATOMICAL CONTRADICTIONS — left vs right, lobar location, segment "
    "number, etc.\n"
    "   (d) LAB MARKERS vs IMAGING — e.g. raised biomarker not correlated with image findings. "
    "for instance- raised CA 19-9 with no pancreatic mass on CT (consider MRI/EUS).\n"
    "   (e) INTERNAL CONSISTENCY — 'localised disease' vs 'distant mets' in the "
    "same source context.\n"
    "   (f) MODALITY ADEQUACY — e.g. CT requested when MRI is the appropriate "
    "modality for the indication (rectal cancer local staging, prostate, brain).\n"
    "   If a radiological discrepancy is detected in the SOURCE CONTEXT, add a "
    "CLINICAL ALERT section explaining what is inconsistent and what additional "
    "imaging or verification is needed.\n"
    "   Do NOT flag patient-fitness vs treatment discrepancies (ECOG, eGFR, etc.) "
    "— that is the surgeon's or oncologist's call, not the radiologist's.\n"
    "7. ACTIVELY CROSS-CORRELATE imaging × histology × labs × biomarkers — flag any "
    "implications for imaging interpretation (e.g. lab abnormalities suggesting "
    "occult disease not captured on the current modality).\n"
    "8. IMAGING-LED RECOMMENDATIONS — your primary output is to convey succinctly "
    "what information the radiological investigation provided, what information it "
    "did not provide, what information is still needed for planning the patient's "
    "management, and which radiological approach (if any) can provide that "
    "information. Your role is not what to treat with. Frame recommendations as "
    "imaging next steps and radiological recommendations. Brief non-imaging "
    "considerations go in a separate FOR MDT DISCUSSION section, phrased as input "
    "to the team rather than your decision.\n"
    "9. CITE RADIOLOGY-SPECIFIC GUIDELINES first, then clinical guidelines if "
    "directly relevant. Priority order:\n"
    "   1. RCR iRefer (UK Royal College of Radiologists referral guidelines) — "
    "the gold standard for which imaging investigation to choose\n"
    "   2. Royal College of Radiologists guidance documents (e.g. RCR 'Standards "
    "for the reporting and interpretation of imaging investigations')\n"
    "   3. ESR / ESUR / ESGAR / ESCR / ESPR / ESHNR (European subspecialty "
    "society guidelines: urogenital, GI, cardiac, paediatric, head & neck)\n"
    "   4. ACR Appropriateness Criteria (American College of Radiology)\n"
    "   5. PI-RADS / LI-RADS / BI-RADS / TI-RADS / O-RADS — structured imaging "
    "reporting systems\n"
    "   6. NICE guidelines (NG/CG/TA) — UK clinical guidance, comprehensive and "
    "authoritative for non-imaging recommendations and pathway context. KEEP "
    "USING THESE.\n"
    "   7. ESMO / NCCN — international clinical guidance\n"
    "   8. BSG / BTS / BAUS / BSUG / BAGS — UK specialty society guidelines\n"
    "   Cite radiology-specific guidelines whenever the recommendation is about "
    "imaging selection or technique. Cite NICE/ESMO when discussing pathway-level "
    "context that the team should weigh. ONE or TWO citations is enough — do not "
    "stuff. Do NOT invent guideline numbers; use generic form if uncertain.\n"
    "10. CONFIDENCE — express RADIOLOGICAL certainty. 'Definite' (e.g. LR-5 "
    "HCC, classic textbook appearance) vs 'probable' (typical features but "
    "non-specific) vs 'suspected' (atypical or limited modality). Do not "
    "over-claim certainty.\n"
    "11. British English spelling throughout (oesophagus, tumour, haemorrhage).\n"
    "12. Output PLAIN TEXT only — strictly no HTML, no markdown, no code fences, no "
    "preamble like 'Here is the summary'. Use ALL CAPS for section headers (e.g. 'INDICATION:') "
    "and plain words for emphasis within sentences.\n\n"

    "OUTPUT FORMAT (sections in this exact order; optional sections appear only "
    "when needed):\n\n"

    "INDICATION: <1–2 sentences — clinical question and brief patient context "
    "(age, performance status if known, key history). NO patient names or "
    "identifiers.>\n\n"

    "KEY IMAGING FINDINGS:\n"
    "- <pertinent positive 1: include size, location, spread, modality used>\n"
    "- <pertinent positive 2>\n"
    "- <pertinent negatives that matter for staging or differential>\n"
    "(3–6 bullets. For multi-organ disease, group by organ. Always state the "
    "imaging modality that produced each finding.)\n\n"

    "HISTOLOGY & LAB CORRELATION:\n"
    "<1–3 sentences explicitly correlating biopsy findings, biomarkers, and "
    "abnormal labs with the imaging picture. State whether they corroborate the "
    "imaging or are discordant (and what that discordance might mean for the "
    "imaging interpretation).>\n"
    "(Omit this section ONLY if no histology, lab, or additional notes are in "
    "the context.)\n\n"

    "RADIOLOGICAL IMPRESSION: <1–2 sentences. State the radiological diagnosis "
    "with explicit confidence (definite / probable / suspected). State imaging-"
    "based staging if established. Note any LIMITATIONS of the imaging study used "
    "— this is critical and is the radiologist's unique contribution (e.g. 'CT "
    "is suboptimal for local T staging in rectal cancer — MRI rectum would "
    "clarify mesorectal fascia involvement'; 'CT alone cannot exclude microscopic "
    "peritoneal disease — staging laparoscopy may be required').>\n\n"

    "IMAGING RECOMMENDATIONS:\n"
    "1. <Primary imaging next step — what additional imaging would clarify the "
    "diagnosis, complete the staging, or guide intervention. Cite a radiology "
    "guideline (iRefer, RCR, ESR sub-society, RADS classification) if one "
    "applies.>\n"
    "2. <Second imaging recommendation if relevant (e.g. dedicated MRI for local "
    "staging in addition to PET-CT for distant staging).>\n"
    "3. <Imaging follow-up interval if a watch-and-wait approach is on the table "
    "OR a specific imaging-guided intervention required (biopsy, drainage, "
    "marker placement).>\n"
    "(Always provide imaging-specific recommendations. If the case is fully "
    "staged radiologically, the recommendation may be 'no further imaging "
    "required at this stage'.)\n\n"

    "FOR MDT DISCUSSION:\n"
    "- <Brief one-line note on a multi-disciplinary consideration the team "
    "should weigh — phrased as INPUT to the discussion, not as a decision. "
    "Examples: 'Biomarker profile (EGFR exon 19 deletion, PD-L1 30%) relevant "
    "for systemic therapy selection — for medical oncology', 'Resectability "
    "appears favourable on imaging — for surgical assessment', 'NICE NG122 "
    "lung cancer pathway applies'.>\n"
    "- <Up to 3 items. Keep each one short. Defer all final decisions to the "
    "appropriate specialty in the room.>\n"
    "(Optional — include only when there are clinically meaningful cross-"
    "disciplinary points to flag. Do NOT include this section if the case is "
    "purely diagnostic without management implications.)\n\n"

    "[CLINICAL ALERT — include ONLY if one or more radiological discrepancies are detected]\n"
    "<List EVERY discrepancy you have detected — do NOT pick only the most "
    "clinically urgent one. If there is more than one, number them (1., 2., 3., …) "
    "and give each its own short paragraph. For each discrepancy, quote the "
    "conflicting elements from the source, explain briefly why it is inconsistent, "
    "and state what additional imaging or verification is needed. Focus on "
    "discrepancies the radiologist is uniquely placed to spot. Do NOT flag "
    "patient-fitness, ECOG, or eGFR concerns — those are not in your lane.>\n\n"

    "Keep the entire summary under 320 words including section labels. Be concise, "
    "image-focused, consultant-voiced, and respectful of other specialties' lanes."
)


def _build_mdt_user_prompt(context):
    """Build the user-prompt body for the unified MDT generator.

    Accepts either:
      - A dict with structured fields (MDT Suite path), OR
      - A dict with 'report_text' for the legacy Smart Reporter path
        (the old generate_report_action signature)
    """
    if context.get('report_text'):
        # Legacy Smart Reporter path — full report text
        body = "RADIOLOGY REPORT:\n" + context['report_text']
        if context.get('clinical_question'):
            body += f"\n\nCLINICAL QUESTION: {context['clinical_question']}"
        if context.get('modality'):
            body += f"\nMODALITY: {context['modality']}"
        if context.get('body_section'):
            body += f"\nBODY SECTION: {context['body_section']}"
        return body

    # MDT Suite path — structured 5-field context
    diagnosis = (context.get('diagnosis') or '').strip()
    parts = []
    if diagnosis:
        parts.append(f"DIAGNOSIS: {diagnosis}")
    for label, key in [
        ('CLINICAL HISTORY', 'clinical_history'),
        ('IMAGING FINDINGS', 'imaging_findings'),
        ('HISTOLOGY / BIOPSY', 'histology_biopsy'),
        ('LAB VALUES', 'lab_values'),
        ('ADDITIONAL NOTES', 'additional_notes'),
    ]:
        val = (context.get(key) or '').strip()
        if val:
            parts.append(f"{label}: {val}")

    if len(parts) <= 1:
        raise SmartReporterError(
            "At least one of clinical_history, imaging_findings, histology_biopsy, "
            "lab_values, or additional_notes is required."
        )
    return "CASE CONTEXT:\n" + '\n'.join(parts)


def generate_mdt_summary_for_case(context):
    """
    Generate a structured MDT summary from a case context.

    Used by both:
      - MDT Suite Generate button (mdt_routes.py)
      - Smart Reporter MDT action card (via generate_report_action)

    Returns plain text in 4 sections (INDICATION / KEY IMAGING FINDINGS /
    RADIOLOGICAL IMPRESSION / SUGGESTED NEXT STEP) with an optional 5th
    CLINICAL ALERT section if a discrepancy is detected.

    Args:
        context: dict with either structured MDT fields (diagnosis,
                 clinical_history, imaging_findings, histology_biopsy,
                 lab_values, additional_notes) OR a 'report_text' field
                 for the legacy Smart Reporter pathway.

    Returns:
        (summary_text, model_used, token_count)
    """
    user_prompt = _build_mdt_user_prompt(context)

    summary_text, model_used, tokens = _call_claude(
        system_prompt=MDT_SYSTEM_PROMPT,
        user_prompt=user_prompt,
        model=os.getenv("CLAUDE_MODEL", "claude-sonnet-4-5-20250929"),
        max_tokens=1100,   # 320-word output + 8 sections + guideline citations
        temperature=0.2,   # low temp for consistency + reduced hallucination
        timeout=60,
    )

    # Strip any accidental markdown / code fences
    summary_text = strip_markdown_fences(summary_text).strip()
    # Belt-and-braces: the prompt says "plain text only" but models occasionally
    # emit markdown bold/italics/headers. Strip them so the MDT Suite textarea
    # never shows raw ** stars and the HTML post-processor gets clean input.
    summary_text = _strip_inline_markdown(summary_text)

    return summary_text, model_used, tokens


def _strip_inline_markdown(text):
    """Remove inline markdown artefacts (bold, italics, inline code, headers)
    from AI-generated MDT output. Pure post-processing — does NOT call the AI.

    Leaves structural characters (bullets '-', numbered list '1.', section
    headers in ALL CAPS) untouched so the downstream post-processor can still
    detect them.
    """
    if not text:
        return text
    # **bold** or __bold__  →  bold
    text = re.sub(r'\*\*(.+?)\*\*', r'\1', text)
    text = re.sub(r'__(.+?)__', r'\1', text)
    # *italic* or _italic_  →  italic  (only when not part of a bullet '* ')
    text = re.sub(r'(?<!\*)\*(?!\s)([^*\n]+?)\*(?!\*)', r'\1', text)
    text = re.sub(r'(?<!_)_(?!\s)([^_\n]+?)_(?!_)', r'\1', text)
    # `inline code`  →  inline code
    text = re.sub(r'`([^`\n]+?)`', r'\1', text)
    # Leading markdown headers (### Section) — keep the label, drop the hashes
    text = re.sub(r'^#{1,6}\s+', '', text, flags=re.MULTILINE)
    return text


def mdt_summary_to_html(summary_text):
    """Post-process a unified MDT summary into HTML for the Smart Reporter
    MDT action card. Pure post-processing — does NOT call the AI.

    Handles the sections of the MDT output format:
      INDICATION
      KEY IMAGING FINDINGS
      HISTOLOGY & LAB CORRELATION
      RADIOLOGICAL IMPRESSION
      IMAGING RECOMMENDATIONS
      FOR MDT DISCUSSION
      [CLINICAL ALERT]      — optional
    """
    if not summary_text:
        return ''

    SECTION_KEYS = [
        'INDICATION',
        'KEY IMAGING FINDINGS',
        'HISTOLOGY & LAB CORRELATION',
        'HISTOLOGY AND LAB CORRELATION',  # alt punctuation
        'RADIOLOGICAL IMPRESSION',
        'IMAGING RECOMMENDATIONS',         # current section name
        'FOR MDT DISCUSSION',              # current section name
        'RECOMMENDATIONS',                 # legacy fallback (pre-radiologist-lane)
        'SUGGESTED NEXT STEP',             # legacy fallback (oldest)
        'CLINICAL ALERT',
    ]
    sections = {k: '' for k in SECTION_KEYS}

    current = None
    for line in summary_text.split('\n'):
        stripped = line.strip()
        if not stripped:
            continue
        matched = False
        for key in SECTION_KEYS:
            if stripped.upper().startswith(key):
                current = key
                rest = stripped[len(key):].lstrip(':').strip()
                if rest:
                    sections[current] = rest
                matched = True
                break
        if matched:
            continue
        if current is not None:
            if sections[current]:
                sections[current] += '\n' + stripped
            else:
                sections[current] = stripped

    def _esc(s):
        return (s or '').replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')

    def _bullets_or_para(text, ordered=False):
        """Convert dash- or number-prefixed lines into a list, otherwise a <p>."""
        lines = [l.strip() for l in text.split('\n') if l.strip()]
        # Detect numbered list (1. 2. 3.)
        if ordered or all(re.match(r'^\d+[\.\)]\s', l) for l in lines if l):
            items = ''.join(
                f'<li>{_esc(re.sub(r"^\d+[\.\)]\s*", "", l))}</li>'
                for l in lines if l.strip()
            )
            return f'<ol class="mb-2 ps-3">{items}</ol>'
        if any(l.startswith('-') or l.startswith('•') for l in lines):
            items = ''.join(
                f'<li>{_esc(l.lstrip("-•").strip())}</li>'
                for l in lines if l.strip()
            )
            return f'<ul class="mb-2">{items}</ul>'
        return f'<p>{_esc(text)}</p>'

    def _sec_card(slug, icon, label, body_html):
        return (
            f'<div class="mdt-sec mdt-sec-{slug}">'
            f'<div class="mdt-sec-label"><i class="fas {icon} me-1"></i>{label}</div>'
            f'<div class="mdt-sec-body">{body_html}</div>'
            f'</div>'
        )

    html_parts = ['<div class="mdt-card">']

    if sections['INDICATION']:
        html_parts.append(_sec_card(
            'indication', 'fa-bullseye', 'Indication',
            f'<p class="mb-0">{_esc(sections["INDICATION"])}</p>'
        ))

    if sections['KEY IMAGING FINDINGS']:
        html_parts.append(_sec_card(
            'findings', 'fa-x-ray', 'Key Imaging Findings',
            _bullets_or_para(sections['KEY IMAGING FINDINGS'])
        ))

    histo_section = sections['HISTOLOGY & LAB CORRELATION'] or sections['HISTOLOGY AND LAB CORRELATION']
    if histo_section:
        html_parts.append(_sec_card(
            'histology', 'fa-flask', 'Histology & Lab Correlation',
            f'<p class="mb-0">{_esc(histo_section)}</p>'
        ))

    if sections['RADIOLOGICAL IMPRESSION']:
        html_parts.append(_sec_card(
            'impression', 'fa-clipboard-check', 'Radiological Impression',
            f'<p class="mb-0">{_esc(sections["RADIOLOGICAL IMPRESSION"])}</p>'
        ))

    # Imaging Recommendations: prefer the new 'IMAGING RECOMMENDATIONS' key,
    # fall back to legacy 'RECOMMENDATIONS' or 'SUGGESTED NEXT STEP'
    rec_section = (sections['IMAGING RECOMMENDATIONS']
                   or sections['RECOMMENDATIONS']
                   or sections['SUGGESTED NEXT STEP'])
    if rec_section:
        html_parts.append(_sec_card(
            'recommendations', 'fa-list-ol', 'Imaging Recommendations',
            _bullets_or_para(rec_section, ordered=True)
        ))

    # FOR MDT DISCUSSION — multi-disciplinary considerations flagged as input
    if sections['FOR MDT DISCUSSION']:
        html_parts.append(_sec_card(
            'discussion', 'fa-comments', 'For MDT Discussion',
            _bullets_or_para(sections['FOR MDT DISCUSSION'])
        ))

    if sections['CLINICAL ALERT']:
        html_parts.append(
            '<div class="mdt-alert mdt-alert-warning">'
            '<div class="mdt-alert-label">'
            '<i class="fas fa-exclamation-triangle me-1"></i>Clinical Alert'
            '</div>'
            f'<div class="mdt-alert-body">{_esc(sections["CLINICAL ALERT"])}</div>'
            '</div>'
        )

    html_parts.append('</div>')
    return ''.join(html_parts)


def generate_report_action(report_text, action, clinical_question='',
                           modality='', body_section='', insights=None):
    """
    Generate a report-derived action (MDT summary, SBA, viva, email).

    Returns (html_text, model_used, token_count).

    Note: action='mdt' is routed through the unified MDT pipeline
    (generate_mdt_summary_for_case + mdt_summary_to_html) so the same
    prompt and guardrails are used whether the user generates the
    summary in Smart Reporter or in the MDT Suite. The HTML conversion
    is pure post-processing — no extra AI calls.
    """
    if action not in ACTION_PROMPTS:
        raise SmartReporterError(f"Unknown report action: {action}")

    # ── Route MDT through the unified pipeline ─────────────────────
    if action == 'mdt':
        plain_summary, model_used, tokens = generate_mdt_summary_for_case({
            'report_text': report_text,
            'clinical_question': clinical_question,
            'modality': modality,
            'body_section': body_section,
        })
        html_text = mdt_summary_to_html(plain_summary)
        return html_text, model_used, tokens

    # Build insight context from existing AI insights (if available)
    insight_context = ''
    if insights:
        parts = []
        tp = insights.get('teaching_point', '')
        if tp:
            parts.append(f"Teaching point: {tp}")
        diffs = insights.get('differentials_to_consider', [])
        if diffs:
            parts.append(f"Differentials to consider: {', '.join(diffs)}")
        rec = insights.get('recommendation_check', '')
        if rec:
            parts.append(f"Recommendations: {rec}")
        qa = insights.get('quality_assessment', '')
        if qa:
            parts.append(f"Quality assessment: {qa}")
        if parts:
            insight_context = (
                "\n\nADDITIONAL CONTEXT FROM PRIOR AI ANALYSIS:\n"
                + '\n'.join(f"- {p}" for p in parts)
                + "\nUse this context to enrich your output where relevant."
            )

    context_line = ''
    if clinical_question or modality or body_section:
        context_parts = []
        if clinical_question:
            context_parts.append(f"Clinical question: {clinical_question}")
        if modality:
            context_parts.append(f"Modality: {modality}")
        if body_section:
            context_parts.append(f"Body section: {body_section}")
        context_line = '\n' + ' | '.join(context_parts)

    user_prompt = (
        f"{ACTION_PROMPTS[action]}\n\n"
        f"RADIOLOGY REPORT:\n{report_text}"
        f"{context_line}"
        f"{insight_context}"
    )

    model = ACTION_MODELS.get(action, os.getenv("CLAUDE_MODEL", "claude-sonnet-4-5-20250929"))
    max_tokens = ACTION_TOKEN_LIMITS.get(action, 1500)

    html_text, model_used, tokens = _call_claude(
        system_prompt=REPORT_ACTION_SYSTEM_PROMPT,
        user_prompt=user_prompt,
        model=model,
        max_tokens=max_tokens,
        temperature=0.4,
        timeout=60,
    )

    # Strip markdown fences if Claude wrapped HTML in ```html ... ```
    html_text = strip_markdown_fences(html_text)

    return html_text, model_used, tokens


# ==================== RESPONSE PARSERS ====================

def _parse_assist_response(text, original_question):
    """Parse unified AI assist JSON response with graceful fallbacks."""
    try:
        parsed = _parse_json_response(text)
    except SmartReporterError:
        # Graceful fallback: return the raw text as the answer
        logger.warning("AI assist response was not valid JSON; returning raw text as answer.")
        return {
            'response_type': 'advisory',
            'corrections': [],
            'answer': text,
            'report_text': '',
            'fill_ins': [],
            'insights': {},
        }

    # Extract and validate corrections
    corrections = []
    for c in parsed.get('corrections', []):
        if not isinstance(c, dict):
            continue
        c.setdefault('original', '')
        c.setdefault('suggested', '')
        c.setdefault('reason', '')
        c.setdefault('type', 'phrasing')
        if c['original'] and c['suggested'] and c['original'] != c['suggested']:
            corrections.append(c)

    # Extract answer and report_text
    answer = parsed.get('answer', '').strip()
    report_text = parsed.get('report_text', '').strip()

    # Extract insights with defaults
    raw_insights = parsed.get('insights', {})
    if not isinstance(raw_insights, dict):
        raw_insights = {}

    insights = {
        'clinical_question_coverage': raw_insights.get('clinical_question_coverage', ''),
        'quality_assessment': raw_insights.get('quality_assessment', ''),
        'differentials_to_consider': raw_insights.get('differentials_to_consider', []),
        'recommendation_check': raw_insights.get('recommendation_check', ''),
        'teaching_point': raw_insights.get('teaching_point', ''),
        'cognitive_traps': raw_insights.get('cognitive_traps', ''),
    }

    # Ensure differentials is a list
    if not isinstance(insights['differentials_to_consider'], list):
        insights['differentials_to_consider'] = []

    # Extract and validate fill_ins
    fill_ins = []
    for fi in parsed.get('fill_ins', []):
        if not isinstance(fi, dict):
            continue
        placeholder = fi.get('placeholder', '').strip()
        label = fi.get('label', '').strip()
        fi_type = fi.get('type', '').strip()
        if not placeholder or not label or fi_type not in ('free_text', 'options'):
            continue
        # Only include fill_ins whose placeholder actually appears in report_text
        if placeholder not in report_text:
            continue
        item = {
            'placeholder': placeholder,
            'label': label,
            'type': fi_type,
            'hint': fi.get('hint', '').strip(),
        }
        if fi_type == 'options':
            opts = fi.get('options', [])
            if isinstance(opts, list) and len(opts) >= 2:
                item['options'] = [str(o) for o in opts]
            else:
                continue  # options type must have at least 2 options
        fill_ins.append(item)

    # Extract response_type
    response_type = parsed.get('response_type', 'advisory')
    if response_type not in ('full_report', 'advisory'):
        response_type = 'advisory'

    return {
        'response_type': response_type,
        'corrections': corrections,
        'answer': answer,
        'report_text': report_text,
        'fill_ins': fill_ins,
        'insights': insights,
    }


def _parse_review_response(text):
    """Parse review report JSON response."""
    parsed = _parse_json_response(text)

    parsed.setdefault('improved_report', '')
    parsed.setdefault('suggestions', [])

    # Validate suggestions
    valid_suggestions = []
    for s in parsed['suggestions']:
        if not isinstance(s, dict):
            continue
        s.setdefault('original', '')
        s.setdefault('suggested', '')
        s.setdefault('reason', '')
        s.setdefault('type', 'phrasing')
        if s['original'] and s['suggested'] and s['original'] != s['suggested']:
            valid_suggestions.append(s)
    parsed['suggestions'] = valid_suggestions

    return parsed


# ==================== TREE RESPONSE PARSER ====================

def _parse_tree_response(text):
    """Parse algorithm tree JSON response with validation and fallbacks."""
    parsed = _parse_json_response(text)

    # Validate required top-level keys
    parsed.setdefault('steps', [])
    parsed.setdefault('lines_tubes_step', {
        'id': 'lines_tubes',
        'organ': 'Lines and devices',
        'question': 'Are there any lines, tubes, or surgical devices?',
        'options': [
            {'label': 'No lines or tubes',
             'report_text': 'No lines, tubes, or surgical devices are identified.',
             'findings_flag': 'normal'},
        ],
        'allow_multiple': True,
    })
    parsed.setdefault('incidental_findings_step', {
        'id': 'incidentals',
        'organ': 'Incidental findings',
        'question': 'Any incidental findings to note?',
        'options': [
            {'label': 'No incidental findings', 'report_text': '',
             'findings_flag': 'normal'},
            {'label': 'Other (free text)', 'report_text': '',
             'findings_flag': 'incidental', 'is_free_text': True},
        ],
        'allow_multiple': True,
    })
    parsed.setdefault('report_template', {})

    # Validate report_template has all HL7 sections
    rt = parsed['report_template']
    rt.setdefault('indication', '')
    rt.setdefault('technique', '')
    rt.setdefault('comparison', 'No prior available for comparison.')
    rt.setdefault('impression_normal', 'No acute abnormality identified.')
    rt.setdefault('impression_abnormal', '')
    rt.setdefault('recommendation', '')

    # Validate each step
    valid_step_ids = {s.get('id') for s in parsed['steps'] if isinstance(s, dict)}
    valid_step_ids.add('lines_tubes')
    valid_step_ids.add('incidentals')

    validated_steps = []
    for step in parsed['steps']:
        if not isinstance(step, dict):
            continue
        step.setdefault('id', f'step_{len(validated_steps) + 1}')
        step.setdefault('organ', '')
        step.setdefault('question', '')
        step.setdefault('options', [])
        step.setdefault('allow_multiple', False)

        # Validate options
        valid_options = []
        for opt in step.get('options', []):
            if not isinstance(opt, dict):
                continue
            opt.setdefault('label', '')
            opt.setdefault('report_text', '')
            opt.setdefault('findings_flag', 'normal')
            # Validate next_step reference — set to null if invalid
            ns = opt.get('next_step')
            if ns and ns not in valid_step_ids:
                opt['next_step'] = None
            elif ns is None:
                opt.setdefault('next_step', None)
            valid_options.append(opt)
        step['options'] = valid_options
        validated_steps.append(step)

    parsed['steps'] = validated_steps

    # Validate lines_tubes_step and incidental_findings_step options
    for special_key in ['lines_tubes_step', 'incidental_findings_step']:
        special = parsed[special_key]
        if isinstance(special, dict):
            special.setdefault('allow_multiple', True)
            valid_opts = []
            for opt in special.get('options', []):
                if isinstance(opt, dict):
                    opt.setdefault('label', '')
                    opt.setdefault('report_text', '')
                    opt.setdefault('findings_flag', 'normal')
                    valid_opts.append(opt)
            special['options'] = valid_opts

    if not parsed['steps']:
        raise SmartReporterError("Algorithm tree has no steps. Generation may have failed.")

    return parsed
