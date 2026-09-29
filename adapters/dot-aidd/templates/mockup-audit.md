# Mockup Audit — [feature name]

## Provenance
| Field | Value |
|---|---|
| Source | [file path / Figma node id / Stitch screen id / image name] |
| Hash (sha256, if a file) | |
| Size | |
| Audit date | |
| Auditor (agent/person) | |

## Screen inventory
| SCREEN-XX | DOM/node id | Name | Type (view/modal/sheet) | Uses (COMP-nnn list) | Use case (US-nnn) | Purpose |
|---|---|---|---|---|---|---|
| SCREEN-01 | | | | | | |

## Component inventory
Anything visually/structurally identical across 2+ screens — a card, a header, a filter bar, a form
section. A control used on only one screen stays a plain CTL-nnn under that screen; don't promote
it here just to have an entry.

| COMP-nnn | Name | Used in (SCREEN-XX list) | Contains (CTL-nnn list) | PR/Spec ref |
|---|---|---|---|---|
| COMP-001 | | | | |

## Control inventory
| CTL-nnn | Screen or COMP-nnn | Visible text | id | Action/handler | Class/style | Calls API-nnn (if any) | Status | PR/Spec ref |
|---|---|---|---|---|---|---|---|---|
| CTL-001 | SCREEN-01 | | | | | | Explicit \| [Not Verified] | |

`Calls API-nnn` stays empty for a frontend-only feature. For a full-stack one, fill it in and mirror the same code in `contracts.md`'s "Consumed by" column — the link must be visible from both directions.

## Navigation map
| Origin | Action | Destination | Data passed | Condition | Alternative |
|---|---|---|---|---|---|
| SCREEN-01 | | | | | |

## Behavior list per screen
| SCREEN-XX-Fnn | Screen | Rule (one testable sentence) | Status | Evidence |
|---|---|---|---|---|
| SCREEN-01-F01 | SCREEN-01 | | Explicit \| Inferred | function/line/annotation |

## Use cases referenced
| US-nnn | Description | Source (this project's use-case doc, or "[Not Verified — assign in Align]") |
|---|---|---|
| US-001 | | |
