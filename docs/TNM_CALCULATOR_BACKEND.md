# TNM Calculator – Backend Code Flow

Technical documentation of the TNM Calculator backend implementation.

---

## Module Structure

```
tnm_calculator/
├── __init__.py
├── engine.py       # Main calculation engine
├── loader.py       # Rule loading and cancer list
├── resolver.py     # Stage group resolution
├── explainer.py    # Human-readable explanations
├── models.py       # TNMInput, TNMResult, CancerDefinition
├── routes.py       # Flask API and page routes
└── tests/
    └── test_calculator.py
```

**Data directory:** `ajcc_tnm/data/` (JSON files and DB-driven content)

---

## Request Flow Overview

```
User → routes.py → TNMCalculator (engine.py) → RuleLoader (loader.py)
                         ↓
              StageResolver (resolver.py) + Explainer (explainer.py)
                         ↓
                   TNMResult → JSON response
```

---

## 1. Flask Routes (`routes.py`)

| Route | Method | Purpose |
|-------|--------|---------|
| `/tnm-calculator/` | GET | Render calculator page with cancer dropdown |
| `/tnm-calculator/api/calculate` | POST | Calculate stage from T/N/M input |
| `/tnm-calculator/api/cancers` | GET | List available cancer types (JSON) |
| `/tnm-calculator/api/cancer/<slug>` | GET | Get cancer details (T/N/M options, subsites) |
| `/tnm-calculator/api/categories/<slug>` | GET | Get T/N/M category lists for a cancer |

### Page Load

```python
# routes.py: calculator_page()
calculator = get_calculator()
cancers = calculator.get_available_cancers()  # Excluded slugs filtered here
return render_template('tnm_calculator.html', cancers=cancers)
```

### Calculate API

```python
# routes.py: calculate()
input = TNMInput.from_dict(request.get_json())
result = calculator.calculate(input)
return jsonify(result.to_dict())
```

---

## 2. Engine (`engine.py`)

`TNMCalculator.calculate(input)`:

1. Load cancer definition via `loader.load_cancer_definition(cancer_type)`.
2. Validate input against the definition (T/N/M in allowed sets, subsite, etc.).
3. Build `StageResolver` and `Explainer` from the definition.
4. Decide staging type:
   - Breast + full biomarkers → prognostic staging (`resolve_prognostic`).
   - Else → anatomic staging (`resolve`).
5. Resolve stage group from T/N/M (and biomarkers for prognostic).
6. Generate explanations for T, N, M, and stage.
7. Return `TNMResult`.

---

## 3. Rule Loader (`loader.py`)

### 3.1 Loading a Cancer Definition

`load_cancer_definition(cancer_type)`:

1. Normalize `cancer_type` to slug (lowercase, spaces → underscores).
2. Check in-memory cache; return if hit.
3. Try sources in order:
   - `_load_from_structured_file` → `ajcc_tnm_structured.json`
   - `_load_from_ontology` → `ajcc_frcr_full_ontology.json`
   - `_load_from_database` → `AJCCStagingData` + `AJCCDiseaseSite`
4. Cache and return the first match, or `None`.

### 3.2 Cancer List (Dropdown)

`get_available_cancers()` builds the list for the UI. **Excluded cancer slugs are filtered out here.**

#### Source Priority

1. **Ontology** (`ajcc_frcr_full_ontology.json`)
   - Expects `body_sections` → `diseases` (objects with `name`, `slug`).
   - Current ontology uses `sections` / `ajcc_section`, so this usually returns nothing.

2. **Database** (fallback when ontology is empty)
   - `AJCCStagingData` with `tnm_data_json` that has `stage_groups` or `clinical_prognostic_stage_groups`.
   - Joins `AJCCDiseaseSite` and `AJCCBodySection` for display names and sections.

3. **Structured file** (fallback when DB is empty)
   - `ajcc_tnm_structured.json` (single disease).

### 3.3 Excluded Cancer Slugs

Introductory/meta sections are excluded from the calculator dropdown; they remain in the DB and reference, but are not selectable.

```python
# loader.py
EXCLUDED_CANCER_SLUGS = frozenset({
    "introduction-to-hematologic-malignancies",
    "introduction-to-soft-tissue-sarcoma",
})
```

#### Where filtering happens

1. **Ontology path** (`get_available_cancers`):
   ```python
   for disease in section.get("diseases", []):
       slug = disease.get("slug", "unknown")
       if slug.lower() in self.EXCLUDED_CANCER_SLUGS:
           continue
       cancers.append({...})
   ```

2. **Database path** (`_get_cancers_from_database`):
   ```python
   disease = AJCCDiseaseSite.query.get(staging.disease_site_id)
   if disease.slug and disease.slug.lower() in self.EXCLUDED_CANCER_SLUGS:
       continue
   cancers.append({...})
   ```

#### Adding more exclusions

Extend `EXCLUDED_CANCER_SLUGS` in `loader.py`:

```python
EXCLUDED_CANCER_SLUGS = frozenset({
    "introduction-to-hematologic-malignancies",
    "introduction-to-soft-tissue-sarcoma",
    "some-other-slug",  # Add new slugs here
})
```

---

## 4. Stage Resolver (`resolver.py`)

- `resolve(t, n, m)` → anatomic stage from T/N/M.
- `resolve_prognostic(t, n, m, grade, her2, er, pr)` → prognostic stage (breast).
- M1 → Stage IV (or equivalent highest stage).
- Uses `definition.stage_groups` and `definition.prognostic_stage_groups` to match T/N/M (and biomarkers) to a stage.
- Returns stage group, `is_metastatic`, and color.

---

## 5. Explainer (`explainer.py`)

- `explain_t(t, subsite)`
- `explain_n(n, staging_type)`
- `explain_m(m)`
- `explain_stage(stage_group, t, n, m, subsite, staging_type)`

Uses `CancerDefinition` (T/N/M definitions, stage groups) to produce human-readable text.

---

## 6. Data Models (`models.py`)

| Class | Purpose |
|-------|---------|
| `TNMInput` | cancer_type, t/n/m, staging_type, subsite, biomarkers |
| `TNMResult` | success, tnm_classification, stage_group, explanations |
| `CancerDefinition` | T/N/M definitions, stage groups, subsites, version |
| `StagingType` | CLINICAL, PATHOLOGICAL, POST_THERAPY |
| `ValidationError` | field, message, severity |

---

## 7. Data Flow Diagram

```
┌─────────────────┐
│  User selects   │
│  cancer type    │
└────────┬────────┘
         │
         ▼
┌─────────────────────────────────────────────────────┐
│  get_available_cancers()                             │
│  1. Try ontology (body_sections/diseases)            │
│  2. Filter: slug NOT IN EXCLUDED_CANCER_SLUGS        │
│  3. Fallback: database (AJCCStagingData)             │
│  4. Filter: slug NOT IN EXCLUDED_CANCER_SLUGS        │
│  5. Fallback: ajcc_tnm_structured.json               │
└────────┬────────────────────────────────────────────┘
         │
         ▼
┌─────────────────┐     POST /api/calculate
│  User submits   │ ───────────────────────────►
│  T, N, M        │
└─────────────────┘
         │
         ▼
┌─────────────────────────────────────────────────────┐
│  load_cancer_definition(slug)                        │
│  1. Check cache                                     │
│  2. ajcc_tnm_structured.json                         │
│  3. ajcc_frcr_full_ontology.json                     │
│  4. Database (AJCCStagingData + AJCCDiseaseSite)     │
└────────┬────────────────────────────────────────────┘
         │
         ▼
┌─────────────────┐    ┌─────────────────┐
│ StageResolver   │    │  Explainer      │
│ resolve(T,N,M)  │    │  explain_*(...) │
└────────┬────────┘    └────────┬────────┘
         │                      │
         └──────────┬───────────┘
                    ▼
         ┌─────────────────────┐
         │  TNMResult          │
         │  (JSON response)    │
         └─────────────────────┘
```

---

## 8. Database Schema (Relevant Tables)

| Table | Role |
|-------|------|
| `ajcc_body_section` | Section names (e.g. Head and Neck, Thorax) |
| `ajcc_disease_site` | Disease names and slugs |
| `ajcc_staging_data` | `tnm_data_json` with stage groups, T/N/M definitions |

`tnm_data_json` includes:

- `stage_groups`: list of `{t, n, m, stage}`
- `clinical_prognostic_stage_groups`: breast prognostic staging
- T/N/M definitions and subsites

---

## 9. Caching

- **RuleLoader** caches `CancerDefinition` by slug in `_cache`.
- `clear_cache()` clears definitions but does not affect `get_available_cancers`, which always recomputes from the data source.
- `EXCLUDED_CANCER_SLUGS` is applied on each `get_available_cancers()` call.
