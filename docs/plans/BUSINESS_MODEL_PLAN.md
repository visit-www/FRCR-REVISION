# RadInsights Business Model & Implementation Plan

> **Last Updated:** January 25, 2026  
> **Domain:** radinsights.xyz  
> **Status:** Planning Phase

---

## Executive Summary

Implement a freemium business model with 7-day trial, tiered subscriptions (monthly/annual), dual-currency support (INR via Razorpay, GBP via Stripe), and progressive upgrade CTAs.

---

## Business Model Summary

### Tier Structure

| Tier | Price (INR) | Price (GBP) | Access |
|------|-------------|-------------|--------|
| Trial | Free / 7 days | Free / 7 days | Full access |
| Free | Free | Free | Unlimited search, 3 case reads/month |
| Monthly | ₹999/mo | £9.99/mo | Unlimited access |
| Annual | ₹6,499/yr | £79.99/yr | Unlimited + priority |

### Revenue Streams

**Primary (80%):**
- Individual subscriptions (Razorpay for INR, Stripe for GBP)
- Institutional licensing (manual initially)

**Secondary (20%):**
- Single case pass: ₹79 / £0.99
- TNM Deep Dive packs: ₹1,499 / £14.99 per organ system
- Mock exam packs: ₹1,999 / £19.99

---

## Current State (Already Built)

The codebase already has subscription infrastructure in `models.py`:

- `SubscriptionStatus` enum: `FREE`, `PAID`, `CANCELED`
- `PaymentStatus` enum: `NO_SUBSCRIPTION`, `ACTIVE`, `PAST_DUE`, `CANCELED`
- `subscription_start_date`, `subscription_end_date` fields on User
- Access control in `access_control.py` limiting FREE users to 2 cases/module
- Helper functions: `upgrade_to_paid()`, `downgrade_to_free()`, `cancel_subscription()`

---

## Implementation Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                         USER JOURNEY                                 │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│   Sign Up → 7-Day Trial → Trial Ends?                               │
│                              │                                       │
│                    ┌─────────┴─────────┐                            │
│                    │                   │                            │
│              No Payment           Subscribe                         │
│                    │                   │                            │
│                    ▼                   ▼                            │
│              Free Tier            Paid Tier                         │
│                    │                                                │
│              Hit Read Limit? ──────► Upgrade Modal                  │
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
│              Update User: PAID                                      │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────┐
│                       ACCESS CONTROL                                 │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│   View Case → Check Subscription                                    │
│                      │                                              │
│         ┌────────────┼────────────┐                                 │
│         │            │            │                                 │
│       PAID        TRIAL         FREE                                │
│         │            │            │                                 │
│         ▼            ▼            ▼                                 │
│       Allow    Check Expiry   Monthly Reads Left?                   │
│                     │            │                                  │
│                     ▼        ┌───┴───┐                              │
│                   Allow      │       │                              │
│                           Yes       No                              │
│                            │         │                              │
│                            ▼         ▼                              │
│                     Allow + Dec   Upgrade Modal                     │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

---

## Phase 1: Database & Model Updates

### New Fields for User Model

Add to `models.py`:

```python
# Payment gateway fields
payment_gateway = db.Column(db.String(20), nullable=True)  # 'razorpay' or 'stripe'
gateway_customer_id = db.Column(db.String(100), nullable=True)
gateway_subscription_id = db.Column(db.String(100), nullable=True)
preferred_currency = db.Column(db.String(3), default='INR')  # 'INR' or 'GBP'

# Trial period
trial_ends_at = db.Column(db.DateTime, nullable=True)
is_trial_used = db.Column(db.Boolean, default=False)

# Monthly read tracking (for free tier)
monthly_reads_count = db.Column(db.Integer, default=0)
monthly_reads_reset_at = db.Column(db.DateTime, nullable=True)
```

### Update SubscriptionStatus Enum

```python
class SubscriptionStatus(enum.Enum):
    TRIAL = "trial"      # NEW: 7-day full access
    FREE = "free"        # Limited: 3 reads/month
    PAID = "paid"        # Unlimited access
    CANCELED = "canceled"
```

---

## Phase 2: Payment Gateway Integration

### New File: `payment_routes.py`

**Endpoints:**

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

# Plans (created in dashboards)
RAZORPAY_PLAN_MONTHLY=plan_xxx
RAZORPAY_PLAN_ANNUAL=plan_xxx
STRIPE_PRICE_MONTHLY=price_xxx
STRIPE_PRICE_ANNUAL=price_xxx
```

---

## Phase 3: Access Control Updates

### Update `access_control.py`

Replace current "2 cases per module" logic with monthly read counter:

```python
def can_view_case(case, user=None):
    # Admin/Content Manager: always allowed
    # Trial: full access if not expired
    # Paid: full access
    # Free: check monthly_reads_count < 3
```

### Add Monthly Reset Logic

Reset `monthly_reads_count` to 0 on the 1st of each month:

```python
def reset_monthly_reads():
    users = User.query.filter(
        User.subscription_status == SubscriptionStatus.FREE
    ).all()
    for user in users:
        user.monthly_reads_count = 0
        user.monthly_reads_reset_at = datetime.utcnow()
    db.session.commit()
```

---

## Phase 4: Frontend Components

### New Templates/Pages

| Page | Description |
|------|-------------|
| `templates/pricing.html` | Plan comparison with currency toggle |
| `templates/checkout_success.html` | Post-payment confirmation |
| `templates/billing.html` | Subscription management, cancel |

### Upgrade Modal (Inject into Case View)

When free user hits limit:
- "You've used 3 of 3 free case reads this month"
- "Upgrade to unlock unlimited cases"
- CTA buttons for Monthly / Annual plans

### Trial Banner

For trial users:
- "Trial ends in X days" banner at top
- Progressive urgency (green → yellow → red)

---

## Phase 5: Email Sequences

Using existing Resend integration in `auth.py`:

| Trigger | Email |
|---------|-------|
| Trial Day 1 | Welcome + feature highlights |
| Trial Day 5 | "2 days left" + upgrade benefits |
| Trial Day 7 | Trial ended + special offer |
| Payment Failed | Retry prompt + account access warning |
| Subscription Canceled | Feedback request + return offer |

---

## Implementation Checklist

### Phase 1: Database
- [ ] Add new User fields (payment_gateway, trial_ends_at, monthly_reads_count)
- [ ] Update SubscriptionStatus enum to include TRIAL
- [ ] Create database migration
- [ ] Test migration locally and on Neon

### Phase 2: Payment Backend
- [ ] Create payment_routes.py with Razorpay integration
- [ ] Add Stripe integration for GBP
- [ ] Implement webhook handlers
- [ ] Add geo-detection utility
- [ ] Create subscription plans in Razorpay dashboard
- [ ] Create price IDs in Stripe dashboard

### Phase 3: Access Control
- [ ] Update can_view_case() for monthly read limits
- [ ] Add monthly read reset logic
- [ ] Update trial expiry check
- [ ] Test access restrictions

### Phase 4: Frontend
- [ ] Create pricing page with currency toggle
- [ ] Add upgrade modal component
- [ ] Add trial countdown banner
- [ ] Create billing management page
- [ ] Style to match app branding (see STYLE_GUIDE.md)

### Phase 5: Emails
- [ ] Trial reminder sequences (Day 1, 5, 7)
- [ ] Payment failure notifications
- [ ] Subscription lifecycle emails
- [ ] Test email delivery

### Phase 6: Testing & Launch
- [ ] Test complete flow in Razorpay/Stripe test mode
- [ ] A/B test trial length (7 vs 14 days)
- [ ] A/B test read limit (3 vs 5 per month)
- [ ] Set up analytics for conversion tracking
- [ ] Monitor conversion metrics

---

## Key Metrics to Track

| Metric | Target |
|--------|--------|
| Trial → Paid conversion | 15-25% |
| Free → Paid conversion | 3-7% |
| Monthly churn | < 5% |
| LTV (Annual) | ₹8,000 / £80-120 |
| CAC payback | < 3 months |

---

## Domain Configuration

**Domain:** `radinsights.xyz`

Once DNS propagates:
1. Update `APP_URL` in Vercel environment variables to `https://www.radinsights.xyz`
2. Update `.env` locally
3. Redeploy application
4. Test password reset emails use new domain

---

## Competitive Positioning

**Our Moat:**
- TNM Intelligence + FRCR-specific structure
- AI-generated staging summaries from radiologist perspective
- FRCR module-aligned case organization
- Personal notes/highlights with case progression

**What Competitors Don't Have:**
- Radiopaedia: No FRCR-specific organization
- Radiology Masterclass: No AI-powered features
- Others: No personalized study tracking

---

## Related Documents

- [APP_STRUCTURE.md](../APP_STRUCTURE.md) - Application architecture
- [STYLE_GUIDE.md](../STYLE_GUIDE.md) - Branding and styling
- [USER_ROLES_WORKFLOWS.md](../USER_ROLES_WORKFLOWS.md) - Role permissions
- [AI_INTEGRATION_REFERENCE.md](../AI_INTEGRATION_REFERENCE.md) - AI features
