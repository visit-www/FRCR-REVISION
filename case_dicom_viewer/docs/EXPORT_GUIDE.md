# Case DICOM Viewer - Export Guide

This module is designed to be self-contained and reusable. To copy it to another Flask app:

1. **Copy the module folder** `case_dicom_viewer/` (excluding `__pycache__`)

2. **Add CaseImageStack model** to your `models.py` or keep in module with adapter

3. **Register the blueprint:**
   ```python
   from case_dicom_viewer import init_app, get_blueprint
   init_app(app)
   app.register_blueprint(get_blueprint())
   ```

4. **Environment variables:** Set `AZURE_CLIENT_ID`, `AZURE_CLIENT_SECRET`, `APP_URL`

5. **Include templates** in your edit_case and view_case pages per the plan

6. **Run migration** for `case_image_stack` table

See `docs/plans/CASE_DICOM_VIEWER_PLAN.md` for full architecture.
