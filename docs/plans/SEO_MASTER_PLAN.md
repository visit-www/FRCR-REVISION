# RadInsights — Master SEO & Architecture Plan

> **Created:** March 30, 2026
> **Last Updated:** March 31, 2026
> **Status:** Phase 1 Done (Public Preview Pages), Phases 2-6 Planned
> **Target:** Top 10 SERP for "radiology education platform", "FRCR revision", "TNM calculator", "AI radiology reporting"
> **Keyword:** `RADINSIGHTS-SEO-2026`

---

## Table of Contents

1. [Executive Summary](#1-executive-summary)
2. [Current SEO Audit](#2-current-seo-audit)
3. [Brand Identity & Messaging](#3-brand-identity)
4. [Implementation Phases](#4-implementation-phases)
5. [Phase 1 — Global Metadata (base.html)](#5-phase-1-global-metadata)
6. [Phase 2 — Schema.org Structured Data](#6-phase-2-structured-data)
7. [Phase 3 — Landing Page Optimization (landing.html)](#7-phase-3-landing-page)
8. [Phase 4 — Per-Page SEO Blocks](#8-phase-4-per-page-seo)
9. [Phase 5 — Technical SEO](#9-phase-5-technical-seo)
10. [Phase 6 — Content Strategy & Keyword Targeting](#10-phase-6-content-strategy)
11. [Keyword Research Matrix](#11-keyword-matrix)
12. [Sitemap Expansion Plan](#12-sitemap-expansion)
13. [robots.txt Review](#13-robots-txt)
14. [Open Graph & Social Cards](#14-open-graph)
15. [Performance & Core Web Vitals](#15-performance)
16. [Monitoring & Analytics](#16-monitoring)
17. [File Inventory](#17-file-inventory)
18. [Implementation Checklist](#18-checklist)

---

## 1. Executive Summary

RadInsights (radinsights.xyz) is a high-end radiology informatics and education platform targeting radiology consultants and residents. It is **not a textbook** — it is a **clinical bridge** between theory and practice.

**Current SEO state:** Basic foundations in place (title tags, meta descriptions, canonical URLs, sitemap with 43 URLs, robots.txt). Missing critical elements: Open Graph tags, Twitter Cards, Schema.org JSON-LD, per-page meta overrides, dynamic sitemap, and content-driven keyword strategy.

**Goal:** Transform RadInsights from an authenticated-only platform into a searchable medical authority with public landing pages, discoverable TNM calculators, and structured data that positions it as the go-to resource in Google's medical knowledge panel.

---

## 2. Current SEO Audit

### 2.1 What's Working

| Element | Status | Notes |
|---------|--------|-------|
| Title tag template | Done | `{% block title %}RadInsights{% endblock %}` — per-page overridable |
| Meta description template | Done | `{% block meta_description %}...{% endblock %}` |
| Google Site Verification | Done | Token present in base.html and landing.html |
| Canonical URLs | Partial | Present on landing, about, pricing, TNM concepts, legal pages |
| Sitemap.xml | Done | 43 URLs — homepage, pricing, about, 39 TNM calculators |
| robots.txt | Done | Blocks admin/API/auth routes, references sitemap |
| PWA Manifest | Done | Proper categories (medical, education, radiology), 6 icon sizes |
| Favicon/Icons | Done | 192x192, 512x512 on Cloudinary + Apple touch icons |
| HSTS Header | Done | `max-age=31536000; includeSubDomains` |
| Semantic HTML | Done | Proper H1-H2 hierarchy on landing page |
| Skip-to-content link | Done | Accessibility aid in base.html |
| Mobile viewport | Done | `width=device-width, initial-scale=1.0` |

### 2.2 What's Missing (Updated March 31, 2026)

| Element | Impact | Priority | Status |
|---------|--------|----------|--------|
| **Open Graph tags** | Social sharing shows no image/description | P1 | **DONE** — added to all public templates via `{% block og_title/og_description %}` |
| **Twitter Card tags** | Twitter sharing broken | P1 | **DONE** — added to base.html, inherited by all templates |
| **Schema.org JSON-LD** | No rich results in Google (medical, software, FAQ) | P1 | **PARTIAL** — CollectionPage + LearningResource + MedicalCondition via `_schema_medical.html` macros. Organization + SoftwareApplication on landing still TODO |
| **Per-page meta descriptions** | 31 templates override title but NOT description | P1 | **DONE** — all public templates now override `{% block meta_description %}` |
| **Canonical URLs on all pages** | Only 6 pages have canonical; rest missing | P2 | TODO |
| **Dynamic sitemap** | Only static XML; no Knowledge Hub, tools, or protocols | P2 | **DONE** — sitemap now includes cases, algorithms, templates, anatomy snippets (100+ URLs) |
| **`<meta name="robots">`** | No per-page noindex control for authenticated pages | P2 | **DONE** — noindex on auth templates (login, register, forgot-password, etc.) |
| **Author/organization markup** | No publisher or creator attribution | P3 | TODO |
| **hreflang tags** | No language targeting (en-GB / en-US) | P4 | TODO |
| **FAQ schema** | Pricing and about pages could use FAQ rich results | P3 | TODO |
| **Breadcrumb schema** | Mobile breadcrumb exists in HTML but no JSON-LD | P3 | TODO |
| **Content keywords strategy** | No deliberate keyword targeting per page | P2 | TODO |

### 2.3 Critical Issues (Updated March 31, 2026)

1. **Landing page (`landing.html`) is a standalone template** — does NOT extend `base.html`, so any SEO improvements to base.html won't apply. Both files need updates. *(Still applies — landing.html needs OG/schema separately)*

2. ~~**31 child templates override `{% block title %}` but NONE override `{% block meta_description %}`**~~ — **FIXED:** All public templates now override `{% block meta_description %}` with page-specific descriptions.

3. ~~**Sitemap is static**~~ — **FIXED:** Sitemap is now dynamic, includes published cases (`/case-library/<id>`), admin algorithms (`/reporting-template/<slug>`), radiology templates (`/radiology-template/view/<id>`), anatomy snippets (`/anatomy-snippets/<slug>`), and 6 new static pages. 100+ URLs.

4. ~~**robots.txt blocks `/cases` and `/practice`**~~ — **FIXED:** robots.txt now allows `/case-library`, `/reporting-algorithms`, `/reporting-templates`, `/incidental-findings`, `/radiology-protocols`, `/knowledge-hub`, `/anatomy-snippets`, `/radiology-pearls`. Still blocks `/cases`, `/view-case/`, `/practice` (authenticated routes).

---

## 3. Brand Identity & Messaging

### 3.1 Core Value Proposition

> **RadInsights is a clinical bridge** — connecting radiology theory to practice through high-yield cases, AI-powered reporting, AJCC TNM 8 staging tools, and evidence-based clinical algorithms.

### 3.2 Target Audience

| Audience | Needs | Features |
|----------|-------|----------|
| **Radiology Registrars/Residents** | FRCR exam prep, systematic reporting skills | Cases, Q&A, discussion forum, revision modules |
| **Radiology Consultants** | Efficient reporting, MDT preparation, quick references | AI reporting, TNM calculators, clinical tools |
| **Radiographers** | Protocols, incidental finding management | RadIQ module, clinical protocols |

### 3.3 Brand Colors (for UI/meta consistency)

| Color | Hex | Usage in SEO |
|-------|-----|-------------|
| **Peachy Orange** | `#e96304` | CTA buttons, og:theme-color |
| **Teal Blue** | `#5E899E` | Headers, theme-color meta, brand accent |
| **Off-White** | `#fdfdfb` | Background |
| **Dark Text** | `#2c3e50` | Primary text |

### 3.4 SEO Title Pattern

```
[Page Name] | RadInsights | High-Yield Radiology Education
```

Examples:
- `TNM Calculators | RadInsights | High-Yield Radiology Education`
- `Oropharynx Cancer TNM Staging | RadInsights | High-Yield Radiology Education`
- `AI Radiology Reporting | RadInsights | High-Yield Radiology Education`

### 3.5 Standard Meta Description

> High-yield radiology pearls, AJCC TNM 8 staging tools, and AI-powered reporting modules. Bridging the gap between textbook theory and clinical practice for radiologists.

Page-specific descriptions should be 150-160 characters, include primary keyword, and end with a call to action where appropriate.

---

## 4. Implementation Phases

| Phase | Scope | Effort | Impact |
|-------|-------|--------|--------|
| **P1** | Global metadata — base.html + landing.html | 1 day | High — fixes social sharing, enables rich results |
| **P2** | Schema.org JSON-LD — Organization, MedicalWebPage, SoftwareApplication | 1 day | High — Google rich results, medical knowledge panel |
| **P3** | Landing page content — "The Bridge" section, keyword-optimized copy | 1 day | High — conversion + organic traffic |
| **P4** | Per-page SEO — title/description/canonical on all 31+ templates | 2 days | Medium — improves long-tail keyword coverage |
| **P5** | Technical SEO — dynamic sitemap, expanded robots.txt, breadcrumb schema | 1 day | Medium — better crawling + indexing |
| **P6** | Content strategy — blog/article SEO, keyword targeting, internal linking | Ongoing | High — long-term organic growth |

---

## 5. Phase 1 — Global Metadata (base.html)

### 5.1 Changes to `templates/base.html`

Add after the existing `<meta name="description">` tag (line 7):

```html
<!-- SEO: Open Graph (Facebook, LinkedIn, WhatsApp) -->
<meta property="og:type" content="{% block og_type %}website{% endblock %}">
<meta property="og:title" content="{% block og_title %}{{ self.title() }}{% endblock %}">
<meta property="og:description" content="{% block og_description %}High-yield radiology pearls, AJCC TNM 8 staging tools, and AI-powered reporting modules. Bridging the gap between textbook theory and clinical practice for radiologists.{% endblock %}">
<meta property="og:image" content="{% block og_image %}https://res.cloudinary.com/dx7b7chvn/image/upload/v1769022136/icon-512x512_myzqfe.png{% endblock %}">
<meta property="og:url" content="{% block og_url %}{{ request.url }}{% endblock %}">
<meta property="og:site_name" content="RadInsights">
<meta property="og:locale" content="en_GB">

<!-- SEO: Twitter Card -->
<meta name="twitter:card" content="summary_large_image">
<meta name="twitter:title" content="{{ self.og_title() }}">
<meta name="twitter:description" content="{{ self.og_description() }}">
<meta name="twitter:image" content="{{ self.og_image() }}">

<!-- SEO: Canonical URL (overridable per page) -->
{% block canonical %}{% endblock %}

<!-- SEO: Robots directive (overridable — authenticated pages can set noindex) -->
{% block robots_meta %}<meta name="robots" content="index, follow">{% endblock %}

<!-- SEO: Author -->
<meta name="author" content="RadInsights">
```

### 5.2 Changes to `templates/landing.html`

Landing.html is standalone (doesn't extend base.html). Add after existing `<meta name="description">` (line 7):

```html
<!-- Open Graph -->
<meta property="og:type" content="website">
<meta property="og:title" content="RadInsights — Radiology Learning & Reporting Platform">
<meta property="og:description" content="High-yield radiology pearls, AJCC TNM 8 staging tools, and AI-powered reporting modules. Bridging the gap between textbook theory and clinical practice for radiologists.">
<meta property="og:image" content="https://res.cloudinary.com/dx7b7chvn/image/upload/v1769022136/icon-512x512_myzqfe.png">
<meta property="og:url" content="https://www.radinsights.xyz/">
<meta property="og:site_name" content="RadInsights">
<meta property="og:locale" content="en_GB">

<!-- Twitter Card -->
<meta name="twitter:card" content="summary_large_image">
<meta name="twitter:title" content="RadInsights — Radiology Learning & Reporting Platform">
<meta name="twitter:description" content="High-yield radiology pearls, AJCC TNM 8 staging tools, and AI-powered reporting. Built for radiologists.">
<meta name="twitter:image" content="https://res.cloudinary.com/dx7b7chvn/image/upload/v1769022136/icon-512x512_myzqfe.png">

<!-- Robots -->
<meta name="robots" content="index, follow">
<meta name="author" content="RadInsights">
```

### 5.3 Authenticated Pages — noindex

For templates that require login (cases, practice, modules, dashboard), override:

```jinja2
{% block robots_meta %}<meta name="robots" content="noindex, nofollow">{% endblock %}
```

Applies to: `cases_list.html`, `view_case.html`, `edit_case.html`, `dashboard.html`, `practice_landing.html`, `revision.html`, `modules.html`, `study.html`

---

## 6. Phase 2 — Schema.org Structured Data

### 6.1 Organization Schema (base.html — global)

Add before `</head>` in `base.html`:

```html
<!-- Schema.org: Organization -->
<script type="application/ld+json">
{
  "@context": "https://schema.org",
  "@type": "Organization",
  "name": "RadInsights",
  "url": "https://www.radinsights.xyz",
  "logo": "https://res.cloudinary.com/dx7b7chvn/image/upload/v1769022136/icon-512x512_myzqfe.png",
  "description": "High-yield radiology education platform bridging the gap between textbook theory and clinical practice.",
  "sameAs": [],
  "contactPoint": {
    "@type": "ContactPoint",
    "contactType": "customer support",
    "email": "support@radinsights.xyz"
  }
}
</script>
```

### 6.2 MedicalWebPage + SoftwareApplication Schema (landing.html)

Add before `</head>` in `landing.html`:

```html
<!-- Schema.org: MedicalWebPage -->
<script type="application/ld+json">
{
  "@context": "https://schema.org",
  "@type": "MedicalWebPage",
  "name": "RadInsights — Radiology Learning & Reporting Platform",
  "url": "https://www.radinsights.xyz",
  "description": "High-yield radiology pearls, AJCC TNM 8 staging tools, and AI-powered reporting modules for radiologists.",
  "medicalAudience": {
    "@type": "MedicalAudience",
    "audienceType": "MedicalProfessional",
    "geographicArea": {
      "@type": "AdministrativeArea",
      "name": "Global"
    }
  },
  "specialty": {
    "@type": "MedicalSpecialty",
    "name": "Radiology"
  },
  "aspect": ["Diagnosis", "Medical Training", "Clinical Protocols", "Radiology Reporting"],
  "about": [
    {"@type": "MedicalCondition", "name": "Oncologic Imaging"},
    {"@type": "MedicalProcedure", "name": "TNM Staging"},
    {"@type": "MedicalProcedure", "name": "Radiological Reporting"}
  ],
  "hasPart": [
    {
      "@type": "SoftwareApplication",
      "name": "RadInsight Intelligence — AI Reporting Engine",
      "applicationCategory": "MedicalSoftware",
      "operatingSystem": "Web",
      "description": "Converts shorthand radiology notes into high-quality neural language reports suitable for MDTs and patient records.",
      "featureList": "Neural language reporting, MDT extraction, clinical-grade automation, shorthand conversion"
    },
    {
      "@type": "SoftwareApplication",
      "name": "TNM Staging & Clinical Calculators",
      "applicationCategory": "EducationalApplication",
      "operatingSystem": "Web",
      "description": "39 interactive AJCC TNM 8th Edition staging calculators covering all FRCR-relevant cancers with auto-calculation and evidence-based pearls.",
      "featureList": "AJCC 8th Edition TNM staging, auto-stage calculation, imaging pearls, pitfall warnings"
    },
    {
      "@type": "SoftwareApplication",
      "name": "RadIQ — Radiology Intelligence Module",
      "applicationCategory": "MedicalSoftware",
      "operatingSystem": "Web",
      "description": "Protocol guidance, incidental finding management, and general radiology queries for radiographers and registrars."
    }
  ],
  "provider": {
    "@type": "Organization",
    "name": "RadInsights",
    "url": "https://www.radinsights.xyz"
  }
}
</script>
```

### 6.3 TNM Calculator Pages — MedicalWebPage Schema

For each TNM calculator page, inject structured data:

```html
<script type="application/ld+json">
{
  "@context": "https://schema.org",
  "@type": "MedicalWebPage",
  "name": "{{ calculator.cancer_name }} TNM Staging Calculator | RadInsights",
  "url": "https://www.radinsights.xyz/tnm-calculator/{{ calculator.slug }}",
  "description": "Interactive AJCC TNM 8th Edition staging calculator for {{ calculator.cancer_name }}.",
  "medicalAudience": {"@type": "MedicalAudience", "audienceType": "MedicalProfessional"},
  "specialty": {"@type": "MedicalSpecialty", "name": "Radiology"},
  "about": {"@type": "MedicalCondition", "name": "{{ calculator.cancer_name }}"},
  "mainEntity": {
    "@type": "MedicalCode",
    "codingSystem": "AJCC TNM 8th Edition",
    "name": "{{ calculator.cancer_name }} TNM Classification"
  }
}
</script>
```

### 6.4 Pricing Page — FAQ Schema

```html
<script type="application/ld+json">
{
  "@context": "https://schema.org",
  "@type": "FAQPage",
  "mainEntity": [
    {
      "@type": "Question",
      "name": "What is included in the free plan?",
      "acceptedAnswer": {
        "@type": "Answer",
        "text": "The free plan includes unlimited search, 3 case reads per month, access to TNM calculators, and basic clinical tools."
      }
    },
    {
      "@type": "Question",
      "name": "Can I cancel my subscription anytime?",
      "acceptedAnswer": {
        "@type": "Answer",
        "text": "Yes, you can cancel your subscription at any time. Your access continues until the end of the current billing period."
      }
    },
    {
      "@type": "Question",
      "name": "Is RadInsights suitable for FRCR exam preparation?",
      "acceptedAnswer": {
        "@type": "Answer",
        "text": "Yes. RadInsights is specifically designed for FRCR Part 2B (Viva) and Part 2A (SBA) preparation with case-based learning, Q&A, and structured reporting practice."
      }
    }
  ]
}
</script>
```

### 6.5 Breadcrumb Schema (base.html)

Add a `{% block breadcrumb_schema %}` that pages can override:

```html
{% block breadcrumb_schema %}{% endblock %}
```

Example override in a TNM calculator template:

```html
{% block breadcrumb_schema %}
<script type="application/ld+json">
{
  "@context": "https://schema.org",
  "@type": "BreadcrumbList",
  "itemListElement": [
    {"@type": "ListItem", "position": 1, "name": "Home", "item": "https://www.radinsights.xyz/"},
    {"@type": "ListItem", "position": 2, "name": "TNM Calculators", "item": "https://www.radinsights.xyz/tnm-calculator"},
    {"@type": "ListItem", "position": 3, "name": "{{ calculator.cancer_name }}"}
  ]
}
</script>
{% endblock %}
```

---

## 7. Phase 3 — Landing Page Optimization

### 7.1 "The AI Reporting Module: Beyond the Shorthand" Section

Add a new content section to `landing.html` between the "Five Pillars" and "Simple is Superb" sections. This section is keyword-optimized for:

- Neural language reporting
- MDT extraction
- Clinical-grade automation
- Radiologist-led AI
- AI radiology reporting
- Shorthand to report conversion

**Content:**

```html
<!-- The Bridge: AI Reporting Section (SEO-optimized) -->
<section class="py-5" style="background: linear-gradient(135deg, #f8f9fa 0%, #eef2f5 100%);">
  <div class="container" style="max-width: 900px;">
    <div class="text-center mb-4">
      <span style="color: var(--brand-primary); font-weight: 600; font-size: 0.85rem; letter-spacing: 1px; text-transform: uppercase;">AI-Powered Reporting</span>
      <h2 class="mt-2" style="font-size: 2rem; font-weight: 700; color: var(--brand-text-primary);">Beyond the Shorthand</h2>
      <p style="color: var(--brand-text-secondary); max-width: 650px; margin: 0 auto;">
        Radiologist-led AI that transforms your clinical shorthand into high-quality, structured reports — ready for MDTs, patient records, and professional communication.
      </p>
    </div>

    <div class="row g-4 align-items-center">
      <div class="col-md-6">
        <div style="background: #1a2332; border-radius: 12px; padding: 1.5rem; font-family: 'Courier New', monospace; font-size: 0.85rem; color: #8b949e;">
          <div style="color: #e96304; font-size: 0.7rem; margin-bottom: 0.5rem;">INPUT — Clinical Shorthand</div>
          <p style="color: #c9d1d9; margin: 0;">RLL mass 4.2cm, spiculated margins, pleural contact. Mediastinal LNs — R paratracheal 1.5cm, subcarinal 1.2cm. No mets. Suggest biopsy.</p>
        </div>
        <div class="text-center my-3">
          <i class="fas fa-arrow-down" style="color: var(--brand-primary); font-size: 1.5rem;"></i>
        </div>
        <div style="background: #fff; border: 2px solid var(--brand-neutral); border-radius: 12px; padding: 1.5rem; font-size: 0.85rem;">
          <div style="color: var(--brand-neutral); font-size: 0.7rem; margin-bottom: 0.5rem;">OUTPUT — Neural Language Report</div>
          <p style="margin: 0; color: var(--brand-text-primary);"><strong>Findings:</strong> A 4.2 cm spiculated mass is identified in the right lower lobe with broad pleural contact, raising concern for primary bronchogenic carcinoma. Mediastinal lymphadenopathy is noted with a 1.5 cm right paratracheal node and a 1.2 cm subcarinal node, suspicious for nodal metastatic involvement. No distant metastatic disease is identified.</p>
          <p style="margin: 0.5rem 0 0; color: var(--brand-text-primary);"><strong>Impression:</strong> Right lower lobe mass with mediastinal lymphadenopathy. Recommend tissue sampling for histological diagnosis and PET-CT for staging.</p>
        </div>
      </div>
      <div class="col-md-6">
        <h3 style="font-size: 1.3rem; font-weight: 600; color: var(--brand-text-primary);">Clinical-Grade Automation</h3>
        <p style="color: var(--brand-text-secondary); font-size: 0.95rem;">
          RadInsight Intelligence uses neural language processing to convert your shorthand dictation into complete, structured radiology reports. Every output follows standardised reporting frameworks — ready for MDT extraction, audit, and peer review.
        </p>
        <ul style="color: var(--brand-text-secondary); font-size: 0.9rem; padding-left: 1.2rem;">
          <li><strong>Shorthand conversion</strong> — type as you think, report as you should</li>
          <li><strong>MDT-ready formatting</strong> — structured findings and impression</li>
          <li><strong>Incidental finding alerts</strong> — automatic flagging and follow-up guidance</li>
          <li><strong>Teaching pearls</strong> — embedded clinical insights from real reporting</li>
        </ul>
        <a href="/register" style="display: inline-block; background: var(--brand-primary); color: #fff; padding: 0.6rem 1.5rem; border-radius: 8px; text-decoration: none; font-weight: 600; font-size: 0.9rem; margin-top: 0.5rem;">Try AI Reporting Free</a>
      </div>
    </div>
  </div>
</section>
```

### 7.2 Landing Page SEO Enhancements

**Update `<title>` (line 6):**
```html
<title>RadInsights | High-Yield Radiology Education | AI Reporting & TNM Calculators</title>
```

**Update `<meta description>` (line 7):**
```html
<meta name="description" content="High-yield radiology pearls, AJCC TNM 8 staging tools, and AI-powered reporting modules. Bridging the gap between textbook theory and clinical practice for radiologists.">
```

**Add keywords meta (low impact but no harm):**
```html
<meta name="keywords" content="radiology education, FRCR revision, TNM staging calculator, AJCC 8th edition, AI radiology reporting, radiology cases, MDT reporting, clinical radiology tools, oncology staging, radiology pearls">
```

---

## 8. Phase 4 — Per-Page SEO Blocks

### 8.1 New Template Blocks (base.html)

The existing `{% block meta_description %}` is already in place but no child templates use it. Add guidance and ensure all public pages override it.

### 8.2 Per-Page SEO Specifications

| Template | Title | Meta Description (150-160 chars) |
|----------|-------|--------------------------------|
| `smart_reporter.html` | Smart Reporter \| RadInsights \| High-Yield Radiology Education | AI-powered radiology reporting tool. Convert shorthand notes into structured reports with neural language processing, MDT formatting, and clinical pearls. |
| `knowledge_hub.html` | Knowledge Hub \| RadInsights \| High-Yield Radiology Education | Browse reporting algorithms, radiology templates, clinical tools, and anatomy snippets. Evidence-based resources for daily radiology practice. |
| `tnm_calculator_list.html` | TNM Calculators — AJCC 8th Edition \| RadInsights | 39 interactive AJCC TNM 8th Edition staging calculators for all FRCR-relevant cancers. Auto-calculation, imaging pearls, and pitfall warnings. |
| `tnm_calculator.html` | {{ name }} TNM Staging \| RadInsights \| High-Yield Radiology Education | Interactive AJCC TNM 8th Edition staging calculator for {{ name }}. Auto-calculate T, N, M categories with evidence-based pearls. |
| `essential_tnm_concepts.html` | Essential TNM Concepts for Registrars \| RadInsights | Core TNM staging concepts every radiology registrar must know. AJCC 8th Edition rules, common pitfalls, and high-yield staging pearls. |
| `pricing.html` | Pricing Plans \| RadInsights \| High-Yield Radiology Education | Choose your RadInsights plan. Free, Standard, or Elite tier. Access AI reporting, TNM calculators, 200+ cases, and clinical tools. |
| `about.html` | About \| RadInsights \| High-Yield Radiology Education | RadInsights bridges the gap between radiology theory and clinical practice. Built by radiologists, for radiologists. |
| `radiology_protocols_user.html` | Clinical Protocols \| RadInsights \| High-Yield Radiology Education | Evidence-based clinical protocols for radiologists. Contrast safety, emergency imaging, MRI protocols, and post-procedural guidelines. |
| `radiology_tools_user.html` | Radiology Tools \| RadInsights \| High-Yield Radiology Education | Interactive radiology calculators and decision tools. Incidental finding management, classification systems, and clinical algorithms. |
| `radiology_pearls_browse.html` | Radiology Pearls \| RadInsights \| High-Yield Radiology Education | High-yield radiology pearls curated from clinical practice. Browse by body section, modality, and topic. |
| `anatomy_snippet_view.html` | {{ name }} Anatomy \| RadInsights \| High-Yield Radiology Education | Essential imaging anatomy for {{ name }}. Normal variants, measurements, pitfalls, and high-yield clinical correlations. |
| `radiq.html` | RadIQ \| RadInsights \| Radiology Intelligence Module | AI-powered radiology intelligence. Protocol guidance, incidental findings, and general radiology queries for radiographers and registrars. |

### 8.3 Authenticated-Only Pages (noindex)

These templates should add `{% block robots_meta %}<meta name="robots" content="noindex, nofollow">{% endblock %}`:

- `cases_list.html`
- `view_case.html`
- `edit_case.html`
- `dashboard.html`
- `practice_landing.html`
- `revision.html`
- `modules.html`
- `study.html`
- `suggest_case.html`
- `forum.html`
- All admin templates (`admin_*.html`)

---

## 9. Phase 5 — Technical SEO

### 9.1 Dynamic Sitemap

Replace the static `sitemap.xml` with a dynamically generated route that includes all public content:

```python
@app.route('/sitemap.xml', methods=['GET'])
def sitemap_xml():
    """Generate dynamic sitemap including all public content."""
    pages = []

    # Static pages
    static_pages = [
        ('https://www.radinsights.xyz/', '1.0', 'weekly'),
        ('https://www.radinsights.xyz/pricing', '0.9', 'monthly'),
        ('https://www.radinsights.xyz/about', '0.7', 'monthly'),
        ('https://www.radinsights.xyz/tnm-calculator', '0.9', 'weekly'),
        ('https://www.radinsights.xyz/essential-tnm-concepts', '0.6', 'monthly'),
        ('https://www.radinsights.xyz/knowledge-hub', '0.8', 'weekly'),
        ('https://www.radinsights.xyz/privacy-policy', '0.3', 'yearly'),
        ('https://www.radinsights.xyz/terms-of-use', '0.3', 'yearly'),
    ]

    # TNM Calculators (dynamic from DB)
    calculators = TNMCalculator.query.filter_by(is_published=True).all()
    for calc in calculators:
        pages.append((f'https://www.radinsights.xyz/tnm-calculator/{calc.slug}', '0.7', 'monthly'))

    # Public Knowledge Hub content
    # Reporting Algorithms (admin-verified only)
    algorithms = ReportingAlgorithm.query.filter_by(origin='admin', is_available=True).all()
    for algo in algorithms:
        pages.append((f'https://www.radinsights.xyz/knowledge-hub/algorithm/{algo.id}', '0.6', 'monthly'))

    # Radiology Tools (published)
    # Clinical Protocols (published)
    # ... extend as public pages are created

    # Build XML
    xml = '<?xml version="1.0" encoding="UTF-8"?>\n'
    xml += '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
    for url, priority, changefreq in static_pages + pages:
        xml += f'  <url><loc>{url}</loc><priority>{priority}</priority><changefreq>{changefreq}</changefreq></url>\n'
    xml += '</urlset>'

    return Response(xml, mimetype='application/xml', headers={
        'Cache-Control': 'public, max-age=3600, s-maxage=86400'
    })
```

### 9.2 Canonical URL Helper

Add a Jinja2 context processor to auto-generate canonical URLs:

```python
@app.context_processor
def seo_helpers():
    def canonical_url():
        return request.url.split('?')[0]  # Strip query params
    return {'canonical_url': canonical_url}
```

Use in base.html:
```html
{% block canonical %}<link rel="canonical" href="{{ canonical_url() }}">{% endblock %}
```

### 9.3 Verify No `noindex` in Production

Add a startup check:

```python
if not app.debug:
    # Ensure no accidental noindex in production templates
    logger.info('Production mode: verify noindex tags are intentional')
```

### 9.4 Image Assets Verification

Ensure all icons reference the correct sizes:
- **192x192:** `icon-192x192_zkqtvu.png` (favicon, PWA)
- **512x512:** `icon-512x512_myzqfe.png` (OG image, PWA splash)

### 9.5 Sitemap Cache Busting

If needed, support `?v=1` query param:
```python
@app.route('/sitemap.xml', methods=['GET'])
def sitemap_xml():
    # v param ignored but forces CDN cache bypass
    ...
```

---

## 10. Phase 6 — Content Strategy & Keyword Targeting

### 10.1 Content Pillars

| Pillar | Content Type | SEO Value | Examples |
|--------|-------------|-----------|---------|
| **Oncology Staging** | TNM calculators, staging guides | Very High | "lung cancer TNM staging", "breast cancer AJCC 8" |
| **Radiology Reporting** | AI reporting, templates, algorithms | High | "radiology report template", "structured reporting radiology" |
| **Clinical Tools** | Calculators, protocols, decision trees | High | "incidental finding management", "adrenal incidentaloma algorithm" |
| **FRCR Education** | Cases, Q&A, revision modules | Medium | "FRCR revision cases", "FRCR viva preparation" |
| **Radiology Pearls** | High-yield clinical tips | Medium | "radiology pearls", "imaging pitfalls" |

### 10.2 Public Content Pages (to create)

Currently, most content requires authentication. To capture organic search traffic, create public-facing versions:

| Page | URL | Content | SEO Target |
|------|-----|---------|------------|
| TNM Calculator Index | `/tnm-calculator` | Grid of 39 calculators with descriptions | "TNM staging calculator" |
| Individual TNM pages | `/tnm-calculator/{slug}` | Already public | "{{ cancer }} TNM staging AJCC 8" |
| Knowledge Hub landing | `/knowledge-hub` | Browse algorithms + templates + tools | "radiology reporting algorithms" |
| Essential TNM | `/essential-tnm-concepts` | Already public | "TNM staging concepts registrar" |
| Clinical Protocols index | `/clinical-protocols` | Browse protocols (summaries public, full requires auth) | "radiology clinical protocols" |

### 10.3 Internal Linking Strategy

- Every TNM calculator links to related calculators and Essential TNM Concepts
- Landing page links to TNM Calculator index, Knowledge Hub, AI Reporting
- Knowledge Hub pages cross-link to related tools, calculators, and pearls
- Add "Related Resources" footer to all public pages

---

## 11. Keyword Research Matrix

### 11.1 Primary Keywords (High Intent)

| Keyword | Monthly Volume (est.) | Difficulty | Target Page |
|---------|----------------------|------------|-------------|
| radiology education platform | 500 | Medium | Landing |
| FRCR revision | 1,200 | Medium | Landing |
| FRCR viva preparation | 800 | Low | Landing |
| TNM staging calculator | 2,400 | Medium | /tnm-calculator |
| AJCC 8th edition calculator | 1,000 | Low | /tnm-calculator |
| AI radiology reporting | 600 | Low | Landing / Smart Reporter |
| radiology report template | 3,600 | High | Knowledge Hub |
| structured radiology reporting | 900 | Medium | Smart Reporter |

### 11.2 Long-Tail Keywords (Per Calculator)

| Keyword | Target Page |
|---------|-------------|
| lung cancer TNM staging AJCC 8 | /tnm-calculator/lung |
| breast cancer TNM calculator | /tnm-calculator/breast |
| oropharynx cancer staging | /tnm-calculator/oropharynx |
| renal cell carcinoma TNM | /tnm-calculator/kidney |
| colorectal cancer staging AJCC | /tnm-calculator/colon |
| hepatocellular carcinoma TNM | /tnm-calculator/liver |
| thyroid cancer staging | /tnm-calculator/thyroid-differentiated |
| pancreatic cancer TNM | /tnm-calculator/pancreas |
| cervical cancer FIGO staging | /tnm-calculator/cervix-uteri |
| prostate cancer TNM AJCC 8 | /tnm-calculator/prostate |

### 11.3 Tool-Specific Keywords

| Keyword | Target Page |
|---------|-------------|
| adrenal incidentaloma algorithm | Radiology Tools |
| thyroid nodule TI-RADS calculator | Radiology Tools |
| liver lesion management algorithm | Radiology Tools |
| incidental pulmonary nodule Fleischner | Radiology Tools |
| Bosniak classification calculator | Radiology Tools |
| LI-RADS scoring calculator | Radiology Tools |

### 11.4 Content Keywords

| Keyword | Content Type |
|---------|-------------|
| radiology pearls high yield | Radiology Pearls page |
| imaging anatomy radiology | Anatomy Snippets |
| radiology reporting best practices | Knowledge Hub |
| neural language radiology report | Landing / AI section |
| MDT radiology report format | Landing / AI section |

---

## 12. Sitemap Expansion Plan

### 12.1 Current (43 URLs)

```
/ (homepage)
/pricing
/about
/tnm-calculator (index)
/essential-tnm-concepts
/privacy-policy
/terms-of-use
+ 39 TNM calculator pages
```

### 12.2 Target (100+ URLs) — DONE (March 31, 2026)

```
Current 43 URLs (TNM calculators + static pages)
+ /case-library                           ← NEW
+ /reporting-algorithms                   ← NEW
+ /reporting-templates                    ← NEW
+ /incidental-findings                    ← NEW
+ /radiology-protocols                    ← NEW
+ /knowledge-hub                          ← NEW
+ Dynamic: /case-library/<id>             ← published cases
+ Dynamic: /reporting-template/<slug>     ← admin algorithms
+ Dynamic: /radiology-template/view/<id>  ← admin templates
+ Dynamic: /anatomy-snippets/<slug>       ← anatomy cache
```

### 12.3 Implementation

~~Switch from static `sitemap.xml` file to dynamic Flask route.~~ **DONE** — `sitemap_xml()` in `app.py` now generates dynamic sitemap with all public content types.

---

## 13. robots.txt Review

### 13.1 Current Disallowed Paths

```
/api/               — Correct (API endpoints)
/auth/              — Correct (authentication)
/admin/             — Correct (admin area)
/stripe/            — Correct (payment processing)
/health             — Correct (health check)
/dashboard          — Correct (user-specific)
/study              — Correct (user-specific)
/practice           — Review: could be public
/modules            — Correct (user-specific)
/cases              — Review: case list could be public
/case-list          — Correct (same as /cases)
/view-case/         — Review: individual cases are behind auth
/revision/          — Correct (user-specific)
/suggest-case       — Correct (user-specific)
/notion/            — Correct (integration)
```

### 13.2 Recommended Changes

1. **Keep blocking** `/cases`, `/view-case/`, `/practice` — these require authentication
2. **Consider unblocking** if public case browse page is created in the future
3. **Add crawl-delay** for aggressive bots:
   ```
   User-agent: AhrefsBot
   Crawl-delay: 10

   User-agent: SemrushBot
   Crawl-delay: 10
   ```

---

## 14. Open Graph & Social Cards

### 14.1 Default OG Image

Use the 512x512 icon for now. Later, create a branded OG image (1200x630px) with:
- RadInsights logo
- Teal gradient background (#5E899E → #3d6575)
- Tagline: "High-Yield Radiology Education"
- Brand orange accent line

**Recommended: Create `/static/og-image.png` (1200x630)**

### 14.2 Per-Page OG Overrides

TNM calculator pages should override with calculator-specific OG:
```jinja2
{% block og_title %}{{ calculator.cancer_name }} TNM Staging | RadInsights{% endblock %}
{% block og_description %}Interactive AJCC TNM 8th Edition staging calculator for {{ calculator.cancer_name }}{% endblock %}
```

---

## 15. Performance & Core Web Vitals

### 15.1 Current Assessment

| Metric | Status | Notes |
|--------|--------|-------|
| **LCP** | Unknown | Landing page hero loads quickly (no large images) |
| **FID/INP** | Unknown | Bootstrap + FontAwesome loaded from CDN |
| **CLS** | Unknown | Inline styles reduce layout shift |
| **TTFB** | Likely good | Vercel Pro with CDN |

### 15.2 Recommendations

1. **Preconnect to CDNs** — add to base.html `<head>`:
   ```html
   <link rel="preconnect" href="https://cdn.jsdelivr.net" crossorigin>
   <link rel="preconnect" href="https://cdnjs.cloudflare.com" crossorigin>
   <link rel="preconnect" href="https://res.cloudinary.com" crossorigin>
   ```

2. **Defer non-critical CSS** — Consider loading FontAwesome asynchronously

3. **Image optimization** — Cloudinary icons should use `f_auto,q_auto` transforms

---

## 16. Monitoring & Analytics

### 16.1 Tools

| Tool | Purpose | Status |
|------|---------|--------|
| Google Search Console | Index coverage, search queries, crawl errors | Set up (verification present) |
| Google Analytics 4 | Traffic, conversions, user behavior | Check if implemented |
| Bing Webmaster Tools | Bing search visibility | Not set up |
| Schema.org Validator | Test structured data | Use after implementation |
| PageSpeed Insights | Core Web Vitals monitoring | Run after deployment |

### 16.2 KPIs to Track

| KPI | Target (6 months) |
|-----|-------------------|
| Organic impressions | 10,000/month |
| Organic clicks | 500/month |
| TNM calculator page clicks | 200/month |
| Landing page bounce rate | < 60% |
| Google rich result appearances | 20+ queries |

---

## 17. File Inventory

### 17.1 Files to Modify

| File | Phase | Changes |
|------|-------|---------|
| `templates/base.html` | P1, P2 | OG tags, Twitter cards, Schema.org Organization, canonical block, robots block, breadcrumb schema block, preconnect hints |
| `templates/landing.html` | P1, P2, P3 | OG tags, Twitter cards, Schema.org MedicalWebPage, title/description update, "Beyond the Shorthand" section |
| `templates/pricing.html` | P2, P4 | FAQ schema, title/description update |
| `templates/smart_reporter.html` | P4 | Title/description override |
| `templates/knowledge_hub.html` | P4 | Title/description override |
| `templates/essential_tnm_concepts.html` | P4 | Title/description update |
| `templates/radiology_protocols_user.html` | P4 | Title/description override |
| `templates/radiology_tools_user.html` | P4 | Title/description override |
| `templates/radiology_pearls_browse.html` | P4 | Title/description override |
| `templates/radiq.html` | P4 | Title/description override |
| `templates/about.html` | P4 | Title/description update |
| `app.py` | P5 | Dynamic sitemap route, canonical context processor |
| `templates/tnm_calculator.html` | P2, P4 | MedicalWebPage schema, breadcrumb schema, title/description |
| 10+ authenticated templates | P4 | `noindex` robots directive |

### 17.2 Files to Create

| File | Phase | Purpose |
|------|-------|---------|
| `static/og-image.png` | P1 | Branded 1200x630 OG image |

---

## 18. Implementation Checklist

### Pre-Phase: Public Preview Pages (DONE — March 31, 2026)
- [x] Create `public_routes.py` blueprint with `/case-library` and `/case-library/<id>` routes
- [x] Create `templates/public_case_library.html` with card grid, filters, search
- [x] Create `templates/public_case_preview.html` with content gating (fade overlay + CTA)
- [x] Create `templates/partials/_public_cta.html` reusable CTA banner
- [x] Create `templates/partials/_schema_medical.html` Schema.org JSON-LD macros
- [x] Remove `@login_required` from reporting algorithms browse + view
- [x] Remove `@login_required` from radiology templates browse + view (gated template text)
- [x] Remove `@login_required` from radiology tools browse + view
- [x] Remove `@login_required` from clinical protocols browse + view (gated content)
- [x] Remove `@login_required` from Knowledge Hub, anatomy snippets, pearls
- [x] Add OG tags + meta descriptions to all 14 public templates
- [x] Add Schema.org JSON-LD (CollectionPage, LearningResource, MedicalCondition) to public templates
- [x] Expand dynamic sitemap to 100+ URLs (cases, algorithms, templates, anatomy)
- [x] Update robots.txt with Allow directives for all public paths
- [x] Add noindex to authenticated-only templates (login, register, forgot-password, etc.)
- [x] Add `.gated-fade-overlay`, `.content-teaser`, `.public-cta-banner` CSS classes
- [x] Wrap auth-only template elements in `{% if current_user.is_authenticated %}` conditionals
- [x] Server-side truncation for case discussion (150 chars) — no content leaks in HTML source

### Phase 1 — Global Metadata
- [x] Add OG tags to `base.html` (og:type, og:title, og:description, og:image, og:url, og:site_name, og:locale)
- [x] Add Twitter Card tags to `base.html`
- [ ] Add OG + Twitter tags to `landing.html` (standalone template)
- [x] Add `{% block canonical %}` to `base.html`
- [x] Add `{% block robots_meta %}` to `base.html` with default `index, follow`
- [x] Add `<meta name="author" content="RadInsights">` to `base.html`
- [ ] Add `<link rel="preconnect">` hints for CDNs
- [x] Verify 512x512 icon URL is valid for OG image

### Phase 2 — Structured Data
- [ ] Add Organization JSON-LD to `base.html`
- [ ] Add MedicalWebPage + SoftwareApplication JSON-LD to `landing.html`
- [ ] Add MedicalWebPage JSON-LD to TNM calculator template
- [ ] Add FAQPage JSON-LD to `pricing.html`
- [x] Add `{% block extra_schema %}` to `base.html` (used by public templates)
- [ ] Add BreadcrumbList JSON-LD to TNM calculator pages
- [ ] Validate all structured data with Google Rich Results Test

### Phase 3 — Landing Page
- [ ] Update `<title>` to match SEO pattern
- [ ] Update `<meta description>` with target keywords
- [ ] Add `<meta name="keywords">` tag
- [ ] Add "Beyond the Shorthand" AI reporting section
- [ ] Ensure proper H1-H6 heading hierarchy
- [ ] Verify all CTAs link to /register

### Phase 4 — Per-Page SEO
- [x] Override `{% block title %}` in all public templates (12+ pages)
- [x] Override `{% block meta_description %}` in all public templates
- [x] Add `noindex, nofollow` to all authenticated-only templates (10+ pages)
- [ ] Add canonical URLs to all pages via context processor
- [x] Add OG overrides to key public pages (algorithms, templates, tools, protocols, knowledge hub, anatomy, cases)

### Phase 5 — Technical SEO
- [x] Replace static sitemap.xml with dynamic Flask route
- [x] Include TNM calculators, Knowledge Hub content in sitemap
- [ ] Update robots.txt with crawl-delay for aggressive bots
- [ ] Add canonical URL context processor
- [ ] Run PageSpeed Insights and fix any Core Web Vitals issues
- [ ] Submit updated sitemap to Google Search Console

### Phase 6 — Content Strategy
- [ ] Ensure all 39 TNM calculator pages have unique titles and descriptions
- [ ] Add internal links between related TNM calculators
- [ ] Create "Related Resources" component for public pages
- [ ] Set up Google Analytics 4 (if not already)
- [ ] Set up Bing Webmaster Tools
- [ ] Monitor Search Console for indexing issues weekly

---

> **Phase 1 (Public Preview Pages) COMPLETE.** Next step: Phase 2 — add Organization JSON-LD to `base.html`, MedicalWebPage + SoftwareApplication to `landing.html`, FAQPage to `pricing.html`, and OG tags to `landing.html` (standalone template).
