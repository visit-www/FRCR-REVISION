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

from ai_client import call_claude as _call_claude_raw, parse_json_response as _parse_json_raw, AIClientError
from clinical_tool_generator import format_resources_for_prompt

logger = logging.getLogger(__name__)


class SmartReporterError(AIClientError):
    """Raised when Smart Reporter generation fails."""
    pass


# ==================== SHARED API HELPERS (delegated to ai_client) ====================

def _call_claude(system_prompt, user_prompt, model=None, max_tokens=4000,
                 temperature=0.3, timeout=60):
    """Wrapper that raises SmartReporterError instead of AIClientError."""
    return _call_claude_raw(system_prompt, user_prompt, model=model,
                            max_tokens=max_tokens, temperature=temperature,
                            timeout=timeout, error_class=SmartReporterError)


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
    "Keep answers under 200 words. Plain text only — no markdown or HTML."
)

REVIEW_REPORT_SYSTEM_PROMPT = (
    "You are a consultant radiologist reviewing a trainee's draft PACS report. "
    "You check for spelling, grammar, radiology phrasing conventions, and structural completeness. "
    "Output valid JSON only. No markdown fences. No text outside the JSON object."
)

# ---- Quick Check (Layer 0): Lightweight proofreading only ----

QUICK_REVIEW_SYSTEM_PROMPT = (
    "You are a medical text proofreader specialising in radiology PACS reports. "
    "Fix spelling (including radiology-specific terms), grammar, and phrasing. "
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
4. Preserve all section headings (INDICATION, TECHNIQUE, FINDINGS, IMPRESSION, etc.) exactly as they appear.
5. Do NOT assess clinical correctness. Do NOT add content. Do NOT change clinical meaning.
6. Each suggestion must quote the EXACT original text so the frontend can locate it.
7. Max 10 suggestions. Prioritise: spelling > grammar > phrasing.
8. If the report is already well-written, return an empty suggestions array and the original text as improved_report.

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
    "- NEVER add findings the trainee didn't describe — the images aren't available to you\n"
    "- NEVER fabricate or hallucinate imaging findings\n"
    "- NEVER suggest the trainee add findings they didn't observe — you cannot see the images\n\n"
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
  "insights": {{
    "clinical_question_coverage": "Does the report answer the referring clinician's question? If the findings do NOT explain the clinical presentation (e.g. right-sided pain but only left-sided pathology found), flag this discordance. 1-2 sentences.",
    "quality_assessment": "Would a subspecialist be satisfied? Specifically: (1) Does the impression answer the clinical question FIRST, before incidental findings? (2) Are findings prioritised by clinical significance? (3) Are measurements provided where they would change management? 1-2 sentences.",
    "differentials_to_consider": ["Differential 1 to consider", "Differential 2"],
    "recommendation_check": "Are recommendations appropriate? Flag if urgent findings lack escalation language, or if follow-up timings are missing/inappropriate. 1 sentence.",
    "teaching_point": "A genuinely insightful clinical pearl — see RULES FOR INSIGHTS below. 1-3 sentences."
  }}
}}

RULES FOR RESPONSE_TYPE:
1. "full_report" — use when you provide complete report text in report_text (a full report, full impression, full findings rewrite, or finalization). The user will REPLACE their draft with report_text.
2. "advisory" — use when you only provide advice, a short suggestion, a knowledge answer, or a partial addition in answer. report_text must be empty string.

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
6. Flag missing measurements where they would change management (e.g. "aortic aneurysm" without
   diameter, "pulmonary nodule" without size, "lymph node" without short-axis measurement).
   Suggest: "Consider adding measurement — management thresholds depend on size."
7. Max 8 corrections. Prioritise: anatomical/sidedness errors > clinical omissions > terminology > phrasing.
8. If the report has no issues, return an empty corrections array.
9. If the report is empty or very short, return empty corrections and note this in quality_assessment.

RULES FOR ANSWER AND REPORT_TEXT:
1. "answer" is for advisory/explanatory text ONLY. Never put complete report sections in answer.
2. "report_text" is for complete PACS-ready report text ONLY. Put full impressions, findings rewrites, or finalized reports here.
3. If the trainee asks BOTH a question AND for report text (e.g. "write the impression and explain why"), put the explanation in answer and the PACS-ready text in report_text.
4. If the trainee only asks a knowledge question (e.g. "what's the differential?"), put the answer in answer and leave report_text as empty string.
5. If the trainee only asks for report text (e.g. "finalize this report"), put the report in report_text. answer can be empty string or a brief note.
6. Write report_text as a consultant would dictate at a workstation. No hedging beyond standard conventions. Plain text only — no markdown, no HTML, no bullet lists.
7. Keep answer under 250 words. report_text has no word limit — write complete sections.
8. Do NOT add commentary about the report quality in answer — only answer the question asked.

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
3. Suggest structural improvements if sections are missing or out of standard order.
4. Do NOT change clinical meaning. Do NOT add findings the user did not describe.
5. Do NOT remove any content the user wrote — only rephrase for clarity and convention.
6. If the report is already well-written, return an empty suggestions array and the original text as improved_report.
7. Each suggestion must quote the EXACT original text so the frontend can locate it.
8. Limit to the most impactful 15 suggestions maximum. Prioritise: spelling > grammar > phrasing > structure.
9. For completeness type: suggest if standard sections (INDICATION, TECHNIQUE, COMPARISON, FINDINGS, IMPRESSION) are missing.

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


# ==================== ANATOMY REFERENCE (Phase 5) ====================

ANATOMY_SYSTEM_PROMPT = (
    "You are a senior consultant radiologist creating a workstation-ready anatomy reference "
    "for radiology trainees. You think like someone who has reported thousands of CT/MRI/X-ray "
    "studies and knows EXACTLY what trips up trainees at the workstation.\n\n"
    "Your output must be:\n"
    "- Clinically aligned: tied to real imaging scenarios, not textbook descriptions\n"
    "- Practically useful: help trainees recognise structures on actual scans and report correctly\n"
    "- Memorable: use mnemonics, analogies, and 'pearl' boxes where helpful\n"
    "- Warning-oriented: emphasise pitfalls, normal variants that mimic pathology, "
    "and common reporting errors\n\n"
    "Output valid HTML. No markdown. Use <h4>, <p>, <ul>, <li>, <strong>, <em> tags. "
    "For high-yield tips, use: <div class=\"anatomy-pearl\"><strong>Pearl:</strong> ...</div>"
)

ANATOMY_PROMPT = """Create a radiology-focused anatomy reference for: {topic}

You are writing for a radiology trainee who needs to understand this anatomy
well enough to REPORT on imaging studies confidently. NOT a textbook chapter —
a practical workstation companion.

Structure your response as HTML with these sections:

1. <h4>Essential Anatomy for Reporting</h4>
   - Key structures a radiologist MUST identify on imaging
   - Use imaging landmarks (e.g. "at the level of the carina", "posterior to the IVC")
   - Include cross-sectional relationships visible on axial CT/MRI

2. <h4>Imaging Appearance by Modality</h4>
   - Normal appearance on CT, MRI, and/or ultrasound (whichever are relevant)
   - Signal/density characteristics, enhancement patterns
   - What the structure looks like vs what it gets confused with

3. <h4>Normal Variants & Pitfalls</h4>
   - CRITICAL: variants that mimic pathology (e.g. persistent sciatic artery mimicking DVT)
   - Common reporting errors related to this anatomy
   - Include a <div class="anatomy-pearl"> for each high-yield pitfall

4. <h4>Key Measurements & Thresholds</h4>
   - Normal size ranges that trigger action if exceeded
   - When to call it abnormal (e.g. "aortic root >4cm warrants follow-up")

5. <h4>Clinical Correlation</h4>
   - How pathology at this site presents on imaging
   - What clinical question is the referrer usually asking?
   - Link anatomy to the report: what findings at this site mean clinically

6. <h4>Memory Aids</h4>
   - Mnemonics, analogies, or systematic approaches to avoid missing findings
   - E.g. "ABCDE approach for chest X-ray" or "the rule of 2s for Meckel's"
   - Keep these genuinely useful, not forced

Target length: 400-500 words. Every sentence should help a trainee report better.
NEVER include generic filler. If a section has nothing useful to add, skip it.
Use HTML tags: <h4>, <p>, <ul>, <li>, <strong>, <em>.
For high-yield tips use: <div class="anatomy-pearl"><strong>Pearl:</strong> text</div>"""


def generate_anatomy_reference(topic):
    """
    Generate a concise anatomy reference for the editor Anatomy Panel.
    Uses Haiku for speed. DB lookup should be attempted first (in routes).

    Args:
        topic: Anatomical topic (e.g. "Circle of Willis", "brachial plexus")

    Returns:
        dict with: title, content_html, source ('ai'), model, token_count
    """
    haiku_model = os.getenv("CLAUDE_QUICK_MODEL", "claude-haiku-4-5-20251001")

    prompt = ANATOMY_PROMPT.format(topic=topic)

    text, model, tokens = _call_claude(
        system_prompt=ANATOMY_SYSTEM_PROMPT,
        user_prompt=prompt,
        model=haiku_model,
        max_tokens=2000,
        temperature=0.3,
        timeout=20,
    )

    return {
        'title': topic.title(),
        'content_html': text,
        'source': 'ai',
        'model': model,
        'token_count': tokens,
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


# ==================== UNIFIED AI ASSIST (Layers 1+2+3) ====================

def unified_ai_assist(report_text, question, clinical_question='', modality='',
                      body_section='', external_context=None, resources=None):
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

    user_prompt = UNIFIED_ASSIST_PROMPT.format(
        report_text=report_text or '(empty report — user may be starting fresh or about to paste their report)',
        question=question,
        clinical_question=clinical_question or 'Not specified',
        modality=modality or 'Not specified',
        body_section=body_section or 'Not specified',
        resource_section=resource_section,
    )

    effective_model = os.getenv("CLAUDE_MODEL", "claude-sonnet-4-5-20250929")

    text, model, tokens = _call_claude(
        system_prompt=UNIFIED_ASSIST_SYSTEM_PROMPT,
        user_prompt=user_prompt,
        model=effective_model,
        max_tokens=4000,
        temperature=0.3,
        timeout=45,
    )

    parsed = _parse_assist_response(text, question)
    parsed['model'] = model
    parsed['token_count'] = tokens

    return parsed


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
    }

    # Ensure differentials is a list
    if not isinstance(insights['differentials_to_consider'], list):
        insights['differentials_to_consider'] = []

    # Extract response_type
    response_type = parsed.get('response_type', 'advisory')
    if response_type not in ('full_report', 'advisory'):
        response_type = 'advisory'

    return {
        'response_type': response_type,
        'corrections': corrections,
        'answer': answer,
        'report_text': report_text,
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
