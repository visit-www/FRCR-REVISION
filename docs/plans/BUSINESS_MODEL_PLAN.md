# RadInsights Business Model & Implementation Plan

> **Last Updated:** March 28, 2026
> **Domain:** radinsights.xyz
> **Status:** Planning Phase — Pricing Finalized

---

## Executive Summary

RadInsights uses a 3-tier freemium model (Free / Standard / Elite) with AI action-based limits. Pricing is designed around radiologist workflow patterns, where one report typically consumes ~2.5 AI actions (Smart Reporter walkthrough + finalize). Payment processing via Stripe (GBP) and Razorpay (INR) with geo-detection.

---

## Pricing Structure

### Tier Overview

| Feature | Free | Standard | Elite | Elite Pro |
|---------|------|----------|-------|-----------|
| **Launch Price** | £0 forever | **£9/month** | **£29/month** | **£99/month** |
| **Post-Launch Price** | £0 forever | £14/month | £45/month | £120/month |
| **Smart Reporter Actions** | 10/month | 50/month | 160/month | 550/month |
| **~Estimated Reports** | ~4 reports | ~20 reports | ~64 reports | ~220 reports |
| **RadIQ Queries** | 5/month | 20/month | 50/month | 80/month |
| **Total AI Actions** | 15/month | 70/month | 210/month | 630/month |

> **Billing unit: AI actions.** Each AI interaction = 1 action. Report estimates assume ~2.5 actions/report average. Simple cases use fewer; users are likely to get more than the estimated report count.
| **Case Library** | Full access | Full access | Full access |
| **TNM Calculators** | Full access | Full access | Full access |
| **Radiology Tools** | Full access | Full access | Full access |
| **Clinical Protocols** | Full access | Full access | Full access |
| **Knowledge Hub** | Full access | Full access | Full access |
| **Learning Questions** | Full access | Full access | Full access |

### INR Pricing (India)

| Tier | Launch Price | Full Price |
|------|-------------|------------|
| Free | ₹0 forever | ₹0 forever |
| Standard | ₹749/month | ₹1,249/month |
| Elite | ₹2,399/month | ₹3,749/month |

### AI Action Economics

**Cost per AI action:** ~£0.016 ($0.02 USD) — Anthropic Claude Sonnet API
- Smart Reporter walkthrough: 1 action per step (~2 steps average)
- Finalize report: 1 action
- **Average per report: ~2.5 AI actions**
- RadIQ query: 1 action each
- Quick Ask (impression, MDT, SBA, etc.): 1 action each

### Tier Cost Analysis

| Tier | Monthly Revenue | Max AI Cost | Gross Margin |
|------|----------------|-------------|--------------|
| Free | £0 | £0.24 (15 actions) | -£0.24 |
| Standard (launch) | £9 | £1.52 (95 actions) | £7.48 (83%) |
| Standard (full) | £15 | £1.52 (95 actions) | £13.48 (90%) |
| Elite (launch) | £29 | £24.96 (1,560 actions) | £4.04 (14%) |
| Elite (full) | £45 | £24.96 (1,560 actions) | £20.04 (45%) |

> **Note:** Elite at launch price has thin margins if user exhausts all 1,500 SR actions. In practice, most users will use 50-70% of quota. At 70% usage, Elite launch margin rises to ~£11.52 (40%).

### Usage Assumptions

Based on real-world radiologist workflow data:
- **Light user (Free):** Explores the platform, tries a few reports
- **Standard user:** ~1-2 reports/day = ~20-40 reports/month (50 actions covers ~20 reports at 2.5 avg)
- **Elite user:** ~3-5 reports/day = ~60-100 reports/month (160 actions covers ~64 reports)
- **Elite Pro user:** ~10+ reports/day, high-volume departments (550 actions covers ~220 reports)
- **RadIQ usage:** Power users ask ~1-2 queries/day = ~20-40/month

---

## Revenue Streams

### Primary (90%)
- Individual subscriptions (Stripe for GBP, Razorpay for INR)
- Institutional licensing (manual onboarding, bulk discounts)

### Secondary (10%)
- Future: Mock exam packs, CME credit packages
- Future: API access for radiology departments

---

## Current State (Already Built)

The codebase has subscription infrastructure in `models.py`:

- `SubscriptionStatus` enum: `FREE`, `PAID`, `CANCELED`
- `PaymentStatus` enum: `NO_SUBSCRIPTION`, `ACTIVE`, `PAST_DUE`, `CANCELED`
- `subscription_start_date`, `subscription_end_date` fields on User
- Access control in `access_control.py` limiting FREE users to 2 cases/module
- Helper functions: `upgrade_to_paid()`, `downgrade_to_free()`, `cancel_subscription()`
- AI rate limiting: `ai_usage_date` + `ai_usage_count` on User model
- `_check_ai_rate_limit()` in `reporting_routes.py` and `radiq_routes.py`

### What Needs to Change

1. **Rate limiting** — Currently flat 50/day for all users. Needs tier-based monthly limits:
   - Separate counters for Smart Reporter and RadIQ
   - Monthly reset instead of daily reset
   - Tier-aware limit checking
2. **Subscription tiers** — Add `STANDARD` and `ELITE` to `SubscriptionStatus` or create separate `SubscriptionTier` enum
3. **Payment integration** — Stripe + Razorpay with webhook handling
4. **Frontend** — Display tier-appropriate limits, upgrade CTAs

---

## Implementation Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                         USER JOURNEY                                 │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│   Sign Up → Free Tier (10 SR + 5 RadIQ/month)                       │
│                    │                                                │
│              Hit AI Limit? ──────► Upgrade Modal                    │
│                    │                                                │
│           ┌────────┴────────┐                                       │
│           │                 │                                       │
│       Standard            Elite                                     │
│    75 SR + 20 RadIQ    1500 SR + 60 RadIQ                          │
│       £9/month            £29/month                                 │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────┐
│                      PAYMENT PROCESSING                              │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│   Pricing Page → Geo-Detect Currency                                │
│                        │                                            │
│              ┌─────────┴─────────┐                                  │
│              │                   │                                  │
│           India              UK/Other                               │
│              │                   │                                  │
│              ▼                   ▼                                  │
│         Razorpay             Stripe                                 │
│         Checkout             Checkout                               │
│              │                   │                                  │
│              ▼                   ▼                                  │
│         Webhook              Webhook                                │
│              │                   │                                  │
│              └─────────┬─────────┘                                  │
│                        ▼                                            │
│              Update User: tier + limits                             │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────┐
│                    AI RATE LIMITING                                   │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│   AI Request → Check Tier → Get Monthly Limit                       │
│                                │                                    │
│                    ┌───────────┼───────────┐                        │
│                    │           │           │                        │
│                  Free      Standard      Elite                      │
│                    │           │           │                        │
│                    ▼           ▼           ▼                        │
│                 10 SR       75 SR      1500 SR                      │
│                 5 RadIQ     20 RadIQ    60 RadIQ                   │
│                    │                                                │
│              Monthly Used < Limit?                                  │
│                    │                                                │
│              ┌─────┴─────┐                                          │
│              │           │                                          │
│            Yes          No                                          │
│              │           │                                          │
│              ▼           ▼                                          │
│           Allow      Upgrade Modal                                  │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

---

## Phase 1: Tier-Based Rate Limiting

### New Fields for User Model

```python
# Subscription tier
subscription_tier = db.Column(db.String(20), default='free')  # 'free', 'standard', 'elite'

# Monthly AI usage tracking (replaces daily ai_usage_count)
sr_usage_month = db.Column(db.Integer, default=0)       # Smart Reporter actions this month
radiq_usage_month = db.Column(db.Integer, default=0)    # RadIQ queries this month
usage_reset_date = db.Column(db.Date, nullable=True)     # 1st of current billing month
```

### Tier Limits Config

```python
TIER_LIMITS = {
    'free':     {'sr_monthly': 10,   'radiq_monthly': 5},
    'standard': {'sr_monthly': 75,   'radiq_monthly': 20},
    'elite':    {'sr_monthly': 1500, 'radiq_monthly': 60},
}
```

### Updated Rate Limit Check

```python
def _check_ai_rate_limit(usage_type='sr'):
    """Check tier-based monthly AI usage."""
    today = date.today()
    # Reset on 1st of month or first use
    if not current_user.usage_reset_date or current_user.usage_reset_date.month != today.month:
        current_user.sr_usage_month = 0
        current_user.radiq_usage_month = 0
        current_user.usage_reset_date = today

    tier = current_user.subscription_tier or 'free'
    limits = TIER_LIMITS.get(tier, TIER_LIMITS['free'])

    if usage_type == 'sr':
        used = current_user.sr_usage_month or 0
        limit = limits['sr_monthly']
    else:
        used = current_user.radiq_usage_month or 0
        limit = limits['radiq_monthly']

    if used >= limit:
        return False, 0, upgrade_response(tier, usage_type)

    # Increment
    if usage_type == 'sr':
        current_user.sr_usage_month = used + 1
    else:
        current_user.radiq_usage_month = used + 1
    db.session.commit()

    return True, limit - used - 1, None
```

---

## Phase 2: Payment Gateway Integration

### New File: `payment_routes.py`

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/payment/detect-currency` | GET | Geo-detect user's currency |
| `/api/payment/plans` | GET | List plans for user's currency |
| `/api/payment/create-checkout` | POST | Create Razorpay/Stripe session |
| `/api/payment/webhook/razorpay` | POST | Razorpay payment callback |
| `/api/payment/webhook/stripe` | POST | Stripe payment callback |
| `/api/payment/status` | GET | Current subscription status |
| `/api/payment/cancel` | POST | Cancel subscription |
| `/api/payment/billing-history` | GET | Past invoices |

### Environment Variables

```bash
# Razorpay (INR)
RAZORPAY_KEY_ID=rzp_live_xxx
RAZORPAY_KEY_SECRET=xxx
RAZORPAY_WEBHOOK_SECRET=xxx

# Stripe (GBP)
STRIPE_SECRET_KEY=sk_live_xxx
STRIPE_PUBLISHABLE_KEY=pk_live_xxx
STRIPE_WEBHOOK_SECRET=whsec_xxx

# Stripe Price IDs
STRIPE_PRICE_STANDARD_MONTHLY=price_xxx
STRIPE_PRICE_ELITE_MONTHLY=price_xxx
```

---

## Phase 3: Frontend Updates

### Upgrade Modal

When user hits AI limit:
- Show current usage vs limit
- "Upgrade to Standard for 75 AI actions/month" or "Upgrade to Elite for 1,500 AI actions/month"
- CTA buttons linking to Stripe/Razorpay checkout
- Launch pricing badge: "Limited time: £9/month (normally £15)"

### Counter Display

- Smart Reporter: Show "X/Y AI actions remaining this month"
- RadIQ: Show "X/Y queries remaining this month"
- Color coding: green (>50%), yellow (25-50%), red (<25%)

### Pricing Page

- 3-column comparison (Free / Standard / Elite)
- Launch pricing prominently displayed
- Feature comparison table
- Currency toggle (GBP/INR)

---

## Phase 4: Email Sequences

Using existing Resend integration in `auth.py`:

| Trigger | Email |
|---------|-------|
| Sign Up | Welcome + feature highlights + Free tier info |
| Hit Free Limit | "Upgrade to unlock more AI actions" |
| Payment Failed | Retry prompt + account access warning |
| Subscription Canceled | Feedback request + return offer |
| Monthly Reset | Usage summary + tier recommendation |

---

## Implementation Checklist

### Phase 1: Tier-Based Rate Limiting
- [ ] Add `subscription_tier`, `sr_usage_month`, `radiq_usage_month`, `usage_reset_date` to User model
- [ ] Add `_add_col_if_missing()` calls in `app.py` for new columns
- [ ] Update `_check_ai_rate_limit()` in `reporting_routes.py` for tier-based monthly limits
- [ ] Update `_check_ai_rate_limit()` in `radiq_routes.py` for tier-based monthly limits
- [ ] Update `/api/smart-reporter/ai-usage` endpoint to return tier info
- [ ] Update Smart Reporter counter display (monthly, tier-aware)
- [ ] Test rate limiting per tier

### Phase 2: Payment Backend
- [ ] Create `payment_routes.py` with Stripe integration
- [ ] Add Razorpay integration for INR
- [ ] Implement webhook handlers (tier upgrade on payment)
- [ ] Add geo-detection utility
- [ ] Create Stripe price IDs for Standard/Elite
- [ ] Create Razorpay plans for Standard/Elite

### Phase 3: Frontend
- [ ] Create pricing page with currency toggle
- [ ] Add upgrade modal component (shown on limit hit)
- [ ] Create billing management page
- [ ] Update Smart Reporter to show monthly usage
- [ ] Update RadIQ to show monthly usage
- [ ] Style to match app branding (see STYLE_GUIDE.md)

### Phase 4: Emails
- [ ] Welcome email on sign up
- [ ] Upgrade prompt on limit hit
- [ ] Payment failure notifications
- [ ] Monthly usage summary
- [ ] Test email delivery

### Phase 5: Testing & Launch
- [ ] Test complete flow in Stripe/Razorpay test mode
- [ ] Monitor AI usage patterns for first 2 weeks
- [ ] Adjust limits if needed based on real usage data
- [ ] Set up analytics for conversion tracking

---

## Key Metrics to Track

| Metric | Target |
|--------|--------|
| Free → Standard conversion | 10-20% |
| Free → Elite conversion | 3-7% |
| Standard → Elite upgrade | 15-25% |
| Monthly churn | < 5% |
| Average revenue per user | £12-18/month |
| CAC payback | < 2 months |

---

## Competitive Positioning

**Our Moat:**
- AI-powered Smart Reporter with structured walkthrough
- RadIQ consultant-level AI assistant
- TNM Intelligence + 39 staging calculators
- FRCR module-aligned case organization
- Knowledge Hub (algorithms, templates, protocols, tools)
- Personal study tracking with learning questions

**What Competitors Don't Have:**
- Radiopaedia: No AI-powered reporting or structured learning
- Radiology Masterclass: No interactive AI features
- RefinedRad: No FRCR-specific structure or TNM intelligence
- Others: No integrated knowledge hub + AI assistant combination

---

## Related Documents

- [APP_STRUCTURE.md](../APP_STRUCTURE.md) - Application architecture
- [STYLE_GUIDE.md](../STYLE_GUIDE.md) - Branding and styling
- [USER_ROLES_WORKFLOWS.md](../USER_ROLES_WORKFLOWS.md) - Role permissions
- [AI_INTEGRATION_REFERENCE.md](../AI_INTEGRATION_REFERENCE.md) - AI features
- [content-creation-plan.md](../content-creation-plan.md) - Content generation roadmap
- [AI_TOOLS_AND_COSTS.md](../AI_TOOLS_AND_COSTS.md) - AI cost analysis
