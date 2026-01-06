# 🚀 Q&A Refactoring - Quick Start Guide

## What Changed? 
The app now stores questions and answers as **individual database records** instead of text blocks. This means:
- ✅ Each question and answer is separate
- ✅ Easy to add/edit/delete pairs
- ✅ Clear visual separation

---

## Try It Now! 👇

### 1️⃣ View a Case
1. Go to home page
2. Click on any case
3. Scroll to "Questions & Answers" section
4. See individual Q&A pairs displayed as cards

### 2️⃣ Edit a Case
1. Click **"Edit Case"** button
2. See all Q&A pairs in the modal
3. Each pair shows:
   - Left: Question textarea
   - Right: Answer textarea
   - Delete button

### 3️⃣ Add New Pair
1. In edit modal, scroll down
2. Click **"Add Q&A Pair"** button
3. New empty pair appears
4. Type question and answer
5. Click **"Save All Changes"**

### 4️⃣ Edit Existing Pair
1. In edit modal, find the pair
2. Click in question/answer textarea
3. Edit the text
4. Click **"Save All Changes"**

### 5️⃣ Delete a Pair
1. In edit modal, find the pair
2. Click **red "Delete" button**
3. Click **"Save All Changes"**

---

## Key Features

| What | How |
|------|-----|
| **View pairs** | Open case → see numbered pairs |
| **Add pair** | Edit Case → "Add Q&A Pair" button |
| **Edit pair** | Edit Case → modify textareas → Save |
| **Delete pair** | Edit Case → click "Delete" → Save |

---

## Under the Hood 🔧

**Database**: Question and Answer tables
```
Question: id, case_id, question_number, question_text
Answer: id, case_id, answer_number, answer_text
```

**API Endpoints**: 12 new endpoints for CRUD
```
GET /api/case/{id}/qa-pairs - View pairs
POST /api/case/{id}/qa - Add pair
PUT /api/question/{id} - Edit question
PUT /api/answer/{id} - Edit answer
DELETE /api/question/{id} - Delete question
DELETE /api/answer/{id} - Delete answer
```

**Frontend**: JavaScript functions
```
loadQAPairs() - Display pairs when viewing case
loadQAPairsForEdit() - Load pairs in edit modal
addNewQAPairRow() - Add new pair
deleteQAPair() - Delete pair
saveQAPairs() - Save all changes
```

---

## Examples

### Example 1: Add a new Q&A pair to Case 5

**Step 1**: Open Case 5 and view current pairs
- See Pair 1, 2, 3...

**Step 2**: Click "Edit Case"
- Modal opens with all pairs

**Step 3**: Scroll to bottom, click "Add Q&A Pair"
- New empty pair appears

**Step 4**: Type in textareas
```
Question: "What is the diagnosis?"
Answer: "The diagnosis is pulmonary embolism based on..."
```

**Step 5**: Click "Save All Changes"
- New pair saved to database

**Step 6**: Close modal
- Main view now shows new Pair 4

---

### Example 2: Edit one answer in Case 3

**Step 1**: Open Case 3
- See all Q&A pairs

**Step 2**: Click "Edit Case"
- Modal shows editable textareas

**Step 3**: Find Pair 2, click Answer textarea
- Cursor in answer text

**Step 4**: Edit the answer text
- Change "..." to your updated text

**Step 5**: Click "Save All Changes"
- Updated answer saved

---

## Desktop vs Mobile

### Desktop (1024px+)
- Q&A pairs shown side-by-side
- Edit modal shows 2 columns

### Mobile (<1024px)
- Q&A pairs stacked vertically
- Edit modal textareas full-width

---

## Troubleshooting

**Q: Added a pair but it didn't save?**
- Make sure you clicked "Save All Changes" button (red button at bottom)

**Q: Edit modal is empty?**
- Wait a moment for data to load
- Refresh page and try again

**Q: Can I undo a deletion?**
- No, use your database backup to recover
- Auto-backup runs every 24 hours

**Q: How many pairs can I have?**
- As many as you want! System supports 100+ per case

---

## Files Involved

**Code Files**:
- `models.py` - Database models
- `app.py` - API endpoints  
- `templates/view_case.html` - User interface

**Documentation**:
- `QA_REFACTORING_COMPLETE.md` - Technical details
- `QA_QUICK_REFERENCE.md` - Full reference guide
- `IMPLEMENTATION_SUMMARY.md` - Complete overview

---

## More Information

For complete technical documentation: **QA_REFACTORING_COMPLETE.md**
For API reference: **QA_QUICK_REFERENCE.md**
For overview: **IMPLEMENTATION_SUMMARY.md**

---

**Questions?** Check the documentation files above or review the API endpoint code in `app.py`.

**Ready to use?** Open a case and click "Edit Case" to try it out! 🎉
