# Cloudinary direct upload for Edit Case images

Case images in **Edit Case** can be uploaded in two ways:

1. **Server upload** – browser sends the file to your app, which uploads it to Cloudinary. On Vercel this is limited to ~4.5 MB per request (413 for larger files).
2. **Direct upload** – browser uploads the file straight to Cloudinary, then your app only stores the URL and `public_id`. No size limit from your server.

When `CLOUDINARY_UPLOAD_PRESET` is set, the Edit Case UI uses direct upload and falls back to server upload if direct upload fails.

---

## Steps to enable direct upload

### 1. Create an unsigned upload preset in Cloudinary

1. Log in to [Cloudinary Dashboard](https://console.cloudinary.com/).
2. Go to **Settings** (gear icon) → **Upload**.
3. Under **Upload presets**, click **Add upload preset**.
4. Set:
   - **Signing Mode**: **Unsigned** (required for browser uploads without exposing your API secret).
   - **Folder** (optional): `frcr_revision/frcr_cases` to match server uploads.
   - **Unique filename**: optional (e.g. true to avoid overwrites).
5. Save and copy the **Preset name** (e.g. `frcr_case_upload`).

### 2. Set the environment variable

Set the preset name in your environment so the Edit Case page can use it:

- **Local:** add to `.env` or `.env.local` (use the preset name you created in the Dashboard):
  ```bash
  CLOUDINARY_UPLOAD_PRESET=your_preset_name
  ```
  Example: if your preset is named `frcr_case_upload`, set `CLOUDINARY_UPLOAD_PRESET=frcr_case_upload`. Set the preset’s folder to `frcr_revision/frcr_cases` so uploads match the app.

- **Vercel:** Project → Settings → Environment Variables → add:
  - **Name:** `CLOUDINARY_UPLOAD_PRESET`
  - **Value:** your preset name (e.g. `frcr_case_upload`)
  - **Environment:** Production (and Preview if you want it in preview deploys).

You must already have `CLOUDINARY_CLOUD_NAME` set (and optionally `CLOUDINARY_API_KEY` / `CLOUDINARY_API_SECRET` for server-side uploads and delete). The preset name is not secret; it is only used by the browser to authorize unsigned uploads.

### 3. Verify

1. Open Edit Case for an existing case.
2. Choose an image larger than ~4 MB and click **Upload**.
3. If direct upload is enabled, the image should upload successfully. If you see a 413 or “too large” error, check that `CLOUDINARY_UPLOAD_PRESET` and `CLOUDINARY_CLOUD_NAME` are set correctly and that the preset is **Unsigned**.

---

## Summary

| Item | Purpose |
|------|--------|
| **Unsigned upload preset** | Lets the browser upload to Cloudinary without your API secret. |
| **CLOUDINARY_UPLOAD_PRESET** | Preset name injected into the Edit Case page so the frontend can use direct upload. |
| **CLOUDINARY_CLOUD_NAME** | Already required; used for both server and direct upload. |

Image **stacks** (DICOM-like slices) are not affected; they continue to use R2 only.
