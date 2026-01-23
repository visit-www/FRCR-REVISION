# TNM Viewer Design Guide

## Overview

The TNM viewer templates follow the design patterns established in the main app's case viewer (`view_case.html`).

## Layout Structure

```
┌─────────────────────────────────────────────────────────────┐
│                        Header/Navbar                         │
├─────────────────────────────────────────────────────────────┤
│                     Breadcrumb Navigation                    │
├─────────────┬───────────────────────────────────────────────┤
│             │                                               │
│   Sidebar   │              Main Content Area                │
│   (20%)     │                 (80%)                         │
│             │                                               │
│ ┌─────────┐ │  ┌─────────────────────────────────────────┐ │
│ │Year Sel │ │  │  Section Title                          │ │
│ └─────────┘ │  ├─────────────────────────────────────────┤ │
│             │  │                                         │ │
│ ┌─────────┐ │  │  Content Area                           │ │
│ │Section  │ │  │  - Tables                               │ │
│ │   1     │ │  │  - Text                                 │ │
│ ├─────────┤ │  │  - Images (with lightbox)               │ │
│ │Section  │ │  │  - Notes                                │ │
│ │   2     │ │  │                                         │ │
│ ├─────────┤ │  │                                         │ │
│ │  ...    │ │  │                                         │ │
│ ├─────────┤ │  │                                         │ │
│ │Section  │ │  │                                         │ │
│ │  10     │ │  │                                         │ │
│ └─────────┘ │  └─────────────────────────────────────────┘ │
│             │                                               │
│ ┌─────────┐ │  ┌─────────────────────────────────────────┐ │
│ │Stage    │ │  │  Footer / Related Links                 │ │
│ │Calcul.  │ │  └─────────────────────────────────────────┘ │
│ └─────────┘ │                                               │
└─────────────┴───────────────────────────────────────────────┘
```

## Component Specifications

### Breadcrumb Navigation

```html
<nav aria-label="breadcrumb">
    <ol class="breadcrumb">
        <li class="breadcrumb-item"><a href="/tnm">TNM Staging</a></li>
        <li class="breadcrumb-item"><a href="/tnm/thorax">Thorax</a></li>
        <li class="breadcrumb-item active">Lung</li>
    </ol>
</nav>
```

### Sidebar Navigation

- Fixed position on desktop
- Collapsible on mobile
- Highlight active section
- Include year selector dropdown
- Optional stage calculator widget

### Year Selector

```html
<div class="year-selector">
    <label>Diagnosis Year:</label>
    <select class="form-select" onchange="changeYear(this.value)">
        <option value="2026" selected>2026</option>
        <option value="2025">2025</option>
        <option value="2024">2024</option>
    </select>
</div>
```

### Section Navigation

```html
<ul class="section-nav">
    <li class="nav-item active">
        <a href="#section-1">
            <span class="section-number">1</span>
            Staging Quick Reference
        </a>
    </li>
    <!-- ... sections 2-10 -->
</ul>
```

### TNM Tables

Tables should match AJCC styling:

```css
.tnm-table {
    width: 100%;
    border-collapse: collapse;
}

.tnm-table th {
    background-color: #f8f9fa;
    padding: 12px;
    text-align: left;
    border-bottom: 2px solid #dee2e6;
}

.tnm-table td {
    padding: 10px 12px;
    border-bottom: 1px solid #dee2e6;
}

.tnm-table .category-cell {
    font-weight: 600;
    width: 80px;
}

.tnm-table .criteria-cell {
    /* Full width for criteria */
}
```

### Stage Group Table

```css
.stage-table {
    width: 100%;
}

.stage-table th {
    text-align: center;
    background-color: #e9ecef;
}

.stage-table .stage-column {
    background-color: #fff3cd;
    font-weight: 600;
}
```

### Image Gallery

Images should use lightbox for full-size viewing:

```html
<div class="figure-container">
    <figure>
        <a href="full-size.jpg" data-lightbox="figures">
            <img src="thumbnail.jpg" alt="Figure 1" class="img-fluid">
        </a>
        <figcaption>Figure 1: Tumor size measurement</figcaption>
    </figure>
</div>
```

### Stage Calculator Widget

```html
<div class="stage-calculator card">
    <div class="card-header">
        <h5>Stage Calculator</h5>
    </div>
    <div class="card-body">
        <div class="form-group">
            <label>T Stage:</label>
            <select id="t-stage" class="form-select">
                <option value="">Select...</option>
                <option value="T1">T1</option>
                <option value="T2">T2</option>
            </select>
        </div>
        <div class="form-group">
            <label>N Stage:</label>
            <select id="n-stage" class="form-select">...</select>
        </div>
        <div class="form-group">
            <label>M Stage:</label>
            <select id="m-stage" class="form-select">...</select>
        </div>
        <button class="btn btn-primary" onclick="calculateStage()">
            Calculate Stage
        </button>
        <div id="stage-result" class="stage-result mt-3">
            <!-- Result displayed here -->
        </div>
    </div>
</div>
```

## Color Palette

| Element | Color | Hex |
|---------|-------|-----|
| Primary | Blue | #0d6efd |
| Headers | Light Gray | #f8f9fa |
| Borders | Gray | #dee2e6 |
| Stage Highlight | Yellow | #fff3cd |
| Links | Blue | #0d6efd |
| Active Nav | Primary Blue | #0d6efd |

## Responsive Breakpoints

| Breakpoint | Behavior |
|------------|----------|
| < 768px | Sidebar collapses to hamburger menu |
| 768px - 992px | Sidebar 25% width |
| > 992px | Sidebar 20% fixed width |

## Typography

- **Section Titles**: 1.5rem, bold
- **Subsection Titles**: 1.25rem, semi-bold
- **Body Text**: 1rem (16px)
- **Table Text**: 0.9rem
- **Category Codes**: Monospace font

## Accessibility

- Use semantic HTML (`<article>`, `<section>`, `<nav>`)
- Include ARIA labels
- Ensure sufficient color contrast
- Keyboard navigable
- Screen reader friendly tables
