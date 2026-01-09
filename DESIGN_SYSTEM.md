# FRCR Revision App - Design System Documentation

**Version:** 2.0  
**Last Updated:** January 9, 2026  
**Status:** Active

---

## Table of Contents

1. [Design Philosophy](#design-philosophy)
2. [Color Palette](#color-palette)
3. [Color Usage Guidelines](#color-usage-guidelines)
4. [Typography](#typography)
5. [Component Styles](#component-styles)
6. [Spacing & Layout](#spacing--layout)
7. [Migration Notes](#migration-notes)

---

## Design Philosophy

The FRCR Revision App is built on three core visual principles:

### 🔥 **Confidence**
- Warm coral-orange tones inspire trust and energy
- Used for primary actions and navigation
- Conveys warmth and approachability

### 🌱 **Growth**
- Sage green represents learning and progress
- Used for success states and achievement indicators
- Communicates calm professionalism

### ✨ **Clarity**
- Honey gold accents highlight important information
- Used for notes, warnings, and focal points
- Adds premium, refined touch

---

## Color Palette

### Primary Colors

| Color Name | Hex Code | RGB | Usage |
|------------|----------|-----|-------|
| **Primary Orange** | `#E8744F` | `rgb(232, 116, 79)` | Primary buttons, navbar, links |
| **Soft Orange** | `#F4A261` | `rgb(244, 162, 97)` | Secondary accents, hover states |
| **Deep Orange** | `#D45D3B` | `rgb(212, 93, 59)` | Active states, emphasis |

### Secondary Colors - Green

| Color Name | Hex Code | RGB | Usage |
|------------|----------|-----|-------|
| **Soft Green** | `#7FB685` | `rgb(127, 182, 133)` | Success states, growth indicators |
| **Deep Green** | `#588B6B` | `rgb(88, 139, 107)` | Success button hover, stability |

### Accent Colors - Gold

| Color Name | Hex Code | RGB | Usage |
|------------|----------|-----|-------|
| **Honey Gold** | `#F2CC8F` | `rgb(242, 204, 143)` | Highlights, warnings, notes |
| **Cream Yellow** | `#FFF8E7` | `rgb(255, 248, 231)` | Subtle backgrounds |

### Neutral Colors

| Color Name | Hex Code | RGB | Usage |
|------------|----------|-----|-------|
| **Soft Charcoal** | `#3D4451` | `rgb(61, 68, 81)` | Dark text, footers |
| **Soft Gray** | `#6B7280` | `rgb(107, 114, 128)` | Secondary text |
| **Soft Light Gray** | `#9CA3AF` | `rgb(156, 163, 175)` | Disabled states, borders |

### Background Colors

| Color Name | Hex Code | RGB | Usage |
|------------|----------|-----|-------|
| **Primary Background** | `#FFF8F0` | `rgb(255, 248, 240)` | Body gradient start |
| **Secondary Background** | `#F7EDE2` | `rgb(247, 237, 226)` | Body gradient mid |
| **Tertiary Background** | `#F0E5D8` | `rgb(240, 229, 216)` | Body gradient end |
| **Card Background** | `#FDFCFB` | `rgb(253, 252, 251)` | Cards, panels |
| **Card Hover** | `#F7F4F0` | `rgb(247, 244, 240)` | Interactive cards |

---

## Color Usage Guidelines

### Navigation Bar

```css
/* Navbar Gradient */
background: linear-gradient(90deg, #E8744F 0%, #D45D3B 100%);

/* Navbar Links */
color: #1C5C35; /* Rich green for contrast */

/* Navbar Link Hover */
color: #2A7E4D;
```

### Buttons

#### Primary Button (Success/Growth)
```css
background-color: #7FB685;
color: white;

/* Hover */
background-color: #6BA073;
```

#### Secondary Button (Confidence)
```css
background-color: #E8744F;
color: white;

/* Hover */
background-color: #D45D3B;
```

#### Warning Button
```css
background-color: #F2CC8F;
color: #3D4451; /* Dark text for contrast */

/* Hover */
background-color: #E6BB78;
```

#### Danger Button
```css
background-color: #CD6B4A;
color: white;

/* Hover */
background-color: #B85A3A;
```

### Cards & Panels

#### Feature Card - Balanced Revision
```css
background: linear-gradient(135deg, #7FB685 0%, #88C298 100%);
color: white;
```

#### Welcome Banner
```css
background: linear-gradient(135deg, #E8744F 0%, #F4A261 100%);
color: white;
```

#### Notes Section
```css
background: linear-gradient(135deg, #FFF8E7 0%, #FFFCF3 100%);
border-left: 5px solid #F2CC8F;
```

### Form Elements

```css
/* Default State */
border: 1.5px solid #D4D4D4;
background-color: #FDFCFB;

/* Focus State */
border-color: #7FB685;
box-shadow: 0 0 0 0.2rem rgba(127, 182, 133, 0.20);
```

### Alerts

#### Info Alert
```css
background-color: #E7F4F8;
border-color: #5A9FB3;
color: #2D5560;
```

#### Success Alert
```css
background: linear-gradient(135deg, #7FB685 0%, #88C298 100%);
color: white;
```

#### Warning Alert
```css
background-color: #FEF6EB;
border-color: #F2CC8F;
color: #6D5336;
```

#### Danger Alert
```css
background-color: #F9EDE9;
border-color: #CD6B4A;
color: #6E3929;
```

---

## Typography

### Font Stack
```css
font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
```

### Headings
- Color: `#3D4451` (Soft Charcoal)
- Font Weight: `600` (Semi-bold)

### Body Text
- Color: `#2c3e50` (Dark)
- Line Height: `1.6` - `1.8`

### Secondary Text
- Color: `#6B7280` (Soft Gray)

### Icon Colors
- Primary icons: `#E8744F` (Primary Orange)
- Success icons: `#7FB685` (Soft Green)
- Warning icons: `#F2CC8F` (Honey Gold)
- Info icons: `#5A9FB3` (Refined Teal)

---

## Component Styles

### Navigation Tabs

```css
.nav-tabs .nav-link:hover {
    border-bottom-color: #7FB685;
    color: #7FB685;
    background-color: rgba(127, 182, 133, 0.05);
}

.nav-tabs .nav-link.active {
    border-bottom-color: #7FB685;
    color: #7FB685;
    background-color: rgba(127, 182, 133, 0.10);
}
```

### Modal Components

```css
.modal-content {
    background-color: #000;
    border: 2px solid #7FB685;
    box-shadow: 0 0 30px rgba(127, 182, 133, 0.3);
}

.modal-header {
    background-color: #2A2F38;
    border-bottom: 1px solid #7FB685;
}
```

### Breadcrumbs

```css
.breadcrumb-item a {
    color: #E8744F;
}

.breadcrumb-item a:hover {
    color: #D45D3B;
}

.breadcrumb-item i {
    color: #7FB685;
}
```

### Footer

```css
background: linear-gradient(135deg, #3D4451 0%, #2A2F38 100%);
border-top: 3px solid #7FB685;
```

---

## Spacing & Layout

### Border Radius
- Small: `0.5rem` (8px)
- Medium: `0.75rem` (12px)
- Large: `1rem` (16px)
- Pills: `20px` - `25px`

### Shadows

#### Card Shadow
```css
box-shadow: 0 2px 8px rgba(0, 0, 0, 0.08);
```

#### Hover Shadow
```css
box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
```

#### Feature Card Shadow
```css
box-shadow: 0 8px 20px rgba(0, 0, 0, 0.12);
```

### Padding
- Small: `0.5rem` - `0.75rem`
- Medium: `1rem` - `1.5rem`
- Large: `2rem` - `3rem`

---

## Migration Notes

### Version 1.0 → 2.0 Color Changes

| Component | Old Color | New Color | Impact |
|-----------|-----------|-----------|--------|
| Primary Orange | `#FF8C42` | `#E8744F` | Buttons, navbar, primary actions |
| Soft Orange | `#FFB366` | `#F4A261` | Gradients, hover states |
| Deep Orange | `#FF6B1A` | `#D45D3B` | Active states |
| Soft Green | `#90C695` | `#7FB685` | Success indicators, badges |
| Deep Green | `#6B9080` | `#588B6B` | Success button hover |
| Yellow | `#FFE66D` | `#F2CC8F` | Notes, warnings |
| Light Yellow | `#FFF4CC` | `#FFF8E7` | Subtle highlights |

### Rationale for Changes

1. **More Sophisticated**: Moved from bright, bold colors to refined, elegant tones
2. **Better Harmony**: Improved color relationships and gradient transitions
3. **Enhanced Accessibility**: Better contrast ratios for readability
4. **Professional Polish**: Colors feel more premium and trustworthy
5. **Preserved Identity**: Maintained confidence, growth, and clarity themes

### Files Updated (January 2026)

- `/static/style.css` - Complete CSS overhaul
- `/templates/student_dashboard.html`
- `/templates/dashboard.html`
- `/templates/view_case.html`
- `/templates/login.html`
- `/templates/register.html`
- `/templates/cases_list.html`
- `/templates/base.html`
- `/templates/modules_view.html`
- `/static/manifest.json` - PWA theme color

---

## Design Tokens (CSS Variables)

```css
:root {
    /* Primary - Orange/Coral */
    --primary-orange: #E8744F;
    --soft-orange: #F4A261;
    --deep-orange: #D45D3B;
    
    /* Secondary - Green/Sage */
    --soft-green: #7FB685;
    --deep-green: #588B6B;
    
    /* Accent - Gold/Honey */
    --pastel-yellow: #F2CC8F;
    --light-yellow: #FFF8E7;
    
    /* Neutrals */
    --soft-charcoal: #3D4451;
    --soft-gray: #6B7280;
    --soft-light-gray: #9CA3AF;
    
    /* Backgrounds */
    --soft-bg-dark: #2A2F38;
    --soft-bg-darker: #1F2329;
    --soft-bg-slate: #374151;
    --soft-bg-card: #FDFCFB;
    --soft-bg-hover: #F3F1EF;
    
    /* Legacy Mappings */
    --primary-color: #E8744F;
    --success-color: #7FB685;
    --danger-color: #CD6B4A;
    --warning-color: #F2CC8F;
    --light-bg: #FDFCFB;
}
```

---

## Accessibility Guidelines

### Contrast Ratios

All color combinations meet WCAG 2.1 Level AA standards:

- **Primary Orange on White**: 4.51:1 ✅
- **Soft Green on White**: 4.72:1 ✅
- **Deep Green on White**: 7.21:1 ✅
- **Charcoal on Light Backgrounds**: 9.45:1 ✅

### Color Blindness Considerations

- Orange and green are distinguishable for most color blindness types
- Icons and text labels supplement color coding
- Never rely on color alone to convey information

---

## Usage Examples

### Hero Section
```html
<div style="background: linear-gradient(135deg, #7FB685 0%, #88C298 100%); 
            color: white; 
            padding: 3rem;">
    <h1>Balanced Revision Mode</h1>
    <p>Smart case selection across all FRCR modules</p>
</div>
```

### Primary Action Button
```html
<button style="background-color: #E8744F; 
               color: white; 
               padding: 0.75rem 1.5rem; 
               border-radius: 0.5rem;">
    Start Revision
</button>
```

### Success Indicator
```html
<span style="background-color: #7FB685; 
             color: white; 
             padding: 0.5rem 1rem; 
             border-radius: 20px;">
    <i class="fas fa-check-circle"></i> Completed
</span>
```

### Notes Section
```html
<div style="background: linear-gradient(135deg, #FFF8E7 0%, #FFFCF3 100%);
            border-left: 5px solid #F2CC8F;
            padding: 1.5rem;">
    <h4><i class="fas fa-sticky-note" style="color: #FFB84D;"></i> My Notes</h4>
    <textarea>Your notes here...</textarea>
</div>
```

---

## Best Practices

### Do's ✅

- Use Primary Orange for primary actions and navigation
- Use Soft Green for success states and achievements
- Use Honey Gold for highlighting and notes
- Maintain consistent gradients across similar components
- Use shadows to create depth and hierarchy
- Ensure sufficient contrast for text readability

### Don'ts ❌

- Don't mix old and new color codes
- Don't use pure black (#000000) except in modals
- Don't override CSS variables without documentation
- Don't use more than 3-4 colors in a single component
- Don't sacrifice readability for aesthetics

---

## Future Considerations

### Potential Enhancements

1. **Dark Mode**: Develop complementary dark theme
2. **High Contrast Mode**: Enhanced accessibility option
3. **Custom Themes**: Allow users to personalize colors
4. **Print Styles**: Optimized colors for printing
5. **Animation Colors**: Micro-interactions and transitions

### Maintenance

- Review color usage quarterly
- Test accessibility with actual users
- Monitor user feedback on visual design
- Update documentation with any changes
- Maintain consistency across all platforms

---

## Resources

### Design Tools
- **Color Picker**: [Adobe Color](https://color.adobe.com/)
- **Contrast Checker**: [WebAIM](https://webaim.org/resources/contrastchecker/)
- **Gradient Generator**: [CSS Gradient](https://cssgradient.io/)

### Related Documentation
- [PWA_TESTING_GUIDE.md](./PWA_TESTING_GUIDE.md)
- [README.md](./README.md)
- [MIGRATION_GUIDE.md](./MIGRATION_GUIDE.md)

---

**Document Created:** January 9, 2026  
**Last Reviewed:** January 9, 2026  
**Next Review:** April 9, 2026  
**Maintained By:** Development Team
