# DICOM/MPR Infrastructure Plan

> **Status:** Future Enhancement  
> **Priority:** Low (current pre-rendered approach works well for education)  
> **Estimated Effort:** High (significant infrastructure changes)

## Current Architecture

The current Case DICOM Viewer uses:
- **Pre-rendered images** (PNG/JPEG) from OneDrive
- **Cornerstone.js 2D viewer** for stack navigation
- **Plans** (axial, coronal, sagittal) as separate image folders
- **Simple proxy** to handle CORS and URL expiry

### Current Limitations
1. **No MPR** - Can't reconstruct arbitrary planes from 2D slices
2. **No window/level from DICOM** - Uses image-level adjustments only
3. **No measurements with calibration** - Pixel spacing unavailable
4. **Large file transfers** - All images must be downloaded even if not viewed

---

## Full DICOM/MPR Architecture

To enable true MPR (Multi-Planar Reconstruction), the following infrastructure would be required:

### 1. DICOM Storage Backend

#### Option A: Self-Hosted (Recommended for Control)
```
┌─────────────────────────────────────────────────┐
│                  Orthanc Server                  │
│    (Open-source DICOM server, C++ based)        │
│                                                  │
│  • DICOMweb API (WADO-RS, STOW-RS, QIDO-RS)    │
│  • PostgreSQL backend for metadata              │
│  • Plugin architecture for customization        │
│  • Lua scripting for workflows                  │
└─────────────────────────────────────────────────┘
```

**Orthanc Setup:**
- Docker container: `jodogne/orthanc-plugins`
- Storage: S3-compatible (MinIO, AWS S3, Cloudflare R2)
- Database: PostgreSQL (can share with existing FRCR app)

**Estimated Cost:**
- Self-hosted: $50-200/month (VPS + storage)
- Managed: $200-500/month (cloud PACS providers)

#### Option B: Cloud PACS
- **Google Cloud Healthcare API** - DICOMweb native
- **AWS HealthLake Imaging** - HIPAA compliant
- **Ambra Health** - Managed PACS with API

### 2. Frontend Viewer Options

#### Option A: Cornerstone3D (Recommended)
```javascript
// Cornerstone3D with volume rendering
import { RenderingEngine, volumeLoader } from '@cornerstonejs/core';
import * as cornerstoneTools from '@cornerstonejs/tools';

// Load volume from DICOMweb
const volumeId = 'cornerstoneStreamingImageVolume:myVolume';
const volume = await volumeLoader.createAndCacheVolume(volumeId, {
  imageIds: dicomwebImageIds,
});

// Create MPR viewports
const renderingEngine = new RenderingEngine('myRenderingEngine');
renderingEngine.setViewports([
  { viewportId: 'axial', type: 'orthographic', orientation: 'AXIAL' },
  { viewportId: 'sagittal', type: 'orthographic', orientation: 'SAGITTAL' },
  { viewportId: 'coronal', type: 'orthographic', orientation: 'CORONAL' },
]);
```

**Pros:**
- Same Cornerstone ecosystem (annotation compatibility)
- WebGL-based, performant
- Active development

**Cons:**
- More complex than 2D viewer
- Requires bundler (webpack/vite)

#### Option B: OHIF Viewer
```html
<!-- Embed OHIF as iframe or mount as React component -->
<iframe src="https://viewer.ohif.org/viewer?StudyInstanceUIDs=1.2.3.4" />
```

**Pros:**
- Full-featured out of the box
- Active community
- DICOM-first design

**Cons:**
- React-based (different from Flask templates)
- Complex to customize
- Large bundle size

### 3. Required API Layer

```
┌─────────────────────────────────────────────────┐
│           DICOMweb Proxy Service                │
│                                                  │
│  Flask endpoints wrapping DICOMweb:             │
│  • /dicomweb/studies/{studyUID}/series          │
│  • /dicomweb/studies/{studyUID}/series/{series}/│
│    instances                                     │
│  • /dicomweb/studies/{studyUID}/series/{series}/│
│    instances/{instance}/frames/{frame}          │
│                                                  │
│  Authentication: Flask-Login integration        │
│  Authorization: Check case access permissions   │
└─────────────────────────────────────────────────┘
```

### 4. Data Flow

```
[PACS Export] → [Orthanc/Cloud PACS] → [DICOMweb API]
                                              ↓
                                    [Flask Proxy Layer]
                                              ↓
                                    [Cornerstone3D / OHIF]
                                              ↓
                                    [MPR Rendering in Browser]
```

---

## Migration Path

### Phase 1: Keep Current (Now)
- Continue using OneDrive + pre-rendered images
- Self-hosted Cornerstone.js 4.x for 2D viewing
- Admin annotations saved to database

### Phase 2: Hybrid (Optional Intermediate Step)
- Add Orthanc alongside current system
- Allow DICOM upload for new cases
- Keep OneDrive option for backward compatibility

### Phase 3: Full DICOM (Future)
- Migrate all cases to DICOM format
- Enable MPR for all studies
- Add advanced tools (3D rendering, segmentation)

---

## Cost Comparison

| Approach | Storage | Compute | Monthly Cost |
|----------|---------|---------|--------------|
| Current (OneDrive) | OneDrive quota | Minimal | ~$0 extra |
| Self-hosted Orthanc | 100GB S3 | 2 vCPU VPS | $50-100 |
| Cloud PACS (Google) | Per GB | Per query | $100-300 |
| Enterprise PACS | Managed | Managed | $500+ |

---

## Technical Requirements

### Server
- 4+ GB RAM (for Orthanc)
- SSD storage (DICOM files are I/O intensive)
- HTTPS required (medical data)

### Browser
- WebGL 2.0 support (Cornerstone3D)
- 4+ GB RAM (for volume rendering)
- Modern Chrome/Firefox/Safari

### Compliance
- HIPAA considerations if storing real patient data
- De-identification pipeline for teaching cases
- Audit logging for access

---

## Recommendation

For FRCR revision purposes, **the current approach is sufficient**:

1. Pre-rendered images are adequate for learning anatomy and findings
2. Admin-created annotations highlight key teaching points
3. OneDrive provides free, reliable storage
4. No infrastructure maintenance burden

**Consider MPR/DICOM infrastructure only if:**
- Users specifically request interactive MPR
- You want to accept raw DICOM uploads
- You're building a case bank with original source data
- You need calibrated measurements

---

## Resources

- [Orthanc Book](https://book.orthanc-server.com/)
- [Cornerstone3D Documentation](https://www.cornerstonejs.org/)
- [OHIF Viewer](https://ohif.org/)
- [DICOMweb Standard](https://www.dicomstandard.org/using/dicomweb)
- [Google Cloud Healthcare API](https://cloud.google.com/healthcare-api/docs)

---

*Document created: 2026-02-02*
