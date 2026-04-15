# Stripe Payment Gateway — Comprehensive Test Plan

> **Created:** March 30, 2026
> **Updated:** April 15, 2026 — lookup keys, 4 tiers, AI action billing, credit pack 25 actions
> **Status:** Ready to Execute
> **Scope:** Full subscription lifecycle testing — signup, trial, upgrade, downgrade, cancellation, credit top-ups, edge cases, webhooks
> **Keyword:** `RADINSIGHTS-STRIPE-TESTS-2026`

---

## Table of Contents

1. [Executive Summary](#1-executive-summary)
2. [Architecture Overview](#2-architecture-overview)
3. [Test Environment Setup](#3-test-environment-setup)
4. [Stripe Test Cards Reference](#4-test-cards)
5. [Test Suite 1 — Initial Signup & Trial](#5-suite-1-signup-trial)
6. [Test Suite 2 — Upgrades (Instant + Proration)](#6-suite-2-upgrades)
7. [Test Suite 3 — Downgrades (End-of-Cycle)](#7-suite-3-downgrades)
8. [Test Suite 4 — Cancellation & Account Deletion](#8-suite-4-cancellation)
9. [Test Suite 5 — Payment Failures & Error Handling](#9-suite-5-payment-failures)
10. [Test Suite 6 — Edge Cases & Idempotency](#10-suite-6-edge-cases)
11. [Test Suite 7 — Webhook Verification](#11-suite-7-webhooks)
12. [Test Suite 8 — AI Usage Rate Limiting](#12-suite-8-rate-limiting)
13. [Test Suite 9 — UI/UX Verification](#13-suite-9-ui-ux)
14. [Test Suite 10 — Security & Compliance](#14-suite-10-security)
15. [Code Review Checklist](#15-code-review)
16. [Automated Test Specifications](#16-automated-tests)
17. [Test Execution Tracking](#17-test-tracking)

---

## 1. Executive Summary

RadInsights uses Stripe Checkout (hosted payment form) with a webhook-first architecture for subscription management. Four tiers: Free, Standard (£9/mo), Elite (£29/mo), Elite Pro (£99/mo) with a 7-day trial for free users. **Prices resolved via Stripe lookup keys** (no price ID env vars). Launch/post-launch auto-switch on 2026-07-17. Billing unit: **AI actions** (not reports). Credit top-up: 25 AI actions for £6. This plan covers 70+ test cases across 11 suites.

**Key files under test:**
- `stripe_routes.py` — Lookup key resolution, checkout, plan changes, credit purchases, webhooks
- `access_control.py` — `upgrade_to_paid()`, `downgrade_to_free()` helpers
- `reporting_routes.py` — `_check_ai_rate_limit()`, `TIER_LIMITS`, credit consumption
- `models.py` — `User` model subscription fields, `report_credits` for top-ups
- `templates/pricing.html` — Pricing UI, checkout triggers, plan change modal, credit purchase
- `templates/smart_reporter.html`, `templates/radiq.html` — Upgrade modals, buy credits

**Architecture pattern:**
- **Price resolution:** `_resolve_price_id(plan)` → `stripe.Price.list(lookup_keys=[...])` → cached
- **Pricing phase:** Auto-switch via `POST_LAUNCH_DATE` (2026-07-17) or `PRICING_PHASE` env var
- **Upgrades:** `Subscription.modify()` + `proration_behavior='create_prorations'` + `billing_cycle_anchor='now'`
- **Downgrades:** `cancel_at_period_end=True` → webhook handles tier change at period end
- **Free → Paid:** Stripe Checkout hosted session → `checkout.session.completed` webhook
- **Credit top-up:** One-time payment → `checkout.session.completed` with `type=credit_pack` metadata → adds 25 AI actions
- **Webhook is single source of truth** for subscription state

---

## 2. Architecture Overview

```
User Action                   Flask Route                     Stripe API                  Webhook
──────────                   ───────────                     ──────────                  ───────
Free → Standard/Elite        POST /stripe/create-checkout    Checkout.Session.create()   checkout.session.completed
Standard → Elite             POST /stripe/change-plan        Subscription.modify()       customer.subscription.updated
Elite → Standard             POST /stripe/change-plan        Subscription.modify()       customer.subscription.deleted
                             (cancel_at_period_end=True)                                 → auto-creates Standard sub
Paid → Free                  POST /stripe/change-plan        Subscription.modify()       customer.subscription.deleted
                             (cancel_at_period_end=True)                                 → downgrade_to_free()
Payment fails                —                               —                           invoice.payment_failed
                                                                                         → payment_status=PAST_DUE
Account deletion             POST /auth/deactivate           Subscription.cancel()       customer.subscription.deleted
```

### Database Fields (User model)

```
subscription_status:  FREE | PAID | CANCELED
payment_status:       NO_SUBSCRIPTION | ACTIVE | PAST_DUE | CANCELED
subscription_tier:    'free' | 'standard' | 'elite' | 'elite_pro'
stripe_customer_id:   'cus_xxx' (Stripe Customer ID)
subscription_start_date: DateTime
subscription_end_date:   DateTime
trial_started_at:        DateTime (NULL = grandfathered, no trial)
pending_subscription_tier:       'standard' | 'elite' | 'free' | None
report_credits:          Integer (purchased AI action credits, consumed when monthly limit hit)
pending_change_effective_date:   DateTime | None
sr_usage_month:    Integer (Smart Reporter actions this month)
radiq_usage_month: Integer (RadIQ queries this month)
usage_reset_date:  Date (1st of billing month)
```

### Tier Limits

| Tier | SR Actions/mo | ~Reports | RadIQ Queries/mo | Trial Days |
|------|--------------|----------|-------------------|------------|
| Free | 10 | ~4 | 5 | 7 |
| Free (post-trial) | 2 | ~1 | 1 | — |
| Standard | 50 | ~20 | 20 | — |
| Elite | 160 | ~64 | 50 | — |
| Elite Pro | 550 | ~220 | 80 | — |
| Admin | 9,999 | ∞ | 9,999 | — |

> Each AI interaction = 1 action. Report estimates assume ~2.5 actions/report average.

---

## 3. Test Environment Setup

### 3.1 Prerequisites

- [ ] Stripe account in **test mode** (dashboard.stripe.com → Test mode toggle)
- [ ] `.env` has test-mode keys:
  ```
  STRIPE_SECRET_KEY=sk_test_...
  STRIPE_PUBLISHABLE_KEY=pk_test_...
  STRIPE_WEBHOOK_SECRET=whsec_...
  ```
  No price ID env vars needed — prices resolved via lookup keys at runtime.
- [ ] **Stripe test-mode products created** with these lookup keys on their prices:
  - `STRIPE_STANDARD_LAUNCH_PRICE_ID` (£9/mo recurring)
  - `STRIPE_ELITE_LAUNCH_PRICE_ID` (£29/mo recurring)
  - `STRIPE_ELITE_PRO_LAUNCH_PRICE_ID` (£99/mo recurring)
  - `STRIPE_CREDIT_PACK_PRICE_ID` (£6 one-time)
  - Post-launch keys optional for testing: `STRIPE_STANDARD_POST_LAUNCH_PRICE_ID`, `STRIPE_ELITE_POST_LAUNCH_PRICE_ID`, `STRIPE_ELITE_PRO_POST_LAUNCH_PRICE_ID`
- [ ] Webhook endpoint registered in Stripe Dashboard: `https://radinsights.xyz/stripe/webhook`
  - Events: `checkout.session.completed`, `customer.subscription.updated`, `customer.subscription.deleted`, `invoice.payment_failed`
- [ ] For local testing: Stripe CLI installed (`stripe listen --forward-to localhost:5000/stripe/webhook`)
- [ ] Test user accounts created (not admin — admin bypasses limits)
- [ ] Optional: set `PRICING_PHASE=launch` env var to force launch pricing during test

### 3.2 Test User Matrix

| User | Email | Purpose |
|------|-------|---------|
| `test-free@test.com` | Fresh signup, trial testing | Signup & trial |
| `test-standard@test.com` | Standard subscriber | Upgrade/downgrade/credits |
| `test-elite@test.com` | Elite subscriber | Upgrade/downgrade/credits |
| `test-elitepro@test.com` | Elite Pro subscriber | Downgrade/cancel/credits |
| `test-expired@test.com` | Trial-expired user | Expiry wall |
| `test-edge@test.com` | Edge case testing | Double-click, failures |

### 3.3 Stripe CLI Commands

```bash
# Forward webhooks to local dev
stripe listen --forward-to localhost:5000/stripe/webhook

# Trigger specific events for testing
stripe trigger checkout.session.completed
stripe trigger customer.subscription.updated
stripe trigger customer.subscription.deleted
stripe trigger invoice.payment_failed

# View recent events
stripe events list --limit 10
```

---

## 4. Stripe Test Cards Reference

| Scenario | Card Number | CVC | Exp | Expected Result |
|----------|-------------|-----|-----|-----------------|
| **Success** | `4242 4242 4242 4242` | Any | Future | Payment succeeds |
| **Card Declined** | `4000 0000 0000 0002` | Any | Future | Payment fails (generic decline) |
| **3D Secure (SCA)** | `4000 0000 0000 3063` | Any | Future | Requires authentication challenge |
| **Incorrect CVC** | `4000 0000 0000 0127` | Any | Future | Fails with CVC error |
| **Insufficient Funds** | `4000 0000 0000 9995` | Any | Future | Fails with insufficient funds |
| **Expired Card** | `4000 0000 0000 0069` | Any | Future | Fails with expired card |
| **Processing Error** | `4000 0000 0000 0119` | Any | Future | Fails with processing error |

**For all test cards:** Use any future expiry date (e.g., 12/30) and any 3-digit CVC.

---

## 5. Test Suite 1 — Initial Signup & Trial

### T1.1 — The 7-Day Hook (Free Signup Trial)

| Step | Action | Expected Result |
|------|--------|-----------------|
| 1 | Register new user at `/register` | Account created with `subscription_tier='free'` |
| 2 | Check `trial_started_at` in DB | Set to current UTC timestamp |
| 3 | Calculate trial end | `trial_started_at + 7 days` |
| 4 | Navigate to `/pricing` | Shows "Trial: X days remaining" badge |
| 5 | Access Smart Reporter | AI features available (within 10/month SR limit) |
| 6 | Access RadIQ | Available (within 5/month limit) |
| 7 | Check Stripe Dashboard | No Stripe Customer created yet (created on first checkout) OR Customer created at registration (non-fatal) |

**Verification queries:**
```sql
SELECT subscription_tier, trial_started_at, subscription_status, payment_status
FROM user WHERE email = 'test-free@test.com';
-- Expected: 'free', NOT NULL, 'free', 'no_subscription'
```

### T1.2 — The Expiry Wall (Day 8)

| Step | Action | Expected Result |
|------|--------|-----------------|
| 1 | Set `trial_started_at` to 8 days ago in DB | Simulates trial expiry |
| 2 | Navigate to `/smart-reporter` | AI features restricted / redirected to pricing |
| 3 | Check `_check_ai_rate_limit()` | Returns `(False, 0, error_response)` with trial expired message |
| 4 | Navigate to `/pricing` | Shows "Trial expired — upgrade to continue" |
| 5 | Verify TNM calculators still work | Calculators are NOT tier-restricted (public pages) |
| 6 | Verify case browse still works | Basic browsing works (3 reads/month limit for free) |

**Verification:**
```python
# In reporting_routes.py _check_ai_rate_limit():
# Free tier with trial_started_at NOT NULL and > 7 days ago = expired
trial_end = user.trial_started_at + timedelta(days=7)
if datetime.utcnow() > trial_end:
    # Trial expired — block AI features
```

### T1.3 — Direct Entry (Skip Trial — Pay Immediately)

| Step | Action | Expected Result |
|------|--------|-----------------|
| 1 | Register new user | `subscription_tier='free'`, `trial_started_at=now()` |
| 2 | Go to `/pricing` and click "Get Standard" | Redirects to Stripe Checkout |
| 3 | Complete payment with `4242 4242 4242 4242` | Checkout success |
| 4 | Webhook `checkout.session.completed` fires | User upgraded in DB |
| 5 | Check DB | `subscription_tier='standard'`, `subscription_status='paid'`, `payment_status='active'` |
| 6 | Verify `subscription_start_date` | Set to now |
| 7 | Verify `subscription_end_date` | ~30 days from now |
| 8 | Verify trial is superseded | Trial no longer relevant — paid plan active |
| 9 | Verify SR limit | 50/month (Standard), NOT 10 (Free) |

### T1.4 — Grandfathered User (No Trial)

| Step | Action | Expected Result |
|------|--------|-----------------|
| 1 | User with `trial_started_at = NULL` | Grandfathered — no trial expiry |
| 2 | Check AI rate limit | Free tier limits apply (10 SR, 5 RadIQ) but no expiry wall |
| 3 | Verify `/pricing` | No "Trial: X days" badge shown |

---

## 6. Test Suite 2 — Upgrades (Instant + Proration)

### T2.1 — Standard to Elite (Mid-Month Upgrade)

| Step | Action | Expected Result |
|------|--------|-----------------|
| 1 | User is on Standard plan (`subscription_tier='standard'`) | Active Stripe subscription |
| 2 | On ~Day 15 of billing cycle, click "Upgrade to Elite" on `/pricing` | Preview modal shows prorated cost |
| 3 | `POST /stripe/preview-change` | Returns `{ type: 'upgrade', amount_due, credit, new_price }` |
| 4 | Confirm upgrade in modal | `POST /stripe/change-plan` with `{ plan: 'elite' }` |
| 5 | Check Stripe API call | `Subscription.modify()` with `proration_behavior='create_prorations'` + `billing_cycle_anchor='now'` |
| 6 | Verify immediate access | `subscription_tier='elite'` in DB, AI limit = 160 SR |
| 7 | Verify Stripe invoice | Prorated credit for unused Standard days, charge for full Elite month |
| 8 | Verify new billing cycle | Resets to today (not original cycle start) |
| 9 | Verify `pending_subscription_tier` | NULL (no pending change — immediate upgrade) |

**Critical code path in `stripe_routes.py`:**
```python
# Upgrade path
stripe.Subscription.modify(
    sub_id,
    items=[{'id': sub_item_id, 'price': new_price_id}],
    proration_behavior='create_prorations',
    billing_cycle_anchor='now',
)
# Immediate DB update:
user.subscription_tier = new_tier
user.subscription_start_date = datetime.utcnow()
```

### T2.2 — Free to Standard (First Payment)

| Step | Action | Expected Result |
|------|--------|-----------------|
| 1 | User on free tier (trial active) | No Stripe subscription |
| 2 | Click "Get Standard" on `/pricing` | Stripe Checkout session created |
| 3 | Complete with `4242 4242 4242 4242` | Redirected to `/stripe/success` |
| 4 | Webhook `checkout.session.completed` | DB updated to `subscription_tier='standard'` |
| 5 | Verify trial superseded | `subscription_status='paid'`, active Standard plan |
| 6 | Verify SR limit | 50/month (not 10) |

### T2.3 — Free to Elite (First Payment)

| Step | Action | Expected Result |
|------|--------|-----------------|
| 1 | User on free tier | No Stripe subscription |
| 2 | Click "Get Elite" on `/pricing` | Stripe Checkout session created |
| 3 | Complete payment | Redirected to success |
| 4 | Webhook fires | `subscription_tier='elite'`, `subscription_status='paid'` |
| 5 | Verify SR limit | 160/month |

### T2.4 — Auto-Checkout via URL Parameter

| Step | Action | Expected Result |
|------|--------|-----------------|
| 1 | Navigate to `/pricing?plan=elite` | Auto-triggers checkout on page load |
| 2 | Verify Stripe Checkout opens | Checkout session for Elite plan |

---

## 7. Test Suite 3 — Downgrades (End-of-Cycle)

### T3.1 — Elite to Standard (Scheduled Downgrade)

| Step | Action | Expected Result |
|------|--------|-----------------|
| 1 | User on Elite plan, Day 10 of 30-day cycle | Active subscription |
| 2 | Click "Switch to Standard" on `/pricing` | Preview shows end-of-cycle change |
| 3 | Confirm downgrade | `POST /stripe/change-plan` with `{ plan: 'standard' }` |
| 4 | Check Stripe API call | `Subscription.modify(cancel_at_period_end=True)` |
| 5 | Verify DB immediately | `subscription_tier='elite'` (STILL Elite), `pending_subscription_tier='standard'`, `pending_change_effective_date` set |
| 6 | Verify `/pricing` UI | Shows "Switching to Standard on [date]" banner with "Undo" button |
| 7 | User retains Elite access | All Elite features work until period end |
| 8 | Period ends → Webhook `customer.subscription.deleted` fires | |
| 9 | Webhook auto-creates Standard subscription | `stripe.Subscription.create()` for Standard plan |
| 10 | Verify DB after period end | `subscription_tier='standard'`, `pending_subscription_tier=NULL` |
| 11 | Verify new billing | Charged £9/month for Standard going forward |

**Critical webhook code:**
```python
# In customer.subscription.deleted handler:
if user.pending_subscription_tier == 'standard':
    # Auto-create Standard subscription
    stripe.Subscription.create(customer=customer_id, items=[{'price': STANDARD_PRICE_ID}])
    user.subscription_tier = 'standard'
    user.pending_subscription_tier = None
```

### T3.2 — Standard to Free (Cancel Subscription)

| Step | Action | Expected Result |
|------|--------|-----------------|
| 1 | User on Standard plan | Active subscription |
| 2 | Click "Downgrade to Free" | Preview shows end-of-cycle change |
| 3 | Confirm | `cancel_at_period_end=True` |
| 4 | Verify immediate state | `subscription_tier='standard'` (still active), `pending_subscription_tier='free'` |
| 5 | Access remains | Standard features work until period end |
| 6 | Period ends → `customer.subscription.deleted` webhook | `downgrade_to_free(user)` called |
| 7 | Verify final state | `subscription_tier='free'`, `subscription_status='free'`, `payment_status='canceled'` |
| 8 | No refund issued | Verify Stripe Dashboard — no refund |
| 9 | SR limit drops | 10/month (Free) |

### T3.3 — Elite to Free (Cancel Subscription)

Same as T3.2 but starting from Elite. Verify:
- Elite access retained until period end
- No partial refund
- Drops to free limits after period end

### T3.4 — Undo Scheduled Downgrade

| Step | Action | Expected Result |
|------|--------|-----------------|
| 1 | User has pending downgrade (Elite → Standard) | `pending_subscription_tier='standard'` |
| 2 | Click "Undo" button on `/pricing` | `POST /stripe/cancel-pending-change` |
| 3 | Stripe API call | `Subscription.modify(cancel_at_period_end=False)` |
| 4 | Verify DB | `pending_subscription_tier=NULL`, `pending_change_effective_date=NULL` |
| 5 | User stays on Elite | No change at period end |

---

## 8. Test Suite 4 — Cancellation & Account Deletion

### T4.1 — Account Deletion (Active Paid User)

| Step | Action | Expected Result |
|------|--------|-----------------|
| 1 | User on Elite plan (paid, Day 2 of cycle) | Active subscription |
| 2 | Navigate to `/auth/deactivate-account` | Deactivation page |
| 3 | Confirm account deletion | Account soft-deleted |
| 4 | Verify Stripe | Subscription canceled immediately (`cancel_at_period_end=False`) |
| 5 | Verify no refund | No refund in Stripe Dashboard |
| 6 | Verify DB | `is_deleted=True`, `deleted_at` set, subscription tier cleared |
| 7 | Verify user cannot login | Session cleared, redirected to login |
| 8 | Verify 31-day recovery window | Account exists in DB with `deleted_at` |

**Critical code verification:**
```python
# In auth.py deactivation:
# Must call stripe.Subscription.cancel() or stripe.Subscription.modify(cancel_at_period_end=False)
# Must NOT pass refund arguments
```

### T4.2 — Account Deletion (Free User)

| Step | Action | Expected Result |
|------|--------|-----------------|
| 1 | Free user (no Stripe subscription) | |
| 2 | Deactivate account | Soft-deleted |
| 3 | Verify no Stripe errors | Handles missing subscription gracefully |

### T4.3 — Account Recovery After Deletion

| Step | Action | Expected Result |
|------|--------|-----------------|
| 1 | Deleted user attempts login within 31 days | Recovery option shown |
| 2 | User recovers account | `is_deleted=False`, `deleted_at=NULL` |
| 3 | Verify subscription state | `subscription_tier='free'` (subscription was canceled, not re-created) |
| 4 | User must re-subscribe | Navigate to `/pricing` and start fresh checkout |

---

## 9. Test Suite 5 — Payment Failures & Error Handling

### T5.1 — Card Declined at Checkout

| Step | Action | Expected Result |
|------|--------|-----------------|
| 1 | Free user clicks "Get Elite" | Stripe Checkout opens |
| 2 | Enter `4000 0000 0000 0002` | Payment attempt fails |
| 3 | Stripe Checkout shows error | "Your card was declined" message |
| 4 | Verify DB | User remains on `subscription_tier='free'` |
| 5 | Verify no subscription created | No Stripe Subscription in Dashboard |
| 6 | User returns to app | Redirected to `/stripe/cancel` → pricing page |

### T5.2 — Card Declined on Renewal

| Step | Action | Expected Result |
|------|--------|-----------------|
| 1 | Standard subscriber's card fails at renewal | Stripe retries per retry schedule |
| 2 | `invoice.payment_failed` webhook fires | |
| 3 | Verify DB | `payment_status='past_due'` |
| 4 | Verify user access | Features still work during grace period (Stripe retry window) |
| 5 | If all retries fail → `customer.subscription.deleted` | `downgrade_to_free(user)` |

### T5.3 — 3D Secure (SCA) Challenge

| Step | Action | Expected Result |
|------|--------|-----------------|
| 1 | Use card `4000 0000 0000 3063` at checkout | 3D Secure challenge shown |
| 2 | Complete authentication | Payment succeeds after auth |
| 3 | Verify webhook fires | `checkout.session.completed` → user upgraded |
| 4 | Reject authentication | Payment fails, user stays on current tier |

### T5.4 — Incorrect CVC

| Step | Action | Expected Result |
|------|--------|-----------------|
| 1 | Use card `4000 0000 0000 0127` at checkout | CVC error shown |
| 2 | Verify user not upgraded | Remains on current tier |

### T5.5 — Insufficient Funds

| Step | Action | Expected Result |
|------|--------|-----------------|
| 1 | Use card `4000 0000 0000 9995` | Insufficient funds error |
| 2 | Verify graceful handling | Error shown, no state change |

---

## 10. Test Suite 6 — Edge Cases & Idempotency

### T6.1 — Double-Click on Upgrade Button

| Step | Action | Expected Result |
|------|--------|-----------------|
| 1 | User on Standard, click "Upgrade to Elite" twice rapidly | |
| 2 | Verify only ONE Stripe API call | Backend should check current tier before calling Stripe |
| 3 | Verify only ONE invoice | No duplicate charges |
| 4 | Verify final state | `subscription_tier='elite'`, single subscription in Stripe |

**What to check in code:**
```python
# stripe_routes.py change-plan should check:
if current_tier == requested_tier:
    return jsonify({'error': 'Already on this plan'}), 400
```

### T6.2 — Rapid Checkout Session Creation

| Step | Action | Expected Result |
|------|--------|-----------------|
| 1 | Click "Get Standard" → back → click "Get Elite" | Two checkout sessions created |
| 2 | Complete the SECOND checkout (Elite) | User ends up on Elite |
| 3 | First session expires | No duplicate subscription |
| 4 | Verify single subscription | One active sub in Stripe Dashboard |

### T6.3 — Webhook Replay / Duplicate

| Step | Action | Expected Result |
|------|--------|-----------------|
| 1 | Stripe sends `checkout.session.completed` twice (retry) | |
| 2 | Verify idempotent handling | User upgraded only once, no duplicate state changes |
| 3 | Check DB | `subscription_tier` set correctly, no duplicate entries |

### T6.4 — Upgrade While Downgrade Is Pending

| Step | Action | Expected Result |
|------|--------|-----------------|
| 1 | User on Elite, has pending downgrade to Standard | `pending_subscription_tier='standard'` |
| 2 | User changes mind, wants to stay on Elite | Clicks "Undo" |
| 3 | Verify | `pending_subscription_tier=NULL`, stays on Elite |

### T6.5 — Downgrade Then Immediate Upgrade

| Step | Action | Expected Result |
|------|--------|-----------------|
| 1 | Elite user schedules downgrade to Standard | `cancel_at_period_end=True` |
| 2 | Before period ends, user upgrades back to Elite | |
| 3 | Verify | `cancel_at_period_end` reversed to `False`, user stays Elite |

### T6.6 — Concurrent Sessions (Two Browser Tabs)

| Step | Action | Expected Result |
|------|--------|-----------------|
| 1 | Open pricing in Tab A and Tab B | |
| 2 | Click "Upgrade to Elite" in both tabs | |
| 3 | Complete checkout in Tab A | User upgraded |
| 4 | Tab B checkout | Should detect existing subscription, not create duplicate |

### T6.7 — Stripe Customer ID Mismatch (Test/Live Mode)

| Step | Action | Expected Result |
|------|--------|-----------------|
| 1 | User has `stripe_customer_id` from live mode, app in test mode | |
| 2 | User attempts checkout | `_ensure_stripe_customer()` detects mismatch |
| 3 | Verify | Creates new test-mode customer, updates `stripe_customer_id` |

---

## 11. Test Suite 7 — Webhook Verification

### T7.1 — Webhook Signature Verification

| Step | Action | Expected Result |
|------|--------|-----------------|
| 1 | Send POST to `/stripe/webhook` without valid signature | Rejected with 400 |
| 2 | Send with valid Stripe signature | Accepted and processed |

### T7.2 — `checkout.session.completed` Webhook

| Test | Scenario | Expected DB State |
|------|----------|-------------------|
| 7.2a | Standard checkout | `tier='standard'`, `status='paid'`, `payment='active'` |
| 7.2b | Elite checkout | `tier='elite'`, `status='paid'`, `payment='active'` |
| 7.2c | Unknown customer ID | Logged as warning, no crash |
| 7.2d | Missing metadata | Graceful handling, no crash |

### T7.3 — `customer.subscription.updated` Webhook

| Test | Scenario | Expected DB State |
|------|----------|-------------------|
| 7.3a | `cancel_at_period_end=True`, `status='active'` | Keep current tier, set `pending_subscription_tier` |
| 7.3b | `cancel_at_period_end=False`, `status='active'` | Apply tier, clear pending fields |
| 7.3c | `status='past_due'` | `payment_status='past_due'` |

### T7.4 — `customer.subscription.deleted` Webhook

| Test | Scenario | Expected DB State |
|------|----------|-------------------|
| 7.4a | `pending_subscription_tier='standard'` | Auto-create Standard sub, `tier='standard'` |
| 7.4b | `pending_subscription_tier='free'` or NULL | `downgrade_to_free()`, `tier='free'` |
| 7.4c | User not found | Logged as warning, no crash |

### T7.5 — `invoice.payment_failed` Webhook

| Test | Scenario | Expected DB State |
|------|----------|-------------------|
| 7.5a | First failure | `payment_status='past_due'` |
| 7.5b | User not found | Logged, no crash |

### T7.6 — Webhook Event Order

| Test | Scenario | Expected Outcome |
|------|----------|-----------------|
| 7.6a | `checkout.session.completed` before user loads success page | Webhook updates DB, success page reads correct state |
| 7.6b | Webhook delayed (arrives after user sees success page) | Success page may show stale data, but next page load is correct |

---

## 12. Test Suite 8 — AI Usage Rate Limiting

### T8.1 — Free Tier Limits

| Step | Action | Expected Result |
|------|--------|-----------------|
| 1 | Free user (trial active) uses Smart Reporter 10 times | All succeed |
| 2 | 11th SR request | Blocked: "Monthly limit reached" |
| 3 | Free user uses RadIQ 5 times | All succeed |
| 4 | 6th RadIQ request | Blocked |
| 5 | Verify response includes `remaining_requests` | Correctly decrements |

### T8.2 — Standard Tier Limits

| Step | Action | Expected Result |
|------|--------|-----------------|
| 1 | Standard user: 50 SR actions | All succeed |
| 2 | 51st SR action | Blocked (unless user has purchased credits) |
| 3 | Standard user: 20 RadIQ queries | All succeed |
| 4 | 21st RadIQ query | Blocked |

### T8.3 — Elite Tier Limits

| Step | Action | Expected Result |
|------|--------|-----------------|
| 1 | Elite user: verify 160 SR / 50 RadIQ limits | Correctly enforced |

### T8.3b — Elite Pro Tier Limits

| Step | Action | Expected Result |
|------|--------|-----------------|
| 1 | Elite Pro user: verify 550 SR / 80 RadIQ limits | Correctly enforced |

### T8.4 — Monthly Reset

| Step | Action | Expected Result |
|------|--------|-----------------|
| 1 | User has exhausted monthly limit | Blocked |
| 2 | Set `usage_reset_date` to previous month | Simulates month rollover |
| 3 | Next AI request | Counters reset, request succeeds |

### T8.5 — Upgrade Resets Limits

| Step | Action | Expected Result |
|------|--------|-----------------|
| 1 | Free user at 10/10 SR limit | Blocked |
| 2 | User upgrades to Standard | |
| 3 | Verify new limit applies | 50/month (Standard), counter may or may not reset (verify behavior) |

### T8.6 — Admin Bypass

| Step | Action | Expected Result |
|------|--------|-----------------|
| 1 | Admin user on "free" tier | |
| 2 | Use AI features extensively | Never blocked (9999 limit) |

---

## 13. Test Suite 9 — UI/UX Verification

### T9.1 — Pricing Page Display

| Test | Scenario | Expected UI |
|------|----------|-------------|
| 9.1a | Anonymous visitor | 4 tiers shown (Free/Standard/Elite/Elite Pro), "Sign Up" CTAs |
| 9.1b | Free user (trial active) | "Trial: X days left" badge, upgrade buttons for Standard/Elite/Elite Pro |
| 9.1c | Free user (trial expired) | "Trial expired" warning, upgrade CTAs prominent |
| 9.1d | Standard subscriber | "Current Plan" on Standard, "Upgrade" on Elite/Elite Pro, "Downgrade" to Free, **credit top-up section visible** |
| 9.1e | Elite subscriber | "Current Plan" on Elite, "Upgrade" on Elite Pro, "Downgrade" to Standard/Free, **credit top-up section visible** |
| 9.1f | Elite Pro subscriber | "Current Plan" on Elite Pro, "Downgrade" to Elite/Standard/Free, **credit top-up section visible** |
| 9.1g | Pending downgrade | Yellow banner: "Switching to [plan] on [date]" with "Undo" button |
| 9.1h | All tiers show AI actions | "50 AI actions/month (~20 reports)" format, NOT just "20 reports/month" |
| 9.1i | Explanatory note visible | Below comparison table: how AI actions work, estimates are averages |

### T9.2 — Plan Change Modal

| Test | Scenario | Expected UI |
|------|----------|-------------|
| 9.2a | Upgrade preview | Shows prorated cost, immediate access date |
| 9.2b | Downgrade preview | Shows end-of-cycle date, "you'll retain access until..." |
| 9.2c | Modal loading state | Spinner while fetching preview |
| 9.2d | Modal error state | Shows error message if preview fails |

### T9.3 — Success/Failure Toasts

| Test | Scenario | Expected UI |
|------|----------|-------------|
| 9.3a | Successful upgrade | Green toast: "Upgraded to [plan]" |
| 9.3b | Successful downgrade schedule | Yellow toast: "Switching to [plan] at end of billing period" |
| 9.3c | Payment failure | Orange toast (#e96304): "Payment failed — please try again" |
| 9.3d | Undo downgrade | Green toast: "Downgrade cancelled" |

### T9.4 — Navigation Guards

| Test | Scenario | Expected Behavior |
|------|----------|------------------|
| 9.4a | Free expired user → Smart Reporter | Redirected to pricing or shown upgrade prompt |
| 9.4b | Free expired user → RadIQ | Redirected or blocked |
| 9.4c | Rate-limited user → AI feature | Shows "Limit reached — upgrade for more" |

---

## 14. Test Suite 10 — Security & Compliance

### T10.1 — Authentication Requirements

| Test | Scenario | Expected Result |
|------|----------|-----------------|
| 10.1a | Unauthenticated POST to `/stripe/create-checkout-session` | 401 Unauthorized |
| 10.1b | Unauthenticated POST to `/stripe/change-plan` | 401 Unauthorized |
| 10.1c | Unauthenticated POST to `/stripe/webhook` | Processed (webhooks are from Stripe, not users) |

### T10.2 — CSRF Protection

| Test | Scenario | Expected Result |
|------|----------|-----------------|
| 10.2a | POST to checkout without session | Rejected |
| 10.2b | Stripe webhook without signature | Rejected |

### T10.3 — Plan Manipulation Attempts

| Test | Scenario | Expected Result |
|------|----------|-----------------|
| 10.3a | POST to `/stripe/change-plan` with `{ plan: 'admin' }` | Rejected: invalid plan |
| 10.3b | POST with `{ plan: 'elite' }` when already on Elite | Rejected: "Already on this plan" |
| 10.3c | Modify `subscription_tier` directly in browser/JS | No effect (server-side only) |

### T10.4 — PII in Stripe Metadata

| Test | Scenario | Expected Result |
|------|----------|-----------------|
| 10.4a | Check Checkout session metadata | Only `user_id` and `plan`, no email/name PII |
| 10.4b | Check Stripe Customer object | Only email (required by Stripe), no medical data |

---

## 15. Code Review Checklist

### 15.1 `stripe_routes.py` — Critical Verification

| Check | What to Verify | Expected |
|-------|---------------|----------|
| **Upgrade proration** | `Subscription.modify()` uses `proration_behavior='create_prorations'` | Yes |
| **Upgrade billing anchor** | Uses `billing_cycle_anchor='now'` for upgrades | Yes |
| **Downgrade scheduling** | Uses `cancel_at_period_end=True` for downgrades | Yes |
| **No downgrade proration** | Downgrades do NOT use `proration_behavior='always_invoice'` | Correct — uses `none` or omits |
| **Auto-create Standard sub** | `customer.subscription.deleted` webhook creates Standard sub when pending | Yes |
| **Account deletion** | Calls `stripe.Subscription.cancel()` without refund arguments | Verify |
| **Customer ID validation** | `_ensure_stripe_customer()` handles live/test mode mismatch | Yes |
| **Idempotency** | Plan change checks current tier before calling Stripe | Verify |
| **Webhook signature** | `stripe.Webhook.construct_event()` with `STRIPE_WEBHOOK_SECRET` | Yes |

### 15.2 `access_control.py` — Subscription Helpers

| Check | What to Verify |
|-------|---------------|
| `upgrade_to_paid()` clears `pending_subscription_tier` and `pending_change_effective_date` |
| `downgrade_to_free()` sets `payment_status=CANCELED` |
| Both commit to DB |

### 15.3 `reporting_routes.py` — Rate Limiting

| Check | What to Verify |
|-------|---------------|
| `TIER_LIMITS` matches pricing page display |
| Trial expiry check uses 7 days |
| Monthly reset logic is correct |
| Admin bypass works |

### 15.4 `templates/pricing.html` — Frontend

| Check | What to Verify |
|-------|---------------|
| Button states match user tier |
| Pending downgrade banner shows with undo |
| Auto-checkout URL param works |
| Confirmation modal shows correct preview data |
| No hardcoded prices (should come from server or config) |

---

## 16. Automated Test Specifications

### 16.1 Python Test File: `tests/test_stripe.py`

```python
"""
Stripe Payment Integration Tests
Run: PYTHONUNBUFFERED=1 python -m pytest tests/test_stripe.py -v

Requires:
- STRIPE_SECRET_KEY (test mode)
- Test database
"""

class TestSignupAndTrial:
    def test_free_signup_sets_trial(self)
    def test_trial_expires_after_7_days(self)
    def test_grandfathered_user_no_trial(self)
    def test_direct_paid_signup_supersedes_trial(self)

class TestUpgrades:
    def test_free_to_standard_checkout(self)
    def test_free_to_elite_checkout(self)
    def test_standard_to_elite_proration(self)
    def test_upgrade_sets_correct_tier(self)
    def test_upgrade_clears_pending_fields(self)

class TestDowngrades:
    def test_elite_to_standard_scheduled(self)
    def test_standard_to_free_scheduled(self)
    def test_pending_downgrade_preserves_access(self)
    def test_undo_downgrade(self)

class TestCancellation:
    def test_account_deletion_cancels_subscription(self)
    def test_account_deletion_no_refund(self)
    def test_free_user_deletion_no_stripe_error(self)

class TestPaymentFailures:
    def test_declined_card_no_upgrade(self)
    def test_payment_failure_webhook_sets_past_due(self)
    def test_sca_challenge_flow(self)

class TestEdgeCases:
    def test_double_click_idempotent(self)
    def test_upgrade_while_downgrade_pending(self)
    def test_same_plan_change_rejected(self)
    def test_invalid_plan_rejected(self)
    def test_webhook_duplicate_idempotent(self)
    def test_stripe_customer_mode_mismatch(self)

class TestWebhooks:
    def test_checkout_completed_upgrades_user(self)
    def test_subscription_updated_pending(self)
    def test_subscription_deleted_auto_downgrade(self)
    def test_subscription_deleted_auto_create_standard(self)
    def test_invoice_failed_sets_past_due(self)
    def test_invalid_signature_rejected(self)
    def test_unknown_customer_handled(self)

class TestRateLimiting:
    def test_free_tier_sr_limit(self)
    def test_free_tier_radiq_limit(self)
    def test_standard_tier_limits(self)
    def test_elite_tier_limits(self)
    def test_elite_pro_tier_limits(self)
    def test_admin_bypass(self)
    def test_monthly_reset(self)
    def test_trial_expired_blocks(self)

class TestCreditTopUp:
    def test_buy_credits_paid_user(self)
    def test_buy_credits_free_user_blocked(self)
    def test_credits_consumed_after_monthly_limit(self)
    def test_credits_not_consumed_before_limit(self)
    def test_buy_credits_radiq_also_works(self)
    def test_webhook_adds_25_action_credits(self)

class TestLookupKeys:
    def test_resolve_price_id_standard(self)
    def test_resolve_price_id_elite(self)
    def test_resolve_price_id_elite_pro(self)
    def test_resolve_price_id_credit_pack(self)
    def test_pricing_phase_launch(self)
    def test_pricing_phase_post_launch(self)
    def test_pricing_phase_env_override(self)
    def test_tier_from_subscription_both_phases(self)
```

### 16.2 Manual Test Checklist Template

```
Date: ____________
Tester: __________
Environment: ☐ Local ☐ Staging ☐ Production
Stripe Mode: ☐ Test ☐ Live

Test ID | Description                          | Pass/Fail | Notes
--------|--------------------------------------|-----------|------
T1.1    | Free signup → trial 7 days           |           |
T1.2    | Trial expiry wall (Day 8)            |           |
T1.3    | Direct paid signup                   |           |
T2.1    | Standard → Elite (mid-month)         |           |
T2.2    | Free → Standard                      |           |
T2.5    | Free → Elite Pro                     |           |
T2.6    | Standard → Elite Pro                 |           |
T3.1    | Elite → Standard (scheduled)         |           |
T3.2    | Standard → Free (cancel)             |           |
T3.5    | Elite Pro → Elite (scheduled)        |           |
T3.4    | Undo scheduled downgrade             |           |
T4.1    | Account deletion (paid)              |           |
T5.1    | Card declined at checkout            |           |
T5.3    | 3D Secure challenge                  |           |
T6.1    | Double-click upgrade                 |           |
T8.1    | Free tier SR limit (10)              |           |
T8.2    | Standard tier SR limit (50)          |           |
T8.3    | Elite tier SR limit (160)            |           |
T8.3b   | Elite Pro tier SR limit (550)        |           |
T9.1    | Pricing page: 4 tiers + AI actions   |           |
T11.1   | Buy credits (paid user)              |           |
T11.2   | Buy credits (free user blocked)      |           |
T11.3   | Credits consumed after limit hit     |           |
T11.4   | Credits for RadIQ after limit hit    |           |
T12.1   | Lookup key resolves (launch phase)   |           |
T12.2   | Phase auto-switch logic              |           |
T12.3   | PRICING_PHASE env override           |           |
```

---

## 17. Test Execution Tracking

### 17.1 Pre-Test Verification

Before running any test:
- [ ] Stripe Dashboard is in **Test mode**
- [ ] Webhook endpoint is receiving events (check Stripe Dashboard → Webhooks → Recent events)
- [ ] Stripe test-mode products have correct lookup keys on prices
- [ ] Local DB has test users (or create fresh)
- [ ] Stripe CLI forwarding is active (if testing locally)

### 17.2 Post-Test Cleanup

After each test session:
- [ ] Check Stripe Dashboard for orphan subscriptions → cancel them
- [ ] Check Stripe Dashboard for orphan customers → delete test ones
- [ ] Reset test user DB fields to known state
- [ ] Clear any `pending_subscription_tier` values

### 17.3 Test Coverage Summary

| Suite | Tests | Priority | Automation |
|-------|-------|----------|------------|
| 1. Signup & Trial | 4 | P0 | Automated |
| 2. Upgrades | 6 | P0 | Automated |
| 3. Downgrades | 5 | P0 | Automated |
| 4. Cancellation | 3 | P1 | Automated |
| 5. Payment Failures | 5 | P1 | Semi-auto (needs test cards) |
| 6. Edge Cases | 7 | P1 | Automated |
| 7. Webhooks | 7+ | P0 | Automated |
| 8. Rate Limiting | 8 | P1 | Automated |
| 9. UI/UX | 15+ | P2 | Manual |
| 10. Security | 4+ | P1 | Automated |
| 11. Credit Top-Ups | 6 | P0 | Automated |
| 12. Lookup Keys & Pricing Phase | 8 | P0 | Automated |
| **Total** | **78+** | | |

---

> **Next steps:**
> 1. Create test-mode Stripe products with correct lookup keys on prices
> 2. Create test users (6 accounts: free, standard, elite, elite_pro, expired, edge)
> 3. Run T12.x (lookup keys) first — verify prices resolve correctly
> 4. Run T1.x (signup/trial) suite
> 5. Run T2.x (upgrades) including Elite Pro paths
> 6. Run T11.x (credit top-ups) — buy, consume, verify RadIQ credits
> 7. Run T7.x (webhooks) — verify webhook-first architecture
> 8. Run T9.x (UI/UX) — verify all 4 tiers show correctly with AI action counts
> 9. Run remaining suites in priority order
