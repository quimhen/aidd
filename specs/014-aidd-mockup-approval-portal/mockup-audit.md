# Mockup Audit — 014 AIDD Mockup-First Spec Approval & Visual Verification Portal

## Provenance
| Field | Value |
|---|---|
| Source | projects/11423933689227171013/screens/53496feba7c24f629f0bddc91383d7fa |
| Hash (sha256, if a file) | n/a — remote Stitch screen |
| Visual snapshot | prototype/stitch-SCREEN-REV-01.png |
| Visual snapshot SHA-256 | 6f93d73ff8e1fbca293a8f93b596f9db486f11966c9c56c4178ee508f26cfa99 |
| Size | 732406 |
| Audit date | 2026-11-03 |
| Auditor (agent/person) | Antigravity |

## Screen inventory
| SCREEN-XX | DOM/node id | Name | Type (view/modal/sheet) | Uses (COMP-nnn list) | Use case (US-nnn) | Purpose |
|---|---|---|---|---|---|---|
| SCREEN-REV-01 | aidd-root | Spec Approval & Mockup Verification Portal | view | COMP-REV-01, COMP-REV-02, COMP-REV-03, COMP-REV-04, COMP-REV-05, COMP-REV-06 | US-REV-01 | Portal ejecutivo interactivo para la revisión y aprobación visual de especificaciones, mockups y tareas bajo la regla R6. |

## Component inventory
Prioritize reuse via a "Shared-First" methodology: check `design-system/` and monorepo shared components.

| COMP-nnn | Name | Used in (SCREEN-XX list) | Contains (CTL-nnn list) | PR/Spec ref | Pattern / Shared Library |
|---|---|---|---|---|---|
| COMP-REV-01 | HeaderBar | SCREEN-REV-01 | CTL-REV-001, CTL-REV-002 | 014 | Barra superior ejecutiva con título del spec, badges de versión y botón de acción principal |
| COMP-REV-02 | MetricCardsGrid | SCREEN-REV-01 | CTL-REV-003, CTL-REV-004, CTL-REV-005, CTL-REV-006 | 014 | Cuadrícula de 4 tarjetas KPI (Esfuerzo, Tareas, Mockups, Verificaciones) |
| COMP-REV-03 | MockupViewportCanvas | SCREEN-REV-01 | CTL-REV-007, CTL-REV-008, CTL-REV-009, CTL-REV-010 | 014 | Lienzo interactivo para renderizar imágenes de mockups con soporte de viewport y zoom |
| COMP-REV-04 | ViewportControlBar | SCREEN-REV-01, COMP-REV-03 | CTL-REV-008, CTL-REV-009 | 014 | Barra de conmutación de dispositivos (Desktop 1440, Tablet 768, Mobile 375) |
| COMP-REV-05 | TabbedChecklistDrawer | SCREEN-REV-01 | CTL-REV-011, CTL-REV-012, CTL-REV-013 | 014 | Panel derecho con pestañas accesibles de tareas, criterios, preguntas y controles |
| COMP-REV-06 | TokenComplianceStrip | SCREEN-REV-01, COMP-REV-03 | CTL-REV-014 | 014 | Tira informativa de tokens de diseño, resolución y conformidad con deuda visual cero |

## Control inventory
| CTL-nnn | Screen or COMP-nnn | Visible text | id | Action/handler | Destination | Data source | States | Class/style | Calls API-nnn (if any) | Status | PR/Spec ref |
|---|---|---|---|---|---|---|---|---|---|---|---|
| CTL-REV-001 | COMP-REV-01 | Guardar progreso / Aprobar y guardar | aidd-approve | saveReview | specs/review.md | state | idle, saving, done | btn-primary font-bold | | Explicit | 014 |
| CTL-REV-002 | COMP-REV-01 | 0 / 0 | aidd-progress | update_progress | self | countDone | live | badge-pill font-mono | | Explicit | 014 |
| CTL-REV-003 | COMP-REV-02 | Esfuerzo Estimado | kpi-effort | show_effort | self | spec_metadata | normal | kpi-card | | Explicit | 014 |
| CTL-REV-004 | COMP-REV-02 | Tareas Planificadas | kpi-tasks | show_tasks | self | task_count | normal | kpi-card | | Explicit | 014 |
| CTL-REV-005 | COMP-REV-02 | Pantallas UI / Mockups | kpi-mockups | show_mockups | self | screen_count | normal | kpi-card | | Explicit | 014 |
| CTL-REV-006 | COMP-REV-02 | Verificaciones | kpi-verification | show_verification | self | verif_count | normal | kpi-card | | Explicit | 014 |
| CTL-REV-007 | COMP-REV-03 | SCREEN-XX (Selector) | screen-tabs | switch_mockup | self | mockups_data | active, idle | tab-pill | | Explicit | 014 |
| CTL-REV-008 | COMP-REV-04 | Desktop / Tablet / Mobile | viewport-toggle | set_viewport | COMP-REV-03 | viewport_modes | 1440, 768, 375 | btn-group | | Explicit | 014 |
| CTL-REV-009 | COMP-REV-04 | 100% / Reset | zoom-reset | reset_zoom | COMP-REV-03 | zoom_state | normal | btn-icon | | Explicit | 014 |
| CTL-REV-010 | COMP-REV-03 | Imagen de Prototipo | mockup-img | inspect_element | self | snapshot_uri | loaded | img-responsive | | Explicit | 014 |
| CTL-REV-011 | COMP-REV-05 | Pestañas (Resumen, Preguntas, ...) | aidd-tablist | select_tab | panels | tab_order | active, idle | tabs font-medium | | Explicit | 014 |
| CTL-REV-012 | COMP-REV-05 | Checkbox de Aprobación | aidd-cb | toggle_check | state | state_map | checked, unchecked | ck-input | | Explicit | 014 |
| CTL-REV-013 | COMP-REV-05 | Comentario (opcional) | aidd-comment | input_comment | state | state_map | empty, typed | aidd-c text-input | | Explicit | 014 |
| CTL-REV-014 | COMP-REV-06 | Executive Precision | token-badge | none | self | design_tokens | normal | badge-dark | | Explicit | 014 |
