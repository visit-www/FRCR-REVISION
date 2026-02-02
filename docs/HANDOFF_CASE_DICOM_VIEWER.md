# Handoff: Case DICOM Viewer

> **Last updated:** 2026-02-02  
> **Branch:** `main`

## Quick start for next agent

Read this file and `docs/plans/CASE_DICOM_VIEWER_PLAN.md`. Key module: `case_dicom_viewer/`. Env vars: `AZURE_CLIENT_ID`, `AZURE_CLIENT_SECRET`, `APP_URL`.

---

## Current state

### ✅ Done
- **OneDrive OAuth** – `/case-dicom-viewer/oauth/authorize` and `/oauth/callback` via MSAL
- **Share link parsing** – `onedrive_service.py`: `encode_share_url()`, `list_folder_contents()`, Graph API integration
- **folder/parse API** – `POST /case-dicom-viewer/api/folder/parse` returns plans (axial, sagittal, etc.) from a share link
- **Admin UI** – "Link Image Stack" button in edit_case; modal with Connect OneDrive, paste link, parse, save; "Remove image stack" option
- **Image Stack tab** – New tab in view_case with plan selector and Prev/Next slice navigation
- **CaseImageStack model** – Migration applied (`case_image_stack` table)
- **Image proxy** – `GET /case-dicom-viewer/api/image?url=...` streams OneDrive images (avoids CORS/expiry); SSRF-safe (allowed hosts only)
- **Proxy URLs in viewer** – view_case rewrites stack URLs to proxy so img/Cornerstone load same-origin
- **Self-hosted Cornerstone.js v4.x** – Libraries in `case_dicom_viewer/static/case_dicom_viewer/lib/`:
  - cornerstone-core 2.6.1
  - cornerstone-math 0.1.10
  - cornerstone-tools 4.22.0
  - cornerstone-web-image-loader 2.1.1
  - hammer.js 2.0.8
- **Full Cornerstone viewer** – `viewer.js` v4 with:
  - Stack scroll (mouse wheel)
  - Window/Level (left mouse drag)
  - Zoom (right mouse drag)
  - Pan (middle mouse drag)
  - Touch support (pinch zoom, multi-touch pan)
  - Image preloading for smooth navigation
- **Admin annotation tools** – Arrow, Text Marker, Freehand, Length, Ellipse ROI
- **Annotation storage** – `CaseImageAnnotation` model, GET/POST/DELETE API endpoints
- **Annotation toolbar UI** – Admin-only toolbar with tool buttons, save/clear functionality
- **Future MPR plan** – Documented in `docs/plans/DICOM_MPR_INFRASTRUCTURE_PLAN.md`

### 🔲 Remaining (optional enhancements)
1. **OneDrive browse** – Allow browsing signed-in user's OneDrive instead of only pasting share links
2. **Annotation display for students** – Currently annotations are saved but not loaded back (need to implement `applyAnnotationsForImage()`)
3. **Annotation persistence per-slice** – Current save captures current image only; full workflow would save on slice change
4. **Cine playback** – Auto-scroll through stack at configurable speed

---

## Key files

| File | Purpose |
|------|---------|
| `case_dicom_viewer/routes.py` | OAuth, status, folder/parse, api/image proxy, case stack CRUD, **annotations API** |
| `case_dicom_viewer/onedrive_service.py` | Share URL encoding, Graph API folder listing |
| `case_dicom_viewer/config.py` | SCOPES, AUTHORITY, env helpers |
| `case_dicom_viewer/static/.../lib/` | **Self-hosted Cornerstone.js libraries (v4.x)** |
| `case_dicom_viewer/static/.../viewer.js` | **v4 Cornerstone viewer** with scroll, zoom, pan, W/L, annotations |
| `templates/edit_case.html` | Link Image Stack button, modal include, JS, remove stack option |
| `templates/view_case.html` | Image Stack tab, annotation toolbar (admin), `loadImageStack()`, proxy URLs |
| `models.py` | `CaseImageStack`, **`CaseImageAnnotation`** models |
| `migrations/add_case_image_annotation_table.sql` | New annotation table migration |
| `docs/plans/CASE_DICOM_VIEWER_PLAN.md` | Original plan |
| `docs/plans/DICOM_MPR_INFRASTRUCTURE_PLAN.md` | **Future MPR/DICOM infrastructure plan** |

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

### New migration required:
```sql
-- Run: migrations/add_case_image_annotation_table.sql
CREATE TABLE IF NOT EXISTS case_image_annotation (
    id SERIAL PRIMARY KEY,
    case_id INTEGER NOT NULL UNIQUE REFERENCES "case"(id) ON DELETE CASCADE,
    annotations_json TEXT NOT NULL DEFAULT '{}',
    created_by_user_id INTEGER REFERENCES "user"(id) ON DELETE SET NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

---

## Viewer Controls

| Action | Control |
|--------|---------|
| Scroll through slices | Mouse wheel |
| Window/Level | Left mouse drag |
| Zoom | Right mouse drag |
| Pan | Middle mouse drag |
| Navigate slices | Prev/Next buttons or keyboard arrows |
| Annotation tools (admin) | Toolbar buttons |

---

## Annotation Tools (Admin Only)

| Tool | Icon | Description |
|------|------|-------------|
| View Mode | Hand pointer | Default W/L mode |
| Arrow | Arrow | Point to findings |
| Text | Font | Add text labels |
| Freehand | Polygon | Draw freehand ROI |
| Length | Ruler | Measure distances |
| Ellipse | Circle | Draw ellipse ROI |

---

## Architecture Notes

### Why Self-Hosted Libraries?
CDN versions of Cornerstone.js had inconsistent APIs across versions. Self-hosting ensures:
- Reliable API compatibility (v4.x tools API)
- No CDN availability issues
- Version control

### Why Not MPR?
Current approach uses pre-rendered 2D images from OneDrive. True MPR requires:
- Original DICOM volumetric data
- DICOM server (Orthanc or cloud PACS)
- Cornerstone3D (WebGL volume rendering)

See `docs/plans/DICOM_MPR_INFRASTRUCTURE_PLAN.md` for full analysis.

---

## Suggested next steps

1. **Run migration** – Execute `add_case_image_annotation_table.sql` on production database
2. **Test viewer** – Connect OneDrive → paste share link → parse → save → view with all controls (scroll, zoom, pan, W/L)
3. **Test annotations** – As admin, use annotation tools, save, verify saved to database
4. **Optional** – Implement annotation display for students (load from API on init)
