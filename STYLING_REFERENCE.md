# FRCR Revision Companion - Styling Reference Guide

This document provides a comprehensive reference for all custom brand classes, CSS variables, and their usage locations. Use this document to quickly find and update styling across the application.

---

## Table of Contents
1. [CSS Variables](#css-variables)
2. [Button Classes](#button-classes)
3. [Text Color Classes](#text-color-classes)
4. [Background Classes](#background-classes)
5. [Card Classes](#card-classes)
6. [Typography Classes](#typography-classes)
7. [Component-Specific Classes](#component-specific-classes)
8. [Quick Update Guide](#quick-update-guide)
9. [View Case Page Styling](#9-view-case-page-styling)
9. [View Case Page Styling](#9-view-case-page-styling)

---

## CSS Variables

**Location**: `static/style.css` (Lines 283-329, 330-429)

| Variable Name | Value | Usage | Update Location |
|--------------|-------|-------|-----------------|
| `--brand-primary` | `#e96304` | Primary brand accent (Peachy Orange) | `static/style.css:286` |
| `--brand-secondary` | `#ffc107` | Secondary accent (Bootstrap Warning Yellow) | `static/style.css:290` |
| `--brand-success` | `#a8d5ba` | Success/Calm (Soft Green) | `static/style.css:295` |
| `--brand-neutral` | `#5E899E` | Neutral actions (Teal-blue - matches navbar/footer) | `static/style.css:336` |
| `--brand-text-primary` | `#2c3e50` | Primary text (Dark Slate) | `static/style.css:319` |
| `--brand-text-secondary` | `#5a6270` | Secondary text (Muted Slate) | `static/style.css:303` |
| `--brand-bg-white` | `#ffffff` | White card backgrounds | `static/style.css:319` |
| `--brand-bg-offwhite` | `#fdfdfb` | Off-white body background | `static/style.css:312` |
| `--peachy-orange` | `#e96304` | Legacy primary color | `static/style.css:286` |
| `--primary-orange` | `#ffc107` | Bootstrap warning color | `static/style.css:290` |
| `--soft-green` | `#a8d5ba` | Soft green (calm) | `static/style.css:295` |
| `--deep-green` | `#8bc9a3` | Deep green variant | `static/style.css:296` |
| `--soft-charcoal` | `#5a6270` | Muted slate text | `static/style.css:303` |
| `--soft-gray` | `#8b94a3` | Soft gray-blue | `static/style.css:304` |

**To Update**: Edit values in `static/style.css` within the `:root` selector (lines 283-329).

---

## Button Classes

**Location**: `static/style.css` (Lines 330-429)

### Primary Button
| Class | Color | Text Color | Hover Color | Usage Locations |
|-------|-------|------------|-------------|-----------------|
| `.btn-brand-primary` | `#e96304` | `#ffffff` | `#c75002` | `templates/student_dashboard.html:23`<br>`templates/dashboard.html:33`<br>`templates/cases_list.html:47,229` |

**CSS Definition**: `static/style.css:330-340`

### Secondary Button
| Class | Color | Text Color | Hover Color | Usage Locations |
|-------|-------|------------|-------------|-----------------|
| `.btn-brand-secondary` | `#ffc107` | `#000000` | `#ffb302` | `templates/dashboard.html:65`<br>`templates/cases_list.html:50`<br>`templates/student_cases_list.html:113` |

**CSS Definition**: `static/style.css:342-352`

### Success Button
| Class | Color | Text Color | Hover Color | Usage Locations |
|-------|-------|------------|-------------|-----------------|
| `.btn-brand-success` | `#a8d5ba` | `#2c3e50` | `#8bc9a3` | `templates/student_dashboard.html:46`<br>`templates/dashboard.html:49,81` |

**CSS Definition**: `static/style.css:354-364`

### Neutral Button
| Class | Color | Text Color | Hover Color | Usage Locations |
|-------|-------|------------|-------------|-----------------|
| `.btn-brand-neutral` | `#5E899E` | `#ffffff` | `#4A6F7F` | `templates/student_dashboard.html:70` |

**CSS Definition**: `static/style.css:366-376`

**To Update**: Edit button classes in `static/style.css` (lines 330-376).

---

## Text Color Classes

**Location**: `static/style.css` (Lines 378-395)

| Class | Color Value | Usage | Update Location |
|-------|-------------|-------|----------------|
| `.text-brand-primary` | `#e96304` | Orange text | `static/style.css:378` |
| `.text-brand-secondary` | `#ffc107` | Yellow text | `static/style.css:382` |
| `.text-brand-success` | `#a8d5ba` | Green text | `static/style.css:386` |
| `.text-brand-white` | `#ffffff` | White text | `static/style.css:390` |

**To Update**: Edit text color classes in `static/style.css` (lines 378-395).

---

## Background Classes

**Location**: `static/style.css` (Lines 397-415)

| Class | Background Color | Text Color | Usage | Update Location |
|-------|------------------|------------|-------|-----------------|
| `.bg-brand-primary` | `#e96304` | `#ffffff` | Primary backgrounds | `static/style.css:397` |
| `.bg-brand-secondary` | `#ffc107` | `#000000` | Secondary backgrounds | `static/style.css:402` |
| `.bg-brand-success` | `#a8d5ba` | `#2c3e50` | Success backgrounds | `static/style.css:407` |

**To Update**: Edit background classes in `static/style.css` (lines 397-415).

---

## Card Classes

**Location**: `static/style.css` (Lines 417-450)

| Class | Purpose | Properties | Usage | Update Location |
|-------|---------|------------|-------|-----------------|
| `.card-brand` | Standard card | White bg, border, shadow, hover effect | Can be applied to any card | `static/style.css:417` |
| `.card-brand-header` | Card header | Padding, border-bottom, gradient bg | Card headers | `static/style.css:430` |
| `.card-brand-title` | Card title | Font size 1.25rem, weight 600 | `templates/student_dashboard.html:15,37,61` | `static/style.css:436` |
| `.card-brand-body` | Card body | Padding 1.5rem | Card bodies | `static/style.css:442` |

**To Update**: Edit card classes in `static/style.css` (lines 417-450).

---

## Typography Classes

**Location**: `static/style.css` (Lines 452-485)

| Class | Font Size | Font Weight | Color | Line Height | Usage | Update Location |
|-------|-----------|-------------|-------|-------------|-------|-----------------|
| `.text-page-title` | `2rem` (32px) | `700` | `#2c3e50` | `1.2` | Page titles | `static/style.css:452` |
| `.text-section-title` | `1.5rem` (24px) | `600` | `#2c3e50` | `1.3` | Section titles | `static/style.css:458` |
| `.text-card-title` | `1.25rem` (20px) | `600` | `#2c3e50` | `1.4` | `templates/student_dashboard.html:15,37,61` | `static/style.css:464` |
| `.text-body-standard` | `1rem` (16px) | `400` | `#2c3e50` | `1.6` | Body text | `static/style.css:470` |
| `.text-small-standard` | `0.875rem` (14px) | `400` | `#5a6270` | `1.5` | Small text | `static/style.css:476` |

**To Update**: Edit typography classes in `static/style.css` (lines 452-485).

---

## Component-Specific Classes

### Navigation

**Location**: `static/style.css` (Lines 542-444)

| Element | Class/Selector | Color | Update Location |
|---------|----------------|-------|-----------------|
| Navbar Background | `.navbar` | `linear-gradient(360deg, #5E899E 0%, #4A6F7F 100%)` | `static/style.css:542-546` |
| Navbar Links | `.navbar-nav .nav-link` | `#ffffff` | `static/style.css:384-394` |
| Breadcrumb Links (Desktop) | `.breadcrumb-custom .breadcrumb-item a` | `#e96304` | `static/style.css:602-607` |
| Breadcrumb Active (Desktop) | `.breadcrumb-custom .breadcrumb-item.active` | `#2c3e50` | `static/style.css:614-617` |
| Breadcrumb Links (Mobile) | `.mobile-breadcrumb-nav .breadcrumb-item a` | `#ffffff` | `static/style.css:225-233` |
| Breadcrumb Active (Mobile) | `.mobile-breadcrumb-nav .breadcrumb-item.active` | `#ffc107` | `static/style.css:235-238` |
| Admin Breadcrumb Links | `.admin-dashboard-container .breadcrumb-item a` | `#e96304` | `static/style.css:2801-2811` |
| Admin Breadcrumb Active | `.admin-dashboard-container .breadcrumb-item.active` | `#2c3e50` | `static/style.css:2813-2816` |

### Footer

**Location**: `static/style.css` (Lines 557-597)

| Element | Class/Selector | Color | Update Location |
|---------|----------------|-------|-----------------|
| Footer Background | `.footer` | `linear-gradient(180deg, #5E899E 0%, #4A6F7F 100%)` | `static/style.css:735-739` |
| Footer Title | `.footer-title` | `#e96304` | `static/style.css:741-746` |
| Footer Text | `.footer-text` | `#ffffff` | `static/style.css:748-752` |
| Footer Links | `.footer-link` | `#ffffff` | `static/style.css:754-759` |
| Footer Link Hover | `.footer-link:hover` | `#f7fbff` | `static/style.css:761-764` |
| Footer Copyright | `.footer-copyright` | `#ffffff` | `static/style.css:771-773` |
| Footer Spacing | `.footer-content` | Compact padding (`0.75rem 0`) | `static/style.css:789-796` |

### Duplicate Case Modal (Edit Case)

**Location**: `static/edit-case-modal.js` + `static/style.css`

| Element | Class/Selector | Color/Style | Update Location |
|---------|----------------|-------------|-----------------|
| Modal Width | `.duplicate-modal-dialog` | `85vw` desktop, `95%` mobile | `static/style.css:3498-3510` |
| Header (Exact) | `.duplicate-modal-header-danger` | `linear-gradient(135deg, #e96304 0%, #c75002 100%)` | `static/style.css:3523-3526` |
| Header (Similar) | `.duplicate-modal-header-warning` | `linear-gradient(135deg, #5E899E 0%, #4A6F7F 100%)` | `static/style.css:3528-3531` |
| Top Row Cards | `.duplicate-case-existing`, `.duplicate-case-new` | Teal + Orange accents | `static/style.css:3588-3594` |
| Bottom Row Cards | Match Summary + Rename | Two-column layout | `static/edit-case-modal.js:1326-1369` |

### Clear Filter Button

**Location**: `templates/cases_list.html` and `templates/student_cases_list.html` (Inline styles)

| Element | Class/Selector | Color | Icon | Update Location |
|---------|----------------|-------|------|-----------------|
| Clear Filter Button | `.filter-clear-btn` | `linear-gradient(135deg, #ff9800 0%, #f57c00 100%)` | `fa-filter-slash` | `templates/cases_list.html:443-463`<br>`templates/student_cases_list.html:370-390` |
| Clear Filter Hover | `.filter-clear-btn:hover` | `linear-gradient(135deg, #f57c00 0%, #e65100 100%)` | - | Same as above |

**Usage Locations**:
- `templates/cases_list.html:125-126`
- `templates/student_cases_list.html:109-110`

### Hero Banner

**Location**: `static/style.css` (Lines 483-539)

| Element | Class/Selector | Color | Update Location |
|---------|----------------|-------|-----------------|
| Hero Background | `.hero-overlay` | `#fdfdfb` | `static/style.css:494-502` |
| Hero Title | `.hero-title` | `#1a1a1a` | `static/style.css:524-531` |
| Hero Subtitle | `.hero-subtitle` | `#e96304` | `static/style.css:533-539` |

---

### Module List Page

**Location**: `templates/modules_view.html`

| Element | Class/Selector | Color | Usage |
|---------|----------------|-------|-------|
| Module Icon Color | `.module-icon` (inline `color`) | Module-specific (matches case list) | `templates/modules_view.html` |
| Module Icon Background | `.module-icon` (inline `background`) | Soft tint per module | `templates/modules_view.html` |
| Module Card | `.module-card` | White card with soft shadow | `templates/modules_view.html:92-104` |
| Module Count Badge | `.module-count-badge` | `#f8f9fa` bg, muted text | `templates/modules_view.html:121-126` |

**Module Icon Color Map** (same as case list):
- Cardiothoracic/Vascular: `#7bb3d0`
- Musculoskeletal/Trauma: `#ff9800`
- Gastrointestinal: `#7bb88a`
- Genitourinary/Breast: `#ce93d8`
- Paediatric: `#fff59d`
- CNS/Head & Neck: `#9fa8da`
- Default: `#90a4ae`

---

### Edit Case Page

**Location**: `templates/edit_case.html`

| Element | Class/Selector | Color | Usage |
|---------|----------------|-------|-------|
| Form Background | `#caseEditForm` (inline JS) | `#f1f6f9` | Consistent neutral background |
| Card Body Background | `.card-body` (inline JS) | `#ffffff` | Ensures all sections look consistent |

---

## Quick Update Guide

### To Change Primary Brand Color

1. **Update CSS Variable**: `static/style.css:286`
   ```css
   --brand-primary: #e96304;  /* Change this value */
   ```

2. **Update Button Class**: `static/style.css:330-340`
   ```css
   .btn-brand-primary {
       background-color: var(--brand-primary);  /* Uses variable */
   }
   ```

3. **Files Using Primary Color**:
   - `templates/student_dashboard.html:23`
   - `templates/dashboard.html:33`
   - `templates/cases_list.html:47,229`

### To Change Secondary Brand Color

1. **Update CSS Variable**: `static/style.css:290`
   ```css
   --brand-secondary: #ffc107;  /* Change this value */
   ```

2. **Update Button Class**: `static/style.css:342-352`
   ```css
   .btn-brand-secondary {
       background-color: var(--brand-secondary);  /* Uses variable */
   }
   ```

3. **Files Using Secondary Color**:
   - `templates/dashboard.html:65`
   - `templates/cases_list.html:50`
   - `templates/student_cases_list.html:113`

### To Change Success/Green Color

1. **Update CSS Variable**: `static/style.css:295`
   ```css
   --brand-success: #a8d5ba;  /* Change this value */
   ```

2. **Update Button Class**: `static/style.css:354-364`
   ```css
   .btn-brand-success {
       background-color: var(--brand-success);  /* Uses variable */
   }
   ```

3. **Files Using Success Color**:
   - `templates/student_dashboard.html:46`
   - `templates/dashboard.html:49,81`

### To Change Text Colors

1. **Update CSS Variables**: `static/style.css:319`
   ```css
   --brand-text-primary: #2c3e50;  /* Primary text */
   --brand-text-secondary: #5a6270;  /* Secondary text */
   ```

2. **Typography classes automatically use these variables**

### To Change Footer Colors

1. **Footer Background**: `static/style.css:557-562`
   ```css
   .footer {
       background: linear-gradient(180deg, #5E899E 0%, #4A6F7F 100%) !important;  /* Change this */
   }
   ```

2. **Footer Text**: `static/style.css:571-575`
   ```css
   .footer-text {
       color: #ffffff;  /* Change this */
   }
   ```

3. **Footer Links**: `static/style.css:577-587`
   ```css
   .footer-link {
       color: #ffc107;  /* Change this */
   }
   ```

4. **Footer Title**: `static/style.css:564-569`
   ```css
   .footer-title {
       color: #ffc107;  /* Change this */
   }
   ```

### To Change Navigation Colors

1. **Navbar Background**: `static/style.css:542-546`
   ```css
   .navbar {
       background: linear-gradient(360deg, #5E899E 0%, #4A6F7F 100%) !important;  /* Change this */
   }
   ```

### To Change Clear Filter Button

1. **Button Color**: `templates/cases_list.html:443-456` and `templates/student_cases_list.html:370-383`
   ```css
   .filter-clear-btn {
       background: linear-gradient(135deg, #ff9800 0%, #f57c00 100%);  /* Change this */
   }
   ```

2. **Hover State**: `templates/cases_list.html:458-463` and `templates/student_cases_list.html:385-390`
   ```css
   .filter-clear-btn:hover {
       background: linear-gradient(135deg, #f57c00 0%, #e65100 100%);  /* Change this */
   }
   ```

3. **Icon**: `templates/cases_list.html:126` and `templates/student_cases_list.html:110`
   ```html
   <i class="fas fa-filter-slash me-2"></i>  <!-- Change icon class here -->
   ```

### To Change Breadcrumb Colors

1. **Desktop Breadcrumbs**: `static/style.css:425-440`
   ```css
   .breadcrumb-custom .breadcrumb-item a {
       color: #ffc107;  /* Link color */
   }
   .breadcrumb-custom .breadcrumb-item.active {
       color: #2c3e50;  /* Active state */
   }
   ```

2. **Mobile Breadcrumbs**: `static/style.css:225-238`
   ```css
   .mobile-breadcrumb-nav .breadcrumb-item a {
       color: #ffffff;  /* Link color */
   }
   .mobile-breadcrumb-nav .breadcrumb-item.active {
       color: #ffc107;  /* Active state */
   }
   ```

---

## File Locations Summary

### CSS Files
- **Main Stylesheet**: `static/style.css`
  - CSS Variables: Lines 283-329
  - Brand Utility Classes: Lines 330-485
  - Component Styles: Throughout file

### Template Files Using Brand Classes

| Template File | Lines Using Brand Classes | Classes Used |
|---------------|---------------------------|--------------|
| `templates/student_dashboard.html` | 15, 23, 37, 46, 61, 70 | `text-card-title`, `btn-brand-primary`, `btn-brand-success`, `btn-brand-neutral` |
| `templates/dashboard.html` | 33, 49, 65, 81 | `btn-brand-primary`, `btn-brand-success`, `btn-brand-secondary` |
| `templates/cases_list.html` | 47, 50, 229 | `btn-brand-primary`, `btn-brand-secondary` |
| `templates/student_cases_list.html` | 113 | `btn-brand-secondary` |

---

## Color Palette Reference

### Primary Colors
- **Brand Primary (Orange)**: `#e96304` - Main action color
- **Brand Secondary (Yellow)**: `#ffc107` - Secondary actions, highlights
- **Brand Success (Green)**: `#a8d5ba` - Success states, calm actions
- **Brand Neutral (Teal-blue)**: `#5E899E` - Neutral actions (matches navbar/footer)

### Text Colors
- **Primary Text**: `#2c3e50` - Main content text
- **Secondary Text**: `#5a6270` - Supporting text
- **White Text**: `#ffffff` - Text on dark backgrounds

### Background Colors
- **White**: `#ffffff` - Card backgrounds
- **Off-White**: `#fdfdfb` - Body background
- **Navbar/Footer**: `linear-gradient(180deg, #5E899E 0%, #4A6F7F 100%)` (matches btn-neutral teal-blue)

---

## Best Practices

1. **Always use CSS variables** when possible for easy global updates
2. **Use brand classes** instead of inline styles for consistency
3. **Check this document** before creating new color classes
4. **Update this document** when adding new classes or changing existing ones
5. **Test across pages** after making color changes

---

## 9. View Case Page Styling

### Case Info Bar (Header)

**Location**: `templates/view_case.html` (Lines 107-124) and `static/style.css` (Lines 1707-1747)

| Element | Implemented Style | CSS Class | Update Location |
|---------|-------------------|-----------|-----------------|
| Case Header Background | `linear-gradient(135deg, #5E899E 0%, #4A6F7F 100%)` | `.case-card-header` | `static/style.css:1708` |
| Case Number (h3) | `font-size: 2rem`, `font-weight: 800`, `text-shadow` | `.case-card-header h3` | `static/style.css:1727-1735` |
| Module Text (p) | `color: #ffffff`, `font-size: 1rem`, `font-weight: 500`, `text-shadow` | `.case-card-header p` | `static/style.css:1737-1743` |
| Image Badge | White background with teal-blue text (`#5E899E`) | Inline style | `templates/view_case.html:119` |
| Card Body Background | `#ffffff` (solid white) | Inline style | `templates/view_case.html:125` |

### Reading Area Sections

**Location**: `templates/view_case.html` (Lines 130-200)

| Section | Background | Border | Icon Color | Text Color | Update Location |
|---------|------------|--------|------------|------------|-----------------|
| Diagnosis | `linear-gradient(135deg, #fff8f0 0%, #fffbf5 100%)` | `5px solid #FFD700` | `#FFC107` | `#2c3e50` | `templates/view_case.html:130` |
| Q&A | `#f8f9fa` (light gray) ✅ | None | `#5E899E` (teal-blue) ✅ | `#2c3e50` | `templates/view_case.html:143` |
| Discussion | `linear-gradient(135deg, #f0f8fc 0%, #f5fbff 100%)` | `5px solid #17a2b8` | `#17a2b8` | `#2c3e50` | `templates/view_case.html:151` |
| Notes | `linear-gradient(135deg, #FFF8E7 0%, #FFFCF3 100%)` | `5px solid #F2CC8F` | `#FFB84D` | `#2c3e50` | `templates/view_case.html:168` |

### Image Description Text (View Case + Edit Case)

**Location**: `static/style.css` (Image description selectors) and `templates/view_case.html`

| Element | Style | Update Location |
|---------|-------|-----------------|
| Description Main Text | White (`#ffffff`) | `static/style.css:1476-1483`, `static/style.css:2331-2337` |
| Credits/Courtesy/Links | Muted black (`#2c2c2c`, opacity `0.75`) | `static/style.css:1485-1491`, `static/style.css:2339-2342` |

### Q&A Cards (Full Width)

**Location**: `static/style.css`

| Element | Style | Update Location |
|---------|-------|-----------------|
| Q&A Cards | `width: 100%` (max width within container) | `static/style.css:1704-1713` |

### Breadcrumb Navigation (View Case)

**Location**: `templates/view_case.html` (Lines 81-103) and `static/style.css` (Lines 591-620)

| Element | Implemented Color | CSS Class | Update Location |
|---------|-------------------|-----------|-----------------|
| Breadcrumb Links | `#e96304` (Brand Orange) ✅ | `.breadcrumb-custom .breadcrumb-item a` | `static/style.css:602-607` |
| Breadcrumb Active | `#2c3e50` (Dark Slate) | `.breadcrumb-custom .breadcrumb-item.active` | `static/style.css:614-617` |
| Breadcrumb Icons | `#e96304` (Brand Orange) ✅ | `.breadcrumb-custom i` | `static/style.css:619-621` |
| Breadcrumb Hover | `#c75002` (Darker Orange) ✅ | `.breadcrumb-custom .breadcrumb-item a:hover` | `static/style.css:609-612` |

**Note**: See `VIEW_CASE_UI_DESIGN_REVIEW.md` for detailed design recommendations and rationale.

---

## Notes

- All brand classes are defined in `static/style.css` starting at line 330
- CSS variables are defined in `:root` selector at line 283
- Bootstrap classes are NOT modified - all custom classes are separate
- All changes are backwards compatible
- Mobile-specific styles are in media queries throughout the CSS file
- View Case page design recommendations are documented in `VIEW_CASE_UI_DESIGN_REVIEW.md`

---

**Last Updated**: After image description, footer compacting, and Q&A width updates
**Maintained By**: Development Team
**Version**: 1.1
