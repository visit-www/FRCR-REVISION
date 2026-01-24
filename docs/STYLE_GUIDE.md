# FRCR Revision - Quick Style Guide

## Brand Colors (Copy-Paste Ready)

### Primary Palette
| Name | Hex | Usage |
|------|-----|-------|
| **Peachy Orange** | `#e96304` | Primary buttons, accents, CTAs |
| **Soft Green** | `#a8d5ba` | Success states, secondary buttons |
| **Teal Blue** | `#5E899E` | Neutral actions, headers, nav |
| **Bootstrap Yellow** | `#ffc107` | Warnings, highlights |

### Text Colors
| Name | Hex | Usage |
|------|-----|-------|
| **Primary Text** | `#2c3e50` | Headings, main content |
| **Secondary Text** | `#5a6270` | Descriptions, muted text |
| **Light Text** | `#8b94a3` | Placeholders, hints |

### Backgrounds
| Name | Hex | Usage |
|------|-----|-------|
| **White** | `#ffffff` | Cards, modals |
| **Off-white** | `#fdfdfb` | Body background |
| **Hover** | `#f5f5f3` | Hover states |
| **Border** | `#c5cad1` | Borders, dividers |

---

## CSS Variables (Use These)

```css
/* Primary Actions */
--brand-primary: #e96304;      /* Peachy Orange */
--brand-secondary: #ffc107;    /* Yellow */
--brand-success: #a8d5ba;      /* Soft Green */
--brand-neutral: #5E899E;      /* Teal Blue */

/* Text */
--brand-text-primary: #2c3e50;
--brand-text-secondary: #5a6270;

/* Backgrounds */
--brand-bg-white: #ffffff;
--brand-bg-offwhite: #fdfdfb;
```

---

## Button Styles

### Primary Button (Orange)
```html
<button class="btn" style="background: #e96304; color: white; border: none;">
    Action
</button>
```

### Success Button (Green)
```html
<button class="btn" style="background: #a8d5ba; color: #2c3e50; border: none;">
    Confirm
</button>
```

### Neutral Button (Teal)
```html
<button class="btn" style="background: #5E899E; color: white; border: none;">
    Info
</button>
```

### Outline Button
```html
<button class="btn" style="background: transparent; color: #5a6270; border: 1px solid #c5cad1;">
    Cancel
</button>
```

---

## Card Styling

```html
<div style="background: #ffffff; border: 1px solid #c5cad1; border-radius: 8px; padding: 15px;">
    <!-- Card content -->
</div>
```

### Card with Accent Border
```html
<div style="background: #fdfdfb; border-left: 3px solid #5E899E; padding: 12px; border-radius: 4px;">
    <!-- Highlighted content -->
</div>
```

---

## Modal Header

```html
<div style="background: linear-gradient(135deg, #5E899E 0%, #4a7285 100%); padding: 15px 20px; color: white;">
    <h5>Modal Title</h5>
</div>
```

---

## Typography

| Element | Size | Weight | Color |
|---------|------|--------|-------|
| H1 | 2rem | 600 | #2c3e50 |
| H2 | 1.5rem | 600 | #2c3e50 |
| H3 | 1.25rem | 600 | #2c3e50 |
| Body | 14px | 400 | #2c3e50 |
| Small | 0.85em | 400 | #5a6270 |
| Muted | 0.85em | 400 | #8b94a3 |

---

## Status Badges

```html
<!-- Success -->
<span style="background: #a8d5ba; color: #2c3e50; padding: 2px 8px; border-radius: 4px; font-size: 0.75em;">
    Success
</span>

<!-- Warning -->
<span style="background: #ffc107; color: #2c3e50; padding: 2px 8px; border-radius: 4px; font-size: 0.75em;">
    Warning
</span>

<!-- Primary -->
<span style="background: #e96304; color: white; padding: 2px 8px; border-radius: 4px; font-size: 0.75em;">
    Active
</span>

<!-- Neutral -->
<span style="background: #5E899E; color: white; padding: 2px 8px; border-radius: 4px; font-size: 0.75em;">
    Info
</span>
```

---

## Bootstrap Classes to Use

```
.btn-warning     → Yellow buttons (Bootstrap)
.btn-secondary   → Gray buttons
.text-muted      → Muted text
.bg-light        → Light backgrounds
.border          → Standard borders
.rounded         → Rounded corners (4px)
.shadow-sm       → Subtle shadows
```

---

## Icons (Font Awesome)

Common icons used in the app:
- `fa-search` - Search
- `fa-plus` - Add
- `fa-edit` - Edit
- `fa-trash` - Delete
- `fa-external-link-alt` - External link
- `fa-check` - Success/Confirm
- `fa-times` - Close/Cancel
- `fa-info-circle` - Info
- `fa-exclamation-circle` - Warning
- `fa-book-medical` - Reference/Medical
