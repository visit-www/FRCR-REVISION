# RadInsights Business & Finance Model

> Source of truth for finance team — cost structure, pricing rationale, unit economics.
> Last updated: 11 April 2026

---

## 1. Revenue Model

### Subscription Tiers (Monthly Recurring Revenue)

| Tier | Launch Price | Post-Launch | AI Actions/mo | RadIQ/mo | Target User |
|------|-------------|-------------|---------------|----------|-------------|
| Free | £0 | £0 | 10 (trial: unlimited 7 days) | 5 | Students, evaluators |
| Standard | £9/mo | £15/mo | 75 (~30 reports) | 20 | Registrars |
| Elite | £29/mo | £45/mo | 300 (~120 reports) | 40 | Active consultants |
| Elite Pro | £99/mo | £120/mo | 1,500 (~600 reports) | 60 | High-volume / departments |

### Revenue Per User Per Month
- Free: £0 (acquisition funnel)
- Standard: £9 (launch) / £15 (full)
- Elite: £29 (launch) / £45 (full)
- Elite Pro: £99 (launch) / £120 (full)

---

## 2. Cost Structure

### Fixed Costs (Monthly)
| Item | Cost | Notes |
|------|------|-------|
| Vercel Pro | ~$20/mo | Hosting, serverless functions, edge network |
| Neon PostgreSQL | ~$19/mo | Database (Pro plan) |
| Cloudinary | ~$0/mo | Free tier for OG images, case photos |
| Domain | ~$1/mo | radinsights.xyz |
| **Total Fixed** | **~$40/mo** | |

### Variable Costs (Per AI Call)
| Call Type | Model | ~Cost/Call | Frequency |
|-----------|-------|-----------|-----------|
| Report finalization | Opus | ~$0.20 | 2-3x per report session |
| Follow-up Q&A | Sonnet | ~$0.03 | 1-2x per session |
| SBA generation | Sonnet | ~$0.05 | Occasional |
| Viva generation | Sonnet | ~$0.04 | Occasional |
| Anatomy snippet | Sonnet | ~$0.04 | Cached after first gen |
| RadIQ query | Sonnet | ~$0.03 | Per query |
| Vetting analysis | Sonnet | ~$0.02 | Per referral |
| Quick review | Haiku | ~$0.01 | Per check |
| Voice transcription | Groq Whisper | ~$0.01 | Per dictation |

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

## 3. Unit Economics Per Subscriber

### Standard Tier (£9/mo)
| Item | Value |
|------|-------|
| Revenue | £9.00 |
| Stripe fees (2.9% + 20p) | -£0.46 |
| Net revenue | £8.54 |
| Estimated AI cost (75 actions: ~30 Opus + 45 Sonnet) | -£4.35 |
| Infrastructure share | -£0.50 |
| **Gross margin** | **£3.69 (43%)** |

### Elite Tier (£29/mo)
| Item | Value |
|------|-------|
| Revenue | £29.00 |
| Stripe fees | -£1.04 |
| Net revenue | £27.96 |
| Estimated AI cost (300 actions: ~100 Opus + 200 Sonnet) | -£14.60 |
| Infrastructure share | -£0.50 |
| **Gross margin** | **£12.86 (46%)** |

### Elite Pro Tier (£99/mo)
| Item | Value |
|------|-------|
| Revenue | £99.00 |
| Stripe fees | -£3.07 |
| Net revenue | £95.93 |
| Estimated AI cost (1500 actions: ~500 Opus + 1000 Sonnet) | -£73.00 |
| Infrastructure share | -£0.50 |
| **Gross margin** | **£22.43 (23%)** |

### Key Insight
- Standard and Elite have healthy margins (43-46%)
- Elite Pro margin is thin (23%) — designed for retention/lock-in, not margin
- **Opus calls are 5x more expensive than Sonnet** — the Opus/Sonnet routing in Smart Reporter is critical for cost control

---

## 4. Cost Tracking System

### How Costs Are Tracked
- Every AI call logged to `AIAuditLog` with: model, input_tokens, output_tokens, user_id, action
- Admin dashboard: `/api/admin/dashboard` → AI Costs tab
- API endpoint: `GET /api/admin/ai-costs?days=30`

### Dashboard Breakdown
| View | What It Shows |
|------|---------------|
| **by_category** | Admin generation (fixed) vs User interaction (variable) |
| **by_user** | Per-user cost — identifies high-cost users |
| **by_action** | Cost per feature — which features drive spend |
| **by_model** | Opus vs Sonnet vs Haiku split |
| **by_family** | Simplified model family view |
| **by_day** | Daily cost trend for forecasting |

### Key Metrics to Monitor
1. **User interaction cost per active user per month** — your marginal cost of serving one subscriber
2. **Opus vs Sonnet ratio** — if users over-use Opus (finalize/redo), costs spike
3. **Action utilisation rate** — what % of allocated actions do users actually consume?
4. **Cost per report** — total AI cost ÷ number of reports generated

---

## 5. Breakeven Analysis

### Assumptions
- Fixed costs: $40/mo (~£32/mo)
- Average revenue per paid user: £19/mo (weighted: 60% Standard, 30% Elite, 10% Pro)
- Average AI cost per paid user: £9.50/mo (weighted)
- Average gross margin per paid user: £9.50/mo

### Breakeven
- **Fixed cost breakeven: 4 paid subscribers** (£32 ÷ £9.50 = 3.4)
- At 10 paid subscribers: ~£95/mo profit
- At 50 paid subscribers: ~£475/mo profit
- At 100 paid subscribers: ~£950/mo profit

### Scale Concerns
- AI costs scale linearly with users (no economy of scale on Anthropic API)
- Opus pricing is the main cost driver — monitor Opus usage ratio
- Cached content (TNM, protocols, anatomy) does NOT scale with users — generate once, serve forever

---

## 6. Pricing Rationale

### Why These Prices?
- **£9 Standard** positions below FRCR textbooks (£30-60 each) and other SaaS tools
- **£29 Elite** comparable to Netflix/Spotify premium — "one subscription for your entire radiology workflow"
- **£99 Elite Pro** positioned for department budget holders who need high volume

### Why Launch Pricing?
- 40% discount incentivises early adoption
- "Lock in" messaging creates urgency
- Early users provide feedback and testimonials
- Lower price reduces barrier for registrars (typically budget-conscious)

### Post-Launch Price Increase Trigger
- When: After first 100 paid subscribers OR 6 months from launch (whichever comes first)
- How: Existing subscribers keep launch price; new subscribers get full price
- Messaging: "Thank you for believing in us early — your price is locked forever"

---

## 7. Risk Factors

| Risk | Impact | Mitigation |
|------|--------|------------|
| Anthropic price increase | Direct cost increase on all tiers | Monitor API pricing; Opus/Sonnet routing already optimised; could switch to cheaper models |
| Low conversion (Free → Paid) | Revenue shortfall | Improve trial experience; email nurture; demonstrate value in 7-day trial |
| High Opus usage ratio | Margin erosion on Elite/Pro | Already routing: only finalize/redo/rewrite use Opus; everything else Sonnet |
| Competitor entry | Market share loss | First-mover advantage; deep radiology-specific features; trust through Peer Review |
| Clinical accuracy liability | Reputation/legal | PII Guard, Peer Review, disclaimers, flag inaccuracy feature, never-fabricate guardrails |
| GDPR/compliance breach | Legal/financial | PII Guard, audit logging, no patient data stored, UK-hosted DB |

---

## 8. Growth Levers

1. **Content marketing** (SEO blog posts on radiology topics) — free organic traffic
2. **FRCR exam season** (May/October) — peak demand for revision tools
3. **Training program partnerships** — bulk licensing for radiology departments
4. **Annual pricing** — 20% discount for annual commitment, improves cash flow
5. **Referral program** — "Give a friend 1 month free, get 1 month free"
6. **Feature expansion** — each new feature (MDT Suite, Vetting, etc.) is a new marketing angle
