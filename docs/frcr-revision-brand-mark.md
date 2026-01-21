# FRCR-Revision — Brand Mark Specification

## Purpose

This document defines the **official brand mark** for **FRCR-Revision**.  
It is a final, canonical specification intended for implementation, not exploration.  
No elements, proportions, or principles described here should be modified without deliberate brand review.

---

## Brand Rationale

**FRCR-Revision** is built for radiologists progressing from structured learning to clinical authority.  
Its visual identity reflects this transition through deliberate restraint. The mark is based on the idea of electromagnetic field coherence: multiple influences resolving into a single point of clarity. Rather than illustrating radiology or education directly, the identity removes explanation in favour of inevitability. What remains is quiet structure, balance, and focus — qualities shared by effective diagnosis and expert clinical judgement. The result is a symbol that does not compete for attention, but earns trust through calm correctness.

---

## The FRCR-Revision Mark

### Conceptual Definition

- A single abstract symbol representing electromagnetic field coherence
- The mark is intentionally minimal and non-expressive
- It should feel **quiet, unfinished, and obvious**
- The mark does not explain itself

### Core Visual Elements

- One small central dot
- Exactly three smooth, thin curves
- Curves pass *near* the dot, not through it
- Curves gently bend inward
- Curves are slightly offset and non-symmetrical
- Large negative space dominates the composition

### Explicit Exclusions

- No enclosure
- No boundary
- No symmetry emphasis
- No repetition
- No texture
- No decoration
- No symbols
- No medical devices
- No illustrative metaphor

---

## Colour Specification

### Background
- Muted teal: `#5E899E`

### Central Focus
- Peach accent: `#e96304`

### Field Curves
- Soft off-white: `#F2F2EE`

---

## SVG Construction Specification (Canonical)

This section defines the **exact construction** of the mark.  
Any deviation from these instructions is considered incorrect.

### Canvas

- ViewBox: `0 0 1000 1000`
- Background colour: `#5E899E`

---

### Central Dot

- Centre: `(500, 500)`
- Radius: `14`
- Fill: `#e96304`

```svg
<circle cx="500" cy="500" r="14" fill="#e96304"/>


Field Curves

Global rules
	•	Stroke only (no fill)
	•	Stroke width: 3
	•	Stroke colour: #F2F2EE
	•	Stroke-linecap: round
	•	Curves must not touch the central dot
	•	Curves must not mirror each other

Curve 1 — Upper-left approach
<path d="M 260 430
         C 360 380, 430 430, 470 470"
      fill="none"
      stroke="#F2F2EE"
      stroke-width="3"
      stroke-linecap="round"/>


Curve 2 — Lower-right approach
<path d="M 740 580
         C 650 620, 580 560, 530 520"
      fill="none"
      stroke="#F2F2EE"
      stroke-width="3"
      stroke-linecap="round"/>

Curve 3 — Upper-right approach
<path d="M 690 360
         C 640 420, 580 450, 525 490"
      fill="none"
      stroke="#F2F2EE"
      stroke-width="3"
      stroke-linecap="round"/>

Wordmark Specification

Wordmark Text
FRCR-Revision

	•	Hyphen is mandatory
	•	Case-sensitive as shown
	•	Tracking must remain default

Typeface (choose one only)
	•	Inter (preferred)
	•	Source Sans 3
	•	IBM Plex Sans

Weight
	•	FRCR → Medium
	•	Revision → Regular

Colour
	•	Primary: #2E3A40
	•	On dark backgrounds: #F2F2EE

⸻

Logo Lockups

Horizontal Lockup (Preferred)
[ MARK ]    FRCR-Revision
	•	Spacing between mark and text: 1.5 × central dot diameter
	•	Text baseline aligned to the vertical centre of the dot

	•	Spacing between mark and text: 2 × central dot diameter

⸻

Clear Space Rule

Minimum clear space around the entire logo (mark + wordmark):

At least the diameter of the central dot on all sides

No other elements may enter this space.

⸻

Usage Principles
	•	Do not embellish
	•	Do not animate
	•	Do not explain
	•	Do not decorate
	•	Do not optimise for attention

The identity functions through restraint, not visibility.

⸻

Final Note

This mark is intentionally quiet.
It is designed to be trusted, not noticed.

Once implemented, it should not be revisited.

The current jpeg logo is stored at following path :
/Users/zen/myRepos/projects/FRCR_REVISION/static/images/frcr-revision-logo.jpg

