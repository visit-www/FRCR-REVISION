# Handoff: Case DICOM Viewer

> **Last updated:** 2026-02-02  
> **Branch:** `main` (merged from `feature/case-dicom-viewer`)

## Quick start for next agent

Read this file and `docs/plans/CASE_DICOM_VIEWER_PLAN.md`. Key module: `case_dicom_viewer/`. Env vars: `AZURE_CLIENT_ID`, `AZURE_CLIENT_SECRET`, `APP_URL`.

---

## Current state

### ✅ Done
- **OneDrive OAuth** – `/case-dicom-viewer/oauth/authorize` and `/oauth/callback` via MSAL
- **Share link parsing** – `onedrive_service.py`: `encode_share_url()`, `list_folder_contents()`, Graph API integration
- **folder/parse API** – `POST /case-dicom-viewer/api/folder/parse` returns plans (axial, sagittal, etc.) from a share link
- **Admin UI** – "Link Image Stack" button in edit_case; modal with Connect OneDrive, paste link, parse, save
- **Image Stack tab** – New tab in view_case with plan selector and Prev/Next slice navigation
- **CaseImageStack model** – Migration applied (`case_image_stack` table)
- **UX fixes** – Connect-first messaging; Parse disabled until OneDrive connected; MSAL reserved scopes fix (`offline_access` removed)
- **Image proxy** – `GET /case-dicom-viewer/api/image?url=...` streams OneDrive images (avoids CORS/expiry); SSRF-safe (allowed hosts only)
- **Proxy URLs in viewer** – view_case rewrites stack URLs to proxy so img/Cornerstone load same-origin
- **Cornerstone stack viewer** – `viewer.js` uses Cornerstone (v1) + cornerstone-web-image-loader; stack scroll (mouse wheel), Zoom, Pan, Wwwc; fallback to `<img>` if Cornerstone not loaded

### 🔲 Remaining (per plan)
1. **OneDrive browse** – Allow browsing signed-in user's OneDrive instead of only pasting share links (discussed, not implemented)

---

## Key files

| File | Purpose |
|------|---------|
| `case_dicom_viewer/routes.py` | OAuth, status, folder/parse, **api/image proxy**, case stack CRUD |
| `case_dicom_viewer/onedrive_service.py` | Share URL encoding, Graph API folder listing |
| `case_dicom_viewer/config.py` | SCOPES, AUTHORITY, env helpers |
| `case_dicom_viewer/static/.../viewer.js` | Cornerstone init, loadStack, setSliceIndex, tools (StackScroll, Zoom, Pan, Wwwc) |
| `templates/edit_case.html` | Link Image Stack button, modal include, JS |
| `templates/view_case.html` | Image Stack tab, `loadImageStack()`, proxy URLs, Cornerstone + img fallback |
| `models.py` | `CaseImageStack` model |
| `docs/plans/CASE_DICOM_VIEWER_PLAN.md` | Full plan |

---

## Environment

```bash
# Required for OneDrive
AZURE_CLIENT_ID=...
AZURE_CLIENT_SECRET=...
APP_URL=https://radinsights.xyz   # or http://localhost:5000 for dev
```

Azure redirect URI: `{APP_URL}/case-dicom-viewer/oauth/callback`  
Scopes: `User.Read`, `Files.Read` (MSAL handles `offline_access` internally)

---

## Migrations

Already run locally and on Neon. If deploying fresh:
```bash
vercel env pull .env.vercel
python scripts/utilities/run_migration.py
```

---

## Other context (from session)

- **Resend email** – Password reset fails to send to `lotusheart2016@gmail.com` because Resend free tier only allows sending to account owner (`gaurav0133@gmail.com`). Fix: verify domain at resend.com/domains and set `EMAIL_FROM` to verified address.
- **Database URL** – `app.py` sanitizes `DATABASE_URL` to strip `\n` (fixes sslmode errors from .env).
- **Merge migration** – `merge_case_image_stack.py` merges `merge_ref_tnm` and `add_case_image_stack` heads.

---

## Suggested next steps

1. Test full flow: Connect OneDrive → paste share link → parse → save → view in Image Stack tab (Cornerstone stack + mouse wheel, or img fallback).
2. Optionally add OneDrive folder browser UI (browse signed-in user's OneDrive instead of only pasting share links).
