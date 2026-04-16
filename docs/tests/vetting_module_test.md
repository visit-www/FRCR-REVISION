# Vetting Module Test Plan — Apr 17, 2026

## Pre-requisites
- Vercel deploy complete (check logs for `sync_master_protocols: done — inserted=0 updated=229`)
- `master-v2` sync should show `updated=229` on first deploy (re-sync all body_sections)
- Subsequent deploys: `skipped=229`

## A. Protocol Matching (AI slug + catalogue)

### A1. Non-contrast studies
| # | Referral text | Expected study | Expected protocol slug | Expected contrast |
|---|--------------|----------------|----------------------|-------------------|
| 1 | "Fall, hit head, GCS 15" | CT Brain | `brain` | none |
| 2 | "Right-sided weakness, rule out stroke" | CT Stroke Protocol | `ct-stroke-protocol-ncct-cta-ctp` | none (NCCT component) |
| 3 | "Loin to groin pain, haematuria" | CT KUB | `kub-calculus` | none |
| 4 | "Chronic cough, non-smoker" | HRCT Chest | `hr-thorax` | none |
| 5 | "Fall on outstretched hand, wrist pain" | XR or CT | non-contrast | none |

### A2. Contrast studies
| # | Referral text | Expected study | Expected contrast |
|---|--------------|----------------|-------------------|
| 6 | "Known lung cancer, staging CT" | CT CAP staging | iv |
| 7 | "RIF pain, ?appendicitis" | CT Abdomen Pelvis | iv |
| 8 | "SOB, pleuritic chest pain, Wells 5, D-dimer positive" | CTPA | iv |
| 9 | "Neck lump, ?SCC, 2WW" | CT Neck | iv |
| 10 | "Known HCC, follow-up" | CT Liver 4-phase | iv |

### A3. Edge cases
| # | Referral text | What to check |
|---|--------------|---------------|
| 11 | "Fall, on apixaban, frontal swelling" | Should pick non-contrast CT Brain, not stroke protocol |
| 12 | "3-year-old, fall from height" | Should flag as paediatric, pick appropriate protocol |
| 13 | "Diabetic, eGFR 28, staging CT for colon cancer" | Should flag metformin + eGFR concern |
| 14 | "Pregnant, 32 weeks, ?PE" | Should flag pregnancy, still recommend CTPA |

## B. Contrast Toggle
| # | Test | Expected |
|---|------|----------|
| 1 | Submit A1 test 1 (head injury) | Toggle auto-set to "Non-contrast" |
| 2 | Click "IV Contrast" toggle | eGFR and Allergy rows appear |
| 3 | Click "Non-contrast" toggle | eGFR and Allergy rows hide |
| 4 | Submit A2 test 6 (staging CT) | Toggle auto-set to "IV Contrast" |

## C. Protocol Generation (when no library match)
| # | Test | Expected |
|---|------|----------|
| 1 | Submit a rare study (e.g. "CT 4D parathyroid") | Should match library protocol `4d-neck` |
| 2 | Submit obscure study with no match | AI generates protocol, no 500 error |
| 3 | Set contrast toggle to "Non-contrast" before generating | Generated protocol should be non-contrast |

## D. AI Flags
| # | Test | Expected |
|---|------|----------|
| 1 | Complete referral: "65M, fall, GCS 15, CT head please" | 0 flags (referral is complete) |
| 2 | Sparse referral: "CT chest" | Flags asking for clinical indication |
| 3 | PE pathway: "SOB, chest pain" (no Wells/D-dimer) | Flags Wells score / D-dimer |

## E. Safety Checks
| # | Test | Expected |
|---|------|----------|
| 1 | Non-contrast study | eGFR/allergy rows hidden |
| 2 | IV contrast study | eGFR/allergy rows visible |
| 3 | Diabetic patient with contrast | metformin_check_required = true |
| 4 | Skip eGFR via N/A button | Proceeds without eGFR |

## F. PII Guard
| # | Test | Expected |
|---|------|----------|
| 1 | Include "St James classification" in question | NOT flagged (classification context) |
| 2 | Include "admitted to St James Hospital" in referral | Flagged as Institution Name |
| 3 | Dismiss PII warning → continue to protocol | PII override allows subsequent requests |

## G. Change Protocol Search
| # | Test | Expected |
|---|------|----------|
| 1 | Search "ct brain" | Brain protocol at top, NOT CT GI Bleed |
| 2 | Search "ctpa" | CT Pulmonary Angiography protocols |
| 3 | Search "liver" | Liver-related protocols, not brain |

## H. Error Handling
| # | Test | Expected |
|---|------|----------|
| 1 | Empty referral text → submit | "Referral text cannot be empty" error |
| 2 | Very long referral (>5000 chars) | Handled gracefully |
| 3 | Network error during protocol generation | Toast message, not stuck UI |
