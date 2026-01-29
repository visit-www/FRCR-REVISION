# Reference Image Curation Feature - Implementation Plan

> **Priority:** 3 (High Value)  
> **Complexity:** Medium  
> **Estimated Effort:** 2-3 weeks  
> **Status:** Planned

## Executive Summary

Implement an admin-side AI-assisted reference image curation system that uses Google Custom Search + Claude AI to find, analyze, and store relevant radiology images for each case. Images are curated once by admin and displayed instantly to all students.

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
    modality = db.Column(db.String(50))
    ai_description = db.Column(db.Text)
    ai_relevance_score = db.Column(db.Float)
    admin_note = db.Column(db.Text)
    display_order = db.Column(db.Integer, default=0)
    added_by_user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
```

---

## Implementation Phases

### Phase 1: Database and Backend (Week 1-2)
- Create `CaseReferenceImage` model and migration
- Implement `GoogleSearchService`
- Implement basic API routes
- Add Cloudinary thumbnail caching

### Phase 2: AI Integration (Week 2-3)
- Implement `AIImageAnalysisService`
- Create Claude prompts for result ranking
- Add optional image vision analysis

### Phase 3: Admin UI (Week 3-4)
- Add Reference Images section to edit_case.html
- Build search results modal
- Implement image selection and saving

### Phase 4: Student UI (Week 4)
- Update view_case.html Anatomy tab
- Display curated images with thumbnails
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

- [ ] Create CaseReferenceImage model and database migration
- [ ] Implement GoogleSearchService with site restrictions
- [ ] Create reference image API routes
- [ ] Implement AIImageAnalysisService with Claude
- [ ] Add Cloudinary thumbnail caching
- [ ] Build admin UI section in edit_case.html
- [ ] Update student view_case.html to display curated images
- [ ] (Optional) Implement batch processing for existing cases
