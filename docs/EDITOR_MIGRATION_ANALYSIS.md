# Editor Migration Analysis: TinyMCE → CKEditor vs Tiptap

## Current State Analysis

### TinyMCE Usage Locations
1. **Discussion Field** (`edit_case.html`)
   - Main case discussion editor
   - Custom cleanup functions
   - Paste handlers for link cleanup
   - Custom toolbar buttons (cleanuphtml, findreference)

2. **Q&A Pairs** (`edit-case-modal.js`)
   - Question text editors
   - Answer text editors
   - Dynamic initialization per pair

3. **Image Descriptions** (`edit-case-modal.js`)
   - Modal-based editor for image descriptions
   - Separate initialization

4. **NOT Used For:**
   - Student notes (plain textarea)
   - Highlights (Recogito.js on rendered HTML)

### Content Storage Format
- **Database**: All content stored as HTML in `Text` columns
  - `Case.discussion` → HTML
  - `Question.question_text` → HTML
  - `Answer.answer_text` → HTML
  - `CandidateNote.note_text` → Plain text with tags (NOT HTML)

### Custom Features Dependent on TinyMCE
1. **Custom Toolbar Buttons**:
   - `cleanuphtml` - HTML cleanup function
   - `findreference` - Reference finder integration

2. **Paste Handlers**:
   - `paste_preprocess` - Link underline removal
   - `PastePostProcess` - Post-paste cleanup

3. **Content Processing**:
   - `cleanupTinyMCEHTML()` - Removes AI wrappers, fixes buttons, cleans links
   - Custom content_style CSS
   - URL handling (relative_urls: false)

### Highlight/Note System (Independent)
- Uses **Recogito.js** for annotations
- Works on **rendered HTML** (not editor content)
- **NOT affected by editor choice**
- Uses `highlightable-text` class on view page
- Text selection on rendered content, not editor

## Editor Comparison

### CKEditor 5
**Pros:**
- ✅ **Enterprise-ready**: SOC 2, WCAG 2.2 compliant
- ✅ **Complete UI**: Built-in toolbar, dialogs, menus
- ✅ **HTML Compatibility**: Accepts TinyMCE HTML directly
- ✅ **Plugin System**: Similar to TinyMCE (easier migration)
- ✅ **Better Paste Handling**: Built-in paste filters
- ✅ **Active Development**: 50+ engineers, 20+ years experience
- ✅ **Documentation**: Extensive migration guides

**Cons:**
- ❌ **Larger Bundle**: ~500KB (vs TinyMCE ~300KB)
- ❌ **Less Flexible**: More opinionated UI
- ❌ **Learning Curve**: Different API structure

**Migration Complexity**: **MEDIUM**
- HTML content works directly (no conversion needed)
- Plugin system similar to TinyMCE
- Need to rewrite initialization code
- Custom buttons need plugin development

### Tiptap
**Pros:**
- ✅ **Headless/Modular**: Build exactly what you need
- ✅ **Modern Architecture**: React-like, extension-based
- ✅ **Smaller Bundle**: ~50KB core (extensions add size)
- ✅ **Better Developer Experience**: TypeScript, modern APIs
- ✅ **HTML Compatible**: Accepts HTML directly
- ✅ **Flexible**: Complete control over UI

**Cons:**
- ❌ **No Built-in UI**: Must build toolbar, menus, dialogs
- ❌ **More Code Required**: Need to implement everything
- ❌ **Less Mature**: Newer, smaller team
- ❌ **No Enterprise Certifications**: Security/accessibility manual
- ❌ **Migration Complexity**: Different architecture

**Migration Complexity**: **HIGH**
- HTML content works directly
- Need to build entire UI from scratch
- Extension system different from plugins
- More custom code required

## Impact on Existing Cases

### Content Compatibility
✅ **Both editors accept HTML directly** - existing cases will work without conversion

### What Changes:
1. **Editor Initialization Code** - needs rewrite
2. **Custom Functions** - need adaptation
3. **Paste Handlers** - different API
4. **Toolbar Buttons** - different implementation

### What Stays the Same:
1. **Database Schema** - no changes needed
2. **Content Format** - HTML remains HTML
3. **Highlight System** - completely independent
4. **Notes System** - not affected (plain textarea)
5. **Rendering** - `renderSafeHTML()` still works

## Recommendation: **STAY WITH TINYMCE** (with fixes)

### Why Not Migrate Now:

1. **Migration Risk vs. Benefit**
   - Current issues are **fixable** (we just fixed button styling)
   - Migration requires **significant testing** of all existing cases
   - **No content format change** - migration doesn't solve storage issues

2. **Custom Code Investment**
   - You have **65 TinyMCE API calls** across 6 files
   - Custom cleanup functions, paste handlers, toolbar buttons
   - All would need **complete rewrite**

3. **Highlight System Independence**
   - Your highlight/note system works on **rendered HTML**
   - Editor choice doesn't affect it
   - Migration won't improve this

4. **Notes Are Plain Text**
   - Notes don't use TinyMCE anyway
   - No benefit from editor change

### Better Approach: **Simplify TinyMCE Usage**

Instead of migrating, **reduce complexity**:

1. **Remove Unnecessary Paste Handlers**
   - Use CSS `!important` rules instead
   - Let CSS handle link styling
   - Remove complex regex replacements

2. **Simplify Cleanup Function**
   - Only run on save, not on every paste
   - Remove redundant checks

3. **Use TinyMCE's Built-in Features**
   - `paste_as_text` option for cleaner pasting
   - `paste_word_valid_elements` for Word cleanup
   - Built-in link handling

4. **CSS-First Approach**
   - Move styling to CSS with `!important`
   - Reduce inline style manipulation
   - Let browser/CSS handle defaults

## If Migration is Still Desired: **CKEditor 5**

If you must migrate, choose **CKEditor 5** because:

1. **Lower Migration Risk**
   - Plugin system similar to TinyMCE
   - Better paste handling out-of-box
   - HTML compatibility guaranteed

2. **Faster Implementation**
   - Built-in UI reduces custom code
   - Better documentation
   - More examples

3. **Enterprise Features**
   - Better for production apps
   - Security certifications
   - Accessibility compliance

### Migration Plan (if proceeding):

**Phase 1: Preparation (1-2 days)**
- Install CKEditor 5
- Create wrapper functions for editor API
- Test HTML content compatibility

**Phase 2: Discussion Field (2-3 days)**
- Replace TinyMCE in discussion
- Adapt cleanup functions
- Test paste handling

**Phase 3: Q&A Pairs (2-3 days)**
- Replace in edit-case-modal.js
- Test dynamic initialization
- Verify content saving

**Phase 4: Image Descriptions (1 day)**
- Replace in image description modal
- Test modal workflow

**Phase 5: Testing (3-5 days)**
- Test all existing cases
- Verify content rendering
- Test highlight system compatibility
- User acceptance testing

**Total Estimated Time**: 10-15 days

## Final Recommendation

**DO NOT MIGRATE** - Instead:

1. **Keep TinyMCE** (it's working, just needs simplification)
2. **Simplify the code** (remove complex paste handlers)
3. **Use CSS for styling** (let CSS handle link underlines)
4. **Fix remaining issues** with targeted solutions

The current issues are **code complexity**, not editor limitations. Migration would:
- ❌ Introduce new bugs
- ❌ Require extensive testing
- ❌ Risk breaking existing cases
- ❌ Not solve the root problem (too much custom code)

**Better solution**: Clean up the TinyMCE code, use CSS properly, and keep what works.

---

## Simplification Plan (Recommended)

### Phase 1: Remove Complex Paste Handlers (1-2 hours)

**Current Problem**: Complex regex-based paste handlers that modify every link

**Solution**: Use TinyMCE's built-in paste options + CSS

```javascript
// Replace paste_preprocess with simpler approach
paste_preprocess: function(plugin, args) {
    // Use TinyMCE's built-in paste filtering
    // Remove only if absolutely necessary
},
paste_postprocess: function(plugin, args) {
    // Minimal cleanup - only for TNM buttons
    // Let CSS handle link styling
},
```

### Phase 2: Simplify Link Styling (30 minutes)

**Current Problem**: Inline style manipulation on every link

**Solution**: Use CSS-only approach

```css
/* In style.css - already done */
.discussion-text a,
.tnm-intelligence-content a {
    text-decoration: none !important;
}
```

Remove all inline `text-decoration: none !important` additions - CSS handles it.

### Phase 3: Simplify Cleanup Function (1 hour)

**Current Problem**: Cleanup runs complex regex on every link

**Solution**: 
- Only run cleanup on **manual "Clean HTML" button click**
- Remove automatic cleanup from paste handlers
- Keep cleanup for: AI wrappers, TNM buttons, reference blocks

### Phase 4: Use TinyMCE Built-in Features (1 hour)

**Add these options**:
```javascript
paste_as_text: false,  // Keep rich text
paste_word_valid_elements: 'p,br,strong,em,u,ol,ul,li,a[href]',  // Clean Word paste
paste_auto_cleanup_on_paste: true,  // Let TinyMCE handle it
```

### Benefits of Simplification:
- ✅ **Reduces code by ~200 lines**
- ✅ **Faster paste operations** (no regex processing)
- ✅ **Easier to maintain** (CSS handles styling)
- ✅ **Fewer bugs** (less custom code)
- ✅ **Better performance** (no per-link processing)

### Estimated Time: 3-4 hours vs 10-15 days migration

---

## Decision Matrix

| Factor | Stay with TinyMCE (Simplified) | Migrate to CKEditor | Migrate to Tiptap |
|--------|--------------------------------|---------------------|-------------------|
| **Time Investment** | 3-4 hours | 10-15 days | 15-20 days |
| **Risk Level** | Low | Medium | High |
| **Code Reduction** | ~200 lines | ~100 lines | ~50 lines |
| **Existing Cases** | ✅ No impact | ⚠️ Testing needed | ⚠️ Testing needed |
| **Highlight System** | ✅ No change | ✅ No change | ✅ No change |
| **Maintenance** | ✅ Easier | ⚠️ New API to learn | ⚠️ More custom code |

**Winner**: Stay with TinyMCE (Simplified)
