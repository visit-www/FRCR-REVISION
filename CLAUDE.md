# RadInsights Coding Agent Instructions

> Project-specific instructions for Claude Code sessions.
> This file is read at the start of every conversation.

## Project Context
- Flask app deployed on Vercel (Pro plan), Neon PostgreSQL
- All AI calls via `requests.post` to Anthropic Messages API (not SDK)
- See memory files for full architecture, feature inventory, and active plans

## Memory Sync Protocol

**When the user says "update memory" or "sync memory" or "check for updates":**

1. Fetch pending memory updates from the production database:
   - Ask the user to run: `curl -s https://www.radinsights.xyz/api/admin/claude-memory-sync | python3 -m json.tool`
   - Or if running locally: `curl -s http://localhost:5000/api/admin/claude-memory-sync`
2. For each unsynced entry in the response:
   - Read the `summary`, `category`, and `details` fields
   - Update the appropriate memory file (or create a new one)
   - Update `MEMORY.md` index if needed
3. After processing, tell the user to mark entries as synced:
   - `curl -X POST https://www.radinsights.xyz/api/admin/claude-memory-sync/mark-synced`

**When the user says "what changed?" or "what's new?":**
- Same protocol — check the sync endpoint first before answering

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

## Code Conventions
- Brand colors: use CSS custom properties (--brand-primary, --brand-neutral, etc.) — NEVER inline hex
- Admin-only features: guard with `getattr(current_user, 'is_admin', False)`
- AI cost tracking: use `ai_cost_tracker.track_ai_call()` for every AI endpoint
- Peer review: wire `radinsight_peer_review.peer_review()` into AI outputs with verifiable claims
- Rate limiting: single source of truth in `reporting_routes.py` `_check_ai_rate_limit()`
- Model: `RadIQFeedback.query` is shadowed — always use `db.session.query(RadIQFeedback)`

## Current Free Tier Model
- Trial (7 days): 10 SR + 5 RadIQ (whichever runs out first)
- Post-trial: 2 SR + 1 RadIQ per month (perpetual free taste)
- All non-AI content free forever
