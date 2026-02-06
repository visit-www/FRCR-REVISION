# RadInsights (FRCR Revision) – Commercial Assessment & Audit

**Date:** February 6, 2026  
**App:** FRCR Revision / RadInsights (radinsights.xyz)  
**Scope:** Functions audit, commercial potential, market outlook, path to revenue

---

## 1. Commercial Potential

### What the app does (audit summary)

| Area | Status | Notes |
|------|--------|--------|
| **Core product** | ✅ Live | FRCR exam prep: cases, Q&A, discussions, images (Cloudinary). |
| **User model** | ✅ | Roles: Student, Content Manager, Admin. Subscription fields present (FREE/PAID/CANCELED). |
| **Access control** | ✅ | Free users limited to **2 cases per module**; paid/unlimited via subscription status. |
| **AI features** | ✅ | Prelim case generation (Claude), TNM intelligence (RAG-style, AJCC-backed), model choice (Sonnet/Opus). |
| **TNM staging** | ✅ | AJCC 8th Edition data, interactive viewers, AI-generated staging summaries, standalone calculators (e.g. larynx, oropharynx, breast). |
| **Study tools** | ✅ | Notes/highlights, Anki, PubMed, TCIA, ScienceDirect integration, reference search. |
| **Payments** | ⚠️ Not implemented | Subscription/payment **models and admin UI exist**; no payment gateway (Razorpay/Stripe) or checkout. |
| **Legal** | ✅ | Terms of Use and Privacy Policy pages present (RadInsights branding). |
| **Deployment** | ✅ | Production at radinsights.xyz, Vercel serverless, Neon PostgreSQL. |

### Commercial potential (summary)

- **Strong fit for paid B2C:** Niche (FRCR candidates), clear outcome (exam prep), and differentiated features (TNM intelligence, FRCR-aligned structure, AI-assisted case building) support a subscription.
- **Pricing already scoped:** Business plan targets Trial → Free (3 reads/month) → Monthly (₹999 / £9.99) → Annual (₹6,499 / £79.99), with optional single-case and TNM/mock packs.
- **Infrastructure ready:** User subscription fields, access limits (2 cases per module for free), and admin subscription management are in place; revenue is blocked only by payment integration and paywall UX.
- **Upside:** Institutional licensing (e.g. deaneries, hospitals) and add-ons (TNM packs, mock exams) can increase ARPU and LTV.

**Verdict:** **High commercial potential** for a focused medical-ed product, assuming payment is implemented and content/UX are maintained.

---

## 2. Possible Future in the Market

### Why it can have a future

- **Clear niche:** FRCR (UK radiology training) has a defined, recurring cohort and no dominant “FRCR-only” platform.
- **Differentiation (from your own planning):**
  - TNM intelligence + FRCR-specific structure.
  - AI staging summaries from a radiologist perspective.
  - FRCR module-aligned cases and study tools (notes, Anki, references).
- **Technical moat:** AJCC-backed TNM + your own calculators and AI prompts are non-trivial to replicate.
- **Trends:** Medical education and exam prep are moving online; AI-assisted, case-based learning is growing.

### Risks and constraints

- **Market size:** FRCR is UK-focused; total addressable market is limited unless you expand (e.g. other radiology exams or geographies).
- **Competition:** Radiopaedia, Radiology Masterclass, and question banks exist but are not FRCR-specific; you compete on “best FRCR + TNM + AI” story.
- **Trust and compliance:** Medical/educational content and AI outputs need consistent disclaimers (“educational only”, “not clinical advice”) and careful handling of personal/health-related data (GDPR, etc.).
- **Unit economics:** Claude API and other services have per-user cost; subscription pricing must cover COGS and leave margin.

**Verdict:** **Reasonable future in the market** as a focused FRCR/TNM product, especially if you add payments, tighten positioning, and optionally expand to adjacent exams or institutional sales.

---

## 3. Steps to Make It Public and Start Generating Money

Below is a concrete sequence: legal/compliance, payments, product, then distribution.

### Phase A: Legal and compliance (before taking money)

1. **Review and finalise legal pages**
   - Ensure Terms of Use clearly state: educational use only, no clinical reliance, subscription terms, refund/cancel policy, and acceptable use.
   - Ensure Privacy Policy covers: sign-up, case views, notes, AI usage, third parties (e.g. Cloudinary, Resend, Anthropic), retention, and user rights (access, delete, data export).
   - If you target UK/EU: confirm GDPR alignment (lawful basis, consent where needed, data processor terms for vendors).
2. **Medical and AI disclaimers**
   - Keep and standardise “educational purposes only / not for clinical decision-making” on:
     - Case view, TNM intelligence output, TNM calculators, and any AI-generated text.
   - Consider a short “About AI” note (e.g. in footer or help) explaining that AI assists learning and can make errors.
3. **Insurance and entity (recommended before serious revenue)**
   - Consider professional indemnity / educational product insurance when revenue grows.
   - If not already: operate as a proper entity (e.g. limited company) and use it in contracts and on the site.

### Phase B: Payments and subscription (revenue engine)

Your `docs/plans/BUSINESS_MODEL_PLAN.md` and `MASTER_PLANNING_INDEX.md` already define this; here is a condensed implementation order:

1. **Database and model**
   - Add any missing fields from the business plan (e.g. `trial_ends_at`, `monthly_reads_count`, `payment_gateway`, `gateway_customer_id`, `gateway_subscription_id`) and run migrations.
2. **Payment backend**
   - Implement `payment_routes.py` (or equivalent) with:
     - Stripe (GBP): checkout session, customer portal, webhook for `invoice.paid` / `customer.subscription.deleted`, etc.
     - Razorpay (INR): orders, verify signature, webhook to update subscription.
   - Map webhook events to `SubscriptionStatus` and `PaymentStatus` (and dates); ensure idempotency and logging.
3. **Access control**
   - Align with business plan: e.g. trial (full access until `trial_ends_at`), free (e.g. 3 case reads per month), paid (unlimited). Implement or adjust `has_case_view_access()` and any monthly reset (cron or daily job).
4. **Frontend**
   - **Pricing page:** plans (trial, monthly, annual), currency detection or toggle (INR/GBP), CTA to checkout.
   - **Checkout:** redirect to Stripe Checkout or Razorpay; success/cancel URLs; optional “billing” page (manage subscription, cancel).
   - **Upgrade prompts:** when a free user hits the limit, show a clear paywall/modal with link to pricing.
   - **Trial banner:** “Trial ends in X days” for users in trial (optional but recommended).
5. **Environment and go-live**
   - Use test keys first; then switch to live Stripe/Razorpay keys and webhook secrets in production.
   - Ensure webhook URLs are correct and verified in both dashboards.

### Phase C: Product and positioning (so people pay)

1. **Content and quality**
   - Enough cases across FRCR modules so paid “unlimited” feels valuable.
   - Keep TNM calculators and AI outputs accurate and clearly disclaimer’d.
2. **Conversion**
   - Onboarding: short “how it works” and trial countdown.
   - In-app CTAs: e.g. “Unlock all cases” when a free user hits limits or browses locked content.
3. **Trust**
   - Testimonials, “Used by FRCR candidates”, or similar (with permission).
   - Clear contact and support (email or form).

### Phase D: Distribution and growth

1. **Launch**
   - Soft launch: existing users / mailing list / radiology trainee forums or societies (where allowed).
   - Pricing page live and linked from nav/footer; sign-up flow leads to trial then paid.
2. **Analytics**
   - Track sign-ups, trial starts, trial→paid and free→paid conversion, churn (even with simple events to start).
3. **Later**
   - Optional: institutional licensing (manual invoicing at first), single-case or TNM/mock packs as in the business plan.

---

## Summary Table

| Question | Answer |
|----------|--------|
| **1. Commercial potential** | **High** for a niche medical-ed product: differentiated FRCR + TNM + AI, subscription model and access control already designed and partly built; revenue blocked mainly by payment integration. |
| **2. Future in market** | **Yes, if** you execute on payments, keep content and disclaimers solid, and own the “FRCR + TNM + AI” position; market is limited to UK radiology unless you expand. |
| **3. Steps to go public and make money** | **(A)** Harden legal pages and disclaimers. **(B)** Implement Stripe + Razorpay, subscription lifecycle, and paywall/upgrade UI. **(C)** Strengthen content and conversion. **(D)** Launch with a clear pricing page and basic analytics, then iterate. |

---

## References in repo

- `docs/plans/BUSINESS_MODEL_PLAN.md` – Freemium tiers, payment flow, checklist.
- `docs/plans/MASTER_PLANNING_INDEX.md` – Plan 5 (Business Model), other priorities.
- `models.py` – `User`, `SubscriptionStatus`, `PaymentStatus`, subscription dates.
- `access_control.py` – `has_case_view_access()` (2 cases per module for free).
- `templates/terms_of_use.html`, `templates/privacy_policy.html` – Legal pages.
