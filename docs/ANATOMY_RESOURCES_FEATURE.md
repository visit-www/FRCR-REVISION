# Anatomy Resources Feature - Design Document

> **Feature:** "Find Normal Anatomy Resources" Button  
> **Target:** Student Case View (`student_cases_list.html` / `view_case.html`)  
> **Status:** Design Phase  
> **Last Updated:** January 17, 2026

---

## 📋 Table of Contents

1. [Feature Overview](#feature-overview)
2. [User Story](#user-story)
3. [Design Recommendations](#design-recommendations)
4. [Comprehensive Resource List](#comprehensive-resource-list)
5. [Implementation Strategy](#implementation-strategy)
6. [UI/UX Design](#uiux-design)
7. [Technical Specifications](#technical-specifications)
8. [Value Proposition](#value-proposition)

---

## Feature Overview

### Purpose

Add a "Find Normal Anatomy Resources" button in the **student case view** that:
- Analyzes the case diagnosis, body part, and modality
- Matches to relevant normal anatomy resources from a comprehensive curated list
- Displays filtered, ranked links to high-quality anatomy resources
- Helps students understand normal anatomy for comparison with pathology

### Key Requirements

- **Target Audience:** Students viewing cases (not admin/editor view)
- **Location:** Student case view page (`view_case.html` when accessed by students)
- **Functionality:** Smart matching + rule-based filtering
- **Display:** Modal popup or expandable section
- **Data Source:** Comprehensive JSON configuration file with curated resources

---

## User Story

**As a** radiology student  
**I want to** quickly access relevant normal anatomy resources when viewing a case  
**So that** I can compare normal anatomy with the pathology and better understand the imaging findings

**Acceptance Criteria:**
- Button appears in student case view (not in admin/edit view)
- Button analyzes case metadata (diagnosis, body part, modality)
- Returns curated, relevant anatomy resource links
- Links are organized by relevance (primary, secondary, related)
- Each link includes description and opens in new tab
- Works for all common diagnoses and body parts

---

## Design Recommendations

### Recommended Approach: Hybrid System

**Primary Method:** Smart matching for common diagnoses
- Pre-mapped diagnosis → resource relationships
- High relevance, curated results
- Fast lookup

**Fallback Method:** Rule-based filtering
- Filter by body part + modality
- Works for any diagnosis
- Broader results

**Display:** Organized sections with relevance ranking

---

## Comprehensive Resource List

### Resource Organization Structure

Resources are organized by:
- **Body Part** (Head, Neck, Chest, Abdomen, MSK, etc.)
- **Modality** (CT, MRI, X-ray, Ultrasound, etc.)
- **Anatomy Type** (Normal, Cross-sectional, 3D, etc.)
- **Quality** (High, Medium)
- **Access** (Free, Subscription required)

---

### 🔗 Head-to-Toe Normal Radiological Anatomy Modules

#### Chest & Abdominal Radiographs

| Resource | URL | Modality | Body Part | Free |
|----------|-----|----------|-----------|------|
| Chest Radiograph | https://www.radiologymasterclass.co.uk/ | X-ray | Chest | ✅ |
| Chest Radiograph (Alternative) | https://medicalimagecafe.com/ | X-ray | Chest | ✅ |
| Abdominal Radiograph | https://www.radiologymasterclass.co.uk/ | X-ray | Abdomen | ✅ |

#### Barium Studies

| Resource | URL | Modality | Body Part | Free |
|----------|-----|----------|-----------|------|
| Barium Swallow | http://www.castlemountain.dk/ | Fluoroscopy | Esophagus | ✅ |

#### Skeletal Radiology

| Resource | URL | Modality | Body Part | Free |
|----------|-----|----------|-----------|------|
| Skeletal Radiology | http://uwmsk.org/ | X-ray | MSK | ✅ |
| Shoulder X-ray | http://www.castlemountain.dk/ | X-ray | Shoulder | ✅ |
| Wrist X-ray | http://www.castlemountain.dk/ | X-ray | Wrist | ✅ |
| Hip X-ray | http://www.castlemountain.dk/ | X-ray | Hip | ✅ |
| Knee X-ray | http://www.castlemountain.dk/ | X-ray | Knee | ✅ |
| Normal Paediatric Bone X-rays (Bone Age) | http://bonexray.com/ | X-ray | Pediatric MSK | ✅ |
| Lower Limb Radiography | https://www.radiologymasterclass.co.uk/ | X-ray | Lower Limb | ✅ |

#### Ultrasound

| Resource | URL | Modality | Body Part | Free |
|----------|-----|----------|-----------|------|
| Ultrasound Knobology | http://www.castlemountain.dk/ | Ultrasound | General | ✅ |

#### Angiography

| Resource | URL | Modality | Body Part | Free |
|----------|-----|----------|-----------|------|
| Lower Limb CT Angiography | http://www.castlemountain.dk/ | CTA | Lower Limb | ✅ |
| Upper Limb Angiography | http://www.castlemountain.dk/ | Angiography | Upper Limb | ✅ |
| Lower Limb Angiography | http://www.castlemountain.dk/ | Angiography | Lower Limb | ✅ |

#### Nuclear Medicine

| Resource | URL | Modality | Body Part | Free |
|----------|-----|----------|-----------|------|
| PET-CT | http://www.castlemountain.dk/ | PET-CT | Whole Body | ✅ |

---

### 🧠 CT Normal Anatomy Modules

#### Head & Neck CT

| Resource | URL | Modality | Body Part | Free |
|----------|-----|----------|-----------|------|
| Head CT | http://www.castlemountain.dk/ | CT | Head/Brain | ✅ |
| Axial CT (Skull Base) | https://docs.google.com/ | CT | Skull Base | ✅ |
| Coronal CT (Skull Base) | https://docs.google.com/ | CT | Skull Base | ✅ |
| Facial Bones 3D - Frontal | https://medicalimagecafe.com/ | CT 3D | Face | ✅ |
| Facial Bones 3D - Lateral | https://medicalimagecafe.com/ | CT 3D | Face | ✅ |
| Temporal Bone - Axial | https://medicalimagecafe.com/ | CT | Temporal Bone | ✅ |
| Temporal Bone - Axial (Alternate) | https://docs.google.com/ | CT | Temporal Bone | ✅ |
| Temporal Bone - Coronal | https://medicalimagecafe.com/ | CT | Temporal Bone | ✅ |
| Paranasal Sinuses | https://docs.google.com/ | CT | Sinuses | ✅ |
| Head and Neck Anatomy | http://sectional-anatomy.org/ | CT | Head/Neck | ✅ |
| Nasopharynx | https://docs.google.com/ | CT | Nasopharynx | ✅ |
| Oropharynx | https://docs.google.com/ | CT | Oropharynx | ✅ |
| Oral Cavity | https://docs.google.com/ | CT | Oral Cavity | ✅ |
| Floor of Mouth | https://docs.google.com/ | CT | Floor of Mouth | ✅ |
| Retromolar Trigone | https://docs.google.com/ | CT | Retromolar Trigone | ✅ |
| Larynx | https://docs.google.com/ | CT | Larynx | ✅ |
| Hypopharynx | https://docs.google.com/ | CT | Hypopharynx | ✅ |
| Innervation and Lymph Node Drainage | https://docs.google.com/ | CT | Neck | ✅ |
| Neck Nodes (Radiopaedia) | https://radiopaedia.org/ | CT | Neck Nodes | ✅ |
| Neck Spaces - Buccal Space | https://docs.google.com/ | CT | Neck Spaces | ✅ |
| Parapharyngeal Space | https://docs.google.com/ | CT | Neck Spaces | ✅ |
| Retropharyngeal & Danger Space | https://docs.google.com/ | CT | Neck Spaces | ✅ |
| Cervical Spine CT | http://www.castlemountain.dk/ | CT | Cervical Spine | ✅ |

#### Chest CT

| Resource | URL | Modality | Body Part | Free |
|----------|-----|----------|-----------|------|
| HRCT Chest | http://www.castlemountain.dk/ | HRCT | Chest | ✅ |
| Lung Window | https://medicalimagecafe.com/ | CT | Lung | ✅ |
| Mediastinal Window | https://medicalimagecafe.com/ | CT | Mediastinum | ✅ |

#### Abdomen & Pelvis CT

| Resource | URL | Modality | Body Part | Free |
|----------|-----|----------|-----------|------|
| Abdomen CT | http://www.castlemountain.dk/ | CT | Abdomen | ✅ |
| Abdomen CT 2 | http://sectional-anatomy.org/ | CT | Abdomen | ✅ |
| Abdomen CT 3 | https://medicalimagecafe.com/ | CT | Abdomen | ✅ |

#### MSK CT

| Resource | URL | Modality | Body Part | Free |
|----------|-----|----------|-----------|------|
| CT Wrist | http://sectional-anatomy.org/ | CT | Wrist | ✅ |

---

### 🧲 MRI Normal Anatomy Modules

#### Brain & Head MRI

| Resource | URL | Modality | Body Part | Free |
|----------|-----|----------|-----------|------|
| Brain MRI | https://medicalimagecafe.com/ | MRI | Brain | ✅ |
| Diffusion Tensor Imaging Atlas | https://www.dtiatlas.org/ | DTI | Brain | ✅ |
| Normal MRI Myelination in Infants | https://www.myelinationmriatlas.com/ | MRI | Pediatric Brain | ✅ |

#### Neck MRI

| Resource | URL | Modality | Body Part | Free |
|----------|-----|----------|-----------|------|
| Neck Spaces MRI Anatomy | https://radiopaedia.org/ | MRI | Neck Spaces | ✅ |
| MR Neck Angiography | http://www.castlemountain.dk/ | MRA | Neck | ✅ |
| MRI Neck Anatomy | https://medicalimagecafe.com/ | MRI | Neck | ✅ |
| Head and Neck MRI Anatomy | https://headandneckrad.com | MRI | Head/Neck | ✅ |

#### Spine MRI

| Resource | URL | Modality | Body Part | Free |
|----------|-----|----------|-----------|------|
| Cervical Spine MRI | http://www.castlemountain.dk/ | MRI | Cervical Spine | ✅ |
| Lumbar Spine MRI | https://www.radiologymasterclass.co.uk/ | MRI | Lumbar Spine | ✅ |
| Lumbar Spine MRI - Axial | https://medicalimagecafe.com/ | MRI | Lumbar Spine | ✅ |
| Lumbar Spine MRI - Sagittal | https://medicalimagecafe.com/ | MRI | Lumbar Spine | ✅ |

#### Body MRI

| Resource | URL | Modality | Body Part | Free |
|----------|-----|----------|-----------|------|
| MRCP | http://www.castlemountain.dk/ | MRCP | Biliary Tree | ✅ |
| Female Pelvis MRI | http://www.castlemountain.dk/ | MRI | Female Pelvis | ✅ |
| Male Pelvis MRI | http://www.castlemountain.dk/ | MRI | Male Pelvis | ✅ |

#### MSK MRI

| Resource | URL | Modality | Body Part | Free |
|----------|-----|----------|-----------|------|
| MSK MRI Anatomy | https://www.freitasrad.net | MRI | MSK | ✅ |
| Knee MRI | https://www.freitasrad.net/ | MRI | Knee | ✅ |
| Knee MRI - Coronal | https://medicalimagecafe.com/ | MRI | Knee | ✅ |
| Knee MRI - Sagittal | https://medicalimagecafe.com/ | MRI | Knee | ✅ |
| Shoulder MRI | https://www.freitasrad.net/ | MRI | Shoulder | ✅ |
| Shoulder MRI - Coronal | https://medicalimagecafe.com/ | MRI | Shoulder | ✅ |
| Shoulder MRI - Sagittal | https://medicalimagecafe.com/ | MRI | Shoulder | ✅ |
| Shoulder Arthrogram | https://www.freitasrad.net/ | MR Arthrogram | Shoulder | ✅ |
| Ankle MRI | https://www.freitasrad.net/ | MRI | Ankle | ✅ |
| Ankle MRI - Axial | https://medicalimagecafe.com/ | MRI | Ankle | ✅ |
| Ankle MRI - Coronal | https://medicalimagecafe.com/ | MRI | Ankle | ✅ |
| Ankle MRI - Sagittal | https://medicalimagecafe.com/ | MRI | Ankle | ✅ |
| Elbow MRI | https://www.freitasrad.net/ | MRI | Elbow | ✅ |
| Wrist MRI | https://www.freitasrad.net/ | MRI | Wrist | ✅ |
| Hip MRI | https://www.freitasrad.net/ | MRI | Hip | ✅ |

---

### 🔎 Comprehensive Online References

#### Primary Resources

| Resource | URL | Description | Free |
|----------|-----|-------------|------|
| Radiology Masterclass | https://www.radiologymasterclass.co.uk/ | Comprehensive radiology education | ✅ |
| University of Washington (MSK) | http://uwmsk.org/ | MSK radiology resources | ✅ |
| IMAIOS e-Anatomy | https://www.imaios.com/en/e-anatomy | High-quality anatomy atlas | ⚠️ Subscription |
| Headneckbrainspine.com | http://headneckbrainspine.com/ | Head and neck anatomy | ✅ |
| Freitasrad | https://www.freitasrad.net | MSK MRI anatomy | ✅ |
| Stanford MSK MRI | https://xrayhead.com/ | MSK imaging | ✅ |
| Imaging Anatomy (Castlemountain) | http://www.castlemountain.dk/ | Cross-sectional anatomy | ✅ |
| W-Radiology | https://w-radiology.com/ | Radiology reference | ✅ |
| Seattle Children's Hospital Radiology Atlases | https://www.seattlechildrens.org/ | Pediatric radiology | ✅ |
| Cross-section Tutorials | https://www.lumen.luc.edu/ | Cross-sectional anatomy | ✅ |
| ASKMSK.in | https://askmsk.in/ | MSK radiology | ✅ |
| Radiopaedia | https://radiopaedia.org/ | Comprehensive radiology reference | ✅ |
| Medical Image Cafe | https://medicalimagecafe.com/ | Medical imaging resources | ✅ |
| Sectional Anatomy | http://sectional-anatomy.org/ | Cross-sectional anatomy | ✅ |
| Head and Neck Radiology | https://headandneckrad.com | Head and neck MRI anatomy | ✅ |
| Radiogyan - Radiological Anatomy | https://radiogyan.com/radiological-anatomy/ | Comprehensive anatomy links collection | ✅ |

---

## Implementation Strategy

### Phase 1: Data Structure

**Create `anatomy_resources.json`:**

```json
{
  "version": "1.0",
  "last_updated": "2026-01-17",
  "resources": [
    {
      "id": "head_ct_castle",
      "title": "Head CT Normal Anatomy",
      "url": "http://www.castlemountain.dk/...",
      "body_parts": ["Head", "Brain"],
      "modalities": ["CT"],
      "anatomy_type": "normal",
      "description": "Axial CT slices showing normal brain anatomy",
      "quality": "high",
      "free": true,
      "source": "Castlemountain"
    },
    {
      "id": "msk_mri_freitas",
      "title": "MSK MRI Anatomy",
      "url": "https://www.freitasrad.net/...",
      "body_parts": ["Knee", "Shoulder", "Ankle", "Elbow", "Wrist", "Hip"],
      "modalities": ["MRI"],
      "anatomy_type": "normal",
      "description": "Comprehensive MSK MRI anatomy atlas",
      "quality": "high",
      "free": true,
      "source": "Freitasrad"
    }
  ],
  "diagnosis_mappings": {
    "Extradural hematoma": {
      "primary": ["head_ct_castle", "brain_mri_medicalimage"],
      "secondary": ["head_neck_mri", "skull_base_ct"],
      "body_part": "Head",
      "modality": "CT"
    },
    "Pneumonia": {
      "primary": ["chest_xray_radiology_masterclass", "hrct_chest"],
      "secondary": ["lung_window", "mediastinal_window"],
      "body_part": "Chest",
      "modality": "X-ray"
    }
  },
  "body_part_keywords": {
    "Head": ["head", "brain", "skull", "cranial"],
    "Neck": ["neck", "cervical", "larynx", "pharynx"],
    "Chest": ["chest", "thorax", "lung", "mediastinum"],
    "Abdomen": ["abdomen", "abdominal", "pelvis"],
    "MSK": ["knee", "shoulder", "ankle", "elbow", "wrist", "hip", "msk", "musculoskeletal"]
  }
}
```

### Phase 2: Matching Logic

**Algorithm:**
1. Extract case metadata:
   - Diagnosis
   - Body part
   - Modality
2. Primary match: Check `diagnosis_mappings` for exact diagnosis
3. Secondary match: Filter by body part + modality
4. Tertiary match: Filter by body part only
5. Rank results by:
   - Primary match (highest priority)
   - Quality rating
   - Free vs. subscription
   - Relevance score

### Phase 3: Backend API

**New Route:** `GET /api/case/<id>/anatomy-resources`

**Response:**
```json
{
  "success": true,
  "case_id": 14,
  "diagnosis": "Extradural hematoma",
  "body_part": "Head",
  "modality": "CT",
  "resources": {
    "primary": [
      {
        "id": "head_ct_castle",
        "title": "Head CT Normal Anatomy",
        "url": "http://www.castlemountain.dk/...",
        "description": "Axial CT slices showing normal brain anatomy",
        "relevance": "high",
        "quality": "high",
        "free": true
      }
    ],
    "secondary": [...],
    "related": [...]
  }
}
```

### Phase 4: Frontend Component

**Location:** `templates/view_case.html` (student view only)

**Button:**
```html
{% if current_user.role == 'student' %}
<button type="button" class="btn btn-outline-primary" id="findAnatomyResourcesBtn">
    <i class="fas fa-book-medical me-2"></i>Find Normal Anatomy Resources
</button>
{% endif %}
```

**Modal Component:**
- Bootstrap modal
- Organized sections (Primary, Secondary, Related)
- Links open in new tab
- Descriptions for each resource
- Search/filter capability (future)

---

## UI/UX Design

### Button Placement

**Recommended Location:**
- Near the diagnosis section
- Or in the case header/toolbar
- Visible but not intrusive

**Button Style:**
```
[📚 Find Normal Anatomy Resources]
```

### Modal Design

```
┌─────────────────────────────────────────────────────┐
│  📚 Normal Anatomy Resources                        │
│  for: Extradural Hematoma                           │
│  Body Part: Head | Modality: CT                     │
├─────────────────────────────────────────────────────┤
│                                                     │
│  🎯 Primary Resources (High Relevance):            │
│  ┌─────────────────────────────────────────────┐  │
│  │ Head CT Normal Anatomy                      │  │
│  │ http://www.castlemountain.dk/...            │  │
│  │ Axial CT slices showing normal brain        │  │
│  │ [Open Link] [Copy URL]                      │  │
│  └─────────────────────────────────────────────┘  │
│                                                     │
│  📚 Secondary Resources:                            │
│  • Brain MRI Normal Anatomy                         │
│  • Skull Base CT Anatomy                            │
│                                                     │
│  🔗 Related Resources:                              │
│  • Head and Neck MRI Anatomy                        │
│  • Cervical Spine CT                                │
│                                                     │
│  [Close]                                            │
└─────────────────────────────────────────────────────┘
```

### Mobile Responsive

- Stack resources vertically
- Full-width buttons
- Touch-friendly spacing
- Collapsible sections

---

## Technical Specifications

### File Structure

```
FRCR_REVISION/
├── static/
│   └── anatomy-resources.json          # Resource configuration
├── templates/
│   └── view_case.html                  # Add button + modal
├── static/
│   └── anatomy-resources.js            # Frontend logic
└── app.py                              # Backend API route
```

### Dependencies

- **Backend:** None (uses existing Flask setup)
- **Frontend:** Bootstrap (already included)
- **Data:** JSON file (no database needed initially)

### Performance Considerations

- Load JSON file once at startup (cache in memory)
- Fast lookup (O(1) for diagnosis mapping, O(n) for filtering)
- Minimal API response time (< 50ms expected)

### Security

- Student role check (only students see button)
- No user input (read-only resource lookup)
- External links open in new tab (security best practice)

---

## Value Proposition

### For Students

1. **Time Savings:** No manual searching for anatomy resources
2. **Relevance:** Curated, diagnosis-specific links
3. **Learning:** Compare normal vs. pathology side-by-side
4. **Comprehensive:** Access to 50+ high-quality resources
5. **Educational:** Supports understanding of normal anatomy context

### For the Application

1. **Differentiation:** Unique feature not found in other radiology apps
2. **User Engagement:** Keeps students in the app longer
3. **Educational Value:** Supports learning objectives
4. **Professional Tool:** Useful for exam preparation
5. **Scalability:** Easy to add more resources over time

---

## Future Enhancements

### Phase 2 Features

1. **User Preferences:**
   - Favorite resources
   - Recently viewed
   - Custom bookmarks

2. **Search/Filter:**
   - Search within results
   - Filter by modality
   - Filter by free/subscription

3. **Analytics:**
   - Track most-used resources
   - Popular diagnoses
   - User feedback

4. **Integration:**
   - Link to AI-generated teaching images
   - Cross-reference with case images
   - Annotated comparisons

### Phase 3 Features

1. **AI Enhancement:**
   - Use AI to suggest most relevant resources
   - Generate resource descriptions
   - Match based on case images

2. **Community Features:**
   - User-submitted resources
   - Ratings and reviews
   - Resource recommendations

---

## Success Metrics

### Key Performance Indicators

1. **Usage:**
   - % of students who click the button
   - Average resources viewed per case
   - Most popular resources

2. **Engagement:**
   - Time spent viewing resources
   - Return usage rate
   - User feedback scores

3. **Educational Impact:**
   - Student feedback on usefulness
   - Correlation with exam performance (if measurable)
   - Integration with learning objectives

---

## Implementation Checklist

### Pre-Development

- [ ] Finalize resource list
- [ ] Create JSON structure
- [ ] Design UI mockups
- [ ] Get stakeholder approval

### Development Phase 1

- [ ] Create `anatomy_resources.json`
- [ ] Implement backend API route
- [ ] Add button to student view
- [ ] Create modal component
- [ ] Implement matching logic

### Development Phase 2

- [ ] Add search/filter functionality
- [ ] Implement user preferences
- [ ] Add analytics tracking
- [ ] Mobile optimization

### Testing

- [ ] Test with various diagnoses
- [ ] Test matching accuracy
- [ ] Test UI responsiveness
- [ ] User acceptance testing

### Deployment

- [ ] Deploy to staging
- [ ] User training/documentation
- [ ] Monitor usage and feedback
- [ ] Iterate based on feedback

---

## Notes

- **Student-Only Feature:** This feature is specifically for student case view, not admin/editor view
- **Read-Only:** Resources are curated and read-only (no user editing)
- **External Links:** All resources open in new tabs for security
- **Maintenance:** Resource list should be reviewed quarterly for broken links
- **Scalability:** JSON structure allows easy addition of new resources

---

*This document serves as the design specification for the Anatomy Resources feature. It should be updated as the feature evolves.*
