# Image Upload Feature - User Guide

## Overview
The FRCR Examiner application now supports uploading and displaying images for **Answers** and **Discussion** sections of case studies. This feature allows you to attach visual references such as radiographs, diagrams, or explanatory images to enhance learning and documentation.

## Features

### Image Upload Capabilities
- **Answer Images**: Upload images directly associated with case answers
- **Discussion Images**: Upload images for case discussions or comments
- **Multiple Images**: Add unlimited images to each case
- **Image Types Supported**: JPEG, PNG, GIF, WebP
- **Maximum File Size**: 10 MB per image

## How to Use

### Uploading Images

1. **Navigate to Case View**
   - Start your exam and select a candidate
   - Choose a packet and case to view

2. **Upload Answer Images**
   - Scroll to the "Answer Images" section
   - Click "Choose File" to select an image
   - Click the "Upload Image" button
   - A success message will appear when upload is complete
   - The image will appear as a thumbnail below

3. **Upload Discussion Images**
   - Scroll to the "Discussion Images" section
   - Click "Choose File" to select an image
   - Click the "Upload Image" button
   - A success message will appear when upload is complete
   - The image will appear as a thumbnail below

### Viewing Images

- Images are displayed as clickable thumbnails (150x150 px max)
- Click on a thumbnail to view the full-size image
- Hover over an image to reveal the delete button (×)

### Deleting Images

1. Hover over the image thumbnail
2. A red delete button (×) will appear in the top-right corner
3. Click the × button
4. Confirm the deletion when prompted
5. The image will be removed from the database

## Technical Details

### Database Structure

The application stores images in the database using two new tables:

**AnswerImage Table**
- `id` - Unique image identifier
- `case_id` - Reference to the case
- `image_data` - Binary image data
- `image_filename` - Original filename
- `image_type` - MIME type (e.g., image/jpeg)
- `created_at` - Upload timestamp

**DiscussionImage Table**
- Same structure as AnswerImage
- Stores images for discussion sections

### API Endpoints

#### Upload Endpoints
- `POST /api/case/<case_id>/answer-image` - Upload answer image
- `POST /api/case/<case_id>/discussion-image` - Upload discussion image

#### Retrieval Endpoints
- `GET /api/case/<case_id>/answer-images` - List all answer images
- `GET /api/case/<case_id>/discussion-images` - List all discussion images
- `GET /api/answer-image/<image_id>` - Retrieve answer image file
- `GET /api/discussion-image/<image_id>` - Retrieve discussion image file

#### Deletion Endpoints
- `DELETE /api/answer-image/<image_id>` - Delete answer image
- `DELETE /api/discussion-image/<image_id>` - Delete discussion image

### File Size Limitations
- **Maximum file size**: 10 MB per image
- **Supported formats**: JPEG, PNG, GIF, WebP
- **Images are stored in the database**, not as files on disk

## Database Initialization

When you run the application for the first time after this update, the database will automatically create the new `answer_image` and `discussion_image` tables. No manual migration is required.

## Best Practices

1. **Image Quality**: Use high-quality images for better clarity
2. **File Size**: Compress images before uploading to keep file sizes reasonable
3. **Relevant Images**: Only upload images that are directly relevant to answers or discussions
4. **Organization**: Delete unused or outdated images to keep the database clean
5. **Formats**: JPEG is recommended for photographs; PNG for diagrams

## Compatibility

### Local Development
- Works with SQLite database
- All image data stored in the local database file

### Production (Railway/PostgreSQL)
- Works seamlessly with PostgreSQL
- LargeBinary fields properly handled by PostgreSQL
- Images persist across deployments

## Troubleshooting

### Upload Not Working
- Check file size (max 10 MB)
- Verify file is a supported image format (JPEG, PNG, GIF, WebP)
- Check browser console for error messages

### Images Not Displaying
- Clear browser cache and refresh the page
- Verify the image was successfully uploaded (check status message)
- Check database connection

### Slow Image Loading
- Large images may take longer to load
- Consider compressing images before uploading
- Check network connection speed

## Future Enhancements

Possible future improvements:
- Image cropping and editing
- Batch upload multiple images at once
- Image annotation and markup
- Image storage in cloud services (AWS S3, etc.)
- Thumbnail caching for faster loading
- Image compression on upload

## Feedback

If you encounter any issues or have suggestions for improvements, please document them for future development.
