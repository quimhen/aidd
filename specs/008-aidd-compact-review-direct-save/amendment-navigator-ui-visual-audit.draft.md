# DRAFT — Visual walkthrough: interactive review navigator

## Provenance

| Field | Value |
|---|---|
| Source | `specs/008-aidd-compact-review-direct-save/prototypes/visor-dinamico-v1.html` |
| SHA-256 | `9cb821e17150605e37b4408ea1c24bad1efaad11b17e105a461448c9fe2685e0` |
| Owner response | `Sí, usar esta dirección` — visual direction only, reported by orchestrator; no task approval and no implementation verdict. |
| Review | Source inspected and prototype rendered with Chromium; evidence files are prototype captures, not the application. |
| Output | `specs/008-aidd-compact-review-direct-save/evidence/visor-dinamico-v1/` (`*-1440.png`, `*-390.png`; may be Git-ignored). |

This is a preliminary walkthrough, not the formal code-level `mockup-audit.md`. The example screen identifiers in the prototype are demo data; do not claim them as real project codes. Formally allocate stable codes and audit rows after the navigator spec is reconciled, then bind the chosen reference hash using AIDD provenance rules. A change to the reference after approval requires re-evaluation.

## Screen and global chrome

| Area | Exact reference section | Visible structure and behavior |
|---|---|---|
| Spec selector | HTML lines 23–27, 41–42 | Dark left rail: AIDD brand, list of example specs, current selection. Selecting a different entry changes title, context and delivery. At narrow width the rail becomes a top strip. |
| Global header | lines 28–32 | Breadcrumb, demo/connection indicators, heading and explanatory subtitle, secondary change button and primary review button. Demo-specific labels and test controls do not imply shipped product copy. |
| Delivery summary | line 32 | Card with amendment, status pill, description, version/base/scope/date, readiness count, explanation and segmented progress indicator. At narrow width the readiness panel stacks below summary. |
| Navigation tree | line 33 | Left white panel: base document and deliveries, nested requirements/plan, verification, task/dependency and screen references, previous version and legend. Active row is visually identified. |
| Tabs | lines 34, 44–48 | Five sections: Resumen, Cambios de la versión, Pantallas, Evidencia, Historial; active tab has a teal underline. Tabs and tree link to their corresponding views. |

## Tab and version walkthrough

| State | Reference | Content observed |
|---|---|---|
| Resumen | line 44 | Heading and link, three-column scope/status table, recent activity card, pre-approval checklist and version-approval note. |
| Cambios | line 45 | Version comparison with three columns: element, previous version and proposed version; dependency/evidence note. |
| Pantallas | line 46 | Two example screen cards with version/status pills, description, state pills and evidence note. The data is illustrative and not a real approval. |
| Evidencia | line 47 | Table of checks, scope and status; explicit note that file presence is not a passing test and reason for reuse/invalidation must be visible. |
| Historial | line 48 | Vertical version timeline, dates and text distinguishing prepared, approved and baseline states. |
| Different spec | lines 40–43, 50 | Different selector entries update context and a generic detail view. Production must not reuse the demo's fixed rows as actual data. |

## Loading, empty, error and dialog

| State | Reference | Observed or required behavior |
|---|---|---|
| Loading | line 50 | White card, loading title and description, three skeleton bars. |
| Empty | line 50 | Centered empty message, explanatory text and return-to-summary button. |
| Error | line 50 | Alert strip with failure message and `Reintentar`. |
| Approval dialog | lines 38, 53 | Centered modal and dim backdrop; current unit/version, note that prototype does not record approval, owner review checkbox, Cancel and initially disabled confirm. Checkbox enables confirm. Product must enforce authenticated consent and exact digest. The viewer is optional: a supported authenticated summary route remains available with equivalent integrity and provenance. |
| Simulation controls | lines 34, 50, 53 | `Ver estado de ejemplo` and simulated approval are prototype-only tools; do not ship them as product workflow. |
| Narrow | responsive CSS line 17 and captures | At 390 px, selector is horizontal, summary stacks, tree uses two columns and content is below. Document scroll width equals viewport width in this capture; horizontal tab strip is part of the prototype. |

## Unrepresented states — no false completion

The prototype does not draw a real missing dependency/cycle, a stale or unsupported-host approval, real authenticated success/failure/recovery, no search results, or all evidence detail states. It is a direction reference, not a complete requirement set; extend the reference or explicitly mark each state unverified before implementing those states. Actual rendering and state logic must use real project data, not demo constants.

## Explicit verification task to place in the eventual approved plan

After build, run the actual viewer and capture paired app/reference screenshots at 1440×900 and 390×844 for all five tabs, loading, empty, error and approval dialog (18 pairs minimum). Add every subsequently approved role, version, error and recovery state; check selector, tree, breadcrumb, cards, panel order, active tab, modal, typography, spacing and responsive behavior. Save each pair and per-state findings under the spec evidence directory, distinguish missing and not-verified, and require independent review. Never count these prototype-only captures as real application comparison.
