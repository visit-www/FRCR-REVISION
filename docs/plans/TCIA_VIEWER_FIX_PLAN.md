# TCIA Viewer Fix - Implementation Plan

> **Priority:** 1 (Quick Win)  
> **Complexity:** Low  
> **Estimated Effort:** 1-2 days  
> **Status:** Planned

## Executive Summary

Fix the TCIA (The Cancer Imaging Archive) integration to ensure the viewer loads case data correctly. Issues include incorrect URL construction, no auto-search on tab open, and missing fallback viewer options.

---

## CRITICAL: App Style and Branding Guidelines

**All UI implementations MUST follow existing app design patterns:**

### Color Palette
- Primary Blue: `#5E899E` (headers, primary actions)
- TCIA Green: `#28a745` (TCIA-specific accent, success states)
- Warning Orange: `#ffc107` (loading states, warnings)
- Danger Red: `#dc3545` (errors, no results)

### UI Patterns
- Follow existing tab structure in view_case.html sidebar
- Match existing search input and button styling
- Use consistent loading spinners and status messages
- Follow existing result card patterns from PubMed tab

### Code Style
- Console logging with `[TCIA]` prefix
- Use existing `showFlash()` for notifications
- Follow existing async/await patterns

---

## Current Issues

### 1. Viewer Links Not Loading Cases

**Current URL construction** in `tcia_service.py`:

```python
# Study page link (potentially incorrect format)
study_page_link = f"https://nbia.cancerimagingarchive.net/nbia-search/?PatientID={patient_id}"

# Individual series viewer
viewer_link = f"https://viewer.imaging.datacommons.cancer.gov/viewer/{series_uid}"
```

**Issues:**
- Study page URL may use incorrect parameter format
- No collection context in URL
- Some viewers require specific URL patterns

### 2. No Auto-Search on Tab Open

Unlike other tabs (Anatomy), TCIA doesn't auto-search when the tab is opened, even though the diagnosis is pre-filled.

### 3. Limited Series Display

Only top 2 series per study are shown, potentially missing relevant imaging data.

---

## Proposed Fixes

### Fix 1: Correct Viewer URL Construction

```python
def get_study_page_link(patient_id: str, collection: str) -> str:
    """Generate correct TCIA study page URL with collection context."""
    from urllib.parse import urlencode
    params = {
        'Collection': collection,
        'PatientId': patient_id
    }
    return f"https://nbia.cancerimagingarchive.net/nbia-search/?{urlencode(params)}"

def get_viewer_link(series_uid: str) -> dict:
    """Generate viewer URLs with fallback options."""
    return {
        'primary': f"https://viewer.imaging.datacommons.cancer.gov/viewer/{series_uid}",
        'fallback': f"https://nbia.cancerimagingarchive.net/viewer/?series={series_uid}",
        'ohif': f"https://viewer.imaging.datacommons.cancer.gov/v3/viewer/{series_uid}"
    }
```

### Fix 2: Add Auto-Search on Tab Open

```javascript
document.addEventListener('DOMContentLoaded', function() {
    const tciaTab = document.getElementById('tciaTab');
    if (tciaTab) {
        let tciaSearched = false;
        tciaTab.addEventListener('shown.bs.tab', function() {
            if (!tciaSearched && caseDiagnosis) {
                tciaSearched = true;
                searchTCIA();
            }
        });
    }
});
```

### Fix 3: Add Fallback Viewer Buttons

```html
<div class="btn-group btn-group-sm" role="group">
    <a href="${series.viewer_link}" target="_blank" class="btn btn-primary">
        <i class="fas fa-eye me-1"></i>IDC Viewer
    </a>
    <a href="https://nbia.cancerimagingarchive.net/viewer/?series=${series.series_uid}" 
       target="_blank" class="btn btn-outline-secondary">
        <i class="fas fa-external-link-alt me-1"></i>NBIA
    </a>
</div>
```

---

## Files to Modify

- `tcia_service.py` - Fix URL construction, add logging
- `resources_routes.py` - Update API response with fallback URLs
- `templates/view_case.html` - Add auto-search, update result display

---

## Success Criteria

- TCIA viewer loads case data correctly for all tested collections
- Auto-search works when tab is opened with diagnosis
- Fallback viewer options available if primary fails
- No regressions in existing TCIA search functionality
- UI matches existing app styling

---

## Todos

- [ ] Fix viewer URL construction with collection context
- [ ] Add auto-search when TCIA tab is opened
- [ ] Add fallback viewer options (NBIA, OHIF)
- [ ] Add debug logging for troubleshooting
- [ ] Update result display with viewer dropdown
- [ ] Test with various collections and diagnoses
