# AI Reporting Assistant - Implementation Plan

**Status:** Planning
**Priority:** High (Teaching Tool)
**Complexity:** Medium-High
**Estimated Effort:** 2-3 weeks
**Dependencies:** Claude API (already integrated)

---

## Executive Summary

Build an AI-powered "Algorithmic Reporting Pathway Generator" that creates structured, diagnosis-agnostic decision trees for radiology case interpretation. This teaching tool helps FRCR trainees develop systematic approaches to image interpretation, ensuring no critical findings are missed.

---

## Core Concept

The AI Reporting Assistant generates **structured decision trees** for any:
- **Modality:** CT, MRI, X-ray, Ultrasound, Nuclear Medicine, CBCT, PET
- **Anatomical Region:** Any body part
- **Clinical Context:** Oncologic staging, emergency, trauma, routine

### Key Principles (from source document)
1. **WORST FIRST** - Life-threatening diagnoses first
2. **SYSTEMATIC BEFORE SPECIFIC** - Complete anatomical review before pattern matching
3. **BINARY DECISION LOGIC** - Yes/No branching narrows differential
4. **DIAGNOSIS-AGNOSTIC** - Works for ANY final diagnosis
5. **ACTIONABLE OUTPUT** - Clear impression with confidence levels

---

## Feature Overview

### 1. Standalone Generator (New Page)
- User inputs: modality, region, indication, patient context
- AI generates complete algorithmic pathway
- Rendered as visual teaching card/poster
- Downloadable/printable format

### 2. Case-Integrated Mode
- From existing case, generate algorithmic approach
- Pre-fills modality, region from case metadata
- Links generated pathway to case for future reference

### 3. Refinement Mode
- Add lab values, clinical data to narrow differential
- AI updates diagnosis ranking and confidence
- Shows how additional data shifts probabilities

---

## Database Schema

### New Models

```python
# models.py additions

class AlgorithmicPathway(db.Model):
    """AI-generated reporting decision tree"""
    __tablename__ = 'algorithmic_pathway'

    id = db.Column(db.Integer, primary_key=True)

    # Input parameters
    modality = db.Column(db.String(50), nullable=False)  # CT, MRI, X-ray, etc.
    anatomical_region = db.Column(db.String(100), nullable=False)
    clinical_indication = db.Column(db.String(500), nullable=False)
    patient_context = db.Column(db.Text, nullable=True)  # Age, risk factors, history

    # Generated content
    title = db.Column(db.String(300), nullable=True)
    pathway_html = db.Column(db.Text, nullable=True)  # Full rendered HTML
    pathway_markdown = db.Column(db.Text, nullable=True)  # Source markdown

    # Metadata
    model_used = db.Column(db.String(50), default='claude-sonnet')
    generation_time_ms = db.Column(db.Integer, nullable=True)
    token_count = db.Column(db.Integer, nullable=True)

    # Linking
    case_id = db.Column(db.Integer, db.ForeignKey('case.id'), nullable=True)
    created_by_user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)

    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, onupdate=datetime.utcnow)

    # Relationships
    case = db.relationship('Case', backref='algorithmic_pathways')
    created_by = db.relationship('User', backref='created_pathways')
    refinements = db.relationship('PathwayRefinement', backref='pathway', cascade='all, delete-orphan')


class PathwayRefinement(db.Model):
    """Refinement with additional clinical/lab data"""
    __tablename__ = 'pathway_refinement'

    id = db.Column(db.Integer, primary_key=True)
    pathway_id = db.Column(db.Integer, db.ForeignKey('algorithmic_pathway.id'), nullable=False)

    # Refinement data (JSON)
    lab_values = db.Column(db.JSON, nullable=True)  # {"WBC": 15000, "CRP": 120, ...}
    clinical_info = db.Column(db.JSON, nullable=True)  # {"fever": true, "duration_days": 3, ...}
    additional_history = db.Column(db.Text, nullable=True)

    # Refined output
    refined_differential_html = db.Column(db.Text, nullable=True)
    confidence_level = db.Column(db.String(20), nullable=True)  # Definite/Probable/Possible/Indeterminate
    most_likely_diagnosis = db.Column(db.String(200), nullable=True)

    created_at = db.Column(db.DateTime, default=datetime.utcnow)
```

### Migration SQL

```sql
-- migrations/add_algorithmic_pathway.sql

CREATE TABLE IF NOT EXISTS algorithmic_pathway (
    id SERIAL PRIMARY KEY,
    modality VARCHAR(50) NOT NULL,
    anatomical_region VARCHAR(100) NOT NULL,
    clinical_indication VARCHAR(500) NOT NULL,
    patient_context TEXT,
    title VARCHAR(300),
    pathway_html TEXT,
    pathway_markdown TEXT,
    model_used VARCHAR(50) DEFAULT 'claude-sonnet',
    generation_time_ms INTEGER,
    token_count INTEGER,
    case_id INTEGER REFERENCES "case"(id) ON DELETE SET NULL,
    created_by_user_id INTEGER REFERENCES "user"(id),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP
);

CREATE TABLE IF NOT EXISTS pathway_refinement (
    id SERIAL PRIMARY KEY,
    pathway_id INTEGER NOT NULL REFERENCES algorithmic_pathway(id) ON DELETE CASCADE,
    lab_values JSONB,
    clinical_info JSONB,
    additional_history TEXT,
    refined_differential_html TEXT,
    confidence_level VARCHAR(20),
    most_likely_diagnosis VARCHAR(200),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_algorithmic_pathway_case ON algorithmic_pathway(case_id);
CREATE INDEX idx_algorithmic_pathway_modality ON algorithmic_pathway(modality);
CREATE INDEX idx_algorithmic_pathway_region ON algorithmic_pathway(anatomical_region);
```

---

## AI Prompts

### System Prompt (Store in `ai_reporting_assistant.py`)

```python
REPORTING_ASSISTANT_SYSTEM_PROMPT = """
ROLE:
You are an experienced consultant radiologist and clinical educator with subspecialty expertise across all imaging modalities. You are guiding a radiology registrar/trainee through systematic image interpretation, teaching them to develop a structured cognitive approach that leads to an accurate, defensible radiological report.

Your teaching style is:
- Methodical and systematic
- Clinically pragmatic
- Focused on pattern recognition and key discriminators
- Alert to pitfalls and mimics
- Confident but appropriately cautious with uncertainty
- Adaptable to both oncologic staging and non-oncologic pathology

CORE PRINCIPLES:

1. WORST FIRST ALWAYS
   - Begin with life-threatening and time-critical diagnoses
   - "What will kill or disable this patient if I miss it?"

2. SYSTEMATIC BEFORE SPECIFIC
   - Enforce reproducible anatomical/technical review before pattern matching
   - Prevents satisfaction of search error
   - Every structure must be checked regardless of the obvious finding

3. BINARY DECISION LOGIC
   - Use "Present / Absent" or "Yes / No" branching
   - Each decision point narrows the differential
   - Clear gates for escalation vs. continuation

4. DIAGNOSIS-AGNOSTIC APPROACH
   - The pathway must work for ANY final diagnosis
   - Do not assume malignancy or any specific pathology
   - Let the imaging features guide toward the diagnosis
   - Support both staging (if cancer) and characterisation (if non-cancer)

5. ACTIONABLE OUTPUT
   - End with clear, structured impression
   - State confidence level
   - Specify what further imaging or clinical correlation is needed

CRITICAL RULES:
- Never assume a diagnosis before completing systematic review
- Always include "Red Flags" that require immediate action
- Provide specific imaging criteria (measurements, thresholds, HU values where applicable)
- Include "How to Identify" guidance for each key finding
- Differentiate from mimics and look-alikes
- Support both emergency and elective imaging contexts
- If the case could be oncologic, include staging systems; if non-oncologic, include appropriate grading/classification systems
"""
```

### User Prompt Template (Generation)

```python
PATHWAY_GENERATION_PROMPT = """
TASK:
Generate a DIAGNOSIS-AGNOSTIC ALGORITHMIC REPORTING PATHWAY for the following radiology case:

CASE DETAILS:
- Modality: {modality}
- Anatomical Region: {region}
- Clinical Indication: {indication}
- Patient Context: {context}

The pathway must:
1. Work regardless of what the final diagnosis turns out to be
2. Guide systematic image review from first to last image
3. Identify critical/urgent findings that need immediate action
4. Characterise any dominant abnormality fully
5. Generate appropriate differential diagnoses based on imaging features
6. Support staging IF malignancy is found, OR appropriate classification for non-malignant pathology
7. Produce a structured report template

OUTPUT FORMAT:
Generate a structured decision tree using the following mandatory sections. Use tables, checkboxes, and clear hierarchies. Output as HTML suitable for rendering as a visual teaching card.

---

MANDATORY OUTPUT STRUCTURE:

## TITLE
"Algorithmic Imaging Approach: [Modality] — [Region] — [Clinical Scenario]"

## QUICK NAVIGATION
Provide anchor links to: Technical Adequacy | Red Flags | Systematic Review | Dominant Abnormality | Differential | Report Template | Refinement Options

## STEP 0 — TECHNICAL ADEQUACY & ORIENTATION
- Checklist for technical quality (coverage, contrast, artefacts, comparison studies)
- Protocol appropriateness for the clinical question
- Initial orientation observations

## STEP 1 — RED FLAGS: CRITICAL & TIME-SENSITIVE FINDINGS
For EACH red flag finding, create a table:
| Finding | How to Identify (specific criteria) | How to Distinguish from Mimics | Present | Absent |

Include a DECISION GATE:
→ If ANY critical finding present → STOP, escalate, communicate urgently
→ If all excluded → Proceed to systematic review

## STEP 2 — SYSTEMATIC ANATOMICAL REVIEW
Region-specific checklist covering ALL structures that must be reviewed.
Format as tables with: Structure | Normal | Abnormal | Comment

Include a "DON'T MISS" subsection for commonly overlooked areas.

## STEP 3 — DOMINANT ABNORMALITY CHARACTERISATION
If an abnormality is identified, characterise it fully:

3.1 CONFIRM THE ABNORMALITY
- Specific criteria/thresholds for abnormality

3.2 LOCALISE
- Precise anatomical location
- Relationship to landmarks

3.3 CHARACTERISE (adapt based on what the abnormality is)
- Size/extent (measurements)
- Morphology (shape, margins, internal architecture)
- Density/signal/echogenicity (modality-specific)
- Enhancement pattern (if contrast given)
- Effect on adjacent structures
- Multiplicity

3.4 SPECIFIC SIGNS
Table of relevant imaging signs: Sign | Appearance | How to Find | Significance

3.5 ASSESS SEVERITY/GRADE
- If ONCOLOGIC: Include relevant staging system (TNM, FIGO, Ann Arbor, etc.)
- If NON-ONCOLOGIC: Include relevant grading/classification (Balthazar, AAST injury grade, infection severity, etc.)
- If UNKNOWN: Provide both options

3.6 ASSESS FOR COMPLICATIONS
Complication-specific checklist

## STEP 4 — AETIOLOGY / DIFFERENTIAL CONSIDERATIONS
Based on the imaging pattern, provide:
- Common causes (with frequency if known)
- Key imaging features that discriminate between causes
- Pattern recognition table

## STEP 5 — DIFFERENTIAL DIAGNOSIS (RANKED)
| Rank | Diagnosis | Supporting Features | Features Against |

Include MIMICS TO CONSIDER

## STEP 6 — SAMPLE STRUCTURED REPORT
Provide a complete report template specific to this case type with:
- Indication
- Comparison
- Technique
- Findings (structured by anatomy/system)
- Impression (numbered, most important first)
- Recommendations

## REFINEMENT OPTIONS
List specific clinical questions and laboratory values that could narrow the differential.
Format as:
"If you provide [X information], I can refine the diagnosis to..."

Include an interpretation grid showing how different lab/clinical combinations change the likely diagnosis.

---

STYLE REQUIREMENTS:
- Use HTML tables with proper styling classes
- Use checkbox symbols for checklists
- Use clear hierarchy with h2, h3, h4 headers
- Include specific numeric thresholds and measurements where applicable
- Include "TEACHING PEARL" callout boxes (class="teaching-pearl")
- Include "PITFALL" callout boxes (class="pitfall-box")
- Use red-flag emoji only for critical findings section header
- Write as if speaking to a trainee at the workstation
- Make it visually scannable with consistent formatting

IMPORTANT REMINDERS:
1. This must work for ANY diagnosis - do not bias toward cancer or any specific pathology
2. If the indication suggests possible malignancy, include staging; if not, focus on appropriate classification
3. Always include the possibility that the study may be NORMAL
4. Red flags should cover life-threatening conditions regardless of the indication
5. The systematic review must be COMPLETE - every structure in the region
"""
```

### Refinement Prompt Template

```python
PATHWAY_REFINEMENT_PROMPT = """
REFINEMENT REQUEST:

The user has provided additional clinical/laboratory information to refine the diagnosis.

ORIGINAL CASE:
- Modality: {modality}
- Region: {region}
- Indication: {indication}

ADDITIONAL INFORMATION PROVIDED:
{refinement_data}

TASK:
Based on this additional information, provide:

1. REFINED DIFFERENTIAL DIAGNOSIS
   - Re-rank the differential based on the new information
   - Explain how each piece of data shifts the probabilities

2. UPDATED MOST LIKELY DIAGNOSIS
   - State the refined most likely diagnosis
   - Confidence level: Definite / Probable / Possible / Indeterminate

3. ADDITIONAL IMAGING CONSIDERATIONS
   - Would any additional imaging help further narrow the diagnosis?
   - What specific protocol or sequences would be most useful?

4. UPDATED REPORT IMPRESSION
   - Provide a refined impression incorporating the clinical/lab correlation

Format the output as clean HTML with consistent styling matching the original pathway.
"""
```

---

## Backend Implementation

### File Structure

```
ai_reporting_assistant/
├── __init__.py
├── prompts.py          # All prompt templates
├── generator.py        # Main generation logic
├── routes.py           # API endpoints
└── templates/
    └── ai_reporting_assistant/
        ├── generator.html      # Standalone generator page
        └── pathway_view.html   # View saved pathway
```

### Core Generator (`ai_reporting_assistant/generator.py`)

```python
"""
AI Reporting Assistant - Algorithmic Pathway Generator
Uses Claude API to generate diagnosis-agnostic reporting decision trees.
"""

import os
import time
import logging
from typing import Tuple, Dict, Any, Optional
from anthropic import Anthropic

from .prompts import (
    REPORTING_ASSISTANT_SYSTEM_PROMPT,
    PATHWAY_GENERATION_PROMPT,
    PATHWAY_REFINEMENT_PROMPT
)

logger = logging.getLogger(__name__)

# Modality options for UI dropdown
MODALITIES = [
    ("CT", "CT (Computed Tomography)"),
    ("CT_CONTRAST", "CT with Contrast"),
    ("MRI", "MRI (Magnetic Resonance Imaging)"),
    ("XRAY", "X-ray / Radiograph"),
    ("US", "Ultrasound"),
    ("NM", "Nuclear Medicine / SPECT"),
    ("PET", "PET / PET-CT"),
    ("CBCT", "CBCT (Cone Beam CT)"),
    ("FLUORO", "Fluoroscopy"),
    ("MAMMO", "Mammography"),
]

# Anatomical region options (grouped)
ANATOMICAL_REGIONS = {
    "Head & Neck": [
        "Brain",
        "Head and Neck",
        "Orbits",
        "Temporal Bones",
        "Paranasal Sinuses",
        "Neck / Soft Tissue Neck",
        "Thyroid",
        "Dental / Maxillofacial",
    ],
    "Chest": [
        "Chest",
        "Chest Abdomen Pelvis (CAP)",
        "Thorax",
        "Mediastinum",
        "Heart / Cardiac",
    ],
    "Abdomen & Pelvis": [
        "Abdomen",
        "Abdomen and Pelvis",
        "Liver",
        "Pancreas",
        "Kidneys / Renal",
        "Adrenals",
        "Pelvis",
        "Male Pelvis",
        "Female Pelvis",
        "Bowel / GI Tract",
    ],
    "Musculoskeletal": [
        "Spine - Cervical",
        "Spine - Thoracic",
        "Spine - Lumbar",
        "Spine - Whole",
        "Shoulder",
        "Elbow",
        "Wrist / Hand",
        "Hip",
        "Knee",
        "Ankle / Foot",
        "Long Bones",
    ],
    "Vascular": [
        "Aorta",
        "Peripheral Arteries",
        "Peripheral Veins",
        "Pulmonary Arteries (CTPA)",
    ],
    "Other": [
        "Whole Body",
        "Polytrauma",
        "Paediatric",
    ],
}

# Common clinical indications (for autocomplete)
COMMON_INDICATIONS = [
    # Oncologic
    "Staging - newly diagnosed cancer",
    "Restaging / follow-up known malignancy",
    "Surveillance post-treatment",
    "Query recurrence",
    "Characterise suspicious lesion",
    # Emergency
    "Acute abdominal pain",
    "Acute chest pain",
    "Query pulmonary embolism",
    "Query aortic dissection",
    "Trauma",
    "Stroke / query CVA",
    "Query appendicitis",
    "Query bowel obstruction",
    # Routine
    "Chronic pain",
    "Pre-operative planning",
    "Post-operative follow-up",
    "Screening",
    "Incidental finding characterisation",
]


def generate_algorithmic_pathway(
    modality: str,
    anatomical_region: str,
    clinical_indication: str,
    patient_context: str = "",
) -> Tuple[bool, str, Dict[str, Any]]:
    """
    Generate an algorithmic reporting pathway using Claude AI.

    Args:
        modality: Imaging modality (CT, MRI, etc.)
        anatomical_region: Body region
        clinical_indication: Why the scan was done
        patient_context: Optional patient details (age, history)

    Returns:
        Tuple of (success, message, result_data)
        result_data contains: title, pathway_html, pathway_markdown, token_count, generation_time_ms
    """
    api_key = os.getenv('CLAUDE_API_KEY')
    if not api_key:
        return False, "CLAUDE_API_KEY not configured", {}

    model = os.getenv('CLAUDE_MODEL', 'claude-sonnet-4-20250514')

    try:
        client = Anthropic(api_key=api_key)

        # Build user prompt
        user_prompt = PATHWAY_GENERATION_PROMPT.format(
            modality=modality,
            region=anatomical_region,
            indication=clinical_indication,
            context=patient_context or "Not specified"
        )

        start_time = time.time()

        response = client.messages.create(
            model=model,
            max_tokens=8000,  # Pathways can be long
            system=REPORTING_ASSISTANT_SYSTEM_PROMPT,
            messages=[
                {"role": "user", "content": user_prompt}
            ]
        )

        generation_time_ms = int((time.time() - start_time) * 1000)

        # Extract content
        pathway_content = response.content[0].text

        # Extract title from content
        title = f"Algorithmic Approach: {modality} — {anatomical_region}"
        if "## TITLE" in pathway_content:
            # Try to extract the actual title
            import re
            title_match = re.search(r'## TITLE\s*\n+"?([^"\n]+)"?', pathway_content)
            if title_match:
                title = title_match.group(1).strip()

        # Token count
        token_count = response.usage.input_tokens + response.usage.output_tokens

        result_data = {
            'title': title,
            'pathway_html': pathway_content,  # Will be rendered as HTML
            'pathway_markdown': pathway_content,  # Keep original
            'token_count': token_count,
            'generation_time_ms': generation_time_ms,
            'model_used': model,
        }

        logger.info(f"[Reporting Assistant] Generated pathway for {modality}/{anatomical_region} in {generation_time_ms}ms")

        return True, "Pathway generated successfully", result_data

    except Exception as e:
        logger.exception(f"[Reporting Assistant] Generation error: {e}")
        return False, str(e), {}


def refine_pathway(
    original_pathway: 'AlgorithmicPathway',
    lab_values: Optional[Dict] = None,
    clinical_info: Optional[Dict] = None,
    additional_history: str = "",
) -> Tuple[bool, str, Dict[str, Any]]:
    """
    Refine an existing pathway with additional clinical/lab data.

    Args:
        original_pathway: The AlgorithmicPathway model instance
        lab_values: Dict of lab values {"WBC": 15000, "CRP": 120, ...}
        clinical_info: Dict of clinical info {"fever": true, "duration_days": 3, ...}
        additional_history: Free text additional history

    Returns:
        Tuple of (success, message, result_data)
    """
    api_key = os.getenv('CLAUDE_API_KEY')
    if not api_key:
        return False, "CLAUDE_API_KEY not configured", {}

    model = os.getenv('CLAUDE_MODEL', 'claude-sonnet-4-20250514')

    # Build refinement data string
    refinement_parts = []

    if lab_values:
        lab_str = "\n".join([f"- {k}: {v}" for k, v in lab_values.items()])
        refinement_parts.append(f"Laboratory Values:\n{lab_str}")

    if clinical_info:
        clinical_str = "\n".join([f"- {k}: {v}" for k, v in clinical_info.items()])
        refinement_parts.append(f"Clinical Findings:\n{clinical_str}")

    if additional_history:
        refinement_parts.append(f"Additional History:\n{additional_history}")

    refinement_data = "\n\n".join(refinement_parts)

    if not refinement_data.strip():
        return False, "No refinement data provided", {}

    try:
        client = Anthropic(api_key=api_key)

        user_prompt = PATHWAY_REFINEMENT_PROMPT.format(
            modality=original_pathway.modality,
            region=original_pathway.anatomical_region,
            indication=original_pathway.clinical_indication,
            refinement_data=refinement_data
        )

        # Include original pathway in context
        messages = [
            {"role": "user", "content": f"Original pathway:\n\n{original_pathway.pathway_markdown}"},
            {"role": "assistant", "content": "I have reviewed the original algorithmic pathway. Please provide the refinement data."},
            {"role": "user", "content": user_prompt}
        ]

        response = client.messages.create(
            model=model,
            max_tokens=4000,
            system=REPORTING_ASSISTANT_SYSTEM_PROMPT,
            messages=messages
        )

        refined_content = response.content[0].text

        # Extract confidence level
        confidence = "Indeterminate"
        for level in ["Definite", "Probable", "Possible", "Indeterminate"]:
            if level.lower() in refined_content.lower():
                confidence = level
                break

        result_data = {
            'refined_differential_html': refined_content,
            'confidence_level': confidence,
            'lab_values': lab_values,
            'clinical_info': clinical_info,
            'additional_history': additional_history,
        }

        return True, "Pathway refined successfully", result_data

    except Exception as e:
        logger.exception(f"[Reporting Assistant] Refinement error: {e}")
        return False, str(e), {}
```

### API Routes (`ai_reporting_assistant/routes.py`)

```python
"""
AI Reporting Assistant - Flask Routes
"""

from flask import Blueprint, render_template, request, jsonify
from flask_login import login_required, current_user
from models import db, UserRole, AlgorithmicPathway, PathwayRefinement
from .generator import (
    generate_algorithmic_pathway,
    refine_pathway,
    MODALITIES,
    ANATOMICAL_REGIONS,
    COMMON_INDICATIONS,
)

reporting_assistant_bp = Blueprint(
    'reporting_assistant',
    __name__,
    url_prefix='/reporting-assistant',
    template_folder='templates'
)


@reporting_assistant_bp.route('/')
@login_required
def index():
    """Main generator page"""
    return render_template(
        'ai_reporting_assistant/generator.html',
        modalities=MODALITIES,
        anatomical_regions=ANATOMICAL_REGIONS,
        common_indications=COMMON_INDICATIONS,
    )


@reporting_assistant_bp.route('/generate', methods=['POST'])
@login_required
def generate():
    """Generate new algorithmic pathway"""
    data = request.get_json()

    modality = data.get('modality', '').strip()
    region = data.get('anatomical_region', '').strip()
    indication = data.get('clinical_indication', '').strip()
    context = data.get('patient_context', '').strip()
    case_id = data.get('case_id')  # Optional link to case

    if not modality or not region or not indication:
        return jsonify({
            'success': False,
            'error': 'Modality, region, and indication are required'
        }), 400

    success, message, result_data = generate_algorithmic_pathway(
        modality=modality,
        anatomical_region=region,
        clinical_indication=indication,
        patient_context=context,
    )

    if not success:
        return jsonify({'success': False, 'error': message}), 500

    # Save to database
    pathway = AlgorithmicPathway(
        modality=modality,
        anatomical_region=region,
        clinical_indication=indication,
        patient_context=context,
        title=result_data.get('title'),
        pathway_html=result_data.get('pathway_html'),
        pathway_markdown=result_data.get('pathway_markdown'),
        model_used=result_data.get('model_used'),
        generation_time_ms=result_data.get('generation_time_ms'),
        token_count=result_data.get('token_count'),
        case_id=case_id if case_id else None,
        created_by_user_id=current_user.id,
    )

    db.session.add(pathway)
    db.session.commit()

    return jsonify({
        'success': True,
        'message': message,
        'pathway_id': pathway.id,
        'title': pathway.title,
        'pathway_html': pathway.pathway_html,
        'generation_time_ms': pathway.generation_time_ms,
    })


@reporting_assistant_bp.route('/pathway/<int:pathway_id>')
@login_required
def view_pathway(pathway_id):
    """View saved pathway"""
    pathway = AlgorithmicPathway.query.get_or_404(pathway_id)
    return render_template(
        'ai_reporting_assistant/pathway_view.html',
        pathway=pathway,
    )


@reporting_assistant_bp.route('/pathway/<int:pathway_id>/refine', methods=['POST'])
@login_required
def refine(pathway_id):
    """Refine existing pathway with additional data"""
    pathway = AlgorithmicPathway.query.get_or_404(pathway_id)
    data = request.get_json()

    lab_values = data.get('lab_values', {})
    clinical_info = data.get('clinical_info', {})
    additional_history = data.get('additional_history', '')

    success, message, result_data = refine_pathway(
        original_pathway=pathway,
        lab_values=lab_values,
        clinical_info=clinical_info,
        additional_history=additional_history,
    )

    if not success:
        return jsonify({'success': False, 'error': message}), 500

    # Save refinement
    refinement = PathwayRefinement(
        pathway_id=pathway.id,
        lab_values=lab_values,
        clinical_info=clinical_info,
        additional_history=additional_history,
        refined_differential_html=result_data.get('refined_differential_html'),
        confidence_level=result_data.get('confidence_level'),
    )

    db.session.add(refinement)
    db.session.commit()

    return jsonify({
        'success': True,
        'message': message,
        'refinement_id': refinement.id,
        'refined_html': refinement.refined_differential_html,
        'confidence_level': refinement.confidence_level,
    })


@reporting_assistant_bp.route('/my-pathways')
@login_required
def my_pathways():
    """List user's generated pathways"""
    pathways = AlgorithmicPathway.query.filter_by(
        created_by_user_id=current_user.id
    ).order_by(AlgorithmicPathway.created_at.desc()).limit(50).all()

    return render_template(
        'ai_reporting_assistant/my_pathways.html',
        pathways=pathways,
    )


# API endpoint for case integration
@reporting_assistant_bp.route('/api/generate-for-case/<int:case_id>', methods=['POST'])
@login_required
def generate_for_case(case_id):
    """Generate pathway linked to specific case"""
    from models import Case

    case = Case.query.get_or_404(case_id)
    data = request.get_json()

    # Use case data to pre-fill
    modality = data.get('modality') or _infer_modality_from_case(case)
    region = data.get('anatomical_region') or _infer_region_from_case(case)
    indication = data.get('clinical_indication') or case.diagnosis or "Case review"
    context = data.get('patient_context', '')

    # Add case_id to the generation
    data['case_id'] = case_id
    data['modality'] = modality
    data['anatomical_region'] = region
    data['clinical_indication'] = indication
    data['patient_context'] = context

    # Reuse generate endpoint logic
    return generate()


def _infer_modality_from_case(case):
    """Infer modality from case module/body_part"""
    # Default to CT if can't determine
    return "CT"


def _infer_region_from_case(case):
    """Infer anatomical region from case body_part"""
    if case.body_part:
        return case.body_part.value
    return "Not specified"
```

---

## Frontend Implementation

### Generator Page (`templates/ai_reporting_assistant/generator.html`)

Key UI components:
1. **Input Form**
   - Modality dropdown
   - Anatomical region cascading dropdown (grouped)
   - Clinical indication (text with autocomplete)
   - Patient context (optional textarea)
   - Generate button

2. **Output Panel**
   - Rendered pathway HTML
   - Collapsible sections for each step
   - Print/download buttons
   - Save button

3. **Refinement Panel** (collapsible)
   - Lab values form (WBC, CRP, etc.)
   - Clinical info checkboxes
   - Additional history textarea
   - Refine button

### Styling Requirements

```css
/* Pathway-specific styles */
.pathway-container {
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
    max-width: 900px;
    margin: 0 auto;
}

.pathway-step {
    margin-bottom: 2rem;
    padding: 1.5rem;
    border: 1px solid #e0e0e0;
    border-radius: 8px;
    background: #fff;
}

.pathway-step h2 {
    color: #5E899E;
    border-bottom: 2px solid #5E899E;
    padding-bottom: 0.5rem;
}

.red-flag-section {
    background: #fff5f5;
    border-color: #dc3545;
}

.red-flag-section h2 {
    color: #dc3545;
    border-bottom-color: #dc3545;
}

.teaching-pearl {
    background: #e8f5e9;
    border-left: 4px solid #28a745;
    padding: 1rem;
    margin: 1rem 0;
    border-radius: 0 4px 4px 0;
}

.teaching-pearl::before {
    content: "TEACHING PEARL";
    font-weight: bold;
    color: #28a745;
    display: block;
    margin-bottom: 0.5rem;
}

.pitfall-box {
    background: #fff3cd;
    border-left: 4px solid #ffc107;
    padding: 1rem;
    margin: 1rem 0;
    border-radius: 0 4px 4px 0;
}

.pitfall-box::before {
    content: "PITFALL";
    font-weight: bold;
    color: #856404;
    display: block;
    margin-bottom: 0.5rem;
}

.decision-gate {
    background: #e3f2fd;
    border: 2px solid #1976d2;
    border-radius: 8px;
    padding: 1rem;
    margin: 1rem 0;
    text-align: center;
}

.checklist-table {
    width: 100%;
    border-collapse: collapse;
}

.checklist-table th,
.checklist-table td {
    border: 1px solid #dee2e6;
    padding: 0.75rem;
    text-align: left;
}

.checklist-table th {
    background: #f8f9fa;
    font-weight: 600;
}

/* Print styles */
@media print {
    .no-print { display: none; }
    .pathway-step { break-inside: avoid; }
}
```

---

## Integration Points

### 1. Case View Integration
Add "Generate Algorithmic Approach" button in view_case.html:
- Appears in a new tab or discussion section
- Pre-fills from case metadata
- Links generated pathway to case

### 2. Navigation
Add to main navigation:
- Dashboard sidebar: "Reporting Assistant" link
- Admin menu: "Manage Pathways" (if admin)

### 3. TNM Calculator Link
If pathway identifies possible malignancy, link to relevant TNM calculator.

---

## API Cost Estimate

| Operation | Tokens (approx) | Cost (Claude Sonnet) |
|-----------|-----------------|----------------------|
| Generate pathway | 8,000-12,000 | ~$0.03-0.05 |
| Refine pathway | 4,000-6,000 | ~$0.02-0.03 |

---

## Testing Checklist

### Functional Tests
- [ ] Generate pathway for each modality type
- [ ] Generate pathway for each anatomical region
- [ ] Oncologic indication generates staging
- [ ] Non-oncologic indication generates appropriate classification
- [ ] Refinement with lab values updates differential
- [ ] Pathway saves to database correctly
- [ ] Pathway links to case correctly

### UI Tests
- [ ] Dropdowns populate correctly
- [ ] Loading state during generation
- [ ] Error handling for API failures
- [ ] Print/download functions work
- [ ] Mobile responsive

### Edge Cases
- [ ] Empty patient context
- [ ] Very long indication text
- [ ] Special characters in input
- [ ] Concurrent generation requests

---

## Implementation Phases

### Phase 1: Core Generator (Week 1)
- [ ] Database models and migrations
- [ ] AI generator module with prompts
- [ ] API endpoints (generate, view)
- [ ] Basic generator UI

### Phase 2: Refinement & Polish (Week 2)
- [ ] Refinement functionality
- [ ] My Pathways list page
- [ ] Print/download features
- [ ] Styling and visual polish

### Phase 3: Integration (Week 3)
- [ ] Case view integration
- [ ] Navigation updates
- [ ] Admin features (view all pathways)
- [ ] Documentation

---

## Files to Create/Modify

| File | Action | Description |
|------|--------|-------------|
| `ai_reporting_assistant/__init__.py` | Create | Module init |
| `ai_reporting_assistant/prompts.py` | Create | All prompt templates |
| `ai_reporting_assistant/generator.py` | Create | Core generation logic |
| `ai_reporting_assistant/routes.py` | Create | Flask routes |
| `templates/ai_reporting_assistant/generator.html` | Create | Main generator UI |
| `templates/ai_reporting_assistant/pathway_view.html` | Create | View saved pathway |
| `templates/ai_reporting_assistant/my_pathways.html` | Create | List user's pathways |
| `models.py` | Modify | Add AlgorithmicPathway, PathwayRefinement |
| `app.py` | Modify | Register blueprint |
| `migrations/add_algorithmic_pathway.sql` | Create | Database migration |
| `static/reporting-assistant.css` | Create | Pathway-specific styles |
| `templates/base.html` | Modify | Add navigation link |

---

## Appendix: Refinement Data Options

### Laboratory Values
| Category | Values |
|----------|--------|
| Inflammatory | WBC, CRP, ESR, Procalcitonin |
| Tumour Markers | CEA, CA-125, CA 19-9, PSA, AFP, HCG, LDH |
| Liver | ALT, AST, ALP, GGT, Bilirubin, Albumin |
| Renal | Creatinine, eGFR, Urea |
| Metabolic | Lactate, Glucose, Amylase, Lipase |
| Coagulation | PT, APTT, INR, D-dimer |
| Haematology | Haemoglobin, Platelets |

### Clinical Information
| Category | Options |
|----------|---------|
| Symptoms | Duration, Severity (1-10), Character |
| Signs | Fever, Peritonism, Guarding, Rebound |
| Haemodynamics | Stable, Tachycardic, Hypotensive, Shock |
| History | Prior surgery, Malignancy, IBD, Immunocompromised |
| Context | Emergency, Elective, Screening, Follow-up |

---

*Last Updated: February 2026*
