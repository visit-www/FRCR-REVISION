# Anatomy Enhancement Feature - Implementation Plan

> **Feature Branch:** `feature/anatomy-enhancement`  
> **Status:** Implementation In Progress  
> **Created:** January 26, 2026  
> **Last Updated:** January 26, 2026  
> **Tagged Baseline:** `v1.0-pre-anatomy-enhancement`

---

## 🚀 Current Implementation Status

### Completed
- [x] Created `AnatomyFigure` model in `models.py`
- [x] Created `static/essential_tnm_data.json` with key concepts for 8 cancers
- [x] Created `static/anatomy_resources.json` for student resources
- [x] Created `scripts/extract_iarc_figures.py` for IARC PDF extraction
- [x] Created `/essential-tnm-concepts` route and template
- [x] Added Essential TNM button injection in `edit_case.html` (for 7 cancers)
- [x] Extracted IARC figures locally to `scripts/iarc_figures/`

### In Progress
- [ ] Inject Essential TNM Key Concepts section in `ai_tnm.py`
- [ ] Add Student Anatomy Resources button to `view_case.html`
- [ ] Run database migration for `AnatomyFigure` model
- [ ] Upload IARC figures to Cloudinary (requires env vars)
- [ ] Modify AI prompts for figure placeholder injection

### Data Files Created
| File | Purpose |
|------|---------|
| `static/essential_tnm_data.json` | Key concepts + figure metadata for 8 cancers |
| `static/anatomy_resources.json` | External anatomy resource links for students |
| `scripts/iarc_figures/` | Local IARC images (gitignored) |

---

## 📋 Executive Summary

This feature enhances the FRCR Revision app with two complementary anatomy visualization capabilities:

1. **Student Anatomy Resources Button** - External links to curated anatomy resources
2. **AI Figure Injection** - Embedded CC-licensed figures in AI-generated discussions
3. **Essential TNM Key Concepts** - IARC-sourced staging key points for 8 common cancers

---

## 🎯 Two Goals, One Feature

### Goal A: Student Anatomy Resources Button
| Aspect | Details |
|--------|---------|
| **User** | Students |
| **Location** | Case view header/notes section |
| **Trigger** | Button click |
| **Output** | Modal with external links to anatomy websites |
| **Reference** | `docs/ANATOMY_RESOURCES_FEATURE.md` (existing) |

### Goal B: AI Figure Injection
| Aspect | Details |
|--------|---------|
| **User** | Admins (during case creation) |
| **Location** | Within AI generation workflow |
| **Trigger** | AI generates case discussion |
| **Output** | Embedded figures in discussion with attribution |
| **Source** | CC-licensed images (OpenStax, IARC, etc.) |

---

## 📚 Open-Access Image Sources

### For `ai_tnm.py` (Cancer Staging)

| Source | License | Content | Status |
|--------|---------|---------|--------|
| **IARC Essential TNM Guide (2024)** | CC BY-NC-ND 3.0 IGO | TNM flowcharts, staging diagrams | PDF available locally |
| **Radiopaedia diagrams** | CC-NC-BY-SA 3.0 | Staging illustrations | Web accessible |

**IARC PDF Location:** `/Users/zen/Library/CloudStorage/OneDrive-Personal/Workstation companions/IARC_TNM_Essentia.pdf`

### For `ai_prelim.py` (General Anatomy)

| Source | License | Content | Status |
|--------|---------|---------|--------|
| **OpenStax Anatomy & Physiology 2e** | CC BY 4.0 | Line drawings, anatomical illustrations | GitHub/Web |
| **Open Anatomy Project** | Open Source | CT/MRI atlases | Web accessible |
| **Visible Human Project** | Public Domain | Cross-sectional anatomy | NIH download |
| **Radiopaedia** | CC-NC-BY-SA 3.0 | Radiology diagrams | Web accessible |

---

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                    ANATOMY ENHANCEMENT SYSTEM                        │
├─────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  ┌──────────────────────┐     ┌──────────────────────┐             │
│  │   STUDENT VIEW       │     │   ADMIN VIEW          │             │
│  │                      │     │                       │             │
│  │  [Find Anatomy       │     │  AI Prelim/TNM Gen   │             │
│  │   Resources Button]  │     │         ↓            │             │
│  │        ↓             │     │  Figures injected    │             │
│  │  Modal with links    │     │  into discussion     │             │
│  └──────────────────────┘     └──────────────────────┘             │
│                                         │                           │
│  ┌──────────────────────────────────────┴───────────────────────┐  │
│  │                     FIGURE DATABASE                           │  │
│  │  ┌─────────────────┐  ┌─────────────────┐                   │  │
│  │  │ OpenStaxFigure  │  │ IARCFigure      │                   │  │
│  │  │ - body_region   │  │ - cancer_type   │                   │  │
│  │  │ - keywords      │  │ - staging_type  │                   │  │
│  │  │ - cloudinary_url│  │ - cloudinary_url│                   │  │
│  │  │ - attribution   │  │ - attribution   │                   │  │
│  │  └─────────────────┘  └─────────────────┘                   │  │
│  └──────────────────────────────────────────────────────────────┘  │
│                                                                      │
│  ┌──────────────────────────────────────────────────────────────┐  │
│  │                      CLOUDINARY                               │  │
│  │  frcr_revision/                                               │  │
│  │  ├── anatomy/openstax/   (OpenStax figures)                  │  │
│  │  ├── anatomy/iarc/       (IARC TNM diagrams)                 │  │
│  │  └── anatomy/open/       (Other CC sources)                  │  │
│  └──────────────────────────────────────────────────────────────┘  │
│                                                                      │
└─────────────────────────────────────────────────────────────────────┘
```

---

## 📊 Database Schema

### New Models

```python
class AnatomyFigure(db.Model):
    """Base model for CC-licensed anatomy figures."""
    __tablename__ = 'anatomy_figure'
    
    id = db.Column(db.Integer, primary_key=True)
    figure_id = db.Column(db.String(100), unique=True, nullable=False)
    title = db.Column(db.String(300), nullable=False)
    description = db.Column(db.Text)
    
    # Classification
    source = db.Column(db.String(50), nullable=False)  # 'openstax', 'iarc', 'radiopaedia'
    body_region = db.Column(db.String(100))  # 'thorax', 'head-neck', 'abdomen'
    figure_type = db.Column(db.String(50))  # 'anatomy', 'staging', 'flowchart'
    keywords = db.Column(db.JSON)  # ['lung', 'bronchi', 'respiratory']
    
    # For TNM-specific figures
    cancer_type = db.Column(db.String(100))  # 'lung', 'breast', etc.
    staging_category = db.Column(db.String(20))  # 'T', 'N', 'M', 'general'
    
    # Image URLs
    original_url = db.Column(db.String(500))
    cloudinary_url = db.Column(db.String(500))
    cloudinary_public_id = db.Column(db.String(300))
    thumbnail_url = db.Column(db.String(500))
    
    # Attribution
    license = db.Column(db.String(100), default='CC BY 4.0')
    attribution = db.Column(db.String(300))
    
    # Metadata
    chapter = db.Column(db.Integer)  # For OpenStax
    page_number = db.Column(db.Integer)  # For IARC PDF
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    def to_dict(self):
        return {
            'id': self.id,
            'figure_id': self.figure_id,
            'title': self.title,
            'cloudinary_url': self.cloudinary_url,
            'attribution': self.attribution,
            'body_region': self.body_region,
            'keywords': self.keywords
        }
```

---

## 🔄 AI Integration

### For `ai_tnm.py`

**Prompt Addition:**
```
When discussing staging, you may reference figures from our licensed library.
Use this format: [FIGURE:TNM:{cancer_type}:{category}]

Examples:
[FIGURE:TNM:lung:T] - Lung T-stage diagram
[FIGURE:TNM:breast:flowchart] - Breast staging flowchart
```

**Post-Processing:**
```python
def inject_tnm_figures(ai_output: str, cancer_type: str) -> str:
    """Replace [FIGURE:TNM:...] placeholders with actual images."""
    pattern = r'\[FIGURE:TNM:(\w+):(\w+)\]'
    
    def replace_figure(match):
        cancer = match.group(1)
        category = match.group(2)
        figure = AnatomyFigure.query.filter_by(
            source='iarc',
            cancer_type=cancer,
            staging_category=category
        ).first()
        
        if figure:
            return f'''
<figure class="tnm-figure">
    <img src="{figure.cloudinary_url}" alt="{figure.title}">
    <figcaption>{figure.title} – {figure.attribution}</figcaption>
</figure>
'''
        return ''
    
    return re.sub(pattern, replace_figure, ai_output)
```

### For `ai_prelim.py`

**Prompt Addition:**
```
When anatomical context would help understanding, you may reference figures.
Use this format: [FIGURE:ANATOMY:{body_region}:{description}]

Examples:
[FIGURE:ANATOMY:thorax:mediastinal anatomy]
[FIGURE:ANATOMY:liver:hepatic segments]
```

---

## 📋 Implementation Phases

### Phase 1: Student Anatomy Resources Button
**Priority:** High | **Effort:** Medium

- [x] Create `static/anatomy_resources.json` from existing doc
- [ ] Add API route `GET /api/case/<id>/anatomy-resources`
- [ ] Add button to `view_case.html` (student view only)
- [ ] Create modal component with categorized links
- [ ] Implement matching logic (diagnosis → resources)

### Phase 2: Database & Figure Extraction
**Priority:** High | **Effort:** High

- [x] Create `AnatomyFigure` model in `models.py`
- [ ] Run database migration
- [x] Create IARC PDF extraction script
- [ ] Extract and catalog OpenStax figures
- [ ] Upload all figures to Cloudinary
- [ ] Populate database with metadata

### Phase 3: AI Integration - Essential TNM Key Concepts
**Priority:** High | **Effort:** Medium

- [x] Create `static/essential_tnm_data.json` with key concepts
- [ ] Add function in `ai_tnm.py` to load and inject key concepts
- [ ] Inject Key Concepts section into TNM intelligence output
- [ ] Add IARC logo with attribution below Key Concepts
- [ ] Add figure injection post-processing

### Phase 4: AI Prompt Modifications
**Priority:** Medium | **Effort:** Low

- [ ] Update `ai_tnm.py` system prompt for figure placeholders
- [ ] Update `ai_prelim.py` system prompt for figure placeholders
- [ ] Add post-processing functions to inject actual images

### Phase 4: Frontend Display
**Priority:** Medium | **Effort:** Medium

- [ ] Style figure containers consistently
- [ ] Add attribution display
- [ ] Implement lightbox for full-size viewing
- [ ] Mobile responsive design

### Phase 5: Testing & Refinement
**Priority:** High | **Effort:** Medium

- [ ] Test with various case types
- [ ] Verify all attributions display correctly
- [ ] Test figure matching accuracy
- [ ] Performance testing (image load times)

---

## 🔧 Scripts Needed

### 1. IARC PDF Extraction Script
```python
# scripts/extract_iarc_figures.py
"""
Extract figures from IARC Essential TNM PDF.
Upload to Cloudinary and populate database.
"""
```

### 2. OpenStax Figure Catalog Script
```python
# scripts/catalog_openstax_figures.py
"""
Catalog OpenStax Anatomy figures from GitHub.
Download, upload to Cloudinary, populate database.
"""
```

### 3. Figure Migration Script
```python
# scripts/migrate_figures_to_cloudinary.py
"""
Batch upload all cataloged figures to Cloudinary.
"""
```

---

## ⚖️ Attribution Requirements

### IARC Essential TNM
```
Figure from IARC Essential TNM Guide (CC BY-NC-ND 3.0 IGO)
```

### OpenStax
```
OpenStax Anatomy & Physiology 2e (CC BY 4.0)
```

### Radiopaedia
```
© Radiopaedia.org (CC BY-NC-SA 3.0)
```

---

## 📁 File Structure

```
FRCR_REVISION/
├── docs/
│   ├── ANATOMY_RESOURCES_FEATURE.md  # Existing (external links)
│   └── ANATOMY_ENHANCEMENT_PLAN.md   # This document
├── scripts/
│   ├── extract_iarc_figures.py       # NEW
│   ├── catalog_openstax_figures.py   # NEW
│   └── migrate_figures_to_cloudinary.py  # NEW
├── static/
│   └── anatomy_resources.json        # NEW (for student button)
├── models.py                         # Add AnatomyFigure model
├── ai_tnm.py                         # Add figure injection
└── ai_prelim.py                      # Add figure injection
```

---

## ✅ Success Criteria

1. **Student Button:** Students can find relevant anatomy resources with 2 clicks
2. **Figure Injection:** AI-generated discussions include relevant embedded figures
3. **Attribution:** All figures display proper CC license attribution
4. **Performance:** Images load within 2 seconds via Cloudinary CDN
5. **Legal Compliance:** Only CC-licensed images used, properly attributed

---

## 🔙 Rollback Plan

If issues arise:
```bash
git checkout main
git branch -D feature/anatomy-enhancement
git checkout v1.0-pre-anatomy-enhancement
```

---

## 📝 Notes

- IARC figures cannot be modified (CC BY-NC-ND), use as-is
- OpenStax figures can be modified (CC BY), can crop/annotate
- Cloudinary transformation can optimize for web delivery
- Consider lazy loading for performance

---

*Document created: January 26, 2026*  
*Last updated: January 26, 2026*
