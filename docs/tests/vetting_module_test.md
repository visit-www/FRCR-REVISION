# Vetting Module Test Plan — Apr 17, 2026

## Pre-requisites
- Vercel deploy complete (check logs for `sync_master_protocols: done — inserted=0 updated=229`)
- `master-v4` sync should show `updated=229` on first deploy (re-sync all body_sections + contrast + ARI protocol field)
- Subsequent deploys: `skipped=229`

## Test Progress
- **Tested Apr 17, 2026**: All sections A-H complete
- **Status**: 28/31 PASS, 1 FAIL (G2 ctpa search — fix deployed), 1 SKIPPED (H3), 1 NOT TESTED (C3)
- **15 bugs found and fixed** during testing — see commit log Apr 17

### Issues Found & Fixed During Testing
1. Protocol "50ml hand inject" stale data — `_SYNC_VERSION` not bumped after contrast fix → bumped to master-v3, then v4
2. "Confirmed Findings" displayed raw flag text — changed to "Additional Clinical Information" with just user's notes, then merged into clinical text with italic "Additional information:" label
3. ARI oncology protocols missing Parameters — fallback to `protocol` field added
4. Colorectal cancer body_section "Cardiovascular" — stale DB, fixed by v4 re-sync (keyword "cancer" → Multisystem)
5. AI overriding user's modality choice (CT→MRI for scaphoid) — modality hint now enforced as hard constraint
6. AI flags too numerous/verbose — structured prompt: max 3, decision-gap focus, no safety/completeness flags
7. Pregnancy check auto-advancing to protocol — removed all auto-advance, user must click "Continue"
8. No rationale shown for library protocols — added rationale card with study name + guideline citation
9. Safety checks not shown in final output — `_collectSafetyResponses` now reads visible inputs regardless of validation_json
10. No low eGFR warning — added red alert + rationale textarea when below threshold
11. No way to override library protocol match — added "Generate via RadIQ" button (orange)
12. Clinical details not editable — added pen icon edit button in Scene 3
13. AI putting flag-like text into cleaned_clinical_text — user can now edit clinical details
14. Personal protocols not in AI catalogue — query now includes current user's personal protocols

### Admin Improvements (during testing session)
- Admin user management: Plan/Usage column (color-coded badges), Reset AI Quota button, Send Password Reset button, Plan change dropdown
- Subscription + plan merged into single column

---

## A. Protocol Matching (AI slug + catalogue)

### A1. Non-contrast studies
| # | Referral text | Expected | Result |
|---|--------------|----------|--------|
| 1 | "Fall, hit head, GCS 15" | CT Brain, slug `brain`, none | PASS — correct protocol, flags clinically appropriate |
| 2 | "Right-sided weakness, rule out stroke" | CT Stroke Protocol | PASS |
| 3 | "Loin to groin pain, haematuria" | CT KUB, `kub-calculus`, none | PASS |
| 4 | "Chronic cough, non-smoker" | HRCT Chest, `hr-thorax`, none | SKIPPED |
| 5 | "Fall on outstretched hand, wrist pain" | XR or CT, non-contrast | PASS — AI correctly suggested XR first-line, generated MRI scaphoid protocol when user indicated normal XR |

### A2. Contrast studies
| # | Referral text | Expected | Result |
|---|--------------|----------|--------|
| 6 | "Known lung cancer, staging CT" | CT CAP staging, iv | PASS |
| 7 | "RIF pain, ?appendicitis" | CT Abdomen Pelvis, iv | PASS |
| 8 | "SOB, pleuritic chest pain, Wells 5, D-dimer positive" | CTPA, iv | PASS |
| 9 | "Neck lump, ?SCC, 2WW" | CT Neck, iv | PASS |
| 10 | "Known HCC, follow-up" | CT Liver 4-phase, iv | NOT TESTED |

### A3. Edge cases
| # | Referral text | Expected | Result |
|---|--------------|----------|--------|
| 11 | "Fall, on apixaban, frontal swelling" | Non-contrast CT Brain, not stroke | PASS |
| 12 | "3-year-old, fall from height" | Paediatric flag, appropriate protocol | PASS |
| 13 | "Diabetic, eGFR 28, staging CT for colon cancer" | metformin_check, eGFR concern | PASS — found colorectal protocol body_section bug (fixed) |
| 14 | "Pregnant, 32 weeks, ?PE" | Pregnancy flag, CTPA | PASS |

## B. Contrast Toggle
| # | Test | Expected | Result |
|---|------|----------|--------|
| 1 | Submit A1 test 1 (head injury) | Toggle auto-set to "Non-contrast" | PASS |
| 2 | Click "IV Contrast" toggle | eGFR and Allergy rows appear | PASS |
| 3 | Click "Non-contrast" toggle | eGFR and Allergy rows hide | PASS |
| 4 | Submit A2 test 6 (staging CT) | Toggle auto-set to "IV Contrast" | PASS |

## C. Protocol Generation (when no library match)
| # | Test | Expected | Result |
|---|------|----------|--------|
| 1 | Submit "CT 4D parathyroid" | Should match library protocol `4d-neck` | PASS — matched correctly, zero flags with complete history |
| 2 | Submit "CT perfusion brain for Moyamoya disease" | AI generates protocol, no 500 error | PASS |
| 3 | Set contrast toggle to "Non-contrast" before generating | Generated protocol should be non-contrast | NOT TESTED |

## D. AI Flags
| # | Test | Expected | Result |
|---|------|----------|--------|
| 1 | Complete referral: "65M, fall, GCS 15, CT head please" | 0 flags | PASS |
| 2 | Sparse referral: "CT chest" | Flags asking for clinical indication | PASS |
| 3 | PE pathway: "SOB, chest pain" (no Wells/D-dimer) | Flags Wells score / D-dimer | PASS |

## E. Safety Checks
| # | Test | Expected | Result |
|---|------|----------|--------|
| 1 | Non-contrast study | eGFR/allergy rows hidden | PASS |
| 2 | IV contrast study | eGFR/allergy rows visible | PASS |
| 3 | Diabetic patient with contrast | metformin_check_required = true | PASS |
| 4 | Skip eGFR via N/A button | Proceeds without eGFR | PASS |

## F. PII Guard
| # | Test | Expected | Result |
|---|------|----------|--------|
| 1 | Include "St James classification" in question | NOT flagged (classification context) | PASS |
| 2 | Include "admitted to St James Hospital" in referral | Flagged as Institution Name | PASS |
| 3 | Dismiss PII warning → continue to protocol | PII override allows subsequent requests | PASS |

## G. Change Protocol Search
| # | Test | Expected | Result |
|---|------|----------|--------|
| 1 | Search "ct brain" | Brain protocol at top, NOT CT GI Bleed | PASS |
| 2 | Search "ctpa" | CT Pulmonary Angiography protocols | FAIL — "ctpa" returned no results. Fix: added abbreviation expansion map. Re-test after deploy. |
| 3 | Search "liver" | Liver-related protocols, not brain | PASS |

## H. Error Handling
| # | Test | Expected | Result |
|---|------|----------|--------|
| 1 | Empty referral text → submit | "Referral text cannot be empty" error | PASS |
| 2 | Very long referral (>5000 chars) | Handled gracefully | PASS — maxlength="5000" on textarea prevents overly long input |
| 3 | Network error during protocol generation | Toast message, not stuck UI | SKIPPED (hard to simulate in production) |
