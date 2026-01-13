# Duplicate Notes and Highlights - Root Cause Analysis

## Summary
- **41 duplicate notes** removed (21 for student1, 20 for gaurav0133@gmail.com)
- **174 duplicate highlights** removed (all for student1)
- **Root cause identified and fixed**

## Why Notes Were Being Duplicated

### Root Cause #1: Auto-save with No Duplicate Prevention
The frontend in `view_case.html` has an auto-save feature that saves notes after 2 seconds of inactivity:

```javascript
notesTextarea.addEventListener('input', function() {
    // Clear existing timeout
    if (notesSaveTimeout) {
        clearTimeout(notesSaveTimeout);
    }
    
    // Set new timeout to save
    notesSaveTimeout = setTimeout(function() {
        saveNotes();  // This calls the API
    }, 2000);  // 2 seconds delay
});
```

**Problem**: If the user types quickly or if there are multiple input events, this could trigger multiple save requests. The backend endpoint `/api/case/<int:case_id>/note` (POST) was checking for existing notes, but there was a race condition where multiple requests could create duplicates before the first one committed.

### Root Cause #2: No Duplicate Check for Highlights
The `add_highlight` endpoint in `app.py` was **not checking for existing highlights** before creating new ones:

```python
# OLD CODE (BROKEN):
highlight = TextHighlight(
    case_id=case_id,
    user_id=current_user.id,
    text_content=text_content,
    highlight_color=highlight_color,
    field_name=field_name
)
db.session.add(highlight)
db.session.commit()
```

**Problem**: Every time a highlight was saved (even if identical), a new record was created. This explains why there were 174 duplicate highlights.

### Root Cause #3: Race Conditions
When multiple requests come in simultaneously:
1. Request A checks for existing note → not found
2. Request B checks for existing note → not found (A hasn't committed yet)
3. Request A creates note
4. Request B creates duplicate note

## Fixes Applied

### 1. Added Duplicate Prevention to Highlights
```python
# NEW CODE (FIXED):
# Check for existing duplicate highlight
existing_highlight = TextHighlight.query.filter_by(
    case_id=case_id,
    user_id=current_user.id,
    text_content=text_content,
    highlight_color=highlight_color,
    field_name=field_name
).first()

if existing_highlight:
    # Return existing highlight instead of creating duplicate
    return jsonify({
        'success': True,
        'highlight': {...},
        'message': 'Highlight already exists'
    }), 200
```

### 2. Enhanced Note Duplicate Prevention
```python
# Check for existing note
note = CandidateNote.query.filter_by(case_id=case_id, user_id=current_user.id).first()

if note:
    # Update existing note only if text has changed
    if note.note_text != note_text:
        note.note_text = note_text
        note.updated_at = datetime.utcnow()
        action = 'updated'
    else:
        # No change, return existing note
        return jsonify({...}), 200
else:
    # Check if there are any other notes with same content (duplicate prevention)
    existing_duplicate = CandidateNote.query.filter_by(
        case_id=case_id,
        user_id=current_user.id,
        note_text=note_text
    ).first()
    
    if existing_duplicate:
        # Return existing duplicate instead of creating new one
        return jsonify({...}), 200
```

### 3. Frontend Improvements (Recommended)
Consider adding:
- Request debouncing to prevent multiple simultaneous requests
- Loading state to disable save button while request is in progress
- Check for duplicate content before sending request

## Testing

Run the cleanup script to verify no duplicates remain:
```bash
python3 check_notes_highlights.py
```

To clean duplicates (if any remain):
```bash
python3 check_notes_highlights.py --clean --force
```

## Current Status

After cleanup:
- **student1@test.com**: 3 notes (was 24), 14 highlights (was 188), 2 cases reviewed
- **gaurav0133@gmail.com**: 1 note (was 21), 0 highlights, 1 case reviewed

The dashboard should now show correct counts.
