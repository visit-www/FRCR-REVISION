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

**Frequency:** One-time per cancer type. 39 calculators generated covering all FRCR-relevant cancers. Never re-generated unless admin explicitly requests it.

**Total projected admin cost:** ~50 calculators × $0.24 = **$12.00** (one-time, mostly already spent)

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
| **File** | `radiology_tools/generator.py` |
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

| # | Tool | Cost/Call | Cached? | Notes |
|---|------|----------|---------|-------|
| 7 | Algorithmic Reporter | $0.10 | Yes (per diagnosis slug) | Deprecated — redirects to Smart Reporter |
| 8 | Algorithm Tree (Smart Reporter) | $0.11 | Yes (per clinical question slug) | Cache stored in `ReportingTemplate` table |
| 9 | Report Review | $0.05 | No (unique per report) | 1-3 reviews per report iteration |
| 10 | Ask Claude | $0.01 | No (unique per question) | Max 20 per session |
| 11 | On-Call Helper | $0.05 | No (queries vary) | Protocol-grounded answers |

> Note: Case discussions (#5) and TNM intelligence (#6) are admin-generated during case creation and cached — students view pre-generated content at zero per-view AI cost.

---

## Projected Monthly Costs by User Activity

### Realistic Session Analysis

A typical active study session (1-2 hours) involves **10-20 AI calls**, not 3-4. Here's what a realistic session looks like:

| Action | Calls | Cost |
|--------|-------|------|
| Generate 3-4 Smart Reporter trees (trying different clinical questions) | 3-4 | $0.33-$0.44 |
| Review/improve reports | 3-5 | $0.15-$0.25 |
| Ask Claude questions about reports | 5-8 | $0.05-$0.08 |
| On-Call Helper queries | 5-8 | $0.25-$0.40 |
| **Session total** | **16-25** | **$0.78-$1.17** |

With **Smart Reporter tree caching** (~40% cache hit rate on popular clinical questions), effective per-session cost drops to **~$0.60-$0.90**.

### User Profiles

| Profile | Description | Sessions/Day | AI Calls/Day | Est. Daily Cost | With Caching |
|---------|-------------|-------------|-------------|-----------------|-------------|
| **Light** | Browses cases, 1 brief session | 0.5-1 | ~8 | ~$0.50 | ~$0.40 |
| **Moderate** | Active trainee, daily practice | 1-2 | ~20 | ~$1.10 | ~$0.85 |
| **Heavy** | Intensive daily study, exam prep | 2-3 | ~40 | ~$2.20 | ~$1.70 |
| **Power** | Exam cramming, maximum usage | 3-5 | ~70 | ~$3.60 | ~$2.80 |

### Monthly Cost Projections (30 days, with caching)

| Users | Light (60%) | Moderate (30%) | Heavy (10%) | Monthly AI Cost |
|-------|-------------|----------------|------------|-----------------|
| 10 | 6 × $12.00 | 3 × $25.50 | 1 × $51.00 | **$199.50** |
| 50 | 30 × $12.00 | 15 × $25.50 | 5 × $51.00 | **$997.50** |
| 100 | 60 × $12.00 | 30 × $25.50 | 10 × $51.00 | **$1,995.00** |
| 250 | 150 × $12.00 | 75 × $25.50 | 25 × $51.00 | **$4,987.50** |
| 500 | 300 × $12.00 | 150 × $25.50 | 50 × $51.00 | **$9,975.00** |
| 1000 | 600 × $12.00 | 300 × $25.50 | 100 × $51.00 | **$19,950.00** |

> Caching reduces costs by ~20-30%. Actual savings depend on how many users query the same clinical questions. Popular topics (CT abdomen appendicitis, chest X-ray pneumonia) will have high cache hit rates.

---

## Subscription Pricing Recommendation

### Cost Analysis

| Metric | Value |
|--------|-------|
| Blended average AI cost per user per month | **~$17.00** (60% light, 30% moderate, 10% heavy) |
| With caching benefit (~25% reduction) | **~$13.00** effective cost |
| Admin content build (one-time, amortised over 12 months) | **~$9.40/month** |
| Infrastructure (Vercel Pro + Neon DB) | **~$45/month** fixed |
| Infrastructure per user (at 100 users) | **~$0.45/month** |
| **Total cost per user per month** | **~$13.50** |

> The biggest cost drivers are On-Call Helper ($0.05/call, non-cacheable) and Smart Reporter tree generation ($0.11/call, cacheable). Caching significantly reduces tree generation costs as the cache builds up.

### Recommended Pricing Tiers

#### Tier 1: Free / Trial
| Feature | Limit |
|---------|-------|
| Price | **$0/month** |
| Case browsing (pre-generated content) | Unlimited |
| Smart Reporter sessions | 2/day |
| On-Call Helper queries | 3/day |
| Report reviews | 2/day |
| Ask Claude questions | 5/day |
| **Projected AI cost to us** | **~$3.00/month** |

> Purpose: Lets users try the platform. Low enough limits to prevent abuse, high enough to demonstrate value. Case discussions & TNM intelligence are pre-generated — no per-view AI cost.

#### Tier 2: Standard
| Feature | Limit |
|---------|-------|
| Price | **$14.99/month** (or $149/year — 2 months free) |
| Case browsing (pre-generated content) | Unlimited |
| Smart Reporter sessions | 10/day |
| On-Call Helper queries | 20/day |
| Report reviews | 10/day |
| Ask Claude questions | 20/session |
| Community publishing | Yes |
| **Projected AI cost to us** | **~$12.00/month** (light user) |
| **Margin** | **~$3.00 (20%)** |

> Rate limits set for typical light-to-moderate usage. Covers the majority of regular trainees.

#### Tier 3: Pro
| Feature | Limit |
|---------|-------|
| Price | **$24.99/month** (or $249/year — 2 months free) |
| Smart Reporter sessions | 30/day |
| On-Call Helper queries | 50/day |
| Report reviews | 30/day |
| Ask Claude questions | 30/session |
| Community publishing | Yes |
| Priority generation (queue skip) | Yes |
| Session history | Unlimited retention |
| **Projected AI cost to us** | **~$25.00/month** (moderate user) |
| **Margin** | **Break-even at moderate usage** |

> For serious exam candidates with intensive daily study. Cache hits improve margin over time. Comparable to Radprimer ($35-50/month) and other medical education platforms.

#### Tier 4: Institutional
| Feature | Details |
|---------|---------|
| Price | **Custom (contact us)** |
| Suggested starting point | $15/user/month (min 20 users) |
| Bulk seat discounts | 50+ users: $12/user, 100+: $10/user |
| Admin dashboard for institution | Yes |
| Usage analytics | Yes |
| Custom protocol library | Yes |

> Institutional pricing benefits from higher cache hit rates — 50 trainees at the same institution will query similar clinical scenarios, meaning more cache hits and lower per-user AI cost.

---

### Revenue Projections

| Users | Free (25%) | Standard (50%) | Pro (25%) | Monthly Revenue | Monthly AI Cost | Net Margin |
|-------|-----------|----------------|-----------|-----------------|-----------------|------------|
| 50 | 12 | 25 | 13 | **$700** | $598 | $102 (15%) |
| 100 | 25 | 50 | 25 | **$1,375** | $1,095 | $280 (20%) |
| 250 | 62 | 125 | 63 | **$3,450** | $2,494 | $956 (28%) |
| 500 | 125 | 250 | 125 | **$6,875** | $4,488 | $2,387 (35%) |
| 1000 | 250 | 500 | 250 | **$13,750** | $7,975 | $5,775 (42%) |

> Margins improve with scale because: (1) cache hit rates increase with more users querying similar topics, (2) fixed infrastructure costs are amortised across more users, (3) free tier users have very low limits. Revenue assumes Standard at $14.99 and Pro at $24.99.

---

### Break-Even Analysis

| Fixed Costs | Monthly |
|-------------|---------|
| Vercel Pro | $20 |
| Neon PostgreSQL | $19 |
| Domain + misc | $5 |
| **Total fixed** | **~$45/month** |

- **Break-even point:** ~8-10 paying users (Standard tier) covers fixed costs + their own AI usage
- **Comfortable profitability:** 100+ paying users = margins improve as caching kicks in
- **Key to profitability:** Cache coverage — every cached Smart Reporter tree saves $0.11 per subsequent user query

### Cost Optimization Roadmap

To improve margins as the platform scales:

1. **Aggressive tree caching** (implemented) — Smart Reporter trees cached by clinical question slug. Popular queries (CT abdomen appendicitis, chest pain PE protocol) serve from cache at $0 cost
2. **Model tiering** — Use Haiku 4.5 ($0.25/$1.25 per MTok) for Ask Claude (#10) and lightweight On-Call queries, saving ~75% on those calls
3. **On-Call protocol matching first** — Before calling AI, check if query matches a pre-built protocol exactly; serve protocol directly without AI call
4. **Batch report review** — Combine multiple review passes into a single API call instead of per-click
5. **Session-based pricing** — Consider charging per session rather than monthly for power users (pay-as-you-go option)
6. **Prompt caching** — System prompts are static; Anthropic cache hits at $0.30/MTok vs $3.00/MTok (90% savings on input tokens)

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

### Cost Optimization (see detailed roadmap in Pricing section above)
- **Response caching** — Smart Reporter trees cached per clinical question slug; Algorithmic Reporter cached per diagnosis
- **Admin pre-generation** — Case discussions (#5) and TNM intelligence (#6) generated once by admin, served to unlimited students at zero per-view cost
- **Prompt caching** — System prompts are static; cache hits at $0.30/MTok vs $3.00/MTok write
- **Model tiering** — Haiku 4.5 for lightweight calls (Ask Claude, simple On-Call queries)
- **Batch API** — 50% discount for admin generators (#1-6)

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
