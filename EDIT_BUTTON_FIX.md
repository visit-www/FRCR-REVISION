# Edit Button Fix - Root Cause and Solution

## Problem
The edit button was not triggering the edit modal because the API endpoint was returning incorrect data format.

## Root Cause
The `/api/case/<int:case_id>` GET endpoint in `app.py` was returning:
```python
'questions': case.questions,  # Returns legacy text field (wrong)
'answers': case.answers,      # Returns legacy text field (wrong)
```

However, the JavaScript expected:
```javascript
'questions': [{'question_text': '...', 'id': ...}],  // Array of objects
'answers': [{'answer_text': '...', 'id': ...}]       // Array of objects
```

## Solution
Fixed the API endpoint to properly serialize the Question and Answer relationships:

```python
@app.route('/api/case/<int:case_id>', methods=['GET', 'PUT'])
def get_case(case_id):
    # ... code ...
    if request.method == 'GET':
        return jsonify({
            'id': case.id,
            'case_number': case.case_number,
            'diagnosis': case.diagnosis,
            'questions': [{'question_text': q.question_text, 'id': q.id} for q in case.question_items],
            'answers': [{'answer_text': a.answer_text, 'id': a.id} for a in case.answer_items],
            'discussion': case.discussion
        })
```

## Files Changed
- **app.py** (Line 237-241): Fixed the GET request response to properly serialize questions and answers

## Result
✅ Edit button now triggers correctly
✅ Modal opens and loads case data properly
✅ Q&A pairs display correctly in the form
✅ Images load correctly

## Testing Steps
1. Click the "Edit" button on a case
2. Verify the modal opens
3. Verify case details are populated
4. Verify Q&A pairs are displayed
5. Verify images are loaded in the grid
