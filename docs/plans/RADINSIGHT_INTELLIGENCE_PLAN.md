# RadInsight Intelligence — User Reporting Preferences

**Status:** Planned
**Priority:** Medium
**Keyword:** `RADINSIGHT-INTELLIGENCE-2026`

---

## Overview

Track how each user edits AI-generated reports (rejected placeholders, language changes, correction rejections) and feed those patterns back into future Smart Reporter prompts so reports progressively align with their reporting style — without compromising clinical quality.

## Architecture

### Storage: JSONB column on User model

```python
# models.py — User model
reporting_preferences = db.Column(db.JSON, default=dict)
```

### Schema

```json
{
  "version": 1,
  "placeholder_rules": [
    {"pattern": "measuring [___]", "action": "remove", "count": 3, "last_seen": "2026-04-01"}
  ],
  "language_rules": [
    {"original": "is noted", "preferred": "is seen", "count": 5},
    {"original": "No evidence of", "preferred": "There is no evidence of", "count": 2}
  ],
  "correction_rejections": [
    {"type": "phrasing", "original": "unremarkable", "suggested": "normal", "count": 4}
  ],
  "fill_in_defaults": {
    "Margins": "well-defined"
  }
}
```

### Prompt Injection

Appended to `unified_ai_assist()` user prompt as a new section (~200 tokens max):

```
REPORTING STYLE PREFERENCES (from this user's history):
- Remove measurement placeholders when exact size is not critical
- Prefer "is seen" over "is noted"
- Prefer "unremarkable" over "normal" for negative findings
- Default margin description: "well-defined"
Respect these preferences where clinically appropriate.
```

---

## Phase 1 — Explicit Signals (Button Clicks)

Track only high-confidence, explicit user actions. No text diffing.

### 1.1 DB Migration

- Add `reporting_preferences = db.Column(db.JSON, default=dict)` to User model
- Add migration block in `app.py`

### 1.2 Backend API Endpoint

`POST /api/smart-reporter/preferences`

Actions:
- `record` — increment a preference counter (called from JS on reject/edit actions)
- `get` — return current preferences (for settings page)
- `clear` — reset all preferences
- `delete_rule` — remove a specific rule

### 1.3 Signals to Capture (JS → API)

| Signal | Trigger | What to Send | Storage Key |
|---|---|---|---|
| Placeholder rejection | `rejectFillIn()` | placeholder pattern, label | `placeholder_rules[]` |
| Correction rejection | `rejectCorrection()` | correction type, original, suggested | `correction_rejections[]` |
| Fill-in chip default | `applyFillIn()` with same value 3+ times | label, chosen value | `fill_in_defaults{}` |

**Activation threshold:** 3 occurrences before a rule becomes active in prompts.

### 1.4 Prompt Builder (Python)

```python
# ai_smart_reporter.py
def build_preference_section(user):
    """Convert user.reporting_preferences into a prompt fragment."""
    prefs = user.reporting_preferences or {}
    if not prefs:
        return ""
    lines = []
    # Only include rules with count >= 3
    for rule in prefs.get('placeholder_rules', []):
        if rule.get('count', 0) >= 3:
            lines.append(f"- Omit placeholder: {rule['pattern']}")
    for rule in prefs.get('correction_rejections', []):
        if rule.get('count', 0) >= 3:
            lines.append(f"- Do not correct \"{rule['original']}\" to \"{rule['suggested']}\"")
    for label, value in prefs.get('fill_in_defaults', {}).items():
        lines.append(f"- Default {label}: {value}")
    if not lines:
        return ""
    header = "REPORTING STYLE PREFERENCES (from this user's history):\n"
    return header + "\n".join(lines) + "\nRespect these where clinically appropriate.\n"
```

### 1.5 Inject into unified_ai_assist()

Pass `preference_section` into the prompt template alongside `resource_section` and `report_status_section`.

### 1.6 Explicit Opt-In (Toast Prompt)

For placeholder rejections (structural changes), show a toast:
> "Save as preference? RadInsight will remember this for future reports."
> [Yes] [No]

Correction rejections and fill-in defaults tracked silently (low-risk, non-structural).

### 1.7 Settings Page — Manage Preferences

Add a section to user settings:
- View active preferences grouped by type
- Toggle individual rules on/off
- "Clear All Preferences" button
- Brief explanation: "RadInsight Intelligence learns your reporting style from your edits."

---

## Phase 2 — Silent Text-Diff Tracking (Future)

### 2.1 Capture Manual Edits

Compare `state.outputText` snapshots before/after manual PACS edits.
Use a debounced `blur` or `beforeunload` event to diff.

### 2.2 Extract Phrase-Level Changes

Diff algorithm extracts phrase substitutions (not insertions/deletions):
- "is noted" → "is seen" (substitution — trackable)
- Added a whole new sentence (insertion — skip)
- Deleted a sentence (deletion — skip)

### 2.3 Language Rules

Store in `language_rules[]` with the same count threshold.

### 2.4 Complexity Notes

- Text diffing is noisy — need good filtering to avoid garbage rules
- Only track changes to AI-generated text (not user's original draft)
- Limit to phrase-level (3-8 words), not word-level or sentence-level

---

## Guardrails

1. **Clinical safety:** Preferences apply to style/phrasing only, never clinical content. The AI prompt already separates these concerns.
2. **Activation threshold:** 3 occurrences minimum before a rule activates.
3. **Staleness decay:** Rules not reinforced in 60 days have count halved. Rules at count 0 are pruned.
4. **Cap:** Maximum 20 active rules per user. Oldest/lowest-count rules pruned first.
5. **Training mode toggle:** Optional flag to ignore all preferences (for exam prep).
6. **Token budget:** Preference section capped at 200 tokens. Rules serialized by priority (highest count first), truncated if over budget.

---

## Cost

| Component | Effort | Ongoing Cost |
|---|---|---|
| DB migration (1 column) | 10 min | 0 |
| API endpoint | 1 hour | 0 |
| JS signal capture | 2 hours | 0 |
| Prompt builder | 1 hour | ~$0.0006/call (~200 tokens) |
| Settings UI | 1.5 hours | 0 |
| **Phase 1 Total** | **~5.5 hours** | **Negligible** |
| Phase 2 text-diff | ~4 hours | 0 |

---

## Files to Modify

- `models.py` — Add `reporting_preferences` column to User
- `app.py` — Migration block for new column
- `ai_smart_reporter.py` — `build_preference_section()`, inject into `unified_ai_assist()`
- `reporting_routes.py` — New `/api/smart-reporter/preferences` endpoint
- `templates/smart_reporter.html` — JS: fire preference signals on reject/apply actions, opt-in toast
- `templates/settings.html` (or equivalent) — Preferences management UI
