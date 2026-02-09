# Cloudinary folder layout

All app uploads use a single top-level folder **`frcr_revision/`** with subfolders per feature. This keeps Media Library organized and avoids a mix of root-level and nested folders.

---

## Standard folder paths

| Purpose | Folder | Used by |
|--------|--------|---------|
| Case images (Edit Case) | `frcr_revision/frcr_cases` | app.py, edit-case-modal.js (direct upload) |
| Forum images | `frcr_revision/frcr_forum` | app.py forum upload |
| Profile pictures | `frcr_revision/frcr_profile` | auth.py |
| AJCC staging figures | `frcr_revision/AJCC_figures` | ajcc_tnm config, post_processor |
| TNM curate images (disease refs) | `frcr_revision/tnm_cases` | ajcc_tnm/routes/admin.py |
| Essential TNM IACR figures | `frcr_revision/essential_tnm_iacr` | scripts/upload_iarc_to_cloudinary.py |
| Anatomy / IARC (scripts) | `frcr_revision/anatomy/iarc` | scripts/extract_iarc_figures.py (if used) |

Optional env override:

- **`AJCC_CLOUDINARY_FOLDER`** – default `frcr_revision/AJCC_figures` (AJCC TNM module).

---

## Why there were two case-image folders

You may see both:

- **`frcr_cases`** (at root) – older uploads when the app used `folder='frcr_cases'` (28 images).
- **`frcr_revision/frcr_cases`** – newer uploads after standardizing under `frcr_revision/` (30 images).

The code now uses only **`frcr_revision/frcr_cases`**. New case images (server and direct upload) go there.

### How to reconcile

- **Leave as-is** – Root `frcr_cases` and `frcr_revision/frcr_cases` can both exist. Existing case image URLs in the database still work; no code changes needed for old assets.
- **Move in Cloudinary (optional)** – In Media Library you can move assets from `frcr_cases` into `frcr_revision/frcr_cases`. If you do that, any **public_id** or **image_url** stored in your database for those assets would need to be updated to the new path/URL, or they will 404. So moving is only worth it if you also update the app DB (e.g. CaseImage `image_public_id` / `image_url`) to match the new locations.
- **Recommendation** – Keep existing root `frcr_cases` assets as they are; use `frcr_revision/frcr_cases` for all new uploads. No DB migration required.

---

## Summary

- All **new** uploads go under **`frcr_revision/<subfolder>`**.
- Case images: **`frcr_revision/frcr_cases`** (single canonical folder from now on).
- Old root **`frcr_cases`** can remain for legacy URLs; reconcile by moving in Cloudinary only if you also update stored URLs/public_ids in the database.
