# RadInsights Business & Finance Model

> Source of truth for finance team — cost structure, pricing rationale, unit economics, credit system.
> Last updated: 15 April 2026

---

## 1. Revenue Model

### Subscription Tiers (Monthly Recurring Revenue)

| Tier | Launch Price | Post-Launch | Reports/mo | RadIQ/mo | Effective/Report | Target User |
|------|-------------|-------------|------------|----------|------------------|-------------|
| Free | £0 | £0 | 4 (trial: 7 days full access) | 5 | free | Students, evaluators |
| Standard | £9/mo | £14/mo | 20 | 20 | 45p | Registrars |
| Elite | £29/mo | £45/mo | 64 | 50 | 45p | Active consultants |
| Elite Pro | £99/mo | £120/mo | 220 | 80 | 45p | High-volume / departments |

### Credit Top-Up System

| Pack | Price | Per Report | Margin |
|------|-------|------------|--------|
| 10 reports | £6 | 60p | 54% |

- Top-ups available to Standard, Elite, and Elite Pro subscribers only
- Free users must upgrade to buy credits
- Credits consumed within billing month (no rollover)
- Price per top-up report (60p) is higher than subscription rate (45p) — incentivises subscription over pay-as-you-go

### Revenue Per User Per Month
- Free: £0 (acquisition funnel — £1.04 cost to serve)
- Standard: £9 (launch) / £14 (full)
- Elite: £29 (launch) / £45 (full)
- Elite Pro: £99 (launch) / £120 (full)
- Top-up packs: £6 per 10 credits (supplemental revenue)

---

## 2. Features by Tier

### AI Features

| Feature | Free | Standard | Elite | Elite Pro |
|---------|------|----------|-------|-----------|
| Smart Reporter (Opus AI) | 4 reports/mo | 20 reports/mo | 64 reports/mo | 220 reports/mo |
| RadIQ queries | 5/mo | 20/mo | 50/mo | 80/mo |
| AI Vetting & Protocol Matching | Yes | Yes | Yes | Yes |
| MDT Summary generation | Yes | Yes | Yes | Yes |
| Email to Colleague | Yes | Yes | Yes | Yes |
| Email to Patient | No | Yes | Yes | Yes |
| SBA Question generation | No | Yes | Yes | Yes |
| Viva Question generation | No | Yes | Yes | Yes |
| Buy top-up credits | No | Yes | Yes | Yes |

### Learning & Content

| Feature | Free | Standard | Elite | Elite Pro |
|---------|------|----------|-------|-----------|
| Browse cases & Case Library | Yes | Yes | Yes | Yes |
| Knowledge Hub (Pearls & Snippets) | Yes | Yes | Yes | Yes |
| SBA & Viva practice questions | Yes | Yes | Yes | Yes |
| TNM Calculators (72) | Yes | Yes | Yes | Yes |
| Reporting Templates & Algorithms | Yes | Yes | Yes | Yes |
| Clinical Guidelines & Radiology Tools | Yes | Yes | Yes | Yes |
| Radiology Protocols | Yes | Yes | Yes | Yes |
| Radiology Pearls | Yes | Yes | Yes | Yes |
| Discussion Hub | Yes | Yes | Yes | Yes |
| Notes & Highlights | Yes | Yes | Yes | Yes |

### Productivity

| Feature | Free | Standard | Elite | Elite Pro |
|---------|------|----------|-------|-----------|
| Save personal templates | No | Yes | Yes | Yes |
| Full template & algorithm library | No | Yes | Yes | Yes |
| MDT Suite (meetings, cases, outcomes) | No | No | Yes | Yes |
| Notion integration | No | No | Yes | Yes |

### Platform

| Feature | Free | Standard | Elite | Elite Pro |
|---------|------|----------|-------|-----------|
| Priority content requests | No | No | Yes | Yes |
| Early access to new features | No | No | Yes | Yes |
| Dedicated support | No | No | No | Yes |

---

## 3. Cost Structure

### Fixed Costs (Monthly)
| Item | Cost | Notes |
|------|------|-------|
| Vercel Pro | ~$20/mo | Hosting, serverless functions, edge network |
| Neon PostgreSQL | ~$19/mo | Database (Pro plan) |
| Cloudinary | ~$0/mo | Free tier for OG images, case photos |
| Domain | ~$1/mo | radinsights.xyz |
| **Total Fixed** | **~$40/mo (~£32/mo)** | |

### Variable Costs (Per AI Call)
| Call Type | Model | ~Cost/Call (USD) | ~Cost/Call (GBP) |
|-----------|-------|------------------|------------------|
| Report finalization | Opus | ~$0.25 | ~£0.20 |
| Follow-up Q&A | Sonnet | ~$0.02 | ~£0.016 |
| Report action (MDT/Email/SBA/Viva) | Sonnet | ~$0.03 | ~£0.024 |
| Anatomy snippet | Sonnet | ~$0.04 | ~£0.032 |
| RadIQ query | Sonnet | ~$0.03 | ~£0.024 |
| Vetting analysis | Sonnet | ~$0.02 | ~£0.016 |
| Quick review | Haiku | ~$0.01 | ~£0.008 |
| CMV peer review | Gemini 2.5 Flash | ~$0.001 | ~£0.001 |
| Voice transcription | Groq Whisper | ~$0.01 | ~£0.008 |

### Blended Cost Per Report
A typical report session: 1× Opus finalize + 1× Sonnet follow-up + 0.5× report action
- **Per report: ~£0.23**
- **Per RadIQ query: ~£0.024**

### Admin Generation Costs (One-Time, Fixed Overhead)
| Content Type | ~Cost/Item | Count | Total |
|-------------|-----------|-------|-------|
| TNM Calculator | ~$0.15 | 72 | ~$11 |
| Imaging Protocol | ~$0.05 | 130 | ~$7 |
| Reporting Algorithm | ~$0.05 | ~50 | ~$3 |
| Anatomy Snippet | ~$0.04 | ~80 | ~$3 |
| Teaching Pearl | ~$0.04 | ~100 | ~$4 |
| IF Calculator | ~$0.10 | 6 | ~$1 |
| **Total Content Investment** | | | **~$29** |

This is a one-time cost. Content is cached and served from DB — no AI cost on subsequent views.

---

## 4. Unit Economics Per Subscriber

### AI Quality by Tier
All tiers including Free receive **Opus-grade AI finalization**. No quality degradation — volume is the constraint, not quality.

### Standard Tier (£9/mo launch, £14/mo post-launch)
| Item | Launch | Post-Launch |
|------|--------|-------------|
| Revenue | £9.00 | £14.00 |
| Stripe fees (2.9% + 30p) | -£0.56 | -£0.78 |
| Max AI cost (20 reports + 20 RadIQ) | -£4.84 | -£4.84 |
| **Gross margin** | **£3.60 (40%)** | **£8.38 (60%)** |

### Elite Tier (£29/mo launch, £45/mo post-launch)
| Item | Launch | Post-Launch |
|------|--------|-------------|
| Revenue | £29.00 | £45.00 |
| Stripe fees | -£1.29 | -£1.84 |
| Max AI cost (64 reports + 50 RadIQ) | -£15.92 | -£15.92 |
| **Gross margin** | **£11.79 (41%)** | **£27.24 (61%)** |

### Elite Pro Tier (£99/mo launch, £120/mo post-launch)
| Item | Launch | Post-Launch |
|------|--------|-------------|
| Revenue | £99.00 | £120.00 |
| Stripe fees | -£3.67 | -£4.38 |
| Max AI cost (220 reports + 80 RadIQ) | -£51.80 | -£51.80 |
| **Gross margin** | **£43.53 (44%)** | **£63.82 (53%)** |

### Top-Up Pack (£6 per 10 reports)
| Item | Value |
|------|-------|
| Revenue | £6.00 |
| Stripe fees | -£0.47 |
| AI cost (10 reports) | -£2.30 |
| **Gross margin** | **£3.23 (54%)** |

### Key Insight
- All tiers maintain 40-60% margin at launch, 53-61% post-launch
- Free tier costs £1.04/user — acquisition cost
- Top-up packs are highest margin product (54%)
- Opus quality for all users drives conversion from Free → Paid

---

## 5. Margins Summary

### Worst Case (100% usage)

| Plan | Revenue | API cost | Stripe | Margin | Margin % |
|------|---------|----------|--------|--------|----------|
| Free | £0 | £1.04 | — | -£1.04 | — |
| Standard (launch) | £9 | £4.84 | £0.56 | +£3.60 | 40% |
| Standard (post-launch) | £14 | £4.84 | £0.78 | +£8.38 | 60% |
| Elite (launch) | £29 | £15.92 | £1.29 | +£11.79 | 41% |
| Elite (post-launch) | £45 | £15.92 | £1.84 | +£27.24 | 61% |
| Elite Pro (launch) | £99 | £51.80 | £3.67 | +£43.53 | 44% |
| Elite Pro (post-launch) | £120 | £51.80 | £4.38 | +£63.82 | 53% |
| Top-up 10 | £6 | £2.30 | £0.47 | +£3.23 | 54% |

### Realistic (60% usage)

| Plan | Revenue | API cost | Stripe | Margin | Margin % |
|------|---------|----------|--------|--------|----------|
| Free | £0 | £0.62 | — | -£0.62 | — |
| Standard (launch) | £9 | £2.90 | £0.56 | +£5.54 | 62% |
| Standard (post-launch) | £14 | £2.90 | £0.78 | +£10.32 | 74% |
| Elite (launch) | £29 | £9.55 | £1.29 | +£18.16 | 63% |
| Elite (post-launch) | £45 | £9.55 | £1.84 | +£33.61 | 75% |
| Elite Pro (launch) | £99 | £31.08 | £3.67 | +£64.25 | 65% |
| Elite Pro (post-launch) | £120 | £31.08 | £4.38 | +£84.54 | 70% |

---

## 6. Upgrade Nudge Points

Top-up pricing (60p/report) is deliberately higher than subscription rate (45p/report). This creates natural upgrade pressure:

| Scenario | Total Spend | Reports | Better Off On |
|----------|-------------|---------|---------------|
| Standard + 1 top-up | £15 | 30 | Still Standard |
| Standard + 3 top-ups | £27 | 50 | Still Standard |
| **Standard + 4 top-ups** | **£33** | **60** | **Upgrade to Elite (64 for £29)** |
| Elite + 2 top-ups | £41 | 84 | Still Elite |
| Elite + 8 top-ups | £77 | 144 | Still Elite |
| **Elite + 12 top-ups** | **£101** | **184** | **Upgrade to Elite Pro (220 for £99)** |

---

## 7. Breakeven Analysis

### Assumptions
- Fixed costs: ~£32/mo
- Average revenue per paid user: £19/mo (weighted: 55% Standard, 30% Elite, 15% Pro)
- Average AI cost per paid user at 60% usage: £7.50/mo
- Average gross margin per paid user: £10/mo

### Breakeven
- **Fixed cost breakeven: 4 paid subscribers** (£32 ÷ £10 = 3.2)
- At 10 paid subscribers: ~£68/mo profit
- At 50 paid subscribers: ~£468/mo profit
- At 100 paid subscribers: ~£968/mo profit

### Revenue Projections (per 100 users)

| Mix | Free | Standard | Elite | Elite Pro | Monthly Revenue | Monthly Cost | Margin |
|-----|------|----------|-------|-----------|-----------------|--------------|--------|
| Launch (typical) | 60 | 25 | 12 | 3 | £870 | £355 | +£515 |
| Post-launch (typical) | 50 | 28 | 15 | 7 | £1,667 | £580 | +£1,087 |
| + Top-up revenue (est.) | — | — | — | — | +£120 | £46 | +£74 |

Assumptions: 60% average usage, 20% of paid users buy 1 top-up/month.

---

## 8. Cost Tracking System

### How Costs Are Tracked
- Every AI call logged to `AIAuditLog` with: model, input_tokens, output_tokens, user_id, action
- Admin dashboard: `/api/admin/dashboard` → AI Costs tab
- API endpoint: `GET /api/admin/ai-costs?days=30`

### Dashboard Metrics
| View | What It Shows |
|------|---------------|
| by_category | Admin generation (fixed) vs User interaction (variable) |
| by_user | Per-user cost — identifies high-cost users |
| by_action | Cost per feature — which features drive spend |
| by_model | Opus vs Sonnet vs Haiku split |
| by_day | Daily cost trend for forecasting |

### Key Metrics to Monitor
1. **Cost per report** — blended AI cost ÷ reports generated (target: <£0.25)
2. **Opus vs Sonnet ratio** — if users over-use Opus (finalize/redo), costs spike
3. **Action utilisation rate** — % of allocated reports actually consumed per tier
4. **Revenue per user** — ARPU vs cost per user per tier

---

## 9. Pricing Rationale

### Why These Prices?
- **£9 Standard** — below FRCR textbooks (£30-60), accessible for registrars on NHS salary
- **£29 Elite** — comparable to Netflix/Spotify premium, "one subscription for your entire radiology workflow"
- **£99 Elite Pro** — department budget holders, high-volume consultants
- **£6 top-up** — 60p/report feels fair as pay-as-you-go; higher than subscription rate nudges toward commitment

### Why Opus for All Tiers?
- Free users experience premium AI quality → higher conversion rate
- Cost of 4 free Opus reports (£1.04) is a cheap acquisition cost
- Quality difference between Opus and Sonnet is noticeable — degrading free tier would hurt brand perception

### Why Launch Pricing?
- 36-40% discount incentivises early adoption
- "Lock in" messaging creates urgency
- Early users provide feedback and testimonials
- Lower price reduces barrier for registrars

### Post-Launch Price Increase Trigger
- When: After first 100 paid subscribers OR 6 months from launch (whichever first)
- How: Existing subscribers keep launch price; new subscribers get full price
- Messaging: "Thank you for believing in us early — your price is locked forever"

---

## 10. Risk Factors

| Risk | Impact | Mitigation |
|------|--------|------------|
| Anthropic price increase | Direct cost increase on all tiers | Monitor API pricing; Opus/Sonnet routing already optimised; could switch to cheaper models |
| Low conversion (Free → Paid) | Revenue shortfall | Improve trial experience; email nurture; 7-day trial with full Opus quality |
| High usage users | Margin erosion | Hard cap + top-up system ensures no unlimited usage; upgrade nudge pricing |
| Competitor entry | Market share loss | First-mover advantage; deep radiology-specific features; Peer Review trust system |
| Clinical accuracy liability | Reputation/legal | PII Guard, CMV Peer Review, disclaimers, flag inaccuracy feature |
| GDPR/compliance breach | Legal/financial | PII Guard, audit logging, no patient data stored, UK-hosted DB |

---

## 11. Growth Levers

1. **Content marketing** (SEO blog posts on radiology topics) — free organic traffic
2. **FRCR exam season** (May/October) — peak demand for revision tools
3. **Training program partnerships** — bulk licensing for radiology departments
4. **Annual pricing** — 20% discount for annual commitment, improves cash flow
5. **Referral program** — "Give a friend 1 month free, get 1 month free"
6. **Top-up revenue** — supplemental income from power users above their cap
7. **Feature expansion** — each new feature (MDT Suite, Vetting, etc.) is a new marketing angle
