# Traceability — [feature name]

Full-stack features only. One row per data field a screen shows or sends, followed end to end:
what the mockup displays, where the app keeps it, the DTO that carries it, the API that serves it and the
stored procedure behind it. A field with a hole in this chain is the "N/D card" or the widget wired to
nothing: it is a gap to close before building, not after the user finds it.

Every cell is required. If a link genuinely does not exist, write `n/a — <reason>` (never leave it blank).

| Mockup field (SCREEN-XX / CTL-nnn) | Room/store | DTO | API | SP | Filled-by |
|---|---|---|---|---|---|
| SCREEN-01 / CTL-001 | | | API-001 | | |

- **Mockup field** — the visible value or input, citing its code from `mockup-audit.md`.
- **Room/store** — the local table, store or state holder that keeps it on the client.
- **DTO** — the transfer object / field name that carries it between client and API.
- **API** — the `API-nnn` from `contracts.md` that serves or receives it.
- **SP** — the stored procedure (and column) the API reads or writes, or `n/a — <reason>`.
- **Filled-by** — who or what populates it: the task (`T-nn`) that implements the link, or the process that fills the source data.

`check_spec.py` flags any row with an empty cell.
