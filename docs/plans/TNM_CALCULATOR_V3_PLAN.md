# TNM Calculator v3 - Clinical Decision-Tree Approach

> **Priority:** 1 (Core Feature Upgrade)
> **Complexity:** Medium
> **Status:** In Progress
> **Branch:** `feature/tnm-calculator-v3`
> **AJCC Version:** 9th Edition (latest)

## Executive Summary

Complete redesign of the TNM Calculator using clinically-curated, decision-tree-based HTML calculators for each disease site. This replaces the current AJCC raw data extraction approach with a more practical, educational, and reliable system.

---

## Why v3? Problems with Current Approach (v2)

| Issue | Current System | v3 Solution |
|-------|---------------|-------------|
| **Data Quality** | Raw AJCC extraction has parsing errors, missing stage groups | Hand-curated, clinically verified data |
| **Clinical Utility** | Generic dropdowns, no decision guidance | Decision-tree logic (T4b → T4a → size) |
| **Educational Value** | Just shows result | Includes mnemonics, pitfalls, imaging tips |
| **HPV-specific** | Single staging system | Proper HPV+/HPV- branching |
| **Offline** | Requires API calls | Standalone HTML works offline |
| **Maintenance** | Complex Python pipeline | Simple HTML per disease |

---

## Architecture Overview

### New Structure
```
tnm_calculator/
├── __init__.py
├── routes.py                    # Updated routes for v3
├── calculators/                 # Disease-specific calculators
│   ├── base_template.html       # Base template with app styling
│   ├── oropharynx_calc.html     # ✅ Created
│   ├── larynx_calc.html         # Pending
│   ├── nasopharynx_calc.html    # Pending
│   ├── oral_cavity_calc.html    # Pending
│   ├── hypopharynx_calc.html    # Pending
│   ├── lung_calc.html           # Pending
│   ├── breast_calc.html         # Pending (with biomarkers)
│   ├── cervix_calc.html         # Pending (FIGO)
│   ├── endometrium_calc.html    # Pending (FIGO)
│   ├── ovary_calc.html          # Pending (FIGO)
│   └── ...
├── engine.py                    # Keep for API compatibility
└── templates/
    └── tnm_calculator_index.html # Index page with disease grid
```

### Integration Points

1. **TNM Calculator Page** (`/tnm-calculator/`)
   - Index page with disease sites grouped by body section
   - Cards link to individual calculators
   - Maintains current grouped layout

2. **Case Discussion Embed** (`/cases/<id>/view`)
   - Calculator embedded inline within case discussion
   - Disease type passed via query param or case metadata
   - Option C: Inline embed (user's choice)

---

## Calculator Design Pattern

Each calculator follows this structure:

### 1. Header Section
- Disease name and AJCC version
- Quick description

### 2. Calculator Form
- **Decision-tree logic**: Check worst case first
  - T4b features → T4a features → Size-based T stage
- **HPV/biomarker branching** where applicable
- **Node assessment**: Size, count, laterality, ENE
- **M stage**: Simple yes/no

### 3. Results Display
- TNM classification
- Overall stage group
- **Detailed reasoning** for each component
- **Clinical implications** (treatment guidance)

### 4. Reference Guide
- **Mnemonics** (e.g., PACE for T4b, HELP for T4a)
- **Size cutoff tables**
- **Staging comparison tables** (HPV+ vs HPV-)
- **Imaging tips** for radiologists
- **Common pitfalls**
- **Systematic reading approach**

---

## Priority Disease Sites

### Phase 1: Head and Neck (AJCC 9th Edition)
| Site | Calculator File | Status | Verification |
|------|----------------|--------|--------------|
| Oropharynx (HPV+/HPV-) | `oropharynx_calc.html` | ✅ Created | Needs AJCC 9 review |
| Larynx (Glottis/Supraglottis/Subglottis) | `larynx_calc.html` | Pending | - |
| Oral Cavity | `oral_cavity_calc.html` | Pending | - |
| Nasopharynx | `nasopharynx_calc.html` | Pending | - |
| Hypopharynx | `hypopharynx_calc.html` | Pending | - |
| Salivary Glands | `salivary_calc.html` | Pending | - |
| Thyroid | `thyroid_calc.html` | Pending | - |

### Phase 2: Thorax
| Site | Calculator File | Status | Notes |
|------|----------------|--------|-------|
| Lung (NSCLC) | `lung_calc.html` | Pending | Include small cell staging |
| Esophagus | `esophagus_calc.html` | Pending | - |

### Phase 3: Breast
| Site | Calculator File | Status | Notes |
|------|----------------|--------|-------|
| Breast | `breast_calc.html` | Pending | Include Grade, ER, PR, HER2 for prognostic staging |

### Phase 4: Gynecological (FIGO Staging)
| Site | Calculator File | Status | Notes |
|------|----------------|--------|-------|
| Cervix | `cervix_calc.html` | Pending | FIGO 2018 |
| Endometrium | `endometrium_calc.html` | Pending | FIGO 2023 |
| Ovary | `ovary_calc.html` | Pending | FIGO 2014 |

---

## Integration with App Base Template

### Template Integration
Each calculator will extend the app's base template:

```html
{% extends 'base.html' %}

{% block mobile_breadcrumb %}
<li class="breadcrumb-item"><a href="{{ url_for('tnm_calculator.index') }}">TNM Calculator</a></li>
<li class="breadcrumb-item active">Oropharynx</li>
{% endblock %}

{% block content %}
<!-- Calculator content here -->
{% endblock %}
```

### CSS Variables (App Branding)
```css
:root {
    --brand-primary: #e96304;      /* Orange - actions */
    --brand-secondary: #ffc107;    /* Yellow - warnings */
    --brand-success: #a8d5ba;      /* Green - success */
    --brand-neutral: #5E899E;      /* Blue-gray - headers */
    --brand-text-primary: #2c3e50;
    --brand-text-secondary: #5a6270;
}
```

---

## Case Discussion Integration (Option C: Inline Embed)

### Implementation
1. Add "TNM Calculator" section in case view template
2. Embed calculator via iframe or include
3. Pass disease type from case metadata

### Template Addition (`view_case.html`)
```html
<!-- TNM Calculator Section -->
<div class="case-section" id="tnm-calculator-section">
    <h3><i class="fas fa-calculator"></i> TNM Calculator</h3>
    {% if case.disease_type %}
    <iframe
        src="{{ url_for('tnm_calculator.calculator', disease=case.disease_type) }}"
        style="width: 100%; height: 800px; border: none;"
    ></iframe>
    {% else %}
    <p>Select disease type to use TNM calculator</p>
    {% endif %}
</div>
```

---

## Data Verification Process

**CRITICAL**: Each calculator must be verified against AJCC 9th Edition before deployment.

### Verification Checklist per Calculator
- [ ] T stage criteria match AJCC 9
- [ ] N stage criteria match AJCC 9 (clinical vs pathological)
- [ ] Stage grouping table verified
- [ ] Special considerations noted (HPV, biomarkers, subsites)
- [ ] Mnemonics are accurate
- [ ] Pitfalls are clinically relevant
- [ ] User (clinician) has reviewed and approved

### Verification Workflow
1. Claude creates calculator draft
2. Claude presents staging criteria to user for verification
3. User confirms or corrects against AJCC 9/FIGO
4. Calculator is updated with verified data
5. Final review before merge

---

## Routes Update

### New Routes
```python
# tnm_calculator/routes.py

@tnm_calc_bp.route('/')
def index():
    """Index page with disease grid grouped by body section."""
    return render_template('tnm_calculator_index.html',
                          diseases=get_available_calculators())

@tnm_calc_bp.route('/<disease>')
def calculator(disease):
    """Render disease-specific calculator."""
    calculator_file = f'calculators/{disease}_calc.html'
    if not calculator_exists(disease):
        return redirect(url_for('tnm_calculator.index'))
    return render_template(f'tnm_calculator/{calculator_file}')

@tnm_calc_bp.route('/embed/<disease>')
def embed(disease):
    """Embeddable version for case discussion (no nav)."""
    return render_template(f'tnm_calculator/calculators/{disease}_calc.html',
                          embed_mode=True)
```

---

## Implementation Phases

### Phase 1: Infrastructure (Current)
- [x] Create feature branch
- [x] Create plan document
- [ ] Set up base template for calculators
- [ ] Create index page with disease grid
- [ ] Set up routes for calculators

### Phase 2: Head and Neck Calculators
- [ ] Update oropharynx_calc.html to AJCC 9
- [ ] Create larynx_calc.html
- [ ] Create oral_cavity_calc.html
- [ ] Create nasopharynx_calc.html
- [ ] Create hypopharynx_calc.html

### Phase 3: Other Priority Sites
- [ ] Create lung_calc.html
- [ ] Create breast_calc.html (with biomarkers)
- [ ] Create gynae calculators (cervix, endometrium, ovary)

### Phase 4: Case Integration
- [ ] Add TNM calculator section to case view
- [ ] Implement embed mode
- [ ] Add disease type field to cases

---

## File Changes Required

### New Files
- `docs/plans/TNM_CALCULATOR_V3_PLAN.md` - This document
- `tnm_calculator/templates/tnm_calculator_index.html` - Index page
- `tnm_calculator/calculators/base_template.html` - Base template
- `tnm_calculator/calculators/*_calc.html` - Disease calculators

### Modified Files
- `tnm_calculator/routes.py` - New routes for v3
- `templates/view_case.html` - Add calculator embed section
- `models.py` - Add disease_type field to Case (if needed)

---

## Success Criteria

1. **Clinical Accuracy**: All calculators verified against AJCC 9/FIGO
2. **User Experience**: Faster than current system, works offline
3. **Educational Value**: Users learn staging logic, not just get results
4. **Maintainability**: Easy to update individual calculators
5. **Integration**: Seamlessly embedded in case discussions

---

## Notes

- Keep existing v2 API endpoints for backward compatibility
- Deprecate v2 UI after v3 is stable
- Consider adding "Report Bug" feature for clinical feedback
- Future: Add ability to save staging results to case records
