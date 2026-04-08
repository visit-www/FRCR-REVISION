# Major Trauma — Whole-Body CT (WBCT) Triage Criteria

> **Source:** RCR Major Adult Trauma Guidance 2024
> https://www.rcr.ac.uk/media/mbzdxefx/rcr-major-adult-trauma-guidance-2024.pdf
>
> **Rule:** A single positive parameter from any of the three categories below leads to the possibility of serious internal injury and WBCT should be initiated.

## Category 1 — Mechanism

| Criterion | Detail |
|---|---|
| High-speed RTC | Combined speed > 30 mph |
| Roll-over | Any |
| Ejection | Any |
| Concurrent death | At the scene |
| Trapped | Longer than 30 minutes |
| Vehicle vs pedestrian / cyclist | High energy |
| Fall | From greater than 3 m (use judgement) |
| Assault | Significant assault to trunk |
| Blast or burn | With associated trauma |
| Other | Any other high-energy mechanism |

## Category 2 — Apparent injury

| Criterion | Detail |
|---|---|
| Blunt thoraco-abdominal trauma | Any evidence |
| Open thoraco-abdominal trauma | Any evidence |
| Multiple long-bone fractures | 2 or more |
| Significant CNS trauma | Requiring intubation |
| Unstable vertebral fractures | Or signs of spinal cord injury |
| Unstable pelvic fracture | Any |

## Category 3 — Vital signs

| Criterion | Threshold |
|---|---|
| GCS | < 14 |
| Systolic BP | < 90 mmHg (guide) |
| Persistent tachycardia | > 120 bpm |
| Respiratory rate | < 10 or > 29 |
| SaO₂ | < 93 % |

## Clinical judgement notes

- Clinical judgement is still required in the sensible application of this triage scheme.
- **Targeted CT** of head and neck is more appropriate in certain low-energy traumas (e.g. GCS < 9 following isolated head injury).
- CT can be easily extended to include extremities if injury is suspected (avoiding immediate plain radiographs).
- The **trauma team leader** may additionally request WBCT at discretion for any reason falling outside the above.

## Also available from the same document (pending ingestion)

- Primary survey template
- Secondary trauma report template
- Full trauma protocol (contrast volume, phases, coverage)

## Seed candidate

This should be imported as a `VettingAlgorithm` with:

```
algorithm_key: acute-trauma-wbct-triage
title: Major Adult Trauma — Whole-Body CT Triage
body_section: Multisystem
clinical_scenario: Blunt or penetrating polytrauma triage for whole-body CT
entry_criteria: (three categories above — one positive triggers WBCT)
steps: (mechanism check → injury check → vital-sign check → decision)
tags: trauma, WBCT, polytrauma, RCR-2024
keywords: WBCT, whole body CT, polytrauma, RTC, trauma call, major trauma
```
