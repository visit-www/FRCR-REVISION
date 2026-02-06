# Custom CSS Classes Reference

This document lists all custom CSS classes used in the FRCR Revision app. Classes from Bootstrap and other third-party libraries are excluded. Source files are indicated for each class.

---

## Table of Contents

1. [Brand & Theme Classes](#1-brand--theme-classes)
2. [Layout & Navigation](#2-layout--navigation)
3. [Q&A / Case Content](#3-qa--case-content)
4. [View Case / Edit Case](#4-view-case--edit-case)
5. [Admin Dashboard](#5-admin-dashboard)
6. [TNM Staging / AJCC](#6-tnm-staging--ajcc)
7. [Duplicate Modal](#7-duplicate-modal)
8. [AI-Generated Content](#8-ai-generated-content)
9. [User Highlights & Notes](#9-user-highlights--notes)
10. [DICOM Viewer](#10-dicom-viewer)
11. [Miscellaneous Utilities](#11-miscellaneous-utilities)

---

## 1. Brand & Theme Classes

| Class | Description | Source |
|-------|-------------|--------|
| `.btn-brand-primary` | Primary brand button (peachy orange) | style.css |
| `.btn-brand-secondary` | Secondary brand button (yellow) | style.css |
| `.btn-brand-success` | Success brand button (soft green) | style.css |
| `.btn-brand-neutral` | Neutral brand button (teal-blue) | style.css |
| `.text-brand-primary` | Primary brand text color | style.css |
| `.text-brand-secondary` | Secondary brand text color | style.css |
| `.text-brand-success` | Success brand text color | style.css |
| `.text-brand-white` | White text color | style.css |
| `.bg-brand-primary` | Primary brand background | style.css |
| `.bg-brand-secondary` | Secondary brand background | style.css |
| `.bg-brand-success` | Success brand background | style.css |
| `.card-brand` | Brand-styled card | style.css |
| `.card-brand-header` | Brand card header | style.css |
| `.card-brand-title` | Brand card title | style.css |
| `.card-brand-body` | Brand card body | style.css |
| `.text-page-title` | Page title typography | style.css |
| `.text-section-title` | Section title typography | style.css |
| `.text-card-title` | Card title typography | style.css |
| `.text-body-standard` | Body text typography | style.css |
| `.text-small-standard` | Small text typography | style.css |
| `.bg-peachy-orange` | Peachy orange background | style.css |
| `.bg-dark-green` | Dark green background | style.css |

---

## 2. Layout & Navigation

| Class | Description | Source |
|-------|-------------|--------|
| `.breadcrumb-custom` | Custom breadcrumb styling | style.css |
| `.quick-nav-group` | Quick navigation button group | style.css |
| `.main-content` | Main content wrapper | style.css |
| `.hero-banner` | Hero banner container | style.css |
| `.hero-overlay` | Hero overlay | style.css |
| `.hero-content` | Hero content wrapper | style.css |
| `.hero-title` | Hero title | style.css |
| `.hero-subtitle` | Hero subtitle | style.css |
| `.footer` | Footer container | style.css |
| `.footer-content` | Footer content | style.css |
| `.footer-title` | Footer title | style.css |
| `.footer-text` | Footer text | style.css |
| `.footer-link` | Footer link | style.css |
| `.footer-divider` | Footer divider | style.css |
| `.footer-copyright` | Footer copyright | style.css |
| `.mobile-breadcrumb-nav` | Mobile breadcrumb navigation | style.css |
| `.case-mobile-nav` | Mobile nav for case/view pages | view_case.html, view_tnm.html |
| `.case-mobile-nav-row` | Row for mobile nav buttons | view_case.html, view_tnm.html |
| `.case-nav-btn` | Case navigation button | view_case.html |

---

## 3. Q&A / Case Content

| Class | Description | Source |
|-------|-------------|--------|
| `.highlightable-text` | Text that can be highlighted (user-select enabled) | style.css |
| `.qa-section` | Q&A section container | style.css |
| `.qa-card` | Q&A card container | style.css |
| `.qa-question-card` | Question card (edit mode) | style.css |
| `.qa-answer-card` | Answer card (edit mode) | style.css |
| `.qa-question-card-display` | Question card (view mode) | style.css |
| `.qa-answer-card-display` | Answer card (view mode) | style.css |
| `.qa-header` | Q&A card header | style.css |
| `.qa-title` | Q&A title | style.css |
| `.qa-icon` | Q&A icon | style.css |
| `.qa-body` | Q&A card body | style.css |
| `.qa-cards-container` | Q&A cards wrapper | style.css |
| `.qa-cards-row` | Q&A cards row | style.css |
| `.qa-card-header` | Q&A card header (display mode) | style.css |
| `.qa-card-number` | Q&A card number badge | style.css |
| `.qa-card-body` | Q&A card body | style.css |
| `.qa-card-text` | Q&A card text | style.css |
| `.qa-pair-divider` | Divider between Q&A pairs | style.css |
| `.qa-separator` | Horizontal separator between pairs | style.css |
| `.qa-pair-grid` | Grid layout for Q&A pairs (edit) | style.css |
| `.qa-pair-row` | Row for Q&A pair | style.css |
| `.qa-pair-text` | Text in Q&A pair | style.css |
| `.qa-mobile-divider` | Mobile divider for Q&A | style.css |
| `.qa-question-col` | Question column in pair grid | style.css |
| `.qa-answer-col` | Answer column in pair grid | style.css |
| `.qa-table-wrapper` | Q&A table wrapper | style.css |
| `.qa-table-container` | Q&A table container | style.css |
| `.qa-table` | Q&A table | style.css |
| `.qa-table-header` | Q&A table header cell | style.css |
| `.qa-question-cell` | Question cell in table | style.css |
| `.qa-answer-cell` | Answer cell in table | style.css |
| `.qa-table-row` | Q&A table row | style.css |
| `.qa-row-even` | Zebra striping - even row | style.css |
| `.qa-row-odd` | Zebra striping - odd row | style.css |
| `.qa-table-cell` | Q&A table cell | style.css |
| `.qa-cell-number` | Cell number badge | style.css |
| `.qa-cell-content` | Cell content | style.css |
| `.plain-text-formatted` | Preserves line breaks and indentation | style.css |
| `.edit-case-questions` | Edit case questions area | style.css |
| `.edit-case-answers` | Edit case answers area | style.css |
| `.edit-case-discussion` | Edit case discussion area | style.css |
| `.case-questions` | Case questions area | style.css |
| `.case-answers` | Case answers area | style.css |
| `.case-discussion` | Case discussion area | style.css |
| `.detail-content` | Detail content wrapper | view_case.html |
| `.qa-question-text` | Question text wrapper | style.css |
| `.qa-answer-text` | Answer text wrapper | style.css |

---

## 4. View Case / Edit Case

| Class | Description | Source |
|-------|-------------|--------|
| `.case-card` | Case card container | style.css |
| `.case-card-header` | Case card header | style.css |
| `.case-details` | Case details container | style.css |
| `.detail-section` | Section within case details | style.css, view_case.html, view_tnm.html |
| `.detail-label` | Section label | style.css, view_case.html, view_tnm.html |
| `.section-title` | Section title | style.css |
| `.diagnosis-section` | Diagnosis section | style.css |
| `.diagnosis-text` | Diagnosis text | style.css |
| `.discussion-section` | Discussion section | style.css |
| `.discussion-text` | Discussion text | style.css |
| `.images-gallery` | Image gallery container | style.css |
| `.image-thumbnail` | Image thumbnail | style.css |
| `.image-delete` | Delete button on thumbnail | style.css |
| `.action-buttons` | Action buttons container | style.css |
| `.btn-group-actions` | Action button group | style.css |
| `.btn-group-primary` | Primary button group | style.css |
| `.btn-group-secondary` | Secondary button group | style.css |
| `.image-description-section` | Image description area | style.css |
| `.image-description-text` | Image description text | style.css |
| `.description-section` | Description section | style.css |
| `.student-case-layout` | Student case layout (grid) | view_case.html |
| `.related-cases-section` | Related cases section | view_case.html |
| `.notes-section` | Notes section | view_case.html, view_tnm.html |
| `.images-section` | Images section | view_case.html, view_tnm.html |
| `.case-row` | Table row for case | style.css |
| `.case-public` | Public case row styling | style.css |
| `.case-private` | Private case row styling | style.css |
| `.case-content` | Case content wrapper | style.css |

---

## 5. Admin Dashboard

| Class | Description | Source |
|-------|-------------|--------|
| `.admin-dashboard-container` | Admin dashboard wrapper | style.css |
| `.search-filter-card` | Search/filter card | style.css |
| `.search-group` | Search group | style.css |
| `.search-input-group` | Search input group | style.css |
| `.btn-search` | Search button | style.css |
| `.btn-clear-search` | Clear search button | style.css |
| `.users-table-card` | Users table card | style.css |
| `.role-superadmin` | Superadmin role badge | style.css |
| `.role-admin` | Admin role badge | style.css |
| `.role-content-manager` | Content manager role badge | style.css |
| `.role-student` | Student role badge | style.css |
| `.badge-admin` | Admin badge | style.css |
| `.badge-content_manager` | Content manager badge | style.css |
| `.badge-student` | Student badge | style.css |
| `.badge-paid` | Paid badge | style.css |
| `.badge-free` | Free badge | style.css |
| `.badge-canceled` | Canceled badge | style.css |
| `.btn-view` | View button | style.css |
| `.btn-edit` | Edit button | style.css |
| `.pagination-footer` | Pagination footer | style.css |
| `.btn-pagination` | Pagination button | style.css |
| `.page-info` | Page info text | style.css |
| `.user-detail-header` | User detail modal header | style.css |
| `.mode-indicator` | Edit/view mode indicator | style.css |
| `.detail-row` | Detail row in modal | style.css |
| `.modal-actions` | Modal action buttons | style.css |
| `.btn-delete` | Delete button | style.css |
| `.delete-options-section` | Delete options section | style.css |
| `.delete-option-button` | Delete option button | style.css |
| `.soft-delete` | Soft delete modifier | style.css |
| `.permanent-delete` | Permanent delete modifier | style.css |
| `.btn-title` | Button title (in delete options) | style.css |
| `.btn-description` | Button description | style.css |
| `.soft-delete-info` | Soft delete info box | style.css |
| `.btn-restore` | Restore button | style.css |
| `.status-active` | Active status | style.css |
| `.status-inactive` | Inactive status | style.css |
| `.status-deleted` | Deleted status | style.css |
| `.golden-enter-key` | Golden Enter key styling | style.css |

---

## 6. TNM Staging / AJCC

| Class | Description | Source |
|-------|-------------|--------|
| `.tnm-table` | TNM staging table | view_tnm.html, edit_tnm.html, style.css |
| `.tnm-row` | TNM table row | view_tnm.html, style.css |
| `.tnm-badge` | TNM category badge (T, N, M) | view_tnm.html, style.css |
| `.tnm-criteria` | TNM criteria cell | view_tnm.html |
| `.tnm-content` | TNM content area (highlightable) | view_tnm.html, style.css |
| `.tnm-html-content` | TNM HTML content (TinyMCE output) | view_tnm.html, edit_tnm.html, style.css |
| `.tnm-label` | Inline bold label in TNM | view_tnm.html |
| `.tnm-btn` | TNM block button | style.css |
| `.tnm-btn-primary` | TNM primary button | style.css |
| `.tnm-btn-secondary` | TNM secondary button | style.css |
| `.tnm-staging-button-wrapper` | TNM staging button wrapper | style.css |
| `.tnm-staging-btn` | TNM staging link/button | style.css |
| `.tnm-btn-icon` | TNM button icon | style.css |
| `.tnm-btn-text` | TNM button text | style.css |
| `.tnm-btn-arrow` | TNM button arrow | style.css |
| `.tnm-intelligence-content` | TNM intelligence content | style.css |
| `.memory-aid-content` | Memory aid content | view_tnm.html |
| `.references-list` | References list | view_tnm.html |
| `.reference-item` | Reference list item | view_tnm.html |
| `.reference-number` | Reference number badge | view_tnm.html |
| `.reference-content` | Reference content | view_tnm.html |
| `.reference-title` | Reference title | view_tnm.html |
| `.reference-meta` | Reference metadata | view_tnm.html |

---

## 7. Duplicate Modal

| Class | Description | Source |
|-------|-------------|--------|
| `.duplicate-modal-dialog` | Duplicate modal dialog | style.css |
| `.duplicate-modal-content` | Duplicate modal content | style.css |
| `.duplicate-modal-header` | Duplicate modal header | style.css |
| `.duplicate-modal-header-danger` | Danger variant header | style.css |
| `.duplicate-modal-header-warning` | Warning variant header | style.css |
| `.duplicate-modal-title` | Duplicate modal title | style.css |
| `.duplicate-modal-body` | Duplicate modal body | style.css |
| `.duplicate-alert` | Alert in duplicate modal | style.css |
| `.duplicate-comparison-row` | Comparison row | style.css |
| `.duplicate-case-card` | Case card in comparison | style.css |
| `.duplicate-top-card` | Top card in comparison | style.css |
| `.duplicate-case-existing` | Existing case card | style.css |
| `.duplicate-case-new` | New case card | style.css |
| `.duplicate-case-header` | Case card header | style.css |
| `.duplicate-case-header-existing` | Existing case header | style.css |
| `.duplicate-case-header-new` | New case header | style.css |
| `.duplicate-case-title` | Case title | style.css |
| `.duplicate-case-body` | Case body | style.css |
| `.duplicate-case-field` | Case field | style.css |
| `.duplicate-case-label` | Case field label | style.css |
| `.duplicate-case-value` | Case field value | style.css |
| `.duplicate-case-id` | Case ID | style.css |
| `.duplicate-case-diagnosis` | Case diagnosis | style.css |
| `.duplicate-case-diagnosis-new` | New case diagnosis | style.css |
| `.duplicate-badge` | Badge in duplicate modal | style.css |
| `.duplicate-badge-success` | Success badge | style.css |
| `.duplicate-badge-secondary` | Secondary badge | style.css |
| `.duplicate-action-btn` | Action button | style.css |
| `.duplicate-btn-reject` | Reject button | style.css |
| `.duplicate-btn-reject-new` | Reject new button | style.css |
| `.duplicate-btn-save` | Save button | style.css |
| `.duplicate-btn-cancel` | Cancel button | style.css |
| `.duplicate-btn-override` | Override button | style.css |
| `.duplicate-rename-section` | Rename section | style.css |
| `.duplicate-section-title` | Rename section title | style.css |
| `.duplicate-section-description` | Rename section description | style.css |
| `.duplicate-rename-input` | Rename input | style.css |
| `.duplicate-modal-footer` | Modal footer | style.css |

---

## 8. AI-Generated Content

| Class | Description | Source |
|-------|-------------|--------|
| `.ai-generated-wrapper` | AI-generated content wrapper | style.css |
| `.ai-generated-pair` | AI-generated Q&A pair | style.css |
| `.ai-cache-info-box` | AI cache info box | style.css |
| `.info-label` | Info box label | style.css |
| `.info-value` | Info box value | style.css |

---

## 9. User Highlights & Notes

| Class | Description | Source |
|-------|-------------|--------|
| `.user-highlight` | User highlight (yellow) | style.css, view_tnm.html |
| `.highlight-green` | Green highlight variant | style.css |
| `.highlight-pink` | Pink highlight variant | style.css |
| `.highlight-blue` | Blue highlight variant | style.css |
| `.note-marker` | Note marker (superscript) | style.css |
| `.selection-popup` | Popup for text selection actions | style.css |
| `.image-desc-meta` | Image description metadata | style.css |
| `.ref-cite` | Reference citation superscript | style.css |
| `.reference-block` | Reference block styling | style.css |
| `.highlight-tip` | Highlight tip tooltip | view_case.html |

---

## 10. DICOM Viewer

| Class | Description | Source |
|-------|-------------|--------|
| `.case-dicom-viewer-viewport` | DICOM viewport | viewer.css |
| `.case-dicom-viewer-plan-tabs` | Plan/plane tabs | viewer.css |
| `.image-stack-fullscreen-overlay-visible` | Fullscreen overlay visible state | viewer.css |
| `.image-stack-fs-plan-label` | Fullscreen plan label | viewer.css |

**Note:** DICOM viewer also uses IDs: `#imageStackViewerWrapper`, `#imageStackViewport`, `#imageStackFullscreenPlanOverlay`, `#imageStackFullscreenOverlay`, `#imageStackFullscreenSliceInfo`, `#imageStackExitFullscreenBtn`, etc.

---

## 11. Miscellaneous Utilities

| Class | Description | Source |
|-------|-------------|--------|
| `.filter-row` | Filter button row | style.css |
| `.filter-item` | Filter item | style.css |
| `.filter-button-item` | Filter button item | style.css |
| `.filter-card` | Filter card (mobile) | style.css |
| `.filter-card-mobile` | Mobile filter card | style.css |
| `.filter-card-body` | Filter card body | style.css |
| `.filter-toggle` | Filter toggle | style.css |
| `.filter-count` | Filter count | style.css |
| `.filter-chips` | Filter chips container | style.css |
| `.filter-chip` | Filter chip | style.css |
| `.card-sm` | Small card | style.css |
| `.form-label-sm` | Small form label | style.css |
| `.form-control-sm` | Small form control | style.css |
| `.btn-warning-outline` | Warning outline button | style.css |
| `.btn-success-outline` | Success outline button | style.css |
| `.btn.loading` | Loading state for buttons | style.css |
| `.start-exam-page` | Start exam page context | style.css |
| `.session-toast` | Session toast notification | style.css |
| `.loading-spinner` | Loading spinner | style.css |
| `.shake` | Shake animation (validation) | style.css |

---

## Custom IDs (Key Elements)

| ID | Description | Source |
|----|-------------|--------|
| `#descriptionModal` | Image description modal | style.css |
| `#imageDescriptionDisplay` | Image description display | style.css |
| `#highlightCursor` | Highlight cursor element | style.css |
| `#imageStackViewerWrapper` | DICOM viewer wrapper | viewer.css |
| `#imageStackViewport` | DICOM viewport | viewer.css |
| `#imageStackFullscreenPlanOverlay` | Fullscreen plan overlay | viewer.css |
| `#imageStackFullscreenOverlay` | Fullscreen bottom overlay | viewer.css |
| `#caseEditForm` | Case edit form | style.css |
| `#toast-container` | Toast notifications container | style.css |
| `#pwa-install-button` | PWA install button | style.css |
| `#pwa-install-banner` | PWA install banner | style.css |

---

## CSS Custom Properties (Variables)

Defined in `:root` in style.css:

| Variable | Description |
|----------|-------------|
| `--peachy-orange` | Primary brand accent (#e96304) |
| `--brand-primary` | Primary brand color |
| `--brand-secondary` | Secondary accent |
| `--brand-success` | Success/calm green |
| `--brand-neutral` | Teal-blue neutral |
| `--brand-text-primary` | Primary text |
| `--brand-text-secondary` | Secondary text |
| `--brand-bg-white` | White background |
| `--brand-bg-offwhite` | Off-white background |
| `--soft-green`, `--deep-green` | Green palette |
| `--soft-charcoal`, `--soft-gray` | Gray palette |
| `--nav-dark`, `--nav-darker` | Navbar gradient |
| `--hero-title-color`, `--hero-subtitle-color` | Hero colors |

---

## File Locations Summary

| File | Purpose |
|------|---------|
| `static/style.css` | Main app styles (~4800+ lines) |
| `case_dicom_viewer/static/case_dicom_viewer/viewer.css` | DICOM viewer styles |
| `ajcc_tnm/templates/view_tnm.html` | Inline TNM-specific styles |
| `ajcc_tnm/templates/edit_tnm.html` | Inline TNM edit styles |
| `templates/view_case.html` | Inline case view styles |
| `ajcc_tnm/templates/ajcc_tnm_viewer.html` | Inline AJCC viewer styles |

---

*Last updated: February 2025*
