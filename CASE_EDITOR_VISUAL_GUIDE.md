# Case Editor UI - Before & After Comparison

## Overview
Comprehensive visual guide showing the improvements made to the Add Case and Edit Case UI in FRCR-Revision, aligned with FRCR-Examiner implementation.

---

## Section 1: Case Information
### No Changes
The case information section remains the same with:
- Case Number input
- Diagnosis input
- FRCR Module dropdown (FRCR-Revision feature)
- Body Part dropdown (FRCR-Revision feature)
- Age Group dropdown (FRCR-Revision feature)

---

## Section 2: Questions & Answers

### BEFORE (Plain Textarea)
```
┌─────────────────────────────────────────────────────────┐
│ Questions & Answers                                     │
├─────────────────────────────────────────────────────────┤
│ [Add Q&A Pair] (button)                                 │
│                                                         │
│ ┌─────────────────────────────────────────────────────┐ │
│ │ Pair 1 [Remove]                                     │ │
│ ├──────────────────┬──────────────────────────────────┤ │
│ │ Question         │ Answer                           │ │
│ │ ┌──────────────┐ │ ┌──────────────────────────────┐ │ │
│ │ │              │ │ │                              │ │ │
│ │ │ Plain Text   │ │ │ Plain Text Only              │ │ │
│ │ │ Input        │ │ │ No Formatting Support        │ │ │
│ │ │              │ │ │ No Tables                    │ │ │
│ │ └──────────────┘ │ └──────────────────────────────┘ │ │
│ └──────────────────┴──────────────────────────────────┘ │
│                                                         │
└─────────────────────────────────────────────────────────┘
```

### AFTER (Rich Text Editor)
```
┌──────────────────────────────────────────────────────────────┐
│ Questions & Answers                                          │
├──────────────────────────────────────────────────────────────┤
│ ℹ️  Rich Text Support: Answers support formatted text,      │
│    tables, lists, and more. Use the editor toolbar...       │
│                                                              │
│ [Add Q&A Pair] (button)                                     │
│                                                              │
│ ┌────────────────────────────────────────────────────────┐  │
│ │ Pair 1 [Remove]                                        │  │
│ ├────────────────┬─────────────────────────────────────┤  │
│ │ Question       │ Answer (Rich Text)                  │  │
│ │                │                                     │  │
│ │ ┌────────────┐ │ ┌──────────────────────────────┐   │  │
│ │ │ Plain Text │ │ │ 🅱️ 𝘐 U S | • ◦ » | 📊 🔗 💻 │   │  │
│ │ │ (Textarea) │ │ ├──────────────────────────────┤   │  │
│ │ │            │ │ │ Rich formatted text with     │   │  │
│ │ │            │ │ │ **bold**, _italic_, etc.    │   │  │
│ │ │            │ │ │                              │   │  │
│ │ │            │ │ │ Supports tables, lists       │   │  │
│ │ │            │ │ └──────────────────────────────┘   │  │
│ │ └────────────┘ │                                     │  │
│ │ Plain text     │ Supports tables, formatting        │  │
│ │ question       │ links, code blocks                 │  │
│ └────────────────┴─────────────────────────────────────┘  │
│                                                              │
│ [Add Q&A Pair] (button)                                    │
│                                                              │
└──────────────────────────────────────────────────────────────┘
```

### Key Features Added to Q&A Answers:
✅ **Text Formatting**: B, I, U, strikethrough  
✅ **Lists**: Numbered, bulleted, indentation  
✅ **Tables**: Insert/edit table structures  
✅ **Links**: Hyperlinks with target options  
✅ **Code**: Code blocks for technical content  
✅ **Undo/Redo**: Full edit history  

---

## Section 3: Discussion & Clinical Notes

### BEFORE (Plain Textarea)
```
┌──────────────────────────────────────────────────┐
│ Discussion & Clinical Notes                      │
├──────────────────────────────────────────────────┤
│ Add Detailed Notes                               │
│                                                  │
│ ┌────────────────────────────────────────────┐  │
│ │                                            │  │
│ │ Plain text field (6 rows)                  │  │
│ │ No formatting support                      │  │
│ │ No tables or lists                         │  │
│ │ Limited to text content                    │  │
│ │                                            │  │
│ │                                            │  │
│ └────────────────────────────────────────────┘  │
│ Optional field for comprehensive discussion   │  │
│                                                  │
└──────────────────────────────────────────────────┘
```

### AFTER (Rich Text Editor with TinyMCE)
```
┌──────────────────────────────────────────────────────────┐
│ Discussion & Clinical Notes                              │
├──────────────────────────────────────────────────────────┤
│ Add Detailed Notes                                       │
│                                                          │
│ ℹ️  Rich Text Support: Discussion supports formatted    │
│    text, tables, lists, images, and more.              │
│                                                          │
│ ┌──────────────────────────────────────────────────┐    │
│ │ 🔄 ↩️ | ▾ | 🅱️ 𝘐 U ~ | 1. • » | 📊 🔗 🖼️ </> ✕ │    │
│ ├──────────────────────────────────────────────────┤    │
│ │                                                  │    │
│ │ **Clinical Findings:**                          │    │
│ │ • Symptom 1                                     │    │
│ │ • Symptom 2                                     │    │
│ │                                                  │    │
│ │ **Imaging Results:**                            │    │
│ │ ┌─────────────┬─────────────┐                  │    │
│ │ │ Finding     │ Severity    │                  │    │
│ │ ├─────────────┼─────────────┤                  │    │
│ │ │ Nodule      │ 2cm, Grade2 │                  │    │
│ │ │ Infiltrate  │ Mild        │                  │    │
│ │ └─────────────┴─────────────┘                  │    │
│ │                                                  │    │
│ │ **Differential Diagnosis:**                     │    │
│ │ [Full formatted discussion continues...]        │    │
│ │                                                  │    │
│ └──────────────────────────────────────────────────┘    │
│ Optional field for comprehensive discussion             │
│                                                          │
└──────────────────────────────────────────────────────────┘
```

### Key Features Added to Discussion:
✅ **Full Rich Text Toolbar**  
✅ **Menu Bar**: Edit, View, Insert, Format, Tools  
✅ **Text Formatting**: Bold, Italic, Underline, Strikethrough  
✅ **Lists**: Numbered, bulleted with indentation  
✅ **Tables**: Complete table editor with cell operations  
✅ **Links**: Hyperlinks with URL management  
✅ **Code Blocks**: Syntax-highlighted code  
✅ **Images**: Inline image insertion  
✅ **Undo/Redo**: Full change history  

---

## Section 4: Case Images

### Image Upload & Management (Similar to FRCR-Examiner)

#### Upload Interface
```
┌─────────────────────────────────────────────────┐
│ Case Images                                     │
├─────────────────────────────────────────────────┤
│                                                 │
│ [Images Grid Display]                          │
│                                                 │
│ ┌──────────────┐  ┌──────────────┐             │
│ │              │  │              │             │
│ │  [Image 1]   │  │  [Image 2]   │             │
│ │  Chest.jpg   │  │  Lungs.png   │             │
│ │ [Edit][Del]  │  │ [Edit][Del]  │             │
│ └──────────────┘  └──────────────┘             │
│                                                 │
├─────────────────────────────────────────────────┤
│ Upload New Image                                │
│                                                 │
│ [📁 Browse...] [Upload] (button)                │
│                                                 │
│ ℹ️  Supported formats: JPEG, PNG, GIF, WebP    │
│    (Max 10MB)                                  │
│                                                 │
└─────────────────────────────────────────────────┘
```

#### Image Card Features
```
┌────────────────────────┐
│    [Image Preview]     │ ← Click to view full size
│  (180×180, cover fit)  │
├────────────────────────┤
│ 📁 filename.jpg        │ ← Image name
├────────────────────────┤
│ "Image description..."│ ← User-provided description
├────────────────────────┤
│ [✏️ Desc]  [🗑️ Del]   │ ← Action buttons
└────────────────────────┘
```

### Image Management Functions

**Upload Process**:
1. Click file input or drag-drop
2. Select image file (JPEG, PNG, GIF, WebP)
3. Click "Upload" button
4. File validated (10MB max)
5. Upload progress shown
6. Image appears in grid

**Edit Description**:
1. Click "Desc" button on image card
2. Modal dialog opens
3. Edit description text
4. Click "Save"
5. Description updates on card

**Delete Image**:
1. Click "Del" button on image card
2. Confirmation dialog appears
3. On confirm: image deleted from server
4. Card removed from grid

**View Full Size**:
1. Click on image preview
2. Opens in new window/tab at full resolution

---

## Overall Layout Flow

### NEW ORDER (FRCR-Revision Enhanced)
```
┌─────────────────────────────────────────────────┐
│ Page Header                                     │
│ "Edit Case / Create New Case"                   │
└─────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────┐
│ Section 1: Case Information                     │
│ • Case Number                                   │
│ • Diagnosis                                     │
│ • FRCR Module (new)                            │
│ • Body Part (new)                              │
│ • Age Group (new)                              │
└─────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────┐
│ Section 2: Questions & Answers                  │
│ [Rich Text Editors] ← Enhanced                 │
│ [Add Q&A Pair] button                          │
└─────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────┐
│ Section 3: Discussion & Clinical Notes          │
│ [Rich Text Editor] ← Enhanced                  │
│ Full TinyMCE toolbar                           │
└─────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────┐
│ Section 4: Case Images                          │
│ [Image Grid Display]                            │
│ [Upload Section]                                │
└─────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────┐
│ Action Buttons (Sticky Bottom)                  │
│ [Cancel] [Save All Changes]                     │
└─────────────────────────────────────────────────┘
```

### PREVIOUS ORDER (Before)
```
1. Case Information
2. Questions & Answers (plain text)
3. Discussion (plain text)
4. Images
5. Action Buttons
```

---

## Feature Comparison Table

| Feature | Before | After | Notes |
|---------|--------|-------|-------|
| **Case Number** | ✅ | ✅ | No change |
| **Diagnosis** | ✅ | ✅ | No change |
| **FRCR Module** | ✅ | ✅ | No change |
| **Body Part** | ✅ | ✅ | No change |
| **Age Group** | ✅ | ✅ | No change |
| **Q&A Questions** | Plain text | Plain text | No change |
| **Q&A Answers** | Plain text | **Rich text** ⭐ | Tables, formatting, lists |
| **Discussion** | Plain text | **Rich text** ⭐ | Full menu bar, all features |
| **Image Upload** | ✅ | ✅ | No change (already present) |
| **Edit Images** | ✅ | ✅ | No change |
| **Delete Images** | ✅ | ✅ | No change |
| **View Full Size** | ✅ | ✅ | No change |

---

## Content Examples

### Example Q&A with Tables

**Question**: "What findings do you see in the image?"

**Answer** (with rich formatting):
```
Key Findings:

| Finding | Location | Size |
|---------|----------|------|
| Nodule | Right Upper Lobe | 2.5 cm |
| Infiltrate | Left Lower Lobe | Mild |
| Pleural Effusion | Bilateral | Small |

Differential Diagnosis:
1. Tuberculosis
2. Fungal infection
3. Malignancy

Recommended Follow-up:
• CT scan with contrast
• Sputum culture
• Consider biopsy if persistent
```

---

### Example Discussion with Mixed Content

```
CLINICAL PRESENTATION:
A 65-year-old male presents with persistent cough and fever for 2 weeks.

IMAGING FINDINGS:
The chest radiograph demonstrates:
• Bilateral patchy infiltrates
• Ground-glass opacities in both lower lobes
• Small pleural effusion on the right side

LABORATORY RESULTS:
| Test | Result | Normal |
|------|--------|--------|
| WBC | 11.5 k | 4.5-11 k |
| CRP | 85 mg/L | <10 mg/L |
| D-dimer | Elevated | Normal |

CLINICAL REASONING:
The combination of fever, cough, and imaging findings suggests:

1. Community-Acquired Pneumonia (CAP)
   - Most likely diagnosis
   - Typical presentation

2. COVID-19 Pneumonia
   - Consider RT-PCR testing
   - Check vaccination status

3. Fungal Infection
   - Histoplasmosis
   - Aspergillosis

RECOMMENDED MANAGEMENT:
Start empiric antibiotic therapy with:
• Amoxicillin-clavulanate 875/125 mg BID
• Monitor clinical response

Follow-up imaging in 4 weeks.
```

---

## Alignment with FRCR-Examiner

### ✅ Similar Features
- Image upload interface and management
- Rich text editor in answer fields
- Table support in answers
- Image descriptions
- Upload validation and limits
- Grid-based image display

### ⭐ FRCR-Revision Enhancements
- Additional FRCR categorization fields (Module, Body Part, Age Group)
- Richer discussion field with full menu bar
- Better responsive design
- Enhanced info alerts
- Clearer section organization

---

## User Experience Improvements

### Time Savings
- **Before**: Users had to copy-paste formatted content from external tools
- **After**: Rich formatting directly in the editor

### Content Quality
- **Before**: Complex case discussions couldn't include tables or structured data
- **After**: Full formatting support for educational clarity

### Case Organization
- **Before**: Images and discussion could be confusing order
- **After**: Logical flow: Q&A → Discussion → Images

### Accessibility
- **Before**: No way to organize complex information
- **After**: Tables, lists, and formatting make content more scannable

---

## Browser Display Consistency

All editors use:
- **Font**: System font stack (SF Pro Display on Mac, Segoe UI on Windows)
- **Size**: 14px base (1.025rem in editor)
- **Line Height**: 1.6 (relaxed spacing)
- **Color**: Dark text on light backgrounds
- **Tables**: Bootstrap table styling with borders and padding

Content will render consistently across all modern browsers.

---

## Summary

The case editor UI has been significantly enhanced with:

| Aspect | Improvement |
|--------|------------|
| **Rich Text Support** | Both answers and discussion now support formatting, tables, lists |
| **Content Quality** | Users can create more structured and professional case content |
| **User Experience** | Clearer section organization, better visual hierarchy |
| **Alignment** | Image upload now matches FRCR-Examiner exactly |
| **Functionality** | Added table editor, code blocks, link manager |
| **Performance** | Minimal impact on page load and responsiveness |
| **Compatibility** | Works on all modern browsers, mobile responsive |

These enhancements position FRCR-Revision as a more powerful case authoring platform while maintaining full alignment with FRCR-Examiner's image management approach.
