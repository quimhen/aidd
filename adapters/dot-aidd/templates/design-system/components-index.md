# Component Index — [project name]

Project-level, not per-feature. One row per `COMP-nnn` ever created, across every spec. Check this
FIRST in Step 1 before minting a new component — a lookup here beats grepping every spec folder.

| COMP-nnn | Name | File | First defined in (spec folder) | Used in (SCREEN-XX across all specs) | Consumers | Notes |
|---|---|---|---|---|---|---|
| COMP-001 | ClientCard | lib/core/widgets/client_card.dart | specs/003-customer-portfolio | SCREEN-02, SCREEN-08 | portfolio_page.dart, client_detail_page.dart | |

`Consumers` = the files that actually import/use the component. A shared standard (header, back button, logo) is a COMP: list every consumer so a change reaches all of them, and so no screen re-does it by hand. A COMP with a screen in `Used in` but an empty `Consumers` is flagged by `check_spec.py`.

Update this file whenever Step 1 (a new component) or Step 5 (a new screen starts using an existing
component) changes the picture — it's only useful if it stays current.
