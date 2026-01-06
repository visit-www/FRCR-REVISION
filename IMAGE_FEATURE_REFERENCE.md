# Image Upload Feature - Quick Reference

## Feature Overview
Add images to case answers and discussions in the FRCR Examiner application.

## Database Tables

### answer_image
| Column | Type | Purpose |
|--------|------|---------|
| id | Integer | Primary key |
| case_id | Integer | Foreign key to case |
| image_data | LargeBinary | Image file content |
| image_filename | String(255) | Original filename |
| image_type | String(50) | MIME type (e.g., image/jpeg) |
| created_at | DateTime | Upload timestamp |

### discussion_image
Same structure as answer_image

## API Quick Reference

### Upload Image
```
POST /api/case/<case_id>/answer-image
Content-Type: multipart/form-data
Form Data: image (file)

POST /api/case/<case_id>/discussion-image
Content-Type: multipart/form-data
Form Data: image (file)
```

### List Images
```
GET /api/case/<case_id>/answer-images
Response: [{"id": 1, "filename": "...", "created_at": "..."}, ...]

GET /api/case/<case_id>/discussion-images
Response: [{"id": 1, "filename": "...", "created_at": "..."}, ...]
```

### Get Image
```
GET /api/answer-image/<image_id>
GET /api/discussion-image/<image_id>
Response: Binary image data (image file)
```

### Delete Image
```
DELETE /api/answer-image/<image_id>
DELETE /api/discussion-image/<image_id>
Response: {"message": "... deleted successfully"}
```

## JavaScript Functions (in view_case.html)

| Function | Purpose |
|----------|---------|
| `loadAnswerImages()` | Fetch and display all answer images |
| `loadDiscussionImages()` | Fetch and display all discussion images |
| `uploadAnswerImage()` | Upload new answer image |
| `uploadDiscussionImage()` | Upload new discussion image |
| `deleteAnswerImage(id)` | Delete answer image by ID |
| `deleteDiscussionImage(id)` | Delete discussion image by ID |
| `showStatus(element, message, type)` | Show status alert |

## Validation Rules

### File Format
- ✓ JPEG (.jpg, .jpeg)
- ✓ PNG (.png)
- ✓ GIF (.gif)
- ✓ WebP (.webp)
- ✗ Other formats rejected

### File Size
- Maximum: 10 MB
- Minimum: No minimum
- Images exceeding limit are rejected

### Error Messages
| Error | Cause | Solution |
|-------|-------|----------|
| "No file selected" | User didn't choose file | Select a file before uploading |
| "File size exceeds 10MB" | File too large | Compress image or use smaller file |
| "Only image files allowed" | Wrong file format | Use JPEG, PNG, GIF, or WebP |
| "Image not found" | Image was deleted | Refresh page or re-upload |

## UI Elements

### HTML Structure
```html
<!-- Answer Images Section -->
<div id="answerImagesContainer">
  <div id="answerImagesList"></div> <!-- Thumbnails -->
  <input id="answerImageInput" type="file" accept="image/*" />
  <button id="uploadAnswerImageBtn">Upload Image</button>
  <div id="answerImageStatus"></div> <!-- Status messages -->
</div>

<!-- Discussion Images Section -->
<!-- Same structure for discussion -->
```

### CSS Classes
- `.image-thumbnail` - Image container with hover effects
- `.image-delete` - Delete button overlay
- `.alert-success` - Success message
- `.alert-danger` - Error message
- `.alert-info` - Info message

## Image Thumbnail Display
- Size: 150px × 150px maximum
- Click image: Opens full-size in new context
- Hover: Reveals delete button (×)
- Responsive on mobile devices

## Database Relationships

```
Case (1) ─────→ (Many) AnswerImage
         └────→ (Many) DiscussionImage

When Case is deleted:
- All related AnswerImages are deleted (cascade)
- All related DiscussionImages are deleted (cascade)
```

## Storage Mechanism

**Local Development (SQLite)**
- Images: Stored as BLOB in database file
- Location: `instance/frcr_examiner.db`

**Production (PostgreSQL)**
- Images: Stored as BYTEA in database
- Persists across deployments

## Performance Notes

- Thumbnail loading: Asynchronous (doesn't block UI)
- Image display: Uses base64 encoding via API
- Cache: Browser caches images (clear cache to refresh)
- Database size: Increases by image file size for each upload

## Troubleshooting

| Issue | Solution |
|-------|----------|
| Images don't upload | Check file size, format, browser console |
| Images don't display | Clear cache, check network tab |
| Slow uploads | Compress images, check connection |
| Delete doesn't work | Check permissions, refresh page |
| Images lost after refresh | Check database connectivity |

## Code Examples

### Uploading an Image (JavaScript)
```javascript
const formData = new FormData();
formData.append('image', fileInput.files[0]);

fetch(`/api/case/1/answer-image`, {
    method: 'POST',
    body: formData
})
.then(r => r.json())
.then(data => console.log(data));
```

### Fetching Images (JavaScript)
```javascript
fetch(`/api/case/1/answer-images`)
    .then(r => r.json())
    .then(images => {
        images.forEach(img => {
            console.log(`Image: ${img.filename}`);
            // Access image at /api/answer-image/{id}
        });
    });
```

### Model Definition (Python)
```python
from models import AnswerImage, DiscussionImage

# Create
img = AnswerImage(
    case_id=1,
    image_data=binary_data,
    image_filename='test.jpg',
    image_type='image/jpeg'
)
db.session.add(img)
db.session.commit()

# Query
images = AnswerImage.query.filter_by(case_id=1).all()

# Delete
db.session.delete(img)
db.session.commit()
```

## Security Considerations

✓ File type validation (MIME type check)
✓ File size limitation (10 MB max)
✓ Stored in database (not executable)
✓ Database cascade protection
✓ Only allow image files

## Deployment Checklist

- [ ] Update database (automatic on first run)
- [ ] Test image upload in development
- [ ] Test with various image formats
- [ ] Verify image deletion works
- [ ] Check database size impact
- [ ] Test with production database
- [ ] Backup database before deploying
- [ ] Monitor for storage growth

---

**Last Updated**: January 5, 2026
**Version**: 1.0
