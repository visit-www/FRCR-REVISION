# Cloudflare R2 Setup for Case Image Stacks

## 1. Create R2 Bucket

1. Go to [Cloudflare Dashboard](https://dash.cloudflare.com) > **R2** > **Overview**
2. Click **Create bucket**
3. Name it (e.g. `radinsights-cases-images`)
4. Choose a region or leave default

## 2. Create API Token

1. R2 > **Manage R2 API Tokens**
2. **Create API token**
3. **Permissions: Object Read & Write** (required for uploads)
4. **Apply to specific buckets only** → select your bucket (or "All buckets" for simplicity)
5. Copy **Access Key ID** and **Secret Access Key** immediately (secret is shown once)
6. Note your **Account ID** (in the R2 URL or dashboard sidebar)

**Access Denied?** Token must have **Object Read & Write**. If scoped to specific buckets, ensure your bucket is included. Recreate the token if unsure.

## Troubleshooting: Access Denied / Unauthorized

**Unauthorized** = invalid credentials or wrong endpoint:
- Recreate R2 API token and copy Access Key ID + Secret Access Key (no extra spaces)
- If bucket is in **EU jurisdiction**: add `R2_JURISDICTION=eu` to `.env`
- `R2_ACCOUNT_ID` must match the account where the bucket was created (32-char hex)

**Access Denied** = credentials valid but insufficient permissions:
1. **Token permissions** – R2 > Manage R2 API Tokens → your token must have **Object Read & Write**
2. **Token scope** – If "Apply to specific buckets only", ensure your bucket is selected
3. **Bucket name** – `R2_BUCKET_NAME` in `.env` must exactly match the bucket (case-sensitive)

Series names with spaces (e.g. "Axial noncontrast") are auto-sanitized to underscores in R2 paths.

## 3. Configure CORS

In the bucket **Settings** > **CORS Policy**, add:

```json
[
  {
    "AllowedOrigins": [
      "https://your-app.vercel.app",
      "http://localhost:5000"
    ],
    "AllowedMethods": ["GET", "HEAD"],
    "AllowedHeaders": ["*"],
    "MaxAgeSeconds": 3600
  }
]
```

(Use your actual app URL and localhost for dev.)

## 4. Environment Variables

**Local development:** Add R2 vars to `.env` (not `.env.local`). The app loads `.env` first, then `.env.local` for overrides. Since `.env.local` usually comes from `vercel env pull` and does not include R2, R2 values from `.env` are used.

```
R2_ACCOUNT_ID=your_account_id
R2_ACCESS_KEY_ID=your_access_key
R2_SECRET_ACCESS_KEY=your_secret_key
R2_BUCKET_NAME=radinsights-cases-images
```

**Jurisdiction (optional):** If your bucket was created in the **European Union** or **FedRAMP** jurisdiction, add:
```
R2_JURISDICTION=eu
```
or `R2_JURISDICTION=fedramp`. Omit for default (US) buckets.

**Production (Vercel):** Add the same vars in Vercel Project Settings > Environment Variables.

**Why two env files?** `.env` = base config (can be committed as template). `.env.local` = machine-specific overrides (gitignored, often from `vercel env pull`). You don't need R2 in `.env.local` unless you want to override `.env` for a specific setup.

## 5. Run Migrations (Vercel/Neon)

```bash
vercel env pull .env.vercel --environment=production
python scripts/utilities/run_sql_migration_vercel_only.py migrations/add_case_image_stack_r2_columns.sql
python scripts/utilities/run_sql_migration_vercel_only.py migrations/add_case_image_stack_multiple_per_case.sql
python scripts/utilities/run_sql_migration_vercel_only.py migrations/make_onedrive_share_id_nullable_neon.sql
python scripts/utilities/run_sql_migration_vercel_only.py migrations/add_study_label_and_annotation_stack_id.sql
```

## 6. (Optional) Delete Existing Stacks

To start fresh with R2-only, delete all existing case image stacks (e.g. via SQL or admin UI). Example SQL:

```sql
DELETE FROM case_image_stack;
DELETE FROM case_image_annotation;  -- annotations are per-study (stack_id)
```

## 7. Local SQLite (optional)

If you use SQLite locally (USE_LOCAL_DB=1), run:

```bash
python scripts/utilities/run_sqlite_r2_migration.py
python scripts/utilities/run_sqlite_study_annotation_migration.py
```

## R2 Path Pattern

Images are stored with human-readable paths:

```
cases/{case_id}_{case_slug}/studies/{study_id}_{study_slug}/series/{series_slug}/{index:04d}.{ext}
```

Example: `cases/5_temporal_bone_ct/studies/12_ct_scan/axial/0000.jpg`

- **case_slug**: sanitized case number/diagnosis for recognition
- **study_slug**: sanitized study label
- **series_slug**: sanitized series name (e.g. axial, axial_contrast)

## 8. Test R2 Connection

Run the diagnostic script to verify credentials and endpoint:

```bash
python scripts/utilities/test_r2_connection.py
```

If you get Unauthorized and your bucket is in EU jurisdiction, add `R2_JURISDICTION=eu` to `.env`.

## 9. Install boto3

```bash
pip install boto3
```

(boto3 is in `requirements.txt` for the project)

## Upload API

`POST /case-dicom-viewer/api/case/<case_id>/stack/upload` (admin only)

Multipart form: one field per series (axial_contrast, sagittal, etc.) with multiple image files. Files are sorted by original filename before storage (slice_001, slice_002, ...).

Example (JavaScript FormData):
```javascript
const fd = new FormData();
for (const file of axialContrastFiles) fd.append('axial_contrast', file);
for (const file of sagittalFiles) fd.append('sagittal', file);
fetch(`/case-dicom-viewer/api/case/${caseId}/stack/upload`, {
  method: 'POST', body: fd, credentials: 'include'
});
```

## Upload UX

- **Pick files**: Standard `<input type="file" multiple>`. Cmd+A selects all in the picker.
- **Pick folder**: "Add series from folder" uses `webkitdirectory` (Chrome, Edge, Safari). Folder name becomes series name. Firefox does not support folder selection.
- **Order**: Backend sorts by filename (natural order) so slice_1, slice_2, slice_10 display correctly.

## Custom File Pickers (optional)

If you need a richer picker (drag-drop, progress, folder support in Firefox):

| Library | Use case | License |
|---------|----------|---------|
| [Uppy](https://uppy.io/) | Drag-drop, folder, progress, resume | MIT |
| [FilePond](https://pqina.nl/filepond/) | Drag-drop, multi-file, light | MIT |
| [Dropzone.js](https://www.dropzone.dev/) | Drag-drop zone | MIT |

The built-in `webkitdirectory` approach requires no dependencies and works in most browsers.

## Upload Size Limit

Default max upload size is 1 GB (configurable via `MAX_UPLOAD_MB` in `.env`). For 1000+ large images, set `MAX_UPLOAD_MB=2048` or higher. If you hit 413 "Request Entity Too Large", increase the limit or upload in smaller batches (e.g. one series at a time).

*Note: The Cloudflare dashboard message "Files larger than 300 MB..." applies to drag-and-drop in the web UI. Our app uses the S3 API and supports large uploads regardless.*

**Timeout (ClientDisconnected):** Uploading 500+ images in one request can timeout. Upload one series at a time, or split large series into multiple stacks.

## Backup and Restore

Admin backup/restore includes case image stacks with all R2 columns:

- `storage_backend`, `r2_config_json`, `display_order`, `description_html`, `study_label`
- Annotations: `stack_id` (per-study) in addition to legacy `case_id`
- Legacy OneDrive columns for compatibility

Restore creates new stack rows (no overwrite). R2 objects remain in the bucket; restore only recreates database records. If you restore to a different environment, ensure R2 bucket and keys match or URLs will point to the wrong storage.

## Remove Study / Series

Removing a study or series from edit_case **unlinks from the database only**. Files stay in R2. To free storage, use Admin Dashboard → R2 Bucket Manager to delete the corresponding folder. The app never deletes R2 objects.

## R2 Bucket Manager (Admin Dashboard)

Admin Dashboard → **R2 Bucket Manager** tab lets admins:

- Browse R2 bucket contents (folders: cases/123/abc123/, etc.)
- Delete stack folders from R2 (permanent)

**Workflow:**
1. **Unlink from case first:** In edit_case, remove the image stack link (DB only; files stay in R2).
2. **Then delete from R2:** In Admin Dashboard → R2 Bucket Manager, navigate to the stack folder and click "Delete this folder from R2".

**Delete all objects:** At bucket root, a "Delete ALL objects in bucket" button appears. Requires typing "DELETE ALL" to confirm. Use to empty the bucket (e.g. before fresh start). Unlink all stacks from cases first.

Deleting from R2 without first unlinking will make the case's image stack non-functional (broken images).
