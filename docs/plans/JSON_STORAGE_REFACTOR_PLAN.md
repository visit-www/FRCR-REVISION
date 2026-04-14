# JSON Storage Refactor Plan

> **Goal:** Store all AI-generated content as structured JSON in DB, render to HTML at serve time. Removes dependency on Claude-generated HTML, reduces token costs, improves CMV accuracy, enables re-rendering.

**Status:** Planned
**Priority:** High (enables better CMV, cheaper generation, consistent UI)
**Keyword:** `RADINSIGHTS-JSON-REFACTOR-2026`

---

## Problem

Currently, Claude generates HTML directly for most content types. This causes:

1. **Wasted tokens:** HTML is 30-50% larger than equivalent JSON
2. **Lossy CMV:** When verifying stored content, we strip HTML to get text — losing table structure, field associations, and context
3. **Fragile rendering:** Claude's HTML varies between calls — inconsistent styling, occasional broken tags
4. **No re-renderability:** If we change card layout or CSS, all existing content is frozen in old format
5. **Temporary bridge code:** `_extract_text_from_ai_output()` has HTML table preservation hacks (`</td>` → `|`) that exist only because we don't have the original JSON

## Architecture

### Current Flow (wasteful)
```
Claude → HTML string → stored in DB → served directly
                                     → stripped to text for CMV (lossy)
```

### Target Flow
```
Claude → structured JSON → stored in DB (template_json column)
                          → rendered to HTML at serve time (render functions)
                          → sent to Gemini CMV as structured JSON (lossless)
```

## DB Changes

Add `template_json` (TEXT/JSON) column to content tables:

| Table | Current HTML Column | New JSON Column | Render Function |
|-------|-------------------|----------------|-----------------|
| `reporting_algorithm` | `template_html` | `template_json` | `render_anatomy_html()` (already exists for anatomy) |
| `reporting_algorithm` | `algorithm_html` | `algorithm_json` | New: `render_algorithm_html()` |
| `radiology_pearl` | `pearl_text` (plain text) | Keep as-is | N/A (already text) |
| `imaging_protocol` | `detailed_protocol_html` | `protocol_json` | New: `render_protocol_html()` |
| `case` | `discussion` / `ai_discussion` | `discussion_json` | New: `render_case_discussion_html()` — includes Q&A |
| `incidental_finding_calculator` | `algorithm_html` | `algorithm_json` | New: `render_tool_html()` |
| `tnm_calculator` | Generated HTML | `tnm_json` | New: `render_tnm_essential_html()` |

### Dual-Read Strategy (migration)

```python
# Serve content: prefer JSON, fallback to stored HTML
if obj.template_json:
    html = render_anatomy_html(json.loads(obj.template_json))
else:
    html = obj.template_html  # Legacy HTML-only content
```

Old content keeps working. New content gets JSON. No forced re-generation.

## Content Types — Full Inventory

### Tier 1: Structured (high-value JSON migration)
These have clear field-level structure. JSON storage significantly improves CMV and re-rendering.

| Content | Current Output | Target JSON Schema | CMV Impact |
|---------|---------------|-------------------|------------|
| **Anatomy Snippet** (admin + user) | JSON → HTML (render exists) | Already JSON — just need to STORE it | High: CMV gets structured fields |
| **Reporting Algorithm** | HTML string | `{title, steps[], decision_points[], references[]}` | High |
| **Radiology Tool** | HTML string | `{title, criteria[], scoring, interpretation[]}` | High |
| **Protocol** (clinical safety) | HTML string | `{title, indications[], contraindications[], technique, dose{}, safety_notes[]}` | Critical: dose values must be verified |
| **TNM Essential** | HTML (from calculator gen) | `{cancer_site, staging_table[], key_points[], references[]}` | High |
| **Case Discussion + Q&A** | HTML/text | `{diagnosis, key_findings[], discussion, questions[{question, answer, teaching_point}], differential[], references[]}` | High: measurements, staging, prevalence in discussion |

### Tier 2: Free-form prose (no JSON migration — metadata only)
These are essentially free text. JSON adds overhead without structural benefit. Store text + metadata. CMV runs on the text directly at generation time.

| Content | Recommendation |
|---------|---------------|
| **Email to Patient** | Keep as text + metadata `{tone, context}` |
| **Email to Colleague** | Keep as text + metadata `{urgency, context}` |
| **MDT Summary** | Keep as text (mostly prose narrative) |
| **Incident Report** | Keep as text + metadata `{category, severity}` |
| **Complaint Response** | Keep as text + metadata `{complaint_summary}` |
| **GP Referral Reply** | Keep as text + metadata `{clinical_context}` |
| **Radiology Pearl** | Already plain text — keep as-is |
| **SBA Question** | Keep as HTML (mostly formatted prose with options) |
| **Viva Question** | Keep as HTML (mostly formatted prose) |

**Rationale:** These outputs are conversational/narrative. Forcing JSON structure adds complexity and prompt overhead without improving CMV accuracy or rendering consistency. CMV verifies them at generation time from the raw text.

## Implementation Phases

### Phase 1: Store JSON alongside HTML (non-breaking)
- Add `template_json` columns via migration
- Modify AI generation functions to save JSON before rendering
- Anatomy snippets: save `parsed` dict to `template_json` (already have the JSON, just not storing it)
- No changes to serve path — still serve `template_html`
- **Effort:** 1 session

### Phase 2: CMV reads from JSON (immediate quality improvement)
- Update `_extract_text_from_ai_output()` to prefer `template_json` when available
- Remove HTML table preservation hacks (temporary bridge code)
- Dashboard "Verify" reads JSON from DB instead of HTML
- **Effort:** 1 session

### Phase 3: Render from JSON at serve time
- Implement `render_*_html()` functions for each content type
- Update serve routes to use dual-read (JSON → render, or fallback to stored HTML)
- **Effort:** 2-3 sessions (one per content tier)

### Phase 4: Prompt optimisation (cost reduction)
- Remove "produce HTML" from all AI prompts
- Replace with "produce JSON matching this schema"
- Smaller output → fewer tokens → lower cost
- Estimated savings: 30-50% on output tokens across all AI calls
- **Effort:** 1-2 sessions

### Phase 5: Cleanup
- Remove temporary bridge code in `gemini_verify.py`
- Remove legacy HTML generation paths
- Backfill: optionally re-generate high-value content (anatomy, protocols) to get JSON versions
- **Effort:** 1 session

## Cost Impact

| Metric | Before | After | Savings |
|--------|--------|-------|---------|
| Anatomy snippet output tokens | ~5000 (HTML) | ~3000 (JSON) | ~40% |
| Algorithm output tokens | ~3000 (HTML) | ~1800 (JSON) | ~40% |
| CMV accuracy | Lossy (HTML→text) | Lossless (JSON direct) | Significant |
| Re-render capability | None | Full | New capability |

## Risks

1. **Dual-read complexity:** Two code paths (JSON vs HTML) during migration. Mitigated by fallback pattern.
2. **Rendering bugs:** New render functions may produce different HTML than Claude did. Test thoroughly.
3. **Schema evolution:** JSON schemas will evolve. Store schema version in JSON for forward compatibility.
4. **Existing content:** ~200+ existing items won't have JSON. Accept this — they keep working via HTML fallback.

## CMV Badge Integration (learned from Apr 14 session)

The current CMV badge injection uses a tiered text-search approach (TreeWalker) to place badges near matching claim text in the DOM. This has fundamental limitations with HTML-stored content:

1. **Whitespace mismatch:** HTML has extra padding/spaces that don't match Gemini's claim text
2. **Cross-element claims:** Claims spanning multiple `<td>` cells can't be found in a single text node
3. **Duplicate matches:** Same number (e.g., "4") appears in multiple places, causing badge clustering
4. **28/30 placement rate:** Current best is ~93% — 2 claims couldn't be placed

**How JSON storage fixes this:**

With JSON, each claim maps to a specific field path (e.g., `measurements[0].normal`, `normal_variants[2].prevalence`). The renderer knows exactly which DOM element corresponds to which JSON field, so badge placement is:

```js
// JSON approach: exact, no searching needed
var cell = document.querySelector('[data-field="measurements.0.normal"]');
cell.insertAdjacentElement('beforeend', badgeEl);
```

**Phase 3 addition:** When implementing `render_*_html()` functions, add `data-field` attributes to elements that contain verifiable claims. The CMV badge JS then matches `claim.field_path` to `[data-field]` — zero text searching, 100% placement accuracy.

**Current bridge (to be removed in Phase 5):**
- `cmv-badges.js` — tiered TreeWalker search (full text → 5 words → 3 words → last 3 words)
- Dead code in `knowledge_hub.html` wrapped in `{% if false %}` block
- `_inject_badges_into_html()` in `radinsight_peer_review.py` — server-side injection (currently unused, kept for other content types)
- HTML table preservation hacks in `gemini_verify.py` `_extract_text_from_ai_output()`

## Dependencies

- Phase 1 is standalone (just add columns + save JSON)
- Phase 2 depends on Phase 1
- Phase 3 depends on Phase 1
- Phase 4 depends on Phase 3
- Phase 5 depends on all above

## Success Criteria

- [ ] All new AI-generated content has `template_json` stored
- [ ] CMV reads from JSON when available (no HTML stripping needed)
- [ ] All render functions produce identical-quality HTML to Claude's output
- [ ] 30%+ reduction in output tokens for Tier 1 content types
- [ ] No regression in content display quality
