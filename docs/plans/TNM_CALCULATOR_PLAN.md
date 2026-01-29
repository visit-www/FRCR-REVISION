# TNM Calculator - Standalone Clinical-Grade Module

> **Priority:** 4 (Core Feature)  
> **Complexity:** High  
> **Estimated Effort:** 3-4 weeks  
> **Status:** Planned

## Executive Summary

Build a clinical-grade, deterministic, rule-based TNM staging calculator as a standalone reusable module. Features full explainability, data-driven rules from JSON, and no AI dependency. Designed for clinical practice and embeddable in other applications.

---

## CRITICAL: App Style and Branding Guidelines

**All UI implementations MUST follow existing app design patterns:**

### Color Palette
- Primary Blue: `#5E899E` (headers, primary actions)
- Success Green: `#28a745` (valid stages, confirmed)
- Warning Orange: `#ffc107` (validation warnings)
- Danger Red: `#dc3545` (errors, M1/Stage IV)
- Info Blue: `#17a2b8` (explanations)

### TNM-Specific Styling
- T Category: Blue accent
- N Category: Orange accent
- M Category: Red for M1 (metastatic)
- Stage Display: Large, prominent, color-coded

---

## Core Principles

- **Deterministic:** No AI or probabilistic logic
- **Explainable:** Every output includes complete reasoning
- **Data-driven:** All rules from JSON (no hard-coding)
- **Reusable:** Standalone module, callable as library or API
- **Safe:** Clear disclaimers, versioned rules, fully testable

---

## Core Engine Interface

```python
class TNMCalculator:
    DISCLAIMER = "Decision-support only. Final staging responsibility remains with the treating clinician."
    
    def calculate(self, input: TNMInput) -> TNMResult:
        """
        Calculate TNM stage from structured input.
        
        Flow:
        1. Validate inputs
        2. Load cancer-specific rules
        3. Apply M overrides (M1 → Stage IV)
        4. Resolve T category
        5. Resolve N category
        6. Match stage group
        7. Generate explanation
        """
        pass
```

---

## Example Output

```json
{
  "tnm_classification": "T2N1M0",
  "stage_group": "Stage IIB",
  "t_explanation": "T2 because tumour measures 35mm (>20mm but ≤50mm)",
  "n_explanation": "N1 because 2 axillary nodes contain macrometastases",
  "m_explanation": "M0 because no distant metastasis present",
  "stage_explanation": "Stage IIB: T2N1M0 per AJCC 8th edition breast cancer",
  "disclaimer": "Decision-support only. Final staging responsibility remains with the clinician."
}
```

---

## Module Structure

```
tnm_calculator/
├── core/
│   ├── engine.py          # Main calculation engine
│   ├── validator.py       # Input validation
│   ├── stage_resolver.py  # Stage grouping logic
│   └── explainer.py       # Explanation generator
├── rules/
│   ├── loader.py          # JSON rule loader
│   └── schema.py          # Rule schema validation
├── data/
│   ├── ajcc_8/            # Cancer-specific rules
│   └── figo/              # FIGO staging rules
└── tests/
    └── test_known_cases.json
```

---

## Implementation Phases

### Phase 1: Core Engine (5-7 days)
- Implement TNMCalculator class
- Implement input validation
- Implement stage resolution logic
- Implement explanation generator

### Phase 2: Rule System (3-4 days)
- Design JSON schema
- Convert existing AJCC data
- Implement rule loader
- Add schema validation

### Phase 3: Testing (3-4 days)
- Create known staging test cases
- Implement unit tests
- Validate against clinical references

### Phase 4: UI Integration (3-4 days)
- Build standalone calculator page
- Implement cancer type selector
- Create result display with explanations

---

## Todos

- [ ] Implement TNMCalculator core engine class
- [ ] Implement input validation with error messages
- [ ] Implement stage resolution with M-override logic
- [ ] Implement explanation generator
- [ ] Design and document JSON rule schema
- [ ] Convert existing AJCC data to new format
- [ ] Create comprehensive test suite
- [ ] Build standalone calculator UI page
