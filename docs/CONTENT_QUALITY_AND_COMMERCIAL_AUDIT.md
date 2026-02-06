# Content Quality & Commercial Potential Audit

**Date:** February 2026  
**App:** RadInsights (radinsights.xyz)  
**Scope:** Content quality audit (cases, TNM, AI, calculators) and commercial potential in light of content.

---

## 1. Content Quality Audit

### 1.1 Case content (core product)

| Dimension | Assessment | Evidence |
|-----------|------------|----------|
| **Structure** | ✅ Strong | Cases have diagnosis, module, body part, age group; Q&A in separate `Question`/`Answer` tables; discussion; `CaseReference`; images via Cloudinary. |
| **Workflow** | ✅ Good | Draft → Pending review → Published. Only `CaseStatus.PUBLISHED` cases are shown to students. Admin/Content Manager can create and edit; visibility controlled. |
| **Completeness** | ⚠️ Variable | No automated “completeness score.” Cases can have empty discussion or few Q&A; UI does not block publishing. Quality depends on creator and optional AI prelim. |
| **AI-assisted creation** | ✅ Good | “Create Preliminary Case Data” (Claude) generates Q&A, discussion, safety checklist, teaching/anatomy images, sources. Prompt v2: “Do NOT invent or hallucinate,” “omit and add warning” if uncertain, diagnosis as anchor. Caching by diagnosis reduces cost and inconsistency. |
| **Differentiation** | ✅ Strong | Case-based + module/specialty alignment + optional TNM intelligence per case + references + notes/highlights. Not just a question bank. |

**Gaps:**  
- No minimum bar (e.g. “at least 3 Q&A and non-empty discussion”) before publish.  
- No explicit “educational only” disclaimer on the case view page (only on ScienceDirect tab).  
- Case count and coverage per module are deployment-specific; recommend tracking “published cases per module” for commercial readiness.

---

### 1.2 TNM staging content

| Dimension | Assessment | Evidence |
|-----------|------------|----------|
| **Authority** | ✅ Strong | AJCC 8th (and 9th where defined) as source. Data in `ajcc_tnm/data/` and DB (`AJCCDiseaseSite`, `AJCCStagingData`). Version mapping per disease in `ai_tnm.py`. |
| **TNM intelligence (AI)** | ✅ Good | `ai_tnm.py`: oncologic detection is keyword-based (no AI). Site matching and staging data from DB. Claude only synthesises narrative from that data; prompt says “Never invent TNM definitions - always anchor to internal AJCC database.” Six-section structured Markdown; figures injected from DB. |
| **Calculators** | ✅ Strong | Deterministic engine (`engine.py`), rule loader from JSON/ontology/DB, stage resolver, explainer. HTML calculators (e.g. larynx, oropharynx, breast) with mnemonics, imaging tips, pitfalls. Algorithm extraction for case discussion uses inline styles for embedding. Excluded slugs (e.g. intro-only) filtered from dropdown. |
| **Disclaimers** | ✅ Present | TNM calculator templates state “educational purposes only” / “Clinical Decision Support: educational only.” |

**Gaps:**  
- Calculator coverage is still a subset of AJCC (driven by which HTML calculators exist).  
- No in-app disclaimer on the TNM Intelligence *output* in the case view (only on calculator pages).

---

### 1.3 Study and reference tools

| Dimension | Assessment | Evidence |
|-----------|------------|----------|
| **References** | ✅ Good | Case-level references (`CaseReference`); TNM references (`TnmReference`). Inline vs list-only tracked. |
| **Integrations** | ✅ Good | PubMed, TCIA, ScienceDirect (with institutional/educational disclaimer), Radiopaedia, Notion, Anki. Anatomy resources by body part/module. |
| **Notes and highlights** | ✅ Good | Per-user, per-case; Anki export with configurable tags (e.g. RadInsights, Radiology, Case-ID). |

**Gaps:**  
- No systematic “reference quality” check (e.g. broken links, missing PMID).  
- Anatomy resources are static JSON; quality depends on curation.

---

### 1.4 Content governance and safety

| Dimension | Assessment | Evidence |
|-----------|------------|----------|
| **Roles** | ✅ Clear | Student (view), Content Manager (create/edit), Admin (full). Approval workflow for sensitive admin actions. |
| **AI transparency** | ✅ Good | AI-generated prelim content wrapped in orange styling in editor; wrappers stripped on save when published so final content is “clean.” Cache warning when diagnosis was previously generated. |
| **Legal** | ✅ Present | Terms of Use and Privacy Policy (RadInsights). Broader “educational only” could be reinforced on case and TNM intelligence views. |

**Gaps:**  
- No “last clinically reviewed” or “content version” field on cases.  
- No formal “senior review” or sign-off field (prompt mentions “aspects that require senior review” but no workflow flag).

---

## 2. Commercial Potential (Content Lens)

### 2.1 Why content supports commercial potential

1. **Differentiation**  
   Combined case-based learning + TNM (AJCC-anchored) + AI prelim + AI TNM intelligence + deterministic calculators is hard to replicate. Competitors (e.g. Radiopaedia, question banks) don’t offer this bundle.

2. **Quality floor**  
   AI prompts explicitly forbid hallucination and tie to diagnosis/AJCC. TNM output is grounded in DB. Calculators are deterministic and explainable. Published cases go through a status workflow.

3. **Scalability**  
   AI prelim and TNM intelligence scale with usage; calculator and AJCC content scale with one-off builds. Case library can grow with Content Managers and admins.

4. **Positioning**  
   Content supports “trainees and consultants,” “reporting and exam prep,” not just “FRCR only,” which fits the broader positioning (see rebrand).

### 2.2 Content-related risks for commercial use

1. **Inconsistent depth**  
   Some cases may be thin (few Q&A, short discussion). A minimum completeness bar or “quality tier” (e.g. “reviewed”) would strengthen perceived value.

2. **No formal clinical review**  
   For paid and/or institutional use, “clinically reviewed” or “senior verified” would improve trust. Currently only workflow is draft → review → publish.

3. **Disclaimer coverage**  
   “Educational only” is on calculator pages and ScienceDirect; adding a short disclaimer on the main case view and on TNM Intelligence output would align with commercial/legal expectations.

4. **Coverage and discovery**  
   Commercial appeal depends on having enough cases across modules/specialties. Tracking and improving “published cases per module” and “cases with TNM” is recommended.

---

## 3. Summary and Recommendations

### Content quality summary

| Area | Quality | Notes |
|------|---------|--------|
| Case structure and workflow | ✅ Strong | Clear schema, publish gate, AI-assisted generation with safety rules. |
| TNM content | ✅ Strong | AJCC-anchored, deterministic calculators, AI synthesis from DB. |
| Study tools and references | ✅ Good | Rich integrations; reference quality not automated. |
| Governance and safety | ✅ Good | Roles and AI transparency in place; no “clinically reviewed” or case-level disclaimer on main view. |

**Overall:** Content quality is **good to strong** and **sufficient to support commercial use**, provided a few gaps are addressed and content volume/coverage is monitored.

### Commercial potential (content perspective)

- **Verdict:** Content has **clear commercial potential**. The mix of cases, TNM (authoritative + AI + calculators), and study tools is differentiated and scalable. Main levers are: (1) minimum quality/completeness for published cases, (2) optional “clinically reviewed” or “verified” tier, (3) consistent disclaimers, (4) tracking and growing coverage.

### Recommended actions (content)

1. **Add a short “educational only” disclaimer** on the main case view (e.g. footer of case content or above Q&A) and on TNM Intelligence output.
2. **Consider a minimum completeness check** before publish (e.g. at least one Q&A pair and non-empty discussion), or a “completeness” badge for students.
3. **Track content metrics:** published cases per module, cases with TNM intelligence, cases with calculator link. Use for prioritising coverage and for sales/marketing.
4. **Optional:** Add “Last reviewed” or “Content version” and/or “Clinically reviewed” for a subset of cases to support higher-tier or institutional positioning.
5. **Keep AI and TNM prompts and data sources as-is** from a quality standpoint; continue to avoid inventing TNM definitions and to anchor to diagnosis/AJCC.

---

## 4. References in Repo

| Topic | Location |
|-------|----------|
| Case model, status, workflow | `models.py` (Case, CaseStatus, Question, Answer) |
| AI prelim prompt and behaviour | `ai_prelim.py`, `docs/FULL_AI_PROMPT.md`, `docs/AI_INTEGRATION_REFERENCE.md` |
| TNM intelligence design | `ai_tnm.py`, `docs/TNM_INTELLIGENCE_WORKFLOW.md` |
| TNM calculator backend | `tnm_calculator/engine.py`, `loader.py`, `docs/TNM_CALCULATOR_BACKEND.md` |
| Commercial and positioning | `docs/COMMERCIAL_ASSESSMENT.md` |
| User roles and workflows | `docs/USER_ROLES_WORKFLOWS.md` |
