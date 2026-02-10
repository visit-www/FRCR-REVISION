# AI Tools, Costs & Subscription Pricing Guide

> **Last updated:** February 2026
> **Model:** Claude Sonnet 4 (`claude-sonnet-4-20250514`) via Anthropic Messages API
> **Pricing source:** [Anthropic API Pricing](https://platform.claude.com/docs/en/about-claude/pricing)

---

## API Pricing Reference

| Metric | Claude Sonnet 4 |
|--------|-----------------|
| Input tokens | **$3.00 / million tokens** |
| Output tokens | **$15.00 / million tokens** |
| Prompt cache write | $3.75 / MTok |
| Prompt cache hit | $0.30 / MTok |
| Batch (50% off) | $1.50 input / $7.50 output per MTok |

> 1 token ≈ 4 characters ≈ 0.75 words in English.

---

## All AI Tools — Complete Inventory

### ADMIN-ONLY AI Tools

These tools are triggered exclusively by administrators to create reusable content. They run once per content item and the output is cached/stored in the database for all users. **Users never trigger these directly.**

---

#### 1. TNM Calculator Generator

| Property | Value |
|----------|-------|
| **File** | `tnm_calculator/tnm_generator.py` |
| **Function** | `generate_calculator_html()` |
| **Purpose** | Generates complete interactive HTML staging calculators (form inputs, auto-calculation, reference section with mnemonics/tips/pitfalls) |
| **Trigger** | Admin clicks "Generate Calculator" for a cancer type |
| **Output** | Self-contained HTML (1500+ lines) stored in `TNMCalculatorContent` |
| **Model** | Claude Sonnet 4 |
| **max_tokens** | 20,000 |
| **Temperature** | 0.3 |
| **Timeout** | 240 seconds |

**Estimated cost per generation:**

| Tokens | Count | Cost |
|--------|-------|------|
| Input (system + user + AJCC data) | ~6,000 | $0.018 |
| Output (full HTML calculator) | ~15,000 | $0.225 |
| **Total per calculator** | | **~$0.24** |

**Frequency:** One-time per cancer type. ~50-100 calculators total covers all major cancers. Never re-generated unless admin explicitly requests it.

**Total projected admin cost:** 100 calculators × $0.24 = **$24.00** (one-time)

---

#### 2. Reporting Template Generator

| Property | Value |
|----------|-------|
| **File** | `reporting_template_generator.py` |
| **Function** | `generate_reporting_template_html()` |
| **Purpose** | Generates interactive non-oncologic reporting templates (trauma grading, LI-RADS, PI-RADS, emergency templates) with decision trees and report generation |
| **Trigger** | Admin clicks "Generate Template" in Reporting Templates management |
| **Output** | Self-contained HTML (1500+ lines) stored in `ReportingTemplate` |
| **Model** | Claude Sonnet 4 |
| **max_tokens** | 20,000 |
| **Temperature** | 0.3 |
| **Timeout** | 240 seconds |

**Estimated cost per generation:**

| Tokens | Count | Cost |
|--------|-------|------|
| Input (system + user prompt) | ~4,500 | $0.014 |
| Output (full HTML template) | ~15,000 | $0.225 |
| **Total per template** | | **~$0.24** |

**Frequency:** One-time per template. ~30-60 templates covers common reporting scenarios.

**Total projected admin cost:** 60 templates × $0.24 = **$14.40** (one-time)

---

#### 3. Clinical Protocol Generator

| Property | Value |
|----------|-------|
| **File** | `ai_oncall_helper.py` |
| **Function** | `generate_protocol_content()` |
| **Purpose** | Generates structured clinical protocol content (grading systems, imaging features, reporting recommendations, pitfalls) for the On-Call Helper knowledge base |
| **Trigger** | Admin clicks "Generate Protocol" in protocol management |
| **Output** | JSON with `content_html`, `content_structured`, `suggested_keywords` stored in `ClinicalProtocol` |
| **Model** | Claude Sonnet 4 |
| **max_tokens** | 4,000 |
| **Temperature** | 0.2 |
| **Timeout** | 120 seconds |

**Estimated cost per generation:**

| Tokens | Count | Cost |
|--------|-------|------|
| Input (system + user prompt) | ~2,500 | $0.008 |
| Output (structured protocol) | ~3,000 | $0.045 |
| **Total per protocol** | | **~$0.05** |

**Frequency:** One-time per protocol. ~100-200 protocols for comprehensive coverage.

**Total projected admin cost:** 200 protocols × $0.05 = **$10.00** (one-time)

---

#### 4. Incidental Finding Calculator Generator

| Property | Value |
|----------|-------|
| **File** | `incidental_findings/generator.py` |
| **Function** | `generate_if_calculator_html()` |
| **Purpose** | Generates interactive HTML calculators for incidental finding management (Fleischner, Bosniak, ACR guidelines) with decision trees and report language |
| **Trigger** | Admin clicks "Generate Calculator" in IF management |
| **Output** | Self-contained HTML stored in `IncidentalFindingCalculator` |
| **Model** | Claude Sonnet 4 |
| **max_tokens** | 20,000 |
| **Temperature** | 0.3 |
| **Timeout** | 240 seconds |

**Estimated cost per generation:**

| Tokens | Count | Cost |
|--------|-------|------|
| Input (system + user + guideline data) | ~5,000 | $0.015 |
| Output (full HTML calculator) | ~15,000 | $0.225 |
| **Total per calculator** | | **~$0.24** |

**Frequency:** One-time per finding type. ~30-50 calculators covers all major incidental findings.

**Total projected admin cost:** 50 calculators × $0.24 = **$12.00** (one-time)

---

#### 5. Preliminary Case Data Generator

| Property | Value |
|----------|-------|
| **File** | `ai_prelim.py` |
| **Function** | `generate_prelim_case_data()` |
| **Purpose** | Generates FRCR case material: Q&A pairs, HTML discussion, safety checklist, sources, TNM metadata for each teaching case |
| **Trigger** | Admin clicks "Generate AI Discussion" when building a case |
| **Output** | JSON with `qa_pairs`, `discussion` (HTML), `safety_checklist`, `sources` stored in case record |
| **Model** | Claude Sonnet 4 |
| **max_tokens** | 6,000 |
| **Temperature** | 0.3 |
| **Timeout** | 90 seconds |

**Estimated cost per generation:**

| Tokens | Count | Cost |
|--------|-------|------|
| Input (system + case context) | ~3,500 | $0.011 |
| Output (Q&A + discussion HTML) | ~4,500 | $0.068 |
| **Total per case** | | **~$0.08** |

**Frequency:** One-time per case. Generated once during case creation, then cached and served to all students. ~200-500 cases in a comprehensive case bank.

**Total projected admin cost:** 500 cases × $0.08 = **$40.00** (one-time)

---

#### 6. TNM Staging Intelligence Generator

| Property | Value |
|----------|-------|
| **File** | `ai_tnm.py` |
| **Function** | `generate_tnm_intelligence()` |
| **Purpose** | Generates imaging-specific staging pearls, critical findings, MDT discussion points for oncologic teaching cases |
| **Trigger** | Admin clicks "Generate TNM Intelligence" when building an oncologic case |
| **Output** | Markdown parsed into structured fields stored in case record |
| **Model** | Claude Sonnet 4 |
| **max_tokens** | 4,000 |
| **Temperature** | 0.3 |
| **Timeout** | 90 seconds |

**Estimated cost per generation:**

| Tokens | Count | Cost |
|--------|-------|------|
| Input (system + AJCC staging data) | ~4,500 | $0.014 |
| Output (Markdown intelligence) | ~3,000 | $0.045 |
| **Total per case** | | **~$0.06** |

**Frequency:** One-time per oncologic case with TNM data. Generated once, cached for all students. ~100-200 oncologic cases.

**Total projected admin cost:** 200 cases × $0.06 = **$12.00** (one-time)

---

### Admin AI — Cost Summary

| Tool | Unit Cost | Estimated Qty | Total Cost | Recurrence |
|------|-----------|---------------|------------|------------|
| TNM Calculators | $0.24 | 100 | $24.00 | One-time |
| Reporting Templates | $0.24 | 60 | $14.40 | One-time |
| Clinical Protocols | $0.05 | 200 | $10.00 | One-time |
| IF Calculators | $0.24 | 50 | $12.00 | One-time |
| Case Prelim Data | $0.08 | 500 | $40.00 | One-time |
| TNM Intelligence | $0.06 | 200 | $12.00 | One-time |
| **Total admin content build** | | | **$112.40** | **One-time** |

> Admin AI costs are **fixed, one-time investments**. Once content is generated and verified, it serves all users indefinitely with zero ongoing AI cost. Occasional regeneration for guideline updates or new cases adds minimal cost (~$10-20/year).

---

### USER-FACING AI Tools

These tools are triggered by authenticated users during their study/work sessions. **These drive ongoing, recurring API costs** that scale with user count and usage frequency.

---

#### 7. Algorithmic Reporter

| Property | Value |
|----------|-------|
| **File** | `ai_algorithmic_reporter.py` |
| **Function** | `generate_algorithmic_report()` |
| **Purpose** | Generates step-by-step reporting algorithm + draft PACS report, differentials, recommendations |
| **Trigger** | User searches for a reporting algorithm in Smart Reporter |
| **Output** | JSON with `algorithmic_approach_html`, `pacs_report`, `differential_diagnosis`, `recommendations` |
| **Model** | Claude Sonnet 4 |
| **max_tokens** | 8,000 |
| **Temperature** | 0.3 |
| **Timeout** | 120 seconds |

**Estimated cost per call:**

| Tokens | Count | Cost |
|--------|-------|------|
| Input (system + diagnosis context) | ~3,500 | $0.011 |
| Output (algorithm + report) | ~6,000 | $0.090 |
| **Total per generation** | | **~$0.10** |

**Usage pattern:** Cached per diagnosis. Popular algorithms get reused without re-generation.

---

#### 8. Smart Reporter — Algorithm Tree Generator

| Property | Value |
|----------|-------|
| **File** | `ai_smart_reporter.py` |
| **Function** | `generate_algorithm_tree()` |
| **Purpose** | Generates structured JSON decision tree for interactive scan reading walkthrough (Scene 1) |
| **Trigger** | User starts guided reporting in Smart Reporter |
| **Output** | JSON algorithm tree with steps, branching, report template |
| **Model** | Claude Sonnet 4 |
| **max_tokens** | 10,000 |
| **Temperature** | 0.3 |
| **Timeout** | 150 seconds |

**Estimated cost per call:**

| Tokens | Count | Cost |
|--------|-------|------|
| Input (system + clinical question) | ~2,500 | $0.008 |
| Output (full algorithm tree) | ~7,000 | $0.105 |
| **Total per generation** | | **~$0.11** |

**Usage pattern:** One call per reporting session. Active users may create 1-3 sessions/day.

---

#### 9. Smart Reporter — Report Review

| Property | Value |
|----------|-------|
| **File** | `ai_smart_reporter.py` |
| **Function** | `review_report()` |
| **Purpose** | Reviews draft PACS report for spelling, grammar, radiology phrasing, structure; returns corrected text + suggestion cards |
| **Trigger** | User clicks "Review & Improve" in Scene 2 |
| **Output** | JSON with `improved_report` and `suggestions[]` array |
| **Model** | Claude Sonnet 4 |
| **max_tokens** | 4,000 |
| **Temperature** | 0.2 |
| **Timeout** | 60 seconds |

**Estimated cost per call:**

| Tokens | Count | Cost |
|--------|-------|------|
| Input (system + report text) | ~1,500 | $0.005 |
| Output (improved report + suggestions) | ~3,000 | $0.045 |
| **Total per review** | | **~$0.05** |

**Usage pattern:** 1-3 reviews per session as user iterates on report quality.

---

#### 10. Smart Reporter — Ask Claude

| Property | Value |
|----------|-------|
| **File** | `ai_smart_reporter.py` |
| **Function** | `ask_claude_about_report()` |
| **Purpose** | Lightweight Q&A — user asks questions about their draft report, gets consultant-level advice |
| **Trigger** | User types question in "Ask Claude" panel (Scene 2) |
| **Output** | Plain text answer (max 200 words) |
| **Model** | Claude Sonnet 4 |
| **max_tokens** | 1,500 |
| **Temperature** | 0.3 |
| **Timeout** | 30 seconds |

**Estimated cost per call:**

| Tokens | Count | Cost |
|--------|-------|------|
| Input (system + report + question) | ~1,000 | $0.003 |
| Output (concise answer) | ~500 | $0.008 |
| **Total per question** | | **~$0.01** |

**Usage pattern:** Rate-limited to 20 per session. Average user asks 3-5 questions per session.

---

#### 11. On-Call Helper Query

| Property | Value |
|----------|-------|
| **File** | `ai_oncall_helper.py` |
| **Function** | `generate_oncall_response()` |
| **Purpose** | Answers clinical queries grounded in verified protocols (contrast reactions, trauma grading, scoring systems) |
| **Trigger** | User submits a query in On-Call Helper |
| **Output** | JSON with `answer_html`, `summary`, `citations`, `confidence`, `matched_protocols` |
| **Model** | Claude Sonnet 4 |
| **max_tokens** | 4,000 |
| **Temperature** | 0.2 |
| **Timeout** | 90 seconds |

**Estimated cost per call:**

| Tokens | Count | Cost |
|--------|-------|------|
| Input (system + matched protocols + query) | ~3,000 | $0.009 |
| Output (formatted answer) | ~2,500 | $0.038 |
| **Total per query** | | **~$0.05** |

**Usage pattern:** On-call queries may spike during shifts. Average 5-15 queries per user per session.

---

### User AI — Cost Per Call Summary

| # | Tool | Cost/Call | Cached? | Avg Calls/User/Day |
|---|------|----------|---------|-------------------|
| 7 | Algorithmic Reporter | $0.10 | Yes (per diagnosis) | 1-2 |
| 8 | Algorithm Tree (Smart Reporter) | $0.11 | Per session | 1-2 |
| 9 | Report Review | $0.05 | No | 2-3 |
| 10 | Ask Claude | $0.01 | No | 3-5 |
| 11 | On-Call Helper | $0.05 | No | 5-10 |

> Note: Case discussions (#5) and TNM intelligence (#6) are admin-generated during case creation and cached — students view pre-generated content at zero per-view AI cost.

---

## Projected Monthly Costs by User Activity

### User Profiles

User-facing AI tools are: Algorithmic Reporter ($0.10), Algorithm Tree ($0.11), Report Review ($0.05), Ask Claude ($0.01), and On-Call Helper ($0.05). Case discussions and TNM intelligence are pre-generated by admin at zero per-view cost.

| Profile | Description | Daily AI Calls | Est. Daily Cost |
|---------|-------------|---------------|-----------------|
| **Light** | Browses cases, occasional Smart Reporter | ~3 calls | ~$0.12 |
| **Moderate** | Active reporting practice + on-call prep | ~10 calls | ~$0.40 |
| **Heavy** | Daily reporting sessions, frequent on-call queries | ~20 calls | ~$0.80 |
| **Power** | Maximum usage across all user tools | ~40 calls | ~$1.60 |

### Monthly Cost Projections (30 days)

| Users | Light (70%) | Moderate (25%) | Heavy (5%) | Monthly AI Cost |
|-------|-------------|----------------|------------|-----------------|
| 10 | 7 × $3.60 | 2 × $12.00 | 1 × $24.00 | **$73.20** |
| 50 | 35 × $3.60 | 12 × $12.00 | 3 × $24.00 | **$342.00** |
| 100 | 70 × $3.60 | 25 × $12.00 | 5 × $24.00 | **$672.00** |
| 250 | 175 × $3.60 | 62 × $12.00 | 13 × $24.00 | **$1,686.00** |
| 500 | 350 × $3.60 | 125 × $12.00 | 25 × $24.00 | **$3,360.00** |
| 1000 | 700 × $3.60 | 250 × $12.00 | 50 × $24.00 | **$6,720.00** |

> These are conservative estimates. Caching (Algorithmic Reporter per-diagnosis) further reduces repeated calls. Real-world costs may be 20-30% lower due to cache hits.

---

## Subscription Pricing Recommendation

### Cost Analysis

| Metric | Value |
|--------|-------|
| Average user AI cost per month | **$5.40** (blended across Light/Moderate/Heavy profiles) |
| With caching benefit (~25% reduction) | **~$4.00** effective cost |
| Admin content build (one-time, amortised over 12 months) | **~$9.40/month** |
| Infrastructure (Vercel Pro + Neon DB) | **~$45/month** fixed |
| Infrastructure per user (at 100 users) | **~$0.45/month** |
| **Total cost per user per month** | **~$4.50** |

### Recommended Pricing Tiers

#### Tier 1: Free / Trial
| Feature | Limit |
|---------|-------|
| Price | **$0/month** |
| Case browsing (pre-generated content) | Unlimited |
| Smart Reporter sessions | 1/day |
| On-Call Helper queries | 3/day |
| Report reviews | 1/day |
| Ask Claude questions | 3/day |
| **Projected AI cost to us** | **~$0.90/month** |

> Purpose: Lets users try the platform. Low enough limits to prevent abuse, high enough to demonstrate value. Case discussions & TNM intelligence are pre-generated — no per-view AI cost.

#### Tier 2: Standard
| Feature | Limit |
|---------|-------|
| Price | **$9.99/month** (or $99/year — 2 months free) |
| Case browsing (pre-generated content) | Unlimited |
| Smart Reporter sessions | 5/day |
| On-Call Helper queries | 20/day |
| Report reviews | 10/day |
| Ask Claude questions | 20/session |
| Community publishing | Yes |
| **Projected AI cost to us** | **~$4.00/month** |
| **Margin** | **~$6.00 (60%)** |

> Covers the majority of active trainees. Enough headroom for serious daily study.

#### Tier 3: Unlimited
| Feature | Limit |
|---------|-------|
| Price | **$14.99/month** (or $149/year — 2 months free) |
| All user AI tools | Unlimited* |
| Priority generation (queue skip) | Yes |
| Community publishing | Yes |
| Session history | Unlimited retention |
| **Projected AI cost to us** | **~$6.00/month** (heavy user average) |
| **Margin** | **~$9.00 (60%)** |

> *Fair use: 100 AI calls/day soft cap to prevent automated abuse.

#### Tier 4: Institutional
| Feature | Details |
|---------|---------|
| Price | **Custom (contact us)** |
| Suggested starting point | $7/user/month (min 20 users) |
| Bulk seat discounts | 50+ users: $6/user, 100+: $5/user |
| Admin dashboard for institution | Yes |
| Usage analytics | Yes |
| Custom protocol library | Yes |

---

### Revenue Projections

| Users | Free (30%) | Standard (50%) | Unlimited (20%) | Monthly Revenue | Monthly AI Cost | Net Margin |
|-------|-----------|----------------|-----------------|-----------------|-----------------|------------|
| 50 | 15 | 25 | 10 | **$400** | $171 | $229 (57%) |
| 100 | 30 | 50 | 20 | **$800** | $336 | $464 (58%) |
| 250 | 75 | 125 | 50 | **$2,000** | $843 | $1,157 (58%) |
| 500 | 150 | 250 | 100 | **$4,000** | $1,680 | $2,320 (58%) |
| 1000 | 300 | 500 | 200 | **$8,000** | $3,360 | $4,640 (58%) |

> Revenue assumes Standard at $9.99 and Unlimited at $14.99. Free tier generates $0 revenue but minimal AI cost (~$0.90/user). Net margin excludes fixed infrastructure costs (~$45/month). Admin content build (~$112 one-time) amortises to ~$9.40/month over year one.

---

### Break-Even Analysis

| Fixed Costs | Monthly |
|-------------|---------|
| Vercel Pro | $20 |
| Neon PostgreSQL | $19 |
| Domain + misc | $5 |
| **Total fixed** | **~$45/month** |

- **Break-even point:** ~5 paying users (Standard tier) covers fixed costs
- **AI cost break-even:** Built into per-user pricing with ~60% margin
- **Comfortable profitability:** 50+ paying users = ~$580/month net after all costs

---

## Technical Architecture Notes

### Common Across All AI Tools
- **API endpoint:** `https://api.anthropic.com/v1/messages`
- **Library:** `requests.post` (direct HTTP, NOT Anthropic SDK)
- **API version:** `anthropic-version: 2023-06-01`
- **System prompt:** Always plain string (NOT array format — array format causes 500 errors)
- **Model selection:** Environment variable `CLAUDE_MODEL` with fallback to `claude-sonnet-4-20250514`
- **Error handling:** JSON parse with regex fallback for markdown-fenced responses
- **Deployment:** Vercel serverless functions, `maxDuration: 300` in `builds[].config`

### Cost Optimization Opportunities
1. **Prompt caching** — System prompts are static; cache writes at $3.75/MTok, cache hits at $0.30/MTok (90% savings on repeat calls)
2. **Batch API** — For admin generators (#1-6), batch processing gives 50% discount ($1.50/$7.50 per MTok)
3. **Model tiering** — Use Haiku 4.5 ($1/$5 per MTok) for lightweight calls like Ask Claude (#10), saving ~67% on those calls
4. **Response caching** — Algorithmic Reporter (#7) already caches results per diagnosis in PostgreSQL; expanding cache coverage to Smart Reporter trees reduces repeat API calls
5. **Admin pre-generation eliminates user cost** — Case discussions (#5) and TNM intelligence (#6) are generated once by admin, then served to unlimited students at zero per-view AI cost

### Rate Limits (Current)
| Tool | Limit |
|------|-------|
| Smart Reporter sessions | Max 5 active per user |
| Ask Claude | Max 20 per session |
| On-Call queries | Logged for audit |
| Smart Reporter tree generation | Cached per clinical question (slug-based) — repeat queries cost $0 |

### Patient Data Protection (PII Guard)
- **Dual-layer:** Client-side JS (`static/pii-guard.js`) + server-side Flask middleware (`pii_guard.py`)
- **Detects:** NHS numbers, MRNs, dates of birth, UK postcodes, phone numbers, emails, patient name patterns
- **Client:** Intercepts all `fetch()` POST/PUT with JSON bodies, shows modal with redact/cancel options
- **Server:** `before_request` hook returns HTTP 422 with `pii_blocked: true` if PII detected
- **Exemptions:** Admin content creation routes, auth routes, backup routes, non-JSON requests
- **Zero false-positive cost:** Modal shows exactly what was detected; user chooses to redact or cancel

---

## Appendix: Token Estimation Methodology

Token counts estimated using:
- System prompts: word count × 1.33 (English average)
- User prompts: measured prompt templates + typical variable content
- Output tokens: observed from development testing (actual usage logged via `generation_tokens` field)

For precise tracking, all generators return `token_count` in their response metadata, logged per session/case in the database.
