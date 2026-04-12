# RadInsights SEO Audit — April 2026

> Comprehensive audit of SEO implementation, gaps, and action items.
> Covers: meta tags, schema.org, sitemap, robots.txt, public routes, content gaps.

---

## 1. What's Working (DONE)

### Meta Tags (All Public Pages)
- Per-page `<title>` overrides on 28+ templates
- Per-page `<meta name="description">` on all public templates
- OG tags (og:type, og:title, og:description, og:image, og:url, og:site_name, og:locale=en_GB)
- Twitter Card tags (summary_large_image) on all public pages
- `<meta name="author" content="RadInsights">`
- Google Site Verification tag present
- Theme color + PWA manifest

### Structured Data
- Organization schema (global, in base.html) — name, URL, logo, contactPoint
- Medical schema macros in `_schema_medical.html`:
  - `medical_web_page()` — MedicalWebPage with audience, specialty
  - `medical_case()` — MedicalCondition for cases
  - `collection_page()` — CollectionPage for browse pages
  - `educational_content()` — LearningResource for educational pages
- FAQ schema on pricing page (6 Q&As — appears in rich snippets)

### robots.txt
- Allows all public content routes
- Blocks: `/api/`, `/auth/`, `/admin/`, `/stripe/`, `/dashboard`, `/study`, `/practice`
- Crawl delays for AhrefsBot and SemrushBot
- Sitemap reference

### Sitemap (Dynamic)
- 100+ URLs with `<lastmod>` from DB timestamps
- Covers: cases, TNM calculators, algorithms, templates, anatomy snippets, pearls, protocols
- Static pages: landing, pricing, about, knowledge-hub, etc.
- Appropriate priority and changefreq per page type

### Public Content Access
- Educational content fully public (no login): algorithms, tools, pearls, anatomy, knowledge hub
- Patient-adjacent content gated: cases (preview + CTA), protocols (gated), templates (first 4 lines)
- `noindex` on auth pages: login, register, forgot-password, verify-2fa, dashboard, study, practice

---

## 2. What's Partially Done

| Item | Status | Gap |
|------|--------|-----|
| Canonical URLs | ~6 pages | Missing on ~20 public pages |
| FAQ Schema | Pricing only | Landing page and About page have no FAQ schema |
| Medical Schema Macros | Created | Not applied to all public view templates |
| Per-page OG images | Default only | All pages use same generic OG image |
| Breadcrumb HTML | Present in mobile nav | No JSON-LD breadcrumb structured data |

---

## 3. What's Missing (TODO)

### HIGH PRIORITY — Schema.org

**Landing page missing critical schemas:**
- `SoftwareApplication` schema for Smart Reporter, TNM Calculators, RadIQ
- `MedicalWebPage` schema with `medicalAudience` and `specialty`
- These directly affect rich snippet appearance in Google for "radiology app" type queries

**Breadcrumb JSON-LD:**
- HTML breadcrumbs exist in mobile nav but no `BreadcrumbList` JSON-LD on public pages
- Breadcrumb rich snippets improve CTR by ~10-30%

**Per-page schemas:**
- Case view pages: should use `MedicalCondition` schema (macro exists, may not be applied everywhere)
- Tool pages (Fleischner, Bosniak, etc.): should use `MedicalWebPage` + `SoftwareApplication`
- TNM calculator pages: should use `MedicalWebPage` with `about: MedicalCondition`

### HIGH PRIORITY — Content Gaps

**No blog / content marketing:**
- Zero long-form SEO content
- Missing huge long-tail keyword opportunities
- Competitors rank for "Fleischner guidelines", "Bosniak classification", "TNM staging" etc.
- We have the tools but no blog articles driving organic traffic to them

**No email capture:**
- Landing page has no newsletter signup
- No lead magnet (PDF guide, cheatsheet, etc.)
- Losing all visitors who aren't ready to sign up immediately

### MEDIUM PRIORITY

| Item | Impact | Effort |
|------|--------|--------|
| hreflang tags (en-GB vs en-US) | Low-Medium | Low |
| Author/byline metadata on educational content | Low | Low |
| Per-page OG images (unique per content type) | Medium | Medium |
| Canonical URLs on remaining ~20 pages | Medium | Low |
| FAQ schema on landing + about pages | Medium | Low |

### LOW PRIORITY

- Local SEO (not needed for global SaaS)
- Video schema (no videos yet)
- Review/rating schema (no reviews yet)
- Samesite/alternate links

---

## 4. Content-Specific SEO Issues

### Landing Page (`landing.html`)
- **CRITICAL: Says "39 TNM calculators" — should say "72"**
- Does NOT extend `base.html` — standalone template with its own `<head>`. This means some global SEO elements may be duplicated or slightly different.
- Missing SoftwareApplication schema
- No FAQ section (pricing page has FAQ; landing should too)
- No testimonials or social proof (affects E-E-A-T signals)

### Pricing Page (`pricing.html`)
- FAQ schema present (6 Q&As) — good
- Clear pricing tables — good for "radiology app pricing" queries
- Missing: annual pricing, team/institution pricing
- Missing: comparison with competitors ("vs. textbooks", "vs. other tools")

### About Page (`about.html`)
- Strong personal brand (developer photo + credentials)
- Missing: clinical advisory board
- Missing: company story / founding narrative
- Missing: FAQ schema
- Description slightly too long (172 chars; ideal 150-160)

### Case Library Pages
- Public with preview + CTA — good
- Schema.org MedicalCondition macro exists — verify it's applied to all case view pages
- Missing: structured data for Q&A pairs (could use FAQ or QAPage schema)

### Knowledge Hub Pages
- Public — good
- LearningResource schema macro exists
- Verify applied to anatomy snippet view, pearl view, algorithm view pages

---

## 5. Sitemap Audit

### What's Included (Good)
- `/` (priority 1.0)
- `/pricing` (0.9)
- `/about` (0.7)
- `/tnm-calculator` (0.9)
- `/case-library` + individual cases
- `/reporting-algorithms` + individual algorithms
- `/radiology-protocols` + individual protocols
- `/incidental-findings` + individual calculators
- `/anatomy-snippets` + individual snippets
- `/radiology-pearls`
- `/knowledge-hub`
- `/contrast-reaction-card`
- `/learn/sba`, `/learn/viva`

### What's Missing
- Individual TNM calculator URLs (e.g., `/tnm-calculator/breast-cancer`) — sitemap has `/tnm-calculator` but not the 72 individual pages
- `/vetting-essentials` — not in sitemap? Verify.
- `/paediatric-ct-protocols` — not in sitemap? Verify.
- `/api/admin/ai-documentation` and other admin pages — correctly excluded (noindex)

---

## 6. Meta Description Audit

| Page | Length | Quality | Issue |
|------|--------|---------|-------|
| Landing | 158 chars | Good | Says "39 TNM calculators" — update to 72 |
| Pricing | 138 chars | Good | — |
| About | 172 chars | Good content, too long | Trim to 155 chars |
| Case Library | Varies | Dynamic per case | Verify not empty for published cases |
| Knowledge Hub | Default | May fall back to base description | Should have unique description |

---

## 7. Keyword Strategy

### Primary Keywords (Currently Targeting)
- "radiology companion" — landing page title
- "AI radiology reporting" — meta description
- "FRCR revision" — meta keywords
- "TNM calculator" — sitemap + landing
- "radiology education" — about page

### Keyword Opportunities (NOT Targeting Yet)
| Keyword | Search Volume | Competition | Our Advantage |
|---------|--------------|-------------|---------------|
| "Fleischner guidelines 2017" | High | Medium | We have the calculator |
| "Bosniak classification" | High | Medium | We have the calculator |
| "TI-RADS calculator" | Medium | Low | We have it built |
| "radiology report template" | High | High | We have AI + templates |
| "FRCR 2B revision" | Medium | Low | Perfect match |
| "radiology MDT preparation" | Low | Very Low | MDT Suite |
| "radiology vetting tool" | Low | Very Low | Unique feature |
| "AI radiology report" | Medium | Medium | Core feature |
| "contrast reaction protocol" | Medium | Low | 6-tab card |
| "TNM staging calculator" | Medium | Medium | 72 calculators |

### Blog Content Opportunities
Each of these could be a 1,500-word SEO article linking to our tools:

1. "Complete Guide to Fleischner Society 2017 Guidelines for Pulmonary Nodules" → links to IF calculator
2. "Bosniak Classification 2019: What Changed and Why" → links to Bosniak calculator
3. "FRCR 2B Revision Strategy: Structured Reporting Practice" → links to Smart Reporter
4. "TNM Staging Made Simple: A Radiologist's Guide" → links to 72 TNM calculators
5. "How to Write a Radiology MDT Summary" → links to MDT Suite
6. "AI in Radiology Reporting: What's Real in 2026" → links to Smart Reporter
7. "Contrast Reaction Management: ACR Guidelines Quick Reference" → links to Contrast Card
8. "Incidental Findings in Radiology: When to Follow Up" → links to all 6 IF calculators

---

## 8. Technical SEO

### Page Speed
- Vercel edge network — fast CDN delivery
- Lazy loading on images (`loading="lazy"`)
- Font preconnect for Google Fonts
- CSS/JS minification via Vercel build

### Mobile
- Responsive Bootstrap 5 layout
- Mobile navigation with breadcrumbs
- Mobile search functionality
- Touch-friendly UI elements

### Crawlability
- No JavaScript rendering requirements for public content (server-rendered HTML)
- Clean URL structure (semantic slugs)
- Internal linking between related content types (cases → algorithms → templates)

### Issues
- `landing.html` is standalone (doesn't extend `base.html`) — risk of SEO element drift
- Some pages may have duplicate content if same content appears at multiple URLs (e.g., algorithm in Knowledge Hub AND in reporting-algorithms)
- No `rel="next"` / `rel="prev"` for paginated content (if any)

---

## 9. Priority Action Plan

### Week 1 (Immediate Fixes) — DONE (Apr 12, 2026)
1. ~~Update "39 TNM calculators" to "72" on landing page + meta descriptions~~ DONE
2. ~~Add RadInsight Peer Review to landing page~~ DONE
3. ~~Add PII Guard to landing page security section~~ DONE
4. ~~Show all 5 RadIQ categories on landing page~~ DONE
5. ~~Trim About page meta description to 155 chars~~ DONE
6. ~~Add individual TNM calculator URLs to sitemap~~ Already present
7. ~~Add missing SEO phrases: "AI assisted radiology reporting", "radiology reporting module"~~ DONE
8. ~~Highlight undersold features: SBA/Viva, action buttons, vetting, forum, protocols~~ DONE

### Week 1b — Search Engine Submission (DO NOW)
9. Submit updated sitemap to Google Search Console (https://search.google.com/search-console)
10. Submit updated sitemap to Bing Webmaster Tools (https://www.bing.com/webmasters)
11. Request re-indexing of key pages in Google Search Console: /, /about, /pricing, /tnm-calculator
12. Request re-indexing in Bing Webmaster Tools for the same pages
13. Verify sitemap is accessible: https://www.radinsights.xyz/sitemap.xml
14. Check robots.txt is correct: https://www.radinsights.xyz/robots.txt

### Week 2-3 (Schema + Structure)
15. Add SoftwareApplication schema to landing page
16. Add BreadcrumbList JSON-LD to all public pages
17. Add canonical URLs to remaining ~20 public pages
18. Add FAQ schema to landing page (5-6 Q&As)
19. Verify MedicalCondition schema applied to all case view pages

### Month 2 (Content)
20. Create first 3 blog articles (Fleischner, Bosniak, FRCR revision)
21. Add email capture to landing page
22. Create FRCR study guide PDF lead magnet
23. Add testimonials section to landing page

### Month 3+ (Growth)
24. Remaining 5 blog articles
25. University/training program partnerships
26. Google Search Console monitoring + iterative keyword optimization
27. Internal linking strategy (each blog article links to 2-3 app features)
28. Consider Google Ads for high-intent keywords ("FRCR revision tool", "TNM calculator")
29. Bing Webmaster Tools monitoring + keyword analysis

---

## 10. Google Search Console & Bing Webmaster Tools

### Google Search Console (https://search.google.com/search-console)
- [ ] Submit sitemap: https://www.radinsights.xyz/sitemap.xml
- [ ] Request indexing for: /, /about, /pricing, /tnm-calculator, /knowledge-hub
- [ ] Resubmit sitemap after each major content deployment
- [ ] Monitor Coverage report for indexing errors
- [ ] Monitor Core Web Vitals (Vercel typically scores well)
- [ ] Check Search Performance for keyword opportunities
- [ ] Verify new public URLs are being crawled (case-library, protocols, anatomy snippets)
- [ ] Monitor for "Crawled but not indexed" issues (common with thin content pages)

### Bing Webmaster Tools (https://www.bing.com/webmasters)
- [ ] Submit sitemap: https://www.radinsights.xyz/sitemap.xml
- [ ] Request indexing for key pages
- [ ] Verify site ownership (meta tag or DNS)
- [ ] Monitor search performance for "radiology reporting module", "AI assisted radiology reporting"
- [ ] Check keyword rankings monthly
