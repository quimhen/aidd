# Mockup Audit — [feature name]

## Provenance
| Field | Value |
|---|---|
| Source | [file path / Figma node id / Stitch screen id / image name] |
| Hash (sha256, if a file) | |
| Visual snapshot | |
| Visual snapshot SHA-256 | |
| Size | |
| Audit date | |
| Auditor (agent/person) | |

For a verifiable review, set `Visual snapshot` to a project-relative (or spec-relative) local
file and `Visual snapshot SHA-256` to its full SHA-256 after auditing it. For an online design,
export an immutable local snapshot and record the remote node/version in `Source`. A changed or
missing snapshot blocks the review until the audit is updated; without a screen-level dependency
map, a new snapshot resets all carried review decisions. Historical audits that predate these
fields remain usable but do not provide automatic source freshness verification. A new audit
containing these fields must fill both; blank fields do not establish visual provenance.

## Screen inventory
| SCREEN-XX | DOM/node id | Name | Type (view/modal/sheet) | Uses (COMP-nnn list) | Use case (US-nnn) | Purpose |
|---|---|---|---|---|---|---|
| SCREEN-01 | | | | | | |

## Component inventory
Prioritize reuse via a "Shared-First" methodology: check `design-system/components-index.md` and the
monorepo/shared library first. Anything visually or structurally reusable across 2+ screens or
components — a card, header, filter bar, form section — must be abstracted into an atomic or
compound component with Inversion of Control (Compound Components, children/slots, configurable props with sane defaults).
A control used on only one screen stays a plain CTL-nnn under that screen; don't promote it here just to have an entry.

| COMP-nnn | Name | Used in (SCREEN-XX list) | Contains (CTL-nnn list) | PR/Spec ref | Pattern / Shared Library |
|---|---|---|---|---|---|
| COMP-001 | | | | | |

## Control inventory
| CTL-nnn | Screen or COMP-nnn | Visible text | id | Action/handler | Destination | Data source | States | Class/style | Calls API-nnn (if any) | Status | PR/Spec ref |
|---|---|---|---|---|---|---|---|---|---|---|---|
| CTL-001 | SCREEN-01 | | | | | | | | | Explicit \| [Not Verified] | |

For every control with an Action: `Destination` = where it leads (a screen, a modal, an external app, or `n/a — <reason>`); `Data source` = where its data comes from (API/SP/store/field, or `n/a — <reason>`); `States` = what it shows when empty / loading / error. A visual wired to nothing, or reachable from nowhere, is a gap, not a pass.

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
