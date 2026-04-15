# RadInsights Coding Agent Instructions

> Project-specific instructions for Claude Code sessions.
> This file is read at the start of every conversation.

## Project Context
- Flask app deployed on Vercel (Pro plan), Neon PostgreSQL
- All AI calls via `requests.post` to Anthropic Messages API (not SDK)
- See memory files for full architecture, feature inventory, and active plans

## Memory Sync Protocol

**At the START of every session**, proactively check for pending memory updates:

1. Ask the user to run: `curl -s https://www.radinsights.xyz/api/admin/claude-memory-sync | python3 -m json.tool`
   - Or if running locally: `curl -s http://localhost:5000/api/admin/claude-memory-sync`
2. For each unsynced entry in the response:
   - Read the `summary`, `category`, and `details` fields
   - Update the appropriate memory file (or create a new one)
   - Update `MEMORY.md` index if needed
3. After processing, tell the user to mark entries as synced:
   - `curl -X POST https://www.radinsights.xyz/api/admin/claude-memory-sync/mark-synced`

**Also check periodically** during long sessions (every ~4-6 hours of active work).

**When the user says "what changed?" or "what's new?":**
- Same protocol — check the sync endpoint first before answering

**Note:** Every document save in the admin Docs Hub auto-creates a sync entry — no manual action needed from the admin side.

## Deployment Rules
- Vercel auto-deploys on `git push` to main — NEVER run `vercel --prod` manually
- Only commit production-necessary files — never commit utility scripts, data files, or test results from scripts/
- Always syntax-check Python files before committing: `python3 -c "import py_compile; py_compile.compile('file.py', doraise=True)"`

## Key Documentation (Admin Frontend)
- `/api/admin/docs-hub` — Documentation hub (editable docs stored in DB)
- `/api/admin/ai-documentation` — AI endpoints, models, prompts, packages
- `/api/admin/marketing` — Marketing launch kit + business model
- `/api/admin/seo-audit` — SEO audit + action plan
- `docs/tests/peer_review_test.md` — Peer review test plan
- `docs/tests/peer_review_package_test.md` — Package-level test plan

## Admin Document Manifest
- When creating a new markdown doc in `docs/`, **always** add a corresponding row to `_DOC_MANIFEST` in `app.py` (search for `_DOC_MANIFEST`) so it auto-syncs to the admin_document DB table on next deploy
- Format: `('slug', 'Title', 'category', 'docs/FILENAME.md')`
- Categories: marketing, finance, seo, technical, qa, general

## Editing Admin Documents (DB is source of truth)
- The DB `admin_document` table is the **single source of truth** for all admin docs
- Template files (`templates/admin_*.html`) are only used for initial seeding — do NOT edit them to update content
- To patch doc content in a code session, write a **one-time migration block** in `app.py` that updates the DB row directly:
  ```python
  _doc = _AD.query.filter_by(slug='the-slug').first()
  if _doc and 'old text' in (_doc.content_html or ''):
      _doc.content_html = _doc.content_html.replace('old text', 'new text')
  ```
- Admin edits docs via TinyMCE in browser — changes are live immediately
- Every save auto-creates a `ClaudeMemoryUpdate` entry for coding agent sync

## Modal Design Rule
- **ALWAYS** add `app-content-modal` class to every Bootstrap modal: `<div class="modal fade app-content-modal">`
- This applies the app's branded modal styling (teal header, brand colors, rounded corners)
- NEVER use plain Bootstrap modals without this class — they look inconsistent with the app design
- For red/danger modals (PII Guard): use `pii-guard-modal` class instead
- See `.app-content-modal` in `static/style.css` for the full styling

## Change Impact Checklist
When making code changes, **always check** whether the change requires updates to these systems:

1. **Backup Manager** (`backup_routes.py`): If you add a new DB model or association table, add it to:
   - Imports at top of file
   - `_build_backup_data()` dict keys + export loop
   - `restore_backup()` import loop
   - `backup_status()` stats dict (for key models)
   - Bump the version in metadata

2. **SEO / Sitemap** (`app.py` → `sitemap_xml()`): If you add a new public-facing route or content type:
   - Add URL to dynamic sitemap with `<lastmod>`
   - Add OG + Twitter Card meta tags to the template
   - Add Schema.org JSON-LD where appropriate
   - Update `robots.txt` Allow directives if needed
   - Reference: `docs/plans/SEO_MASTER_PLAN.md`

3. **Marketing / Landing Page**: If you add a new user-facing feature:
   - Update the marketing doc in admin Docs Hub (`/api/admin/marketing`)
   - Consider adding to landing page feature showcase
   - Update feature list in admin AI documentation

4. **Admin Docs** (`_DOC_MANIFEST`): If you add a new markdown doc in `docs/`, add manifest row

## AI Content Storage: JSON in DB, HTML on Frontend
**This is the current architecture for all AI-generated content. Follow it strictly.**

- **DB stores structured JSON** (not rendered HTML) for AI-generated content
- **Frontend renders JSON → HTML** client-side using the standalone renderer
- **Legacy HTML** in DB is supported for backward compat (frontend detects format by checking if content starts with `{`)
- **Never pre-render JSON to HTML and store the HTML** — this bakes in presentation and breaks re-rendering, badge placement, and style updates

### Standalone JSON Content Renderer
- **File**: `static/js/json-content-renderer.js` (loaded globally via `base.html`)
- **API**:
  - `JsonContentRenderer.render(jsonData)` → returns HTML string
  - `JsonContentRenderer.renderInto(el, jsonData)` → renders into DOM element
  - `JsonContentRenderer.isJson(rawString)` → detects if string is JSON discussion
  - `JsonContentRenderer.emphCaps(text)` → styles ALL CAPS phrases
- **Use this renderer everywhere AI JSON output is displayed** — do NOT write inline rendering logic
- Handles: flexible sections, staging/classification tables (auto-detect columns), step-by-step cards, key findings, differentials, management recommendations (auto-table for `:` pattern), ALL CAPS styling (safety words → red, caps phrases → grey pill, medical abbreviations excluded)

### When adding new AI content types
1. AI returns structured JSON (flexible sections, not rigid fields)
2. Backend stores `json.dumps(structured_data)` in the DB text column
3. Frontend calls `JsonContentRenderer.isJson()` to detect, then `JsonContentRenderer.renderInto()` to render
4. CMV badges match against structured elements via `data-section-title` and `data-claim-anchor` attributes

- **Default AI model**: `claude-sonnet-4-6` (Sonnet 4.0 `claude-sonnet-4-20250514` retired June 2026)
- **Case generation** (`ai_prelim.py`): flexible `sections` array — model decides which sections to include, no rigid schema
- **JSON transition status**: Case discussions DONE. Next: anatomy snippets, algorithms, radiq, vetting — migrate when touching those generators

## CMV Peer Review — Admin vs User Views
- **Admin**: inline badges + popup actions + review panel with "Corrected Text" field
- **Users**: summary trust bar + collapsible "Peer Review Log" table at bottom (no inline badges)
- `cmv-badges.js` gates on `_checkAdmin()` (`body.is-admin` class)
- Inline correction: `corrected_claim_text` column on `PeerReviewClaim`, backend `_apply_claim_correction()` does find-and-replace in source content
- Disputed claims in Peer Review Log show version history: CMV flag → suggestion → corrected text → expert notes
- Trust bar hidden if unresolved disputes exist
- Dashboard crosshair link: `?claim=<id>` param → `cmv-badges.js` auto-scrolls to badge

## Case Deletion
- `delete_case()` in `app.py` has 11 cleanup steps covering ALL FK references to `case.id`
- If you add a new model with `ForeignKey('case.id')` without `ondelete='CASCADE'`, you MUST add explicit deletion in `delete_case()`

## Code Conventions
- Brand colors: use CSS custom properties (--brand-primary, --brand-neutral, etc.) — NEVER inline hex
- Admin-only features: guard with `getattr(current_user, 'is_admin', False)`
- AI cost tracking: use `ai_cost_tracker.track_ai_call()` for every AI endpoint — pass both `input_tokens` and `output_tokens`
- Peer review: wire `radinsight_peer_review.peer_review()` into AI outputs with verifiable claims
- Rate limiting: single source of truth in `reporting_routes.py` `_check_ai_rate_limit()`
- Model: `RadIQFeedback.query` is shadowed — always use `db.session.query(RadIQFeedback)`

## Current Free Tier Model
- Trial (7 days): 10 SR + 5 RadIQ (whichever runs out first)
- Post-trial: 2 SR + 1 RadIQ per month (perpetual free taste)
- All non-AI content free forever
