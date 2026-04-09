# RadInsights — Comprehensive TODO & Roadmap

**Generated:** 2026-03-13 | **Last updated:** 2026-04-08
**Sources:** UK GDPR Gap Analysis, Security Audit, Feature Completeness Audit, Production Readiness Audit, Content Coverage Audit, Code Quality Audit, Vetting Gaps Closeout Audit (Apr 2026)

### Progress Summary

| Status | Count |
|--------|-------|
| DONE | **68** / 107 |
| WONTFIX | 2 / 107 |
| TODO | **37** / 107 |
| **Completion** | **64%** |

---

## Status Legend

| Symbol | Meaning |
|--------|---------|
| DONE | Completed (Mar 2026 session) |
| TODO | Not yet started |
| WONTFIX | Assessed and intentionally skipped |

---

## TIER 1 — CRITICAL (Do Before Public Launch)

### 1.1 Security

| # | Item | Status | Details |
|---|------|--------|---------|
| 1 | Remove debug routes from `auth.py` | DONE | Removed `/auth/test-email`, `/auth/test-send-email`, `/auth/reset-password-test`, `/auth/reset-password-simple`, `/auth/debug`, `/auth/debug/verify-db-users` |
| 2 | PII Guard — remove email from SKIP_KEYS | DONE | Removed `'email'` from both `pii_guard.py` and `pii-guard.js` SKIP_KEYS |
| 3 | PII Guard — add NINO pattern | DONE | Added `[A-Z]{2}\d{6}[A-D]` to both client and server |
| 4 | PII Guard — sync client skip routes with server | DONE | Added `/on-call-helper/admin/`, `/incidental-findings/admin/`, `/admin/reporting-algorithms/` to `pii-guard.js` |
| 5 | DB SSL enforcement | DONE | Appends `sslmode=require` to DATABASE_URL if missing. **File:** `app.py` |
| 6 | Encrypt sensitive API tokens in DB | DONE | `EncryptedText` TypeDecorator with Fernet applied to `notion_access_token`, `anki_api_key`, `sciencedirect_session_cookies`. **File:** `models.py` |
| 7 | Content-Security-Policy header | DONE | CSP header added in `add_security_headers`. **File:** `app.py` |
| 8 | Forum image upload — add magic byte validation | DONE | Added `_validate_image_magic(file)` check before content-type check in `upload_forum_image()` |
| 9 | File upload filename sanitization | DONE | `re.sub(r'[^a-zA-Z0-9._-]', '_', os.path.basename(file.filename))` in `upload_case_image()` |
| 10 | Cron job auth — enforce CRON_SECRET always | DONE | Rewritten: debug mode allows, production requires CRON_SECRET configured, logs error if missing |
| 11 | HTML sanitizer — script/event handlers | WONTFIX | Assessed: all call sites are behind `@require_admin`. Sanitizer processes only trusted admin/AI content, not user input. Safe by design. |
| 12 | Password complexity requirements | WONTFIX | User explicitly declined: "we do not want to make password complex as for now" |

### 1.2 UK GDPR / Legal

| # | Item | Status | Details |
|---|------|--------|---------|
| 13 | Privacy policy — comprehensive rewrite | DONE | Added: third-party processors (Anthropic, Cloudinary, Resend, Neon, Vercel, OneDrive, Notion), AI processing disclosure, breach notification (ICO 72h), data retention periods, IP logging, DPIA summary, expanded rights. **File:** `templates/privacy_policy.html` |
| 14 | Cookie consent banner (PECR) | DONE | Added PECR-compliant banner with localStorage persistence. **File:** `templates/base.html` |
| 15 | AI processing disclosure in Smart Reporter | DONE | Added note: "Powered by AI — your input is processed by Anthropic's Claude. Do not enter patient-identifiable data." **File:** `templates/smart_reporter.html` |
| 16 | Auto-purge expired soft-deleted accounts | DONE | If `is_deleted=True` and `deleted_at + 31 days < now()`, calls `delete_user_completely()` at login check. **File:** `auth.py` |
| 17 | Contact email inconsistency | DONE | Standardized to `contact@radinsights.xyz` across terms of use, privacy policy, and base.html footer |
| 18 | Medical non-diagnostic disclaimer | DONE | Added disclaimers to smart_reporter, reporting_algorithms_browse, reporting_templates_browse, radiology_protocols_user, student_dashboard. Existing disclaimers verified on 9 other pages. |

### 1.3 Error Handling

| # | Item | Status | Details |
|---|------|--------|---------|
| 19 | Create error pages (404, 500, 403) | DONE | Created branded `templates/errors/404.html`, `500.html`, `403.html` with brand styling and recovery links |
| 20 | Register error handlers in `app.py` | DONE | Added `@app.errorhandler(404)`, `@app.errorhandler(500)`, `@app.errorhandler(403)` — returns JSON for `/api/` routes, HTML templates for pages |

---

## TIER 2 — HIGH PRIORITY (Before Feature Expansion)

### 2.1 Security Hardening

| # | Item | Status | Details |
|---|------|--------|---------|
| 21 | General API rate limiting | DONE | `flask-limiter` with 200/min default. Stricter: register 5/hr, login 10/min, forgot-password 5/hr |
| 22 | Backup exports — add encryption | DONE | `?encrypted=true` param → AES-256 Fernet encrypted ZIP. Key derived from SECRET_KEY |
| 23 | Image EXIF stripping | DONE | `_strip_exif()` via Pillow strips GPS/device metadata before Cloudinary upload (case + forum) |
| 24 | Hardcoded superadmin email | DONE | Removed default fallback. Returns early with warning log if `SUPERADMIN_EMAIL` not set |
| 25 | Display name impersonation prevention | DONE | Blocklist: admin, administrator, moderator, support, system, radinsights, staff, superadmin |

### 2.2 Monitoring & Observability

| # | Item | Status | Details |
|---|------|--------|---------|
| 26 | Error tracking service (Sentry) | DONE | `sentry-sdk[flask]` with Flask + SQLAlchemy integrations. PII scrubbed via `before_send` (no cookies, auth headers, request bodies, IPs). Set `SENTRY_DSN` env var to activate. Privacy policy updated. |
| 27 | Health check endpoint | DONE | `GET /health` returns `{"status": "ok", "database": "ok"}` with DB connection check |
| 28 | Structured logging (JSON format) | DONE | Production uses JSON formatter (`_JSONFormatter`); local dev uses human-readable format |
| 29 | Slow query logging | DONE | SQLAlchemy `before/after_cursor_execute` listeners log queries > 1s to `slow_query` logger |

### 2.3 Production Infrastructure

| # | Item | Status | Details |
|---|------|--------|---------|
| 30 | Automated database backups | DONE | Cron endpoint `GET /api/backup/scheduled-backup` — builds backup JSON, gzip-compresses, uploads to R2. Keeps last 30 backups, auto-prunes older. Runs daily at 2am UTC via Vercel cron. |
| 31 | `robots.txt` | DONE | `GET /robots.txt` disallows admin/API/auth routes. Updated Mar 2026: allows `/case-library`, `/reporting-algorithms`, `/reporting-templates`, `/incidental-findings`, `/radiology-protocols`, `/knowledge-hub`, `/anatomy-snippets` |
| 32 | SEO meta tags | DONE | `base.html` supports `{% block title %}` and `{% block meta_description %}` — templates can override. OG + Twitter Card tags added. |

---

## TIER 3 — MEDIUM PRIORITY (Improve Quality)

### 3.1 Code Architecture

| # | Item | Status | Details |
|---|------|--------|---------|
| 33 | Split `app.py` (5,212 lines) | TODO | Monolithic file with 124 functions. Split into: `config.py`, `error_handlers.py`, `case_routes.py`, `forum_routes.py`, `image_routes.py`, etc. |
| 34 | Split `models.py` (2,995 lines, 56 classes) | TODO | Organize into `models/user.py`, `models/case.py`, `models/reporting.py`, `models/clinical.py`, etc. |
| 35 | Consolidate duplicate `_call_claude()` helpers | DONE | Created `ai_client.py` with `call_claude()`, `parse_json_response()`, `strip_markdown_fences()`. All 3 AI modules now import from shared module. |
| 36 | Consolidate duplicate JSON parsing | DONE | `parse_json_response()` and `strip_markdown_fences()` in `ai_client.py`. Used by `ai_smart_reporter.py` and `clinical_tool_generator.py`. |
| 37 | Consolidate duplicate `format_resources_for_prompt()` | DONE | Removed duplicate from `ai_smart_reporter.py`, now imports from `clinical_tool_generator.py` (superset version). |
| 38 | Standardize API response format | TODO | Inconsistent: `{error: ...}`, `{success: true}`, `{message: ...}`, `{results: [...]}`. Define standard wrapper (success/error/meta). |
| 39 | Standardize error exception classes | DONE | All 5 AI error classes now inherit from `AIClientError` base class. Callers can catch any AI error via `AIClientError`. |

### 3.2 Testing

| # | Item | Status | Details |
|---|------|--------|---------|
| 40 | Set up pytest configuration | DONE | Created `pytest.ini`, `tests/conftest.py` with fixtures, `tests/test_routes.py` (13 smoke tests), `tests/test_ai_client.py` (13 unit tests). 26/26 pass. |
| 41 | Add route/integration tests | DONE | Created `tests/test_integration.py` — 26 integration tests: auth flows (register, login, logout, lockout), case CRUD, admin access control, algorithm verify, content requests. 58 total tests pass. |
| 42 | Add CI/CD pipeline (GitHub Actions) | DONE | `.github/workflows/test.yml` — runs pytest on push/PR to main. Python 3.11, pip cache. |
| 43 | API documentation (OpenAPI/Swagger) | TODO | 269 routes, no documentation. At minimum document the public-facing API endpoints. |

### 3.3 UX / Feature Gaps

| # | Item | Status | Details |
|---|------|--------|---------|
| 44 | Pagination on admin lists | DONE | Admin case list: page/per_page params with Bootstrap pagination controls. Admin user list already had pagination. |
| 45 | Pagination on algorithm search (limit=50 hardcoded) | DONE | Added `offset` param to `/api/algorithms/search`. Response includes `has_more`, `total`, `offset` for "load more" support. |
| 46 | Bulk admin operations | TODO | No bulk delete, publish, or reassign for cases/algorithms. |
| 47 | Content moderation queue | DONE | "Moderation" tab in admin dashboard with badge counter. Shows pending/completed/declined content requests + user algorithm drafts. Publish/decline/delete actions. Lazy-loads on tab click. Endpoints: `/api/admin/moderation/counts`, `/moderation/user-drafts`, `/moderation/user-drafts/<id>/publish`. |
| 48 | Notion image caching | TODO | Notion-hosted image URLs expire after ~1 hour. Need to re-host to Cloudinary on fetch. **File:** `notes_integration_routes.py:76, 188, 341` |

### 3.4 Additional GDPR Items

| # | Item | Status | Details |
|---|------|--------|---------|
| 49 | 2FA for admin accounts | DONE | TOTP 2FA via `pyotp` + `qrcode`. Setup in admin dashboard (Users tab), verify page at `/auth/verify-2fa`. Secret encrypted via `EncryptedText`. 5-attempt limit, 5-min session window. Disable requires valid code. |
| 50 | Immutable audit logs | TODO | Current audit logs in same DB — can be modified by DB admin. Consider append-only log table or external log service. |
| 51 | Data retention cleanup cron | DONE | `GET /api/cron/data-retention-cleanup` — deletes expired recovery codes (7d), approval codes (30d), old TNM jobs (90d). Cron-authenticated. |
| 52 | IP logging documented in privacy policy | DONE | Added in privacy policy rewrite. |

---

## TIER 4 — LOW PRIORITY / NICE-TO-HAVE

### 4.0 SEO & Public Access (Mar 2026)

| # | Item | Status | Details |
|---|------|--------|---------|
| 73 | Public preview pages for all content types | DONE | Created `public_routes.py` blueprint. Removed `@login_required` from algorithms, templates, tools, protocols, knowledge hub, anatomy, pearls. Content gating: educational content fully public, patient-adjacent content gated with CTA. |
| 74 | Schema.org JSON-LD structured data | DONE | Created `templates/partials/_schema_medical.html` with macros: `medical_web_page()`, `medical_case()`, `collection_page()`, `educational_content()`. Applied to all public browse + view pages. |
| 75 | Dynamic sitemap expansion (100+ URLs) | DONE | `sitemap_xml()` now includes 6 new static pages + dynamic URLs for published cases, admin algorithms, admin templates, anatomy snippets. Expanded from ~43 to 100+ URLs. |

### 4.1 Code Quality

| # | Item | Status | Details |
|---|------|--------|---------|
| 53 | Run `flake8 --select=F401` to find unused imports | DONE | Removed 5 unused imports: `engine_from_config` (app.py), `flash` (auth.py), `timedelta` (backup_routes.py), `url_for` + `SmartReporterError` (reporting_routes.py). |
| 54 | Remove deprecated `ReportingTemplate` legacy model | DONE | Removed ORM class from `models.py`. Migration function in `app.py` rewritten to use raw SQL (no ORM dependency). Backup import already used new models. |
| 55 | Remove deprecated `Algorithm Finder` route | DONE | Removed redirect route from `reporting_routes.py`. No remaining references in templates or JS. |
| 56 | Split `static/style.css` (5,613 lines) | TODO | Organize into component-based CSS files (`variables.css`, `buttons.css`, `modals.css`, etc.). |
| 57 | Organize templates into subfolders | TODO | 54 templates in flat structure. Move to `auth/`, `admin/`, `reporting/`, `cases/`, etc. |
| 58 | Input validation with Marshmallow | TODO | No schema validation for request parameters. Add `marshmallow` for API request validation. |
| 59 | Update dependencies | TODO | Flask 2.3.3 (latest 3.x), Werkzeug 2.3.7 (latest 3.x), etc. Update quarterly. |
| 60 | API versioning | TODO | No version prefix on API routes. Use `/api/v1/` for future compatibility. |

### 4.2 Accessibility & SEO

| # | Item | Status | Details |
|---|------|--------|---------|
| 61 | WCAG 2.1 AA audit | TODO | ARIA labels partially applied. Color contrast unverified. No skip links. |
| 62 | Dynamic page titles | DONE | Added `{% block title %}` to 28 templates with context-specific titles (e.g. "Smart Reporter - RadInsights"). |
| 63 | Sitemap.xml | DONE | `GET /sitemap.xml` generates dynamic XML sitemap. Updated Mar 2026: now includes published cases, algorithms, templates, anatomy snippets (100+ URLs). |
| 64 | Skip-to-content link | DONE | Added `<a href="#main-content" class="visually-hidden-focusable skip-link">` in `base.html` with `id="main-content"` target on content div. |

### 4.3 Admin UX

| # | Item | Status | Details |
|---|------|--------|---------|
| 71 | Shared HTML syntax highlighting editor | TODO | Extract `highlightHTML()` + scroll sync from `edit_reporting_algorithm.html` into `static/js/html-syntax-highlight.js`. Expose `initSyntaxEditor(textareaId, highlightId)`. Apply to: TNM calculator edit, Radiology Tools admin, Clinical Protocols admin, Anatomy snippet add modal. |
| 72 | Protocol nav tab not active | TODO | Verify why the Protocols nav tab is not highlighted as active when working with protocols. Likely same Jinja2 `{% block %}` inside `{% if %}` issue fixed for anatomy snippets (commit e3d7973). Check protocol templates for correct `tool_active_protocols` block definition. |
| 76 | RadInsight Intelligence — User Reporting Preferences | TODO | Track user editing patterns (placeholder rejections, correction rejections, fill-in defaults) and inject as preference rules into Smart Reporter prompts. JSONB column on User model, ~200 token preference section, 3-occurrence activation threshold. **Plan:** `docs/plans/RADINSIGHT_INTELLIGENCE_PLAN.md`. **Note:** Low priority — future suggestion only. |
| 77 | Vetting Tool — Core Workflow (Phases 1-3) | DONE | Fully deployed: 3 AI functions (analysis, protocol gen, shorthand extraction), 23 API routes, 4 templates, 3 DB models (ImagingProtocol, VettingSession, VettingAlgorithm), 50 protocols + 20 algorithms imported, Quick Clean mode, speech-to-text, algorithm-guided protocol generation. **Plan:** `docs/plans/VETTING_TOOL_PLAN.md` |
| 78 | Vetting Tool — Session History Browser | TODO | Users cannot review past vetting sessions. Add `/vetting/history` route, list API, browse template. Data already saved in VettingSession model. |
| 79 | Vetting Tool — TinyMCE Inline Editing on Output | TODO | Output sections (clinical details, shorthand, detailed protocol) are read-only with copy buttons. Add inline editing so users can tweak before copying. |
| 80 | Vetting Tool — Publish Draft Protocols & Algorithms | TODO | 49 admin protocols in draft, 20 algorithms in draft. Need admin review, verification, and publishing to make them available in the protocol picker during vetting. |
| 81 | Vetting Tool — Protocol Usage Analytics | TODO | Track which protocols are used most frequently via VettingSession.protocol_id. Display usage count in admin protocol list. |
| 82 | Create Elite Pro price in Stripe dashboard | TODO | Create a new recurring price in Stripe for Elite Pro tier: £99/mo (launch) / £120/mo (post-launch). Note the price ID. |
| 83 | Set STRIPE_ELITE_PRO_PRICE_ID env var on Vercel | TODO | After creating the Stripe price (#82), set `STRIPE_ELITE_PRO_PRICE_ID` env var in Vercel project settings. Code in `stripe_routes.py` already reads this var. |
| 84 | Smart Reporter — Regeneration workflow | DONE | Finalize→Regenerate button transformation, confirm dialog, Go+Cancel buttons, regen question prefix ("Rewrite and finalize..."), auto-insert into PACS, Opus routing. E2E tested Apr 2026. |
| 85 | Smart Reporter — Post-finalization UX polish | DONE | Sonnet full_report frontend guard, stale report text cleanup, model badge on all endpoints, Changes Made auto-collapse, markdown rendering, fill-in edit guard, textarea resize fix. |
| 86 | Smart Reporter — Action card management | DONE | MDT/Email replace-on-regen with confirmation, SBA/Viva always stack new cards, collapsible action history, MDT switched from Haiku to Sonnet. |

### 4.4 Performance

| # | Item | Status | Details |
|---|------|--------|---------|
| 65 | Application-level caching (Redis) | TODO | No Redis/Memcached. Repeated DB queries for same data. |
| 66 | Async job queue for AI generation | TODO | Background tasks run synchronously in request handler. Consider Celery/RQ. |
| 67 | Query optimization (N+1) | TODO | Multiple `Case.query.filter()` without `.options()` loading. Profile with SQLAlchemy analysis. |
| 103 | Anthropic prompt caching for large system prompts | TODO | **Revisit post-launch (~500+ paying users).** Add `cache_control: {type: "ephemeral"}` to large stable system prompts (MDT_SYSTEM_PROMPT ~1100 tokens, Smart Reporter Opus prompts ~3000+ tokens) to get a ~25% input-cost reduction on warm calls within a 5-minute window. Trade-offs: 7% surcharge on the FIRST call in any window, cache invalidates on every prompt edit (so don't enable while prompts are still being iterated), cache TTL only 5 minutes. **Estimated saving:** ~$15/mo at 100 active users, ~$1,800/yr at 1,000 users, ~$18,000/yr at 10,000 users. **Highest-leverage targets:** Smart Reporter Opus finalize prompt (largest), MDT_SYSTEM_PROMPT, vetting analysis prompt. **Why park:** absolute spend at current scale is rounding-error, prompts still iterating, complexity in monitoring (4 token types in usage logs vs 2). **Code change:** ~1 line per prompt. **Implementation note:** test PR4 of `_call_claude` wrapper to thread cache_control through transparently. **See full pros/cons analysis in commit message of this entry.** |

### 4.5 Other

| # | Item | Status | Details |
|---|------|--------|---------|
| 68 | DICOM header stripping | TODO | Files on user's OneDrive, not processed locally. Document user responsibility in privacy policy. Low priority. |
| 69 | Analytics integration | TODO | No Google Analytics/Mixpanel. No visibility into user behavior or feature adoption. |
| 70 | Deployment runbook | DONE | Created `docs/DEPLOYMENT_RUNBOOK.md` — env vars, Vercel deployment, Neon DB, monitoring, cron, backup/restore, disaster recovery, rollback, common issues. |

---

## CONTENT CREATION (Separate Track)

See `docs/content-creation-plan.md` for full details. Keyword: `RADINSIGHTS-CONTENT-BATCH-2026`

### Current State (Mar 2026)

| Content Type | Current | Target | % Complete |
|---|---|---|---|
| Cases | 36 | 86+ | 42% |
| TNM Calculators | 39 | 39 | 100% |
| Reporting Algorithms | 4 admin | 60+ | 7% |
| Radiology Templates | 1 admin | 65+ | 2% |
| Radiology Tools | 1 | 30+ | 3% |
| Clinical Protocols | 20 | 30+ | 67% |

### Critical FRCR Gaps

| Subspecialty | Cases | Gap |
|---|---|---|
| Paediatric Radiology | **0** | **CRITICAL** — 8-10 needed for FRCR 2B |
| Cardiothoracic | 3 | HIGH — 10-12 needed |
| Breast Imaging | 0 | HIGH — 4-6 needed |
| Musculoskeletal | 5 | MEDIUM — 10-12 needed |
| Interventional | 0 cases | MEDIUM — protocol-only coverage |

### Batch Generation Commands

```bash
# Phase 1 (55 items, ~$5.30 batch API)
PYTHONUNBUFFERED=1 python scripts/batch_algorithms.py batch --phase 1
PYTHONUNBUFFERED=1 python scripts/batch_templates.py batch --phase 1
PYTHONUNBUFFERED=1 python scripts/batch_tools.py batch --phase 1
PYTHONUNBUFFERED=1 python scripts/batch_protocols.py batch --phase 1

# Phase 2 (62 items + 30 cases, ~$9.20)
PYTHONUNBUFFERED=1 python scripts/batch_algorithms.py batch --phase 2
PYTHONUNBUFFERED=1 python scripts/batch_templates.py batch --phase 2
# Cases: manual creation (50 total across phases)
```

---

## COMPLETED ITEMS (Mar – Apr 2026 Sessions)

68 of 97 items completed. Key implementations:

1. **PII Guard email bypass fix** — removed `'email'` from SKIP_KEYS in both layers
2. **PII Guard NINO pattern** — added `[A-Z]{2}\d{6}[A-D]` detection
3. **PII Guard route sync** — client skip prefixes match server
4. **DB SSL enforcement** — auto-appends `sslmode=require`
5. **Token encryption** — `EncryptedText` TypeDecorator with Fernet for 3 token columns
6. **Auto-purge soft-deleted accounts** — 31-day expiry at login check
7. **Privacy policy rewrite** — 14 sections, full UK GDPR compliance
8. **Cookie consent banner** — PECR-compliant with localStorage
9. **AI disclosure in Smart Reporter** — note with link to privacy policy
10. **CSP header** — Content-Security-Policy covering all CDN resources
11. **Column widening migration** — `notion_access_token`, `anki_api_key` widened to TEXT for encryption
12. **Debug routes removed** — `/auth/test-email`, `/test-send-email`, `/reset-password-test`, `/reset-password-simple`, `/debug`, `/debug/verify-db-users`
13. **Error pages (404/500/403)** — branded templates + error handlers (JSON for API routes, HTML for pages)
14. **Forum image magic byte validation** — `_validate_image_magic()` check added
15. **Filename sanitization** — `re.sub()` + `os.path.basename()` for case image uploads
16. **Cron auth hardened** — requires `CRON_SECRET` in production, logs error if missing
17. **Contact email standardized** — all pages now use `contact@radinsights.xyz`
18. **Superadmin email env var** — removed hardcoded default, requires `SUPERADMIN_EMAIL` env var
19. **Display name blocklist** — blocks admin/moderator/support/system/staff impersonation
20. **Health check endpoint** — `GET /health` with DB connection check
21. **robots.txt** — disallows admin, API, auth, backup routes
22. **SEO meta tags** — `{% block title %}` + `{% block meta_description %}` in base.html
23. **Rate limiting** — flask-limiter: 200/min default, 5/hr register, 10/min login, 5/hr forgot-password
24. **Backup encryption** — `?encrypted=true` → AES-256 Fernet encrypted ZIP
25. **EXIF stripping** — `_strip_exif()` via Pillow on case + forum image uploads
26. **Structured JSON logging** — production uses JSON formatter, local uses human-readable
27. **Slow query logging** — SQLAlchemy event listeners log queries > 1s
28. **Sentry error tracking** — `sentry-sdk[flask]` with PII scrubbing, admin monitoring tab
29. **Automated daily backups** — cron → gzip → R2 upload, 30-day retention, auto-prune
30. **Consolidate AI helpers** — shared `ai_client.py` with `call_claude()`, `parse_json_response()`
31. **AI error class hierarchy** — all AI errors inherit from `AIClientError`
32. **pytest + CI/CD** — 58 tests (smoke + integration), GitHub Actions pipeline
33. **Pagination** — admin case list + algorithm search with offset/has_more
34. **Content moderation queue** — admin dashboard tab with badge, publish/decline/delete actions
35. **2FA for admin accounts** — TOTP via `pyotp`, setup on profile page, 5-attempt lockout
36. **Data retention cron** — auto-cleanup expired recovery codes, approval codes, old TNM jobs
37. **Dynamic page titles** — `{% block title %}` on 28 templates
38. **Sitemap.xml** — dynamic XML with cases, templates, algorithms, calculators
39. **Skip-to-content link** — accessible skip link in `base.html`
40. **Deployment runbook** — comprehensive `docs/DEPLOYMENT_RUNBOOK.md`
41. **Unused imports removed** — 5 unused imports cleaned up via flake8
42. **Legacy ReportingTemplate removed** — ORM class removed, migration uses raw SQL
43. **Algorithm Finder redirect removed** — deprecated route cleaned up
44. **Medical disclaimers** — added to Smart Reporter, browse pages, student dashboard
45. **Service worker CSP fix** — fixed 503 errors from CDN resources blocked by CSP
46. **Public preview pages** — all content types publicly accessible (algorithms, tools, protocols, templates, cases, knowledge hub, anatomy, pearls). Content gating with fade overlay + CTA for patient-adjacent content. 5 new files, 14 modified files.
47. **Schema.org JSON-LD macros** — `_schema_medical.html` with CollectionPage, LearningResource, MedicalCondition, MedicalWebPage macros. Applied to all public templates.
48. **Dynamic sitemap expansion** — sitemap now includes published cases, algorithms, templates, anatomy snippets. Expanded from ~43 to 100+ URLs.
49. **OG/Twitter Card meta tags** — all public templates now have Open Graph + Twitter Card tags via `{% block og_title/og_description %}`
50. **noindex on auth pages** — login, register, forgot-password, reset-password, verify-2fa, account-deactivated templates now have `noindex, nofollow`
51. **Smart Reporter Regeneration workflow** — Finalize→Regenerate button transformation, confirm dialog, Go+Cancel buttons, regen question prefix, auto-insert into PACS, Opus routing via `_isRegenMode`
52. **Smart Reporter post-finalization UX** — Sonnet full_report guard (frontend blocks unwanted PACS replacement), stale report text cleanup, model badge on report actions, Changes Made auto-collapse on action generation
53. **Smart Reporter action card management** — MDT/Email replace-on-regen with confirmation, SBA/Viva stack new cards, collapsible action history with expand/collapse toggle
54. **Vetting source rebrand** — 124 ImagingProtocol rows rebranded to canonical "RadInsights Protocols — enriched by publicly available guidelines and resources" (idempotent migration with `<!-- src:radinsight-v1 -->` sentinel)
55. **Vetting Gaps PR1 — imaging protocols** (commit `1be7120`) — 7 new protocols added via idempotent migration: CT GI Bleed, CT Brain Dementia, CT Anastomosis Leak, CT Liver 4-Phase HCC, CT IAMs, CT Subclavian Angio, CT Renal Cyst Characterisation
56. **Vetting Gaps PR2 — prompt + templates** (commit `0290bbb`) — `_WBCT_CRITERIA_BLOCK` in ai_vetting.py (RCR 2024 triage verbatim, GCS<14/SBP<90/RR<10>29/SaO2<93%); CTPA-pregnancy protocol (Litmanovich AJR 2009); AJR DOI backfill on bladder-cancer + CTPA; 2 RCR trauma report templates (Primary + Secondary Survey WBCT) in `radiology_template` table
57. **Vetting Gaps PR3 — RadiQ + UX + calculator** (commit `49cbe83`) — RadiQ `_find_relevant_db_content` now searches `ImagingProtocol` on 24 protocol-related keywords and surfaces matches as links; Pregnancy "do-not-insert-unless-confirmed" UX with mandatory rationale textarea; KOC Omnipaque weight-based iodine calculator in Contrast Card Tab 6 (concentration 240/300/350, target 1.2/1.5/2.0 g I/kg, live volume/total iodine/mg I/kg output)
58. **NICE cache scraper** — `scripts/nice_cache.py` local-only scraper (not committed) with robots.txt+rate-limit+checksum-dedup; `data/nice_cache/` gitignored; hybrid path for internal admin-only JSON decision trees
59. **ACR Contrast Block** — `docs/vetting/ACR_CONTRAST_BLOCK_2025.md` committed; `_ACR_CONTRAST_BLOCK` wired into `ANALYSIS_SYSTEM_PROMPT` + `PROTOCOL_SYSTEM_PROMPT` in ai_vetting.py
60. **Contrast Reaction Card module** — 6-tab unified module (`_contrast_reaction_card.html`): Premedication / Acute Reactions / Extravasation / Renal+CI-AKI / Special Populations / Paediatric Calculator; used in vetting drawer, protocols #1/#11, standalone `/contrast-reaction-card` public SEO page

---

## SEO / Google Search Console — Pending (Apr 2026)

After each content-expansion deploy, the dynamic sitemap grows. Items to action:

- **#84** Resubmit `sitemap.xml` in Google Search Console (https://search.google.com/search-console) after the Apr 8 vetting gaps deploy — new URLs: 7 imaging protocols, 2 trauma templates, CTPA-pregnancy protocol, contrast reaction card public page
- **#85** Verify indexation of `/contrast-reaction-card` (should be indexed with Schema.org `LearningResource`)
- **#86** Verify indexation of `/vetting/protocols` browse page and child `/vetting/protocols?search=<slug>` deep links
- **#87** Run GSC "URL Inspection" tool on 3 sample new protocol URLs to confirm `<lastmod>` is honoured
- **#88** Review GSC Coverage report for any 404 / soft-404 regressions from the source rebrand migration (should be none — URLs unchanged)
- **#89** Follow `docs/plans/SEO_MASTER_PLAN.md` Phases 2-6 (keyword: `RADINSIGHTS-SEO-2026`) — Phase 1 complete; Phase 2 (internal linking), Phase 3 (E-A-T signals), Phase 4 (schema upgrades), Phase 5 (link building), Phase 6 (analytics)
- **#90** Add canonical URL tags to all paginated browse pages (currently only browse root is canonical)
- **#91** Audit Core Web Vitals on GSC Experience report; address any LCP/CLS regressions from the new Contrast Reaction Card drawer
- **#92** Submit `/contrast-reaction-card` + 7 new protocols to Bing Webmaster Tools
- **#93** Add RSS/Atom feed for new pearls + protocols (indexation accelerator)

---

## NEXT SPRINT — Apr 8, 2026 User Report (DO NEXT)

These items come from direct user testing on Apr 8. They are **the next priority** after the vetting gaps closeout deploy has stabilised.

### Smart Reporter — Anatomy Snippet + Action Persistence

- **#94** Anatomy snippet DB search unreliable — existing snippets in DB sometimes not returned by search; when a match IS found the UI still shows "no snippet found" banner, and the rendered result is not clickable. Need to audit `/api/anatomy/search` (or equivalent) response handling in Smart Reporter frontend, and fix the state where a match exists but the UI reports none.
- **#95** Anatomy snippet session persistence — if user generates more than one anatomy snippet in a single session, keep the earlier snippets rendered but auto-collapse them (pattern: mirror Changes Made / action card collapse behaviour). New generation should expand, previous should collapse.
- **#96** Universal session-output persistence — ALL generated outputs in a Smart Reporter session (anatomy snippets, MDT notes, Email Colleague, Email Patient, SBA, Viva, every action button output) should persist in the UI (collapsed if not currently active) until the user explicitly clicks Dismiss / Close. Currently some outputs disappear on re-action. Audit `askClaude` + report-action response handlers.

### Smart Reporter — Safari Dictation

- **#97** Safari: dictation text is being auto-inserted **twice** into the report text area. Likely a duplicate event listener or race between Web Speech API `result` and `speechend` callbacks on WebKit. Need Safari-specific event dedup (the fix probably belongs in `static/js/dictation.js` or wherever the SpeechRecognition bindings live).
- **#98** "stop" voice command not working — currently literally types the word "stop" instead of terminating dictation. Need to intercept the transcript before insertion and match command keywords (`stop`, `end`, `finish`).
- **#99** "new line" voice command not working — nothing happens; should insert `\n` at cursor. Add to the voice-command interceptor alongside "stop".

### Vetting — Protocol Matching Miss

- **#100** Appendicitis test case returns "No library protocol matched" despite DB containing a CT Abdomen/Pelvis with IV contrast protocol. Test referral: *"65-year-old male presented with abdominal pain. Initially central but then progressed to right iliac fossa. One episode of vomiting. Low-grade fever. White blood cell count 14, C-reactive protein 34."* AI correctly cites **RCR iRefer CT abdomen pelvis with IV contrast for suspected appendicitis in adults with clinical features** but the library match fails and falls back to AI generation. Audit `vetting_routes.py::_search_protocols` + the AI protocol-matching step — likely the appendicitis protocol has a slug/title that doesn't match the indication keywords. May need to add "appendicitis" to `keywords` or `indication_json.symptoms` on the CT AP with IV contrast row.

### ImagingProtocol DB Cleanup — KOC Replacement + Aberdeen ARI Scrub

- **#101** Identify all ImagingProtocol rows where `detailed_protocol_html` or `positioning` section contains the literal string **"Use the image on the right as a guide."** (KOC-style phrasing). Alternatively, directly list all protocols whose source / origin is KOC CT protocols docx. Query Neon and provide the list. These are to be REPLACED with Swansea / Radiology Assistant / UK NHS Trust equivalents in a follow-up migration block.
- **#102** Search the ImagingProtocol DB for all occurrences of **"Aberdeen ARI"** (across title, detailed_protocol_html, special_notes, any text column) and replace with blank space (empty string). Idempotent migration block with sentinel marker.

---

## MDT SUITE — In-Progress (branch `mdt-module`, not merged)

Testing paused at Part B1 of `docs/tests/mdt_test.md`. Resume from **Part B2**.

| # | Item | Status | Details |
|---|---|---|---|
| 104 | MDT Suite — core build (schema, routes, UI, prompt, Smart Reporter save) | IN TEST | Branch `mdt-module`. Models + blueprint + full UI + unified prompt all shipped. Testing A1–B1 passed. See `docs/plans/MDT_SUITE_PLAN.md` + `docs/tests/mdt_test.md`. |
| 105 | MDT Suite — HTML-first summary + TinyMCE edit mode | DONE | `pre_mdt_summary` stores HTML, rendered `.mdt-card` with 6 colour-accented section cards + CLINICAL ALERT band. TinyMCE plugins lists/autoresize/table/link/image/code. Cloudinary upload with `f_auto,q_auto,w_1200,c_limit/` transform for mobile. Copy button walks DOM for clean plain-text extraction. |
| 106 | MDT Suite — prompt guardrails (exact dimensions, all discrepancies) | DONE | Guardrail #2 rewrote for exact-dimension TNM threshold rule (no rounding), CLINICAL ALERT now requires listing ALL detected discrepancies numbered. `IMAGING INFORMATION GAPS` section removed (redundant with RECOMMENDATIONS). `_strip_inline_markdown()` scrubber added. B1 test passed on 4.2 cm → T2b + discrepancy detection. |
| 107 | MDT Suite — Smart Reporter Save-to-MDT flow refactor | DONE | MDT button in Smart Reporter renamed "Save to MDT", now opens save modal directly (no in-card generation). Diagnosis optional. On save, iframe overlay opens MDT case detail with `?embed=1` (hides nav/breadcrumb). "Open full screen" button navigates out. Source banner warns when using draft vs finalised report. Mobile: fullscreen overlay. |
| 108 | MDT Suite — resume testing B2 → H | TODO | Parts still to run: B2 (TinyMCE edit mode), B2b-d (table/link, image upload, copy plain text), B3 (sparse case negative), C (search), D (export), E (bulk paste-back), F (linking), G (new Smart Reporter save flow + iframe overlay), H (cross-user isolation). |
| 109 | MDT Suite — merge `mdt-module` to main | BLOCKED | Wait until B2–H all pass. Will include prompt update, HTML renderer, TinyMCE edit mode, Cloudinary image upload, Smart Reporter iframe save flow, `mdt_routes.py`, `models.py` MdtMeeting+MdtCase, migrations. |
| 110 | MDT Suite — typo scrubber (deferred) | TODO | Model occasionally emits `�` unicode replacement char or merged tokens (e.g. `TAosimertinib`). Low frequency, clinically harmless. Add targeted post-process regex IF users complain. Do NOT bump temperature — trades determinism for marginal gain. |
| 111 | MDT Suite — prompt caching for `MDT_SYSTEM_PROMPT` | DEFERRED | See #103. Revisit post-launch when prompt iteration settles and steady traffic exists. ~2,650-token system prompt is the biggest caching candidate in the MDT path. Expected ~40% call-cost reduction on warm calls. |

## QUICK REFERENCE — What To Work On Next

### Remaining TODO Items (40 total, 111 overall)

**Active dev track — MDT Suite (branch `mdt-module`, NOT merged):**
- **#108** Resume testing Part B2 → H (see `docs/tests/mdt_test.md`)
- **#109** Merge `mdt-module` to main once tests pass
- **#110** Typo scrubber (deferred unless users complain)

**Next Sprint — Apr 8 user report (AFTER MDT merge):**
- **#94–96** Smart Reporter anatomy snippet search + session output persistence
- **#97–99** Safari dictation fixes (double-insert, stop command, new line command)
- **#100** Vetting appendicitis protocol match miss
- **#101** KOC protocol replacement (find by "Use the image on the right as a guide.")
- **#102** Aberdeen ARI string scrub in ImagingProtocol DB

**Tier 3 — Medium Priority:**
- **#33** Split `app.py` (~7000 lines) into route modules
- **#34** Split `models.py` (~3000 lines) into model packages
- **#38** Standardize API response format
- **#43** API documentation (OpenAPI/Swagger) — 269 routes, no docs
- **#46** Bulk admin operations (delete, publish, reassign)
- **#48** Notion image caching (URLs expire after ~1 hour)
- **#50** Immutable audit logs (append-only or external service)

**Tier 4 — Low Priority:**
- **#56** Split `static/style.css` (5,613 lines) into component files
- **#57** Organize 54 templates into subfolders
- **#58** Input validation with Marshmallow
- **#59** Update dependencies (Flask 2→3, Werkzeug 2→3)
- **#60** API versioning (`/api/v1/` prefix)
- **#61** WCAG 2.1 AA accessibility audit
- **#65** Application-level caching (Redis/Memcached)
- **#66** Async job queue for AI generation (Celery/RQ)
- **#67** Query optimization (N+1 queries)
- **#68** DICOM header stripping
- **#69** Analytics integration (GA/Mixpanel)
- **#71** Shared HTML syntax highlighting editor
- **#72** Protocol nav tab not active
- **#76** User Reporting Preferences (future suggestion only)
- **#78** Vetting Tool — Session History Browser
- **#79** Vetting Tool — TinyMCE Inline Editing on Output
- **#80** Vetting Tool — Publish Draft Protocols & Algorithms
- **#81** Vetting Tool — Protocol Usage Analytics
- **#82** Create Elite Pro price in Stripe dashboard
- **#83** Set STRIPE_ELITE_PRO_PRICE_ID env var on Vercel

### Suggested Priorities

**If you have 1 hour:** #38 (standardize API responses — define a wrapper pattern)
**If you have 4 hours:** + #33 (split app.py — biggest code quality win)
**If you have 1 day:** + #34, #43 (split models.py, start API docs)
**If you have 1 week:** + #46, #48, #56-57 (bulk ops, Notion caching, CSS/template reorg)
**If you have 1 month:** + #50, #58-59, #61 (audit logs, validation, deps update, accessibility)
