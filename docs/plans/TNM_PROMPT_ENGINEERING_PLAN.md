# TNM Calculator AI Prompt Engineering Plan

> **Priority:** 12 (Quality Improvement)
> **Complexity:** Medium
> **Estimated Effort:** 1-2 days
> **Dependencies:** None
> **Status:** Ready to Implement

---

## Problem Statement

The larynx calculator (generated through the app's AI workflow) is significantly worse than the oropharyngeal calculator (generated directly on Claude platform). We need to fix the AI prompt and workflow to consistently produce oropharyngeal-quality results.

---

## Root Cause Analysis

| Issue | Current State | Required State |
|-------|--------------|----------------|
| **Example** | Prompt says "based on oropharynx" but provides NO example | Must include concrete HTML excerpts |
| **Architecture** | Describes "expandable cards" and "decision tree" | Must describe form-based calculator + reference guide |
| **Stage Calculation** | User manually selects T/N/M stages | System calculates stages from input findings |
| **Reasoning Output** | Just shows final stage | Must explain WHY each stage was assigned |
| **Reference Section** | Tips scattered in expandable cards | Separate comprehensive reference with mnemonics, tables, pitfalls |
| **Quality Criteria** | None specified | Explicit checklist of requirements |
| **Token Limit** | 16,000 tokens | 20,000+ tokens for longer output |
| **Temperature** | Not set (defaults to 1.0) | Set to 0.3 for consistency |

### Quality Comparison

| Feature | Oropharynx (Gold Standard) | Larynx (AI-Generated) |
|---------|---------------------------|----------------------|
| **Lines** | 1916 | 741 |
| **Architecture** | Form-based calculator + Reference guide | Expandable decision-tree cards only |
| **Input Method** | Checkboxes, number inputs, radio buttons | Radio button selection only |
| **Calculation Logic** | Automatic staging from findings | User selects T stage manually |
| **Reasoning Output** | Detailed explanation of WHY each stage | Just shows final stage |
| **Reference Section** | 2 mnemonics, size tables, 6 imaging tips, 8 pitfalls, 8-step systematic approach | Scattered tips within expandable cards |
| **Clinical Implications** | Treatment guidance in results | None |
| **Dynamic Features** | HPV status changes visible fields | None |

---

## Files to Modify

1. **`/Users/zen/myRepos/projects/FRCR_REVISION/tnm_calculator/tnm_generator.py`**
   - Replace `CALCULATOR_HTML_PROMPT` with new comprehensive prompt
   - Add `temperature=0.3` to API calls
   - Increase `max_tokens` to 20000
   - Add `validate_calculator_quality()` function

2. **`/Users/zen/myRepos/projects/FRCR_REVISION/scripts/generate_tnm_calculator.py`**
   - Expand `DISEASE_DEFAULTS` with detailed notes for each cancer

---

## Implementation Plan

### Step 1: Replace CALCULATOR_HTML_PROMPT (tnm_generator.py lines 43-94)

New prompt must specify:

**A) Two-Part Architecture:**
- Section A: Form-based Calculator (checkboxes, number inputs, auto-calculation)
- Section B: Comprehensive Reference Guide (mnemonics, tables, tips, pitfalls, systematic approach)

**B) Calculator Section Requirements:**
- T4b features as checkboxes (if ANY checked = T4b)
- T4a features as checkboxes (if ANY checked = T4a)
- Tumor size input for T1-T3 determination
- Node measurements and distribution inputs
- ENE checkbox
- M stage radio
- Calculate button → results with REASONING

**C) Reference Section Requirements:**
- At least 2 mnemonics (for T4b and T4a)
- Size-based T staging comparison table
- N staging table (with variants if applicable)
- 6+ imaging tips in card format
- 6+ numbered common pitfalls with explanations
- 8-step systematic reading approach

**D) Example HTML Excerpts:**
Include ~500 lines of key structure excerpts from oropharynx calculator showing:
- Form-based checkbox/input pattern
- Results display with reasoning
- Reference section structure
- CSS patterns

**E) Quality Criteria Checklist:**
```
- [ ] Form-based inputs (not manual T/N/M selection)
- [ ] Automatic stage calculation from findings
- [ ] Detailed reasoning in results
- [ ] At least 2 mnemonics
- [ ] Size cutoff reference table
- [ ] At least 6 imaging tips
- [ ] At least 6 common pitfalls
- [ ] 8-step systematic approach
- [ ] Clinical implications
- [ ] Responsive design
- [ ] 1500+ lines of HTML
```

### Step 2: Update API Call Parameters (tnm_generator.py line 176-185)

```python
response = client.messages.create(
    model=get_claude_model(),
    max_tokens=20000,      # Increased from 16000
    temperature=0.3,       # Added for consistency
    messages=[...]
)
```

### Step 3: Add Validation Function (tnm_generator.py new function)

```python
def validate_calculator_quality(html_content: str) -> Tuple[bool, List[str]]:
    """Check generated calculator meets quality criteria."""
    issues = []

    # Check minimum length (~1500 lines)
    if len(html_content) < 120000:
        issues.append(f"Too short: {len(html_content)} chars")

    # Check required elements
    required = [
        ('calculator-form|form-section', 'Calculator form'),
        ('reference-section', 'Reference section'),
        ('type="checkbox"', 'Checkbox inputs'),
        ('type="number"', 'Number inputs'),
        ('mnemonic', 'Mnemonics'),
        ('tip-card', 'Imaging tips'),
        ('pitfall', 'Pitfalls'),
        ('systematic|step-number', 'Systematic approach'),
        ('resultReasoning|reasoning', 'Reasoning output'),
    ]

    for pattern, name in required:
        if not re.search(pattern, html_content, re.I):
            issues.append(f"Missing: {name}")

    return len(issues) == 0, issues
```

### Step 4: Expand DISEASE_DEFAULTS (generate_tnm_calculator.py)

Each disease needs detailed notes specifying:
- T4b criteria with mnemonic suggestion
- T4a criteria with mnemonic suggestion
- Size cutoffs for T1-T3
- N staging specifics
- Disease-specific features to include

Example for larynx:
```python
'larynx': {
    'features': ['Subsites', 'Cartilage Invasion', 'Voice Preservation'],
    'notes': '''
CRITICAL REQUIREMENTS:
1. Subsite selector (Glottis/Supraglottis/Subglottis) changes criteria
2. T4b: PACE (Prevertebral, Artery encasement, Central mediastinal, Extensive)
3. T4a: Through outer cortex thyroid cartilage, trachea, soft tissues, etc.
4. T3 KEY: Vocal cord FIXATION (not impaired) OR paraglottic OR inner cortex
5. T2: Extends to adjacent subsites, NORMAL or IMPAIRED mobility (not fixed)
6. Glottic: T1a (one cord) vs T1b (both cords)
7. Voice preservation in clinical implications
8. Cartilage invasion decision tree
''',
}
```

### Step 5: Regenerate Larynx Calculator

After implementing changes:
1. Run `python scripts/generate_tnm_calculator.py larynx "Larynx" "Head and Neck" --overwrite`
2. Validate output meets quality criteria
3. Compare to oropharynx calculator

---

## Verification

1. **Length Check**: Generated HTML should be 1500+ lines (120,000+ chars)
2. **Structure Check**: Has form-based calculator AND reference section
3. **Feature Count**:
   - 6+ checkboxes for T4b/T4a features
   - 2+ mnemonics
   - 6+ imaging tips
   - 6+ pitfalls
   - 8 systematic steps
4. **Functionality**: Automatic stage calculation with reasoning output
5. **Manual Review**: Compare side-by-side with oropharynx calculator

---

## Expected Outcome

After implementation, running the generator for ANY cancer type should produce:
- Form-based calculator (not expandable cards)
- Automatic staging from findings
- Detailed reasoning in results
- Comprehensive reference section
- Quality on par with oropharynx calculator

---

## Related Documents

- [TNM_CALCULATOR_V3_PLAN.md](TNM_CALCULATOR_V3_PLAN.md) - Overall TNM calculator architecture
- [TNM_CALCULATOR_PLAN.md](TNM_CALCULATOR_PLAN.md) - Original standalone module plan
- [AI_INTEGRATION_REFERENCE.md](../AI_INTEGRATION_REFERENCE.md) - AI integration documentation

---

## Version History

| Date | Change | Author |
|------|--------|--------|
| 2026-02-05 | Initial plan created | AI Assistant |
