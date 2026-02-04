# Algorithmic Staging Cases & Related Cases Feature

## Overview

This document describes the approach for creating **algorithmic staging case documents** that guide radiologists through a systematic approach to reporting cancer staging scans. Each case will combine:

1. **Visual algorithmic approach** in the discussion section
2. **Embedded TNM calculator** for the specific cancer
3. **Related cases** linking system for cross-referencing

---

## Educational Approach

### Goal
Transform the TNM calculator logic into a **visual, step-by-step reading algorithm** that radiologists can follow while reporting staging CT/MRI scans.

### Structure for Each Cancer Type

Each algorithmic staging case will include:

```
Case: [Cancer Type] - Algorithmic Approach to Staging Scan Reporting

1. DISCUSSION SECTION (Algorithmic Approach)
   ├── Quick Reference Card (mnemonics, size cutoffs)
   ├── Step-by-Step Reading Algorithm (flowchart style)
   ├── Imaging Tips for Each Step
   ├── Common Pitfalls to Avoid
   └── Clinical Implications by Stage

2. EMBEDDED TNM CALCULATOR
   └── Calculator iframe for interactive staging

3. RELATED CASES
   └── Links to similar/related cases (e.g., base of tongue → oropharynx algorithm)
```

---

## Related Cases Feature

### Database Model

Add a many-to-many relationship for related cases:

```python
# New association table
related_cases = db.Table('related_cases',
    db.Column('case_id', db.Integer, db.ForeignKey('case.id'), primary_key=True),
    db.Column('related_case_id', db.Integer, db.ForeignKey('case.id'), primary_key=True)
)

# In Case model
related_cases_list = db.relationship(
    'Case',
    secondary=related_cases,
    primaryjoin=(related_cases.c.case_id == id),
    secondaryjoin=(related_cases.c.related_case_id == id),
    backref='related_from'
)
```

### UI Flow

**Admin (edit_case.html):**
- Searchable dropdown to find and add related cases
- Display list of linked cases with remove option
- Auto-suggest cases with similar diagnosis/body_part

**Student (view_case.html):**
- "Related Cases" section in header/sidebar
- Card-style links with case title and diagnosis
- Badge indicating type: "Algorithm", "Similar Case", "Reference"

---

## Priority Algorithmic Cases

### Phase 1: Head & Neck
1. **Oropharyngeal Cancer** (HPV+ and HPV- pathways)
2. Laryngeal Cancer (Glottic, Supraglottic, Subglottic)
3. Oral Cavity Cancer (with Depth of Invasion)
4. Nasopharyngeal Cancer

### Phase 2: Thorax
5. Lung Cancer (NSCLC)
6. Esophageal Cancer

### Phase 3: Gynecological
7. Cervical Cancer (FIGO 2018)
8. Endometrial Cancer (FIGO 2023)
9. Ovarian Cancer

### Phase 4: Breast
10. Breast Cancer (with biomarkers: ER, PR, HER2, Grade)

---

## Visual Design Guidelines

### App Style Integration
Use the app's existing color palette:

```css
--brand-primary: #e96304;      /* Orange - highlights, actions */
--brand-secondary: #ffc107;    /* Yellow - warnings, tips */
--brand-success: #a8d5ba;      /* Green - completed, positive */
--brand-neutral: #5E899E;      /* Blue-gray - headers, info */
--brand-text-primary: #2c3e50; /* Dark - main text */
--brand-bg-offwhite: #fdfdfb;  /* Background */
```

### Algorithm Visual Elements

1. **Step Numbers** - Circular badges (brand-neutral background)
2. **Decision Points** - Orange borders with Yes/No paths
3. **Teaching Points** - Yellow background with left border
4. **Imaging Tips** - Blue-gray left border
5. **Pitfalls** - Warning yellow with numbered list
6. **Mnemonics** - Orange border box, centered letters

### Flowchart Style
```
┌─────────────────────────┐
│  STEP 1: Check HPV      │ ← Blue-gray header
├─────────────────────────┤
│  • Look at pathology    │
│  • Different staging!   │
└──────────┬──────────────┘
           │
     ┌─────┴─────┐
     │  HPV+?    │ ← Orange decision diamond
     └─────┬─────┘
      Yes / No
```

---

## Implementation Steps

### Step 1: Database Migration
```sql
CREATE TABLE related_cases (
    case_id INTEGER NOT NULL,
    related_case_id INTEGER NOT NULL,
    relation_type VARCHAR(50) DEFAULT 'related',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (case_id, related_case_id),
    FOREIGN KEY (case_id) REFERENCES "case" (id) ON DELETE CASCADE,
    FOREIGN KEY (related_case_id) REFERENCES "case" (id) ON DELETE CASCADE
);
```

### Step 2: Model Updates
- Add `related_cases` relationship to Case model
- Add helper methods: `add_related_case()`, `remove_related_case()`

### Step 3: API Routes
- `POST /api/case/<id>/related` - Add related case
- `DELETE /api/case/<id>/related/<related_id>` - Remove
- `GET /api/case/<id>/related` - List related cases

### Step 4: Admin UI
- Add "Related Cases" section in edit_case.html
- Case search/select dropdown with autocomplete
- Display linked cases with badges and remove buttons

### Step 5: Student UI
- Add "Related Cases" card in view_case.html header
- Show as clickable cards with diagnosis preview

### Step 6: Create Algorithmic Cases
- Start with oropharyngeal cancer as template
- Create case with rich HTML discussion
- Link TNM calculator
- Cross-link with specific cancer cases

---

## Example: Oropharyngeal Cancer Algorithmic Case

**Case Title:** Oropharyngeal Cancer - Algorithmic Approach to Staging Scan Reporting

**Discussion Section Content:**

```html
<div class="algorithm-container">
  <!-- Quick Reference Card -->
  <div class="quick-ref-card">
    <h3>Quick Reference</h3>
    <div class="mnemonic-grid">
      <div class="mnemonic">T4b = PACE (Prevertebral, Artery, Cranium, Extension)</div>
      <div class="mnemonic">T4a = HELP (Hard palate, Extrinsic muscles, Larynx, Pterygoid)</div>
    </div>
    <div class="size-table">...</div>
  </div>

  <!-- Step-by-Step Algorithm -->
  <div class="algorithm-steps">
    <div class="step">
      <span class="step-number">1</span>
      <h4>Confirm HPV Status</h4>
      <p>Check pathology report - different staging systems!</p>
      <div class="imaging-tip">HPV+ tumors often present with cystic nodal mets</div>
    </div>
    <!-- More steps... -->
  </div>

  <!-- Pitfalls -->
  <div class="pitfalls-section">
    <h3>Common Pitfalls</h3>
    <ol>
      <li>Not confirming HPV status first</li>
      <li>Measuring nodes on long axis (use SHORT axis)</li>
      <!-- ... -->
    </ol>
  </div>
</div>
```

**Related Cases to Link:**
- Base of Tongue SCC
- Tonsillar SCC
- Soft Palate Cancer
- HPV-Positive Head and Neck Cancer

---

## Success Metrics

1. Students can systematically stage a cancer using the algorithm
2. Reduced staging errors in MDT discussions
3. Increased calculator usage linked from cases
4. Positive feedback on algorithm clarity

---

## Timeline

- **Week 1:** Database migration, model updates, basic API
- **Week 2:** Admin UI for related cases
- **Week 3:** Student UI, create oropharyngeal algorithm case
- **Week 4:** Create additional algorithm cases, testing
