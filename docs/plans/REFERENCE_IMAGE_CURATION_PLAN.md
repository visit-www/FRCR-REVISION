# Reference Image Curation Feature - Implementation Plan

> **Priority:** 3 (High Value)  
> **Complexity:** Medium  
> **Estimated Effort:** 2-3 weeks  
> **Status:** Planned

## Executive Summary

Implement an admin-side AI-assisted reference image curation system that uses Google Custom Search + Claude AI to find, analyze, and store relevant radiology images for each case. Images are curated once by admin and displayed instantly to all students.

### Image Types to Curate

| Type | Focus | Purpose |
|------|-------|---------|
| **CT/MRI imaging** | Modality-specific images representing the diagnosis | Show typical imaging appearances (e.g. "CT brain glioblastoma", "MRI knee ACL tear") |
| **Anatomy diagrams** | Line diagrams and schematics of anatomy for the body part in diagnosis | Describe normal anatomy for comparison with pathology |
| **Concept diagrams** | Illustrations explaining staging, pathophysiology, classification | Aid understanding of concepts (e.g. TNM staging diagram, flowcharts) |

### Mandatory: Creative Commons License Only

**All images MUST be under Creative Commons or public domain** to be used in the app without legal concern. Non-CC images must be rejected. This is non-negotiable.

---

## CRITICAL: App Style and Branding Guidelines

**All UI implementations MUST follow existing app design patterns:**

### Color Palette
- Primary Blue: `#5E899E` (headers, primary actions)
- Success Green: `#28a745` (matched/relevant images)
- Info Blue: `#17a2b8` (AI descriptions)

### UI Patterns
- Match existing card styling in edit_case.html
- Follow existing modal patterns
- Use consistent image thumbnail styling
- Follow existing attribution patterns

---

## Key Benefits

| Model | Cost per 1000 Students Viewing Case |
|-------|-------------------------------------|
| Current (student search) | $20+ (if we added search) |
| Proposed (admin curation) | $0.03 (amortized) |

**Savings: 99.85%**

---

## Database Schema

```python
class CaseReferenceImage(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    case_id = db.Column(db.Integer, db.ForeignKey('case.id'), nullable=False)
    source_url = db.Column(db.String(1000), nullable=False)
    source_domain = db.Column(db.String(255), nullable=False)
    thumbnail_url = db.Column(db.String(500))
    # image_type: 'ct_mri' | 'anatomy_diagram' | 'concept_diagram'
    image_type = db.Column(db.String(50), nullable=False, default='ct_mri')
    modality = db.Column(db.String(50))  # CT, MRI, etc. (for imaging type)
    ai_description = db.Column(db.Text)
    ai_relevance_score = db.Column(db.Float)
    admin_note = db.Column(db.Text)
    display_order = db.Column(db.Integer, default=0)
    added_by_user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    # REQUIRED: License must be Creative Commons or public domain
    license = db.Column(db.String(100), nullable=False, default='CC BY 4.0')  # CC BY, CC BY-SA, CC0, etc.
    attribution = db.Column(db.String(500), nullable=False)  # Required for CC attribution
```

---

## Search Strategy

### Google Custom Search Configuration

- **Usage rights:** Always use `rights=creative_commons` (or `cc_publicdomain`) so results are CC-licensed
- **Image search:** Use Google Custom Search API with `searchType=image`
- **Query variants per image type:**

| Image Type | Query Pattern | Example |
|------------|---------------|---------|
| CT/MRI | `{diagnosis} {modality} imaging` | "glioblastoma CT brain", "ACL tear MRI knee" |
| Anatomy diagram | `{body_part} anatomy line diagram` | "brain anatomy cross section diagram", "knee anatomy schematic" |
| Concept diagram | `{diagnosis} staging diagram` or `{concept} flowchart` | "TNM staging flowchart", "lung cancer classification diagram" |

### Validation Rules

- **Before save:** Reject any image without confirmed CC/public domain license
- **AI ranking:** Instruct Claude to only recommend images with explicit CC attribution; reject if license unclear
- **Admin UI:** Display license and attribution; require admin to confirm before adding

---

## Implementation Phases

### Phase 1: Database and Backend (Week 1-2)
- Create `CaseReferenceImage` model and migration (including `image_type`, `license`, `attribution`)
- Implement `GoogleSearchService` with `rights=creative_commons` for CC-only results
- Implement query builder for CT/MRI, anatomy diagrams, concept diagrams
- Create reference image API routes
- Add Cloudinary thumbnail caching

### Phase 2: AI Integration (Week 2-3)
- Implement `AIImageAnalysisService`
- Create Claude prompts: result ranking + **CC-only validation** (reject if license unclear)
- Add optional image vision analysis
- Enforce license/attribution extraction in AI response

### Phase 3: Admin UI (Week 3-4)
- Add Reference Images section to edit_case.html
- Build search results modal with image type filter (CT/MRI, Anatomy, Concept)
- Display license and attribution for each result; require confirmation before add
- Implement image selection and saving (block save if license missing)

### Phase 4: Student UI (Week 4)
- Update view_case.html Anatomy tab
- Display curated images with thumbnails, grouped by type (imaging, anatomy, concept)
- Show attribution for each image (CC requirement)
- Fallback to static links if no curated images

---

## Files to Create/Modify

### New Files
- `google_search_service.py`
- `ai_image_service.py`
- `reference_image_routes.py`

### Modified Files
- `models.py` - Add CaseReferenceImage model
- `templates/edit_case.html` - Admin curation UI
- `templates/view_case.html` - Student display

---

## Environment Variables

```bash
GOOGLE_SEARCH_API_KEY=your_api_key
GOOGLE_SEARCH_ENGINE_ID=your_cse_id
```

---

## Todos

- [ ] Create CaseReferenceImage model with `image_type`, `license`, `attribution` and migration
- [ ] Implement GoogleSearchService with `rights=creative_commons` (CC-only)
- [ ] Implement query variants for CT/MRI, anatomy diagrams, concept diagrams
- [ ] Create reference image API routes
- [ ] Implement AIImageAnalysisService with Claude (CC-only validation in prompts)
- [ ] Add Cloudinary thumbnail caching
- [ ] Build admin UI section in edit_case.html with image type filter and license display
- [ ] Update student view_case.html to display curated images with attribution
- [ ] (Optional) Implement batch processing for existing cases
