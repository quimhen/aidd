# DRAFT — Plan: dynamic specification review navigator

DRAFT ONLY. Source: `amendment-navigator-ui-spec.draft.md` and `amendment-navigator-ui-visual-audit.draft.md`; visual direction `Sí, usar esta dirección` is not an approval of this plan or any task. The unit registry, summary approval and Codex adapter are separate workstreams. No source code is authorized by this draft.

## Naming & File Contract
| Item | Convention |
|---|---|
| Reference | `prototypes/visor-dinamico-v1.html`; bind its current SHA-256 in the formal visual audit. |
| Entry point | Extend the existing AIDD review workflow for the current repository; exact executable route to be finalized with the UI implementation task. |
| Visual tasks | The owner of each viewer component implements a new view faithful to the prototype; existing parser/data logic may be reused but legacy presentation is not substituted for the new design. |
| Evidence | Versioned source reference, capture viewport, application code state, app/reference image pair and a comparison verdict per state. Prototype-only screenshots are not application evidence. |

## Prototype coverage and gaps
The preliminary walkthrough records the global shell, spec selector, breadcrumb, title/actions, delivery summary, tree, five tabs and their content, loading/empty/error, approval dialog and narrow layout. Example data and the state selector are simulation-only and do not become product data or controls. The reference does not yet draw every missing dependency, stale/unsupported approval, failed consent or recovery condition; each must be drawn or explicitly marked unverified and routed to a real task before implementation. Formal audit must assign unique screen/control codes only after checking the existing catalog.

## Explicit visual verification task — navigator release

**Nature:** verification of a new view; executed by the orchestrator after the approved UI implementation and before any close or release.

**Depends on:** prototype audit and owner visual-direction consent, exact-fidelity clarification, approved UI tasks, actual viewer build and a reachable deterministic fixture. If the consent source is unavailable, verify the blocked state without fabricating an approval.

**Reference:** `prototypes/visor-dinamico-v1.html` at the audited source hash, plus any separately approved references for additional states.

**Steps:**
1. Build and run the actual application using the exact approved implementation task's commands; confirm the viewer reaches the intended repository and does not display an error boundary.
2. At 1440×900 and 390×844, capture the actual app and matching reference side by side for each of five tabs (Resumen, Cambios, Pantallas, Evidencia, Historial), loading, empty, error and the approval dialog: **18 pairs minimum**. Set each real state through deterministic fixture, never the prototype-only state selector.
3. Capture and compare every added selected-spec, current/history version, role, failed/missing dependency, stale evidence, unsupported consent, cancelled and recovery state from the finalized audit. Native approval controls that cannot be automated are `not-verified` with an executable human check; do not issue an owner approval.
4. For each pair record source hash, unit/revision, state, viewport, app code fingerprint, environment, paths and verdict; compare selector, breadcrumb, chrome, summary card, tree, active tab, content hierarchy, badges, dialog, typography, spacing and responsiveness against the exact approved reference.
5. Report every mismatch and missing state against its owning task; do not repair within the verification task, weaken assertions or call a prototype capture an application capture. Recheck shared shell/token changes for dependent screens.
6. One independent UI auditor reviews the executed pairs and manifest. A passing DOM test or a design-direction confirmation alone cannot close the spec.

**Proposed output:** `evidence/visor-dinamico-v1/` or a task-specific sibling, containing app/reference pairs and a per-state comparison report. The existing 18 images in that directory are reference-only captures.

**Ready-to-approve condition:** finalize the formal screen/control inventory and target files, provide the exact build/capture commands for the implemented stack, define all role/consent/recovery states and use the template to create an executable task with dependencies, estimates and verification. No test count, implementation readiness or product PASS is inferred from this draft.
