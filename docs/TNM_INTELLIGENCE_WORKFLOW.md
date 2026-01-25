# TNM Intelligence Workflow

> **Module:** `ai_tnm.py`  
> **Last Updated:** January 2026  
> **Prompt Version:** v1

---

## Overview

The TNM Intelligence Engine transforms AJCC cancer staging data into actionable radiology guidance for MDT/tumour board discussions. It is **completely separate** from the preliminary case AI (`ai_prelim.py`).

### Design Philosophy

- **Single responsibility**: TNM staging intelligence ONLY
- **Expert perspective**: Onco-radiologist for MDT/tumour boards
- **Imaging focus**: Criteria and thresholds visible on imaging
- **Data anchored**: Uses internal AJCC database as source of truth
- **Lazy-loaded**: Only called when user explicitly requests

---

## Architecture Flow

```
User clicks TNM Intelligence button
         ↓
┌─────────────────────────────────────────────────────────────┐
│ 1. ONCOLOGIC DETECTION (Deterministic - No AI)              │
│    • Keyword check: cancer, carcinoma, tumor, etc.          │
│    • Returns: is_oncologic = true/false                     │
└─────────────────────────────────────────────────────────────┘
         ↓
┌─────────────────────────────────────────────────────────────┐
│ 2. AJCC SITE MAPPING (Deterministic - No AI)                │
│    • Query AJCCDiseaseSite table                            │
│    • Score-based matching with anatomical exclusions        │
│    • Returns: disease_site_id, disease_name, section_slug   │
└─────────────────────────────────────────────────────────────┘
         ↓
┌─────────────────────────────────────────────────────────────┐
│ 3. STAGING DATA RETRIEVAL (Database)                        │
│    • Fetch from AJCCStagingData table                       │
│    • Extract: T/N/M definitions, stage groups               │
│    • Extract: explanatory notes, figures, images            │
└─────────────────────────────────────────────────────────────┘
         ↓
┌─────────────────────────────────────────────────────────────┐
│ 4. CLAUDE AI SYNTHESIS                                      │
│    • Input: AJCC data + locked system prompt                │
│    • Output: Structured Markdown with 6 sections            │
│    • Post-process: Inject actual figures                    │
└─────────────────────────────────────────────────────────────┘
         ↓
┌─────────────────────────────────────────────────────────────┐
│ 5. RETURN RESULT                                            │
│    • tnm_intelligence_markdown: Full Markdown output        │
│    • tnm_link: Internal link to TNM viewer                  │
│    • images: AJCC figures for inline display                │
└─────────────────────────────────────────────────────────────┘
```

---

## Oncologic Detection Keywords

The system uses deterministic keyword matching to identify oncologic diagnoses:

```python
ONCOLOGIC_KEYWORDS = [
    "cancer", "carcinoma", "tumor", "tumour", "malignancy", "malignant",
    "sarcoma", "lymphoma", "leukemia", "leukaemia", "melanoma",
    "adenocarcinoma", "squamous cell", "metastatic", "metastasis",
    "metastases", "neoplasm", "neoplastic", "blastoma", "myeloma"
]
```

**No AI is used for this step** - purely keyword-based.

---

## AJCC Site Matching Algorithm

The matching algorithm uses a scoring system with anatomical exclusion patterns:

### Scoring Components

| Component | Score | Example |
|-----------|-------|---------|
| Primary cancer phrase at start | +20 | "Laryngeal cancer with..." |
| Primary cancer phrase anywhere | +12 | "...suggestive of laryngeal cancer" |
| Exact disease name match | +10 | "Larynx" in diagnosis |
| Word-level matching | +2/word | "laryngeal" matches "larynx" |
| Body part hint bonus | +3 | Module = Head & Neck |
| Organ keyword match | +5 | "laryngeal" → "larynx" |

### Anatomical Exclusion Patterns

The algorithm prevents false matches on anatomical terms:

```python
anatomical_exclusions = {
    "thyroid": [
        "thyroid cartilage",           # Laryngeal anatomy
        "thyroid cartilage invasion",
        "thyroid notch",
    ],
    "cervix": [
        "cervical spine",              # Spine anatomy
        "cervical lymph node",         # Lymph node location
        "cervical cord",               # Spinal cord
    ],
    "lung": [
        "lung metastasis",             # Metastasis TO lung, not FROM
        "pulmonary metastases",
    ],
    # ... more patterns
}
```

**Example:** "Laryngeal cancer with thyroid cartilage invasion" will correctly match to **Larynx**, not Thyroid.

---

## System Prompt (Locked)

This prompt is **immutable** and defines Claude's role:

```
You are an expert oncologic radiologist specializing in TNM staging,
MDT decision-making, and radiology education.

Your role is to transform provided AJCC TNM staging data into
clinically actionable radiology intelligence.

AUTHORITATIVE SOURCE RULE:
• AJCC data provided to you is the single source of truth
  for TNM definitions, cutoffs, and staging rules.
• You must NOT invent, alter, or contradict staging criteria.

ALLOWED REASONING:
You MAY use general, non-proprietary radiology knowledge to:
• Explain how AJCC definitions are applied on imaging
• Clarify measurement techniques and imaging landmarks
• Highlight common imaging pitfalls and limitations
• Translate explanatory notes into high-yield clinical pearls
• Frame MDT / tumour board discussion points

FORBIDDEN ACTIONS:
• Do NOT reproduce AJCC tables verbatim unless explicitly supplied
• Do NOT introduce staging rules not present in the provided data
• Do NOT cite proprietary or paywalled sources as references
• Do NOT speculate beyond evidence-based radiology knowledge

REFERENCE STYLE (DESCRIPTIVE ONLY):
• Suggest relevant educational resources using DESCRIPTIVE format only
• NEVER include DOIs, PMIDs, URLs, or page numbers
• Use this exact format:
  - "Radiographics: [Article Topic]"
  - "Radiopaedia: [Topic]"
  - "AJR: [Topic]"
• Users will search for these references themselves

TONE & STYLE:
• Senior consultant radiologist teaching a fellow
• Precise, structured, and clinically focused
• Bullet points only, no narrative paragraphs
• No filler, no repetition

OUTPUT FORMAT:
• Structured Markdown with clear section headers
• Use #### for section headings
• Use bullet points (- ) for all content
• Use **bold** for emphasis on critical findings
• Group stage-changing findings by T, N, M separately
```

---

## User Prompt Template (Dynamic)

Built from retrieved AJCC staging data:

```
Primary cancer site: {disease_name}
Body Section: {section_name}
Edition: {tnm_version}

You are provided with AJCC TNM staging data for this site,
including definitions, explanatory notes, and figures.

Using ONLY the provided AJCC data as the staging authority,
and applying radiology knowledge appropriately,
perform the following tasks:

═══════════════════════════════════════════════════════════════════
AJCC STAGING DATA (Retrieval Priority Order Applied)
═══════════════════════════════════════════════════════════════════

>>> EXPLANATORY NOTES (HIGHEST PRIORITY - analyze carefully) <<<
{explanatory_notes_text}

>>> T, N, M DEFINITIONS <<<
{t_definitions}
{n_definitions}
{m_definitions}
{stage_groups}

>>> FIGURES & DIAGRAMS <<<
{figures_section}

═══════════════════════════════════════════════════════════════════
YOUR TASK: Generate TNM Imaging Intelligence
═══════════════════════════════════════════════════════════════════

1) PRACTICAL APPLICATION OF TNM ON IMAGING
   Focus on imaging landmarks, measurement rules, modality strengths

2) CRITICAL STAGE-CHANGING IMAGING FINDINGS
   Group by T, N, M with specific transitions (e.g., T2 → T3)

3) HIGH-YIELD PEARLS FROM EXPLANATORY NOTES
   Extract clinically relevant, memorable radiology pearls

4) MDT / TUMOUR BOARD DISCUSSION POINTS
   Resectability, high-risk features, imaging limitations

5) FIGURES & DIAGRAMS
   Include AJCC figures using [FIGURE_N] placeholders

6) SUGGESTED READING (DESCRIPTIVE ONLY)
   Format: "Source: Topic" - NO URLs, DOIs, or PMIDs
```

---

## Output Structure

The AI generates structured Markdown with these sections:

```markdown
### TNM Imaging Intelligence – {Disease Name}

#### 1. Practical Application on Imaging
- Imaging landmarks relevant to this site
- Measurement rules important for staging
- Modality strengths (CT vs MRI)
- Imaging surrogates for clinical findings

#### 2. Critical Stage-Changing Findings
**T-stage**
- T2 → T3: [Finding that causes upstaging]
- T3 → T4a: [Finding that causes upstaging]
**N-stage**
- [Node findings that change staging]
**M-stage**
- [Metastasis findings]

#### 3. High-Yield Explanatory Note Pearls
- [Memorable clinical pearl]
- [Common staging error to avoid]
- [Subtle but critical nuance]

#### 4. Tumour Board / MDT Discussion Points
- Resectability assessment
- High-risk features to mention
- Imaging limitations to acknowledge
- Areas of uncertainty

#### 5. AJCC Figures & Diagrams
[FIGURE_1]
Description of what this figure illustrates...

[FIGURE_2]
Description of what this figure illustrates...

#### 6. Suggested Reading
- Radiographics: [Topic]
- AJR: [Topic]
- Radiopaedia: [Topic]

🔴 REPORTING REMINDER
[Critical imaging limitation for this cancer]

💡 TIP: Use the "Find Reference" feature to locate full articles.
```

---

## Figure Injection

After Claude generates the Markdown, figures are injected:

```python
def _inject_figures_into_markdown(markdown_content, images):
    for i, img_url in enumerate(images, 1):
        placeholder = f"[FIGURE_{i}]"
        img_html = f'''
<div style="margin: 1rem 0; text-align: center;">
    <img src="{img_url}" alt="AJCC Figure {i}" 
         style="max-width: 100%; border-radius: 8px;">
    <p style="font-size: 0.85em; color: #5a6270;">
        <strong>Figure {i}</strong>
    </p>
</div>'''
        markdown_content = markdown_content.replace(placeholder, img_html)
    return markdown_content
```

---

## API Functions

### Main Entry Point

```python
def generate_tnm_intelligence(
    *,
    diagnosis: str,           # Required
    module: str = None,       # Optional: FRCR module
    body_part: str = None,    # Optional: Body part hint
    from_case_id: int = None, # Optional: For back navigation
    provider: str = "claude"
) -> Dict:
    """
    Returns:
        - ajcc_match: AJCC disease site mapping
        - tnm_link: Internal URL to TNM page
        - tnm_intelligence_markdown: Full Markdown output
        - images: AJCC figures
        - generated_at: Timestamp
    """
```

### Helper Functions

| Function | Purpose |
|----------|---------|
| `is_oncologic_diagnosis(diagnosis)` | Keyword check for oncologic terms |
| `get_tnm_reference_only(...)` | Fast path - no AI, just AJCC link |
| `get_all_candidate_sites(...)` | Returns all matching sites with scores |
| `should_show_tnm_button(diagnosis)` | Check if TNM button should display |
| `get_tnm_button_data(...)` | Get data needed to render TNM button |

---

## Integration with ai_prelim.py

When a case has an oncologic diagnosis, `ai_prelim.py` adds TNM metadata:

```python
# In ai_prelim.py generate_prelim_case_data()
if is_oncologic_diagnosis(diagnosis):
    tnm_ref = get_tnm_reference_only(
        diagnosis=diagnosis,
        module=module,
        body_part=body_part,
        from_case_id=case_id
    )
    
    parsed["tnm_metadata"] = {
        "is_oncologic": True,
        "has_staging_data": tnm_ref.get("has_staging_data"),
        "disease_name": tnm_ref["ajcc_match"].get("disease_name"),
        "tnm_link": tnm_ref.get("tnm_link"),
    }
    
    # Add reference link to discussion
    if tnm_ref.get("has_staging_data"):
        discussion += f"\n\n**TNM Staging Reference:** [View AJCC TNM staging]({tnm_link})"
```

---

## Database Models

### AJCCDiseaseSite

```python
class AJCCDiseaseSite(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    disease_name = db.Column(db.String(200), nullable=False)
    slug = db.Column(db.String(100), nullable=False)
    body_section_id = db.Column(db.Integer, ForeignKey)
    # FRCR mapping fields
    frcr_module = db.Column(db.Enum(FRCRModule))
    frcr_body_part = db.Column(db.Enum(BodyPart))
    frcr_age_group = db.Column(db.Enum(AgeGroup))
```

### AJCCStagingData

```python
class AJCCStagingData(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    disease_site_id = db.Column(db.Integer, ForeignKey)
    diagnosis_year_id = db.Column(db.Integer, ForeignKey)
    # HTML sections from AJCC
    section_1_quick_reference_html = db.Column(db.Text)
    section_7_clinical_staging_workup_html = db.Column(db.Text)
    section_8_staging_rules_html = db.Column(db.Text)
    section_10_explanatory_notes_html = db.Column(db.Text)
    # JSON structured data
    t_definitions_json = db.Column(db.JSON)
    n_definitions_json = db.Column(db.JSON)
    m_definitions_json = db.Column(db.JSON)
    stage_groups_json = db.Column(db.JSON)
```

---

## Error Handling

| Error | Cause | Resolution |
|-------|-------|------------|
| `AiTnmError: not oncologic` | No oncologic keywords | TNM not applicable |
| `AiTnmError: no AJCC match` | Disease not in database | Add AJCC mapping |
| `AiTnmError: no staging data` | AJCC match but no data | Extract from AJCC first |
| `AiTnmError: Claude timeout` | API timeout | Retry or increase timeout |

---

## Configuration

| Environment Variable | Default | Description |
|---------------------|---------|-------------|
| `CLAUDE_API_KEY` | Required | Anthropic API key |
| `CLAUDE_MODEL` | `claude-sonnet-4-20250514` | Model to use |

---

## Usage Example

```python
from ai_tnm import generate_tnm_intelligence, is_oncologic_diagnosis

diagnosis = "Laryngeal cancer with thyroid cartilage invasion"

if is_oncologic_diagnosis(diagnosis):
    result = generate_tnm_intelligence(
        diagnosis=diagnosis,
        module="Head and Neck",
        from_case_id=123
    )
    
    print(result["tnm_intelligence_markdown"])
    # → Structured Markdown with 6 sections
    
    print(result["tnm_link"])
    # → /tnm/head-and-neck/larynx?year=2026&from_case=123
```

---

*Last updated: January 2026*
