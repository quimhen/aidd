# API Contracts — [feature name]

One row per endpoint the frontend depends on. Fill this before Step 4 (Tasks) when the feature
is full-stack — a task that implements a `CTL-nnn` calling an undefined `API-nnn` is not ready to approve.

Fixed rules (see SKILL.md "Data access & frontend↔backend communication"):
- Frontend↔backend communication is via API only — never direct DB/service access from the frontend.
- DB access goes through a stored procedure by default — an empty "Stored procedure(s)" cell is a gap, not a shortcut, unless "Exception reason" says why.
- No `API-nnn` is done without its Swagger/OpenAPI ref matching this table.

| API-nnn | Method + path | Request schema | Response schema | Error cases | Auth | Stored procedure(s) | Swagger/OpenAPI ref | Consumed by (CTL-nnn) | Exception reason (if no SP) | PR/Spec ref |
|---|---|---|---|---|---|---|---|---|---|---|
| API-001 | `POST /orders` | `{ clientId, items[] }` | `{ orderId, status }` | 400 invalid items, 409 client blocked | Bearer token | `sp_CreateOrder` | `/swagger/orders#post` | CTL-078 | | |

## Contract details (one block per API-nnn, only when the table row needs more than a schema summary)

### API-001 — `POST /orders`
- **Purpose:** [one sentence]
- **Request body:** [full schema or link to it]
- **Response body:** [full schema or link to it]
- **Error responses:** [status code → meaning → what the frontend should show]
- **Stored procedure(s):** [name(s), and what each one does — never inline SQL for this unless the Exception reason above justifies it]
- **Index/plan evidence:** [which existing index it uses, or the one added for it — verified with the engine's own plan tool: `EXPLAIN ANALYZE` (PostgreSQL/MySQL), execution plan (SQL Server), `EXPLAIN PLAN` (Oracle). "It works" isn't evidence; the plan is.]
- **Swagger/OpenAPI:** [path to the spec file or the live docs URL — generated alongside the endpoint, not after]
- **Idempotency / retries:** [if applicable]
- **Backward compatibility:** [does this change an existing contract? what breaks?]
