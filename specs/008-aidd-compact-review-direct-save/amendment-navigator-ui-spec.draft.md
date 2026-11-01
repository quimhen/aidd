# DRAFT — Interactive specification review navigator

DRAFT / NOT APPROVED. This is a separate UI proposal for the existing 008 review workflow. It is not a mockup, an approval, or a request to build UI. The owner's latest request was relayed by the orchestrator: select a spec, navigate dependencies/screens/tasks, inspect descriptions/plan, versions/amendments, prior runs/history and evidence, then approve a version. Exact wording and consent provenance must be reconciled by the orchestrator from the owner's actual message before a final spec is approved.

## Scope proposed
- Select a project spec; show its title, current unit, task count and current lifecycle state.
- Expand a dependency tree of requirements, amendment units, screens/revisions and tasks, with explicit links to their originating approved source and dependent items. Avoid repeated or cyclic tree recursion; show each reference as a link to its canonical item.
- Show selected item detail: objective, scope, plan, requirements, task dependencies, file targets and current/previous versions, with change summary and affected shared dependencies.
- Display execution and audit evidence by version, state, viewport and environment, with visible `pending`, `failed`, `stale`, `unsupported` and `not verified` states; evidence links must stay inside trusted project boundaries or use explicitly allowed safe external URLs.
- Offer an optional owner-controlled approval action bound to the exact unit and full digest; preview the scope and dependencies before asking. The owner may instead use a supported authenticated summary route without opening the viewer; both routes have equivalent integrity, traceability, full hash and freshness checks. No action may fabricate consent or mark a prior draft approved. When Codex consent transport is unavailable, show unsupported and a supported owner-controlled fallback only if it can verify this exact unit; otherwise keep the unit blocked. Legacy review approves legacy tasks only; no bypass.
- Preserve original spec/code/task IDs. A generated consolidated view and change comparison do not rewrite approved source.

## Required states and behavior
1. Selector: loading, no specs, populated list, no search match, unreadable/invalid spec.
2. Tree: empty, loading, valid tree, missing reference, duplicate ID, cycle/conflict; errors identify the offending source and disable approval for ambiguous scope.
3. Detail: no selection, changed/unchanged, completed/pending/stale evidence, deleted or absent artifact, split task files, history with provenance.
4. Approval: not ready, ready, awaiting owner, accepted, declined, stale after change, unsupported host, permission error and retry; gate must verify the digest again when consent is recorded.
5. Layout: keyboard navigation, visible focus, labels, semantic roles and responsive desktop/narrow viewport behavior; exact presentation must follow the approved prototype.
6. Preserve legacy spec behavior and historical seals. A previous approval cannot authorize a new amendment, and selecting a version is not consent.

## Visual source and R4
Reference prototype: `specs/008-aidd-compact-review-direct-save/prototypes/visor-dinamico-v1.html`, SHA-256 `9cb821e17150605e37b4408ea1c24bad1efaad11b17e105a461448c9fe2685e0`. The owner answered exactly `Sí, usar esta dirección`: approval of the visual direction only, not approval of tasks, every state, implementation or release. The owner also requires the viewer approval to be optional, preserving an authenticated alternative with equal integrity and traceability. The element/state walkthrough is in `amendment-navigator-ui-visual-audit.draft.md`. Before implementation, reconcile that walkthrough with the formal mockup audit and assign stable screen/control codes without reusing the example IDs shown in the prototype. Explicitly confirm the expected fidelity during the clarification phase. Draw or explicitly defer missing states; do not claim existing 008 review-page approval covers this navigator.

The eventual plan must contain a named visual verification task: build/run the real viewer, capture app and prototype at 1440×900 and 390×844 for the five tabs (Resumen, Cambios, Pantallas, Evidencia, Historial), loading, empty, error and the approval dialog; compare each pair directly for header, selector, tree, tabs, panels, content and dialog, spacing and responsive behavior. Also compare every additional approved role/version/error state, and save per-pair verdicts and references. Report differences and unverified states; a code-only review or a passing DOM test alone cannot close visual work. Native dialogs/accessibility require explicit test and human check if automation cannot observe them.

## Dependencies and release
The unit registry / stable IDs / canonical hashes and the authenticated consent boundary are owned by the separate `amendment-units-*` draft; the UI consumes those contracts rather than inventing its own. The UI may be prototyped and audited while backend work proceeds, but implementing its approval action is blocked until a trusted owner consent channel exists. Implemented UI requires its own approved tasks and does not modify those drafts' seals. Generated consolidated artifacts are read-only views, not owner approvals or production deployment.

## Review needed before implementation
- Assume the navigator extends the existing review page and selects specs within the current repository; document these implementation choices in the prototype for review.
- Use the existing desktop review viewport and a narrow responsive viewport as defaults; verify keyboard navigation and focus. Confirm expected fidelity to the proposed prototype explicitly before implementation.
- Resolve how unavailable or stale visual evidence is displayed and confirm trusted consent transport per host without fabricating events.
- Build a template-derived spec/plan/task list, run find_spec and mechanical checks, complete pre-build audit, and obtain explicit approval for its task hash. This exploratory document has no executable tasks and grants no build authorization.
