# apps/backend/CLAUDE.md

Module-specific guidance for the backend. See the root `CLAUDE.md` for commands, environment, and
cross-cutting notes.

## Backend architecture (`apps/backend/app`)

- `core/main.py` — FastAPI app assembly: middleware, router mounts, `/health`. Read this first to see
  which routers exist and what dependency guards are attached at the router level (e.g. the
  leaderboard router blanket-denies the `client`, `referee` and `telecaller` roles via
  `dependencies=[Depends(deny_outsiders)]` so no endpoint added later can forget it).
- `core/config.py` — `Settings` (pydantic-settings), loaded once as the `settings` singleton. It
  locates the root `.env` by walking up for `pnpm-workspace.yaml` rather than a fixed number of
  parent hops — a hardcoded hop count silently resolves to a path with no `.env` if this file ever
  moves, and every setting then falls back to its default without erroring.
- `core/database.py` — Beanie/Mongo init. **Every Beanie Document model must be registered in the
  `document_models` list here** (and mirrored in `tests/conftest.py`'s fixture) or it fails at
  query time with `CollectionWasNotInitialized` instead of at startup. If Mongo index sync fails
  (conflicting/quota-exceeded indexes), each model is re-registered individually so only the
  models that actually conflict fall back to `skip_indexes=True` — the rest keep their indexes,
  unique constraints included. `/health` flips to `"degraded"` and names the affected
  collections. See `scripts/inspect_indexes.py` to view the drift and
  `scripts/fix_index_conflicts.py` to repair it (`fix_ttl_indexes.py` only compares
  `expireAfterSeconds`, so it cannot fix an option or name conflict).
- `core/dependencies.py` — the auth/tenant dependency chain used across nearly every route. Understand
  this before touching any endpoint:
  - `get_current_user` → decodes the `access_token` HttpOnly cookie (or `Authorization: Bearer`)
    as a local JWT.
  - `get_current_user_doc` → loads the full `User`.
  - `get_current_employee` → resolves to an `Employee` record (auto-provisions one if missing).
  - `get_tenant` → the main guard. Returns a `TenantScope(brand_id, employee_id, role)` and
    **rejects the `client` and `telecaller` roles outright**. Most staff endpoints depend on this,
    so both are denied by default everywhere and access must be deliberately opened per-endpoint —
    the containment strategy is "forgetting a guard locks them out; it never leaks."
    `tests/test_auth/test_telecaller_access.py` sweeps every route in the OpenAPI schema as a real
    signed-in telecaller, so a new endpoint that forgets its guard fails there.
  - `get_client_scope` / `get_viewer` → the opposite path, for endpoints both staff and clients
    may hit. `get_viewer` returns a `TenantScope` with `client_id` set for clients; handlers using
    it **must** call `scope.scoped(match)` to narrow their Mongo query, since nothing else stops a
    client reading another company's data.
  - `get_inbox_viewer` → `get_viewer` plus telecallers, for the notification inbox only. Not a
    widening of `get_viewer`, which would open every pipeline/positions/dashboard endpoint built on
    it.
  - `require_admin`, `require_maintainer`, `deny_outsiders` — narrower role guards.
- `app/modules/<name>/` — one package per bounded context: `auth`, `brands`, `recruitment`,
  `dashboard`, `gamification`, `leaderboard`, `storage`. `recruitment` is the core domain
  (candidates, positions, pipeline, clients, client-messaging, teams, tags, activity — all unified
  into one module because they share tenant-scoping and cross-reference each other constantly).
  Within a module the convention is `router`/`controller` (HTTP layer) → `service` (business logic)
  → `repository` (Mongo access) → `models` (Beanie documents) → `schemas` (Pydantic I/O). In
  `recruitment` specifically, each layer is a package whose `__init__.py` is the public surface and
  whose `_impl.py` is private to it: `repository/{__init__,_impl}.py` and
  `service/{__init__,_impl,resume_service}.py`. Import from the package, never from `_impl` — the
  underscore is the rule, and it is what lets `_impl.py` be split into per-domain modules (the
  mid-refactor direction; `resume_service.py` is the first piece carved out) without touching a
  caller. There is no separate `services/` package; reintroducing one would put two importable
  names a single letter apart, which is exactly what was just removed. Every repository function
  takes a `TenantScope` and prepends `brand_id` to its query; never call `get_motor_collection()`
  outside `repository/_impl.py`. `dashboard` follows the same shape with its HTTP layer in
  `routers/` and business logic in `services/` — plural there, since those directories hold several
  peers and no facade.
- Gamification/leaderboard credit is fire-and-forget from the recruitment service layer — a
  duplicate award or Redis failure must never roll back the domain write that triggered it.

## Inbound lead intake

Every external candidate is screened by a telecaller before a recruiter sees them. Meta lead-ad
candidates land in a Google Sheet and are ingested on a schedule; public-form applications
(referrals included — they come through the same form with a connect code) open a lead as they
are submitted (`intake_service.open_lead_for_application`). Design doc and decisions log:
`specs/telecaller_intake_spec.md`.

```
pending_telecaller ──accept + details form──▶ pending_review ──admin picks a team──▶ pending_recruiter ──first mapping──▶ actioned
        └──reject──▶ rejected                   (no SLA clock)     (team round-robin)     (recruiter SLA)
```

**Accept requires the details form** (`IntakeCandidateDetails`: the manual-create required fields
minus brand experience, CV link optional) and parks the lead in `pending_review` with the
candidate still PENDING. **`POST /intake/leads/assign-team`** (maintainer+) picks the recruiter
with a per-team round-robin (`Counter` key `intake_team_rr:<team_id>`, roster =
`intake_service.team_roster`), approves the candidate, and starts the recruiter SLA clock. The
External tab's approve/reject refuses (409) any candidate whose lead is still being screened or
reviewed (`open_lead_for`), so the two paths cannot both decide one person.

| Piece | Where |
|---|---|
| Sheet read — service account, `spreadsheets.readonly` | `recruitment/utils/google_sheets.py` |
| Column mapping, row parsing, phone normalisation | `recruitment/utils/{lead_sheet,phone}.py` |
| Ingest, round-robin, accept / reject / team assignment / reassign | `recruitment/service/intake_service.py` |
| Funnel, per-leg timings, campaign report | `recruitment/service/intake_analytics.py` |
| Hourly breach sweep, daily digest | `recruitment/service/intake_sla.py` |
| HTTP | `recruitment/controller/intake.py` |
| Scheduled jobs | `recruitment/tasks.py` + the beat schedule in `core/celery_app.py` |
| Historical import | `scripts/backfill_intake_leads.py` (report-only unless `--confirm`) |

These sit *beside* `service/_impl.py` rather than inside it — the direction `resume_service.py`
started. Import them by module path; only `_impl` is off-limits.

**Timestamps read back from Mongo are naive, and Python raises on comparing them to an aware
`datetime` rather than guessing.** `intake_service.as_utc()` is the single place that fixes it, and
every comparison between a stored timestamp and "now" must go through it. This is not theoretical:
it was found by a test after it had already shipped in code that would have crashed every poll the
moment the integration was switched on. `intake_analytics` and `intake_sla` both import `as_utc`
from `intake_service`; the read and alert models depend on the write model and never the reverse,
which is what keeps all three importable.

**Ingest is idempotent.** `(brand_id, external_id)` is unique on `IntakeLead`, so re-reading a row
is a no-op — which is what lets the poll read the whole range every run instead of tracking a
cursor into someone else's spreadsheet. Dedupe against *people* already in the pool is separate,
and is an in-memory index built per run (`_ContactIndex`), not a stored field: a stored
`phone_normalized` would have missed every candidate created before it existed.

**Two doors into this module, on purpose.** The queue routes take `get_telecaller_tenant`, the only
dependency that admits the role. Everything under `/intake/analytics`, `/intake/leads` (the admin
list), `/intake/assignees` and `/intake/config` takes plain `get_tenant`, so the refusal that
protects the rest of the app also keeps a telecaller out of the reports about their own response
times. `/leads/mine` must stay declared *before* `/leads/{lead_id}` or the path parameter swallows
it — there is a test for exactly that.

**Assignment rosters** come from `intake_service.assignment_roster()`, which is what the round-robin
itself draws from. Do not build a picker out of `GET /teams/employees`: that endpoint deliberately
hides `NON_RECRUITER_ROLES`, telecallers included, so it would offer names the assignment then
refuses. `GET /intake/assignees` is the one for this.

**Analytics are cached** in the `dashboard_cache` Redis namespace under `<brand>:intake:*` and
dropped by `intake_analytics.invalidate()` after every lead write. `map_candidate` already clears
`<brand>:*`, so the recruiter leg rides along with it. The admin lead list is deliberately *not*
cached — a five-minute-old answer to "what is overdue right now" is worse than the query.

**SLA alerts fire once per lead**, guarded by the `*_sla_breached_at` stamp, which is set whether or
not there was anyone to notify: the breach is a fact about the lead, not about the delivery. A
reassignment clears it so the new owner starts clean. Recipients are admins *and* maintainers —
reassigning is maintainer-gated, so that is exactly the set who can act on the alert.


## Auth model

Custom JWT (not Clerk, not a third-party auth provider), issued on `/api/v1/auth/login` or
`/signup` and set as an HttpOnly `access_token` cookie; `COOKIE_DOMAIN` is set to a shared parent
domain in prod so the frontend and backend subdomains both receive it. Google OAuth
(`/api/v1/auth/google/*`) is a secondary login path onto the same `User`/JWT model, not a
replacement for it. Roles (`app/modules/auth/models.py: UserRole`) form a staff hierarchy plus
roles outside it: `admin ⊇ maintainer ⊇ employee` (all recruiters/agency staff, with `employee` being
the leaderboard-earning recruiter); `client` — an employer contact with no `Employee` record,
scoped to exactly one company via `ClientUser`, and excluded from every staff endpoint unless a
route explicitly opts in via `get_viewer`/`get_client_scope`; `referee`, likewise grant-based via
`RefereeUser`; and `telecaller` — agency staff who screen inbound leads by phone. A telecaller
*does* have an `Employee` record and a brand, which is exactly why `get_tenant` must refuse it: to
every endpoint written before the role existed, it would look like a recruiter.

Recruiter rosters (leaderboard, task progress, dashboard employee table, employee listings) exclude
`NON_RECRUITER_ROLES` with `$nin`, never `role == "employee"` — `Employee` rows predating the role
field have none, and an equality match would silently drop those recruiters. A new staff role that
does not recruit goes into that tuple and nowhere else. Roles are assigned manually with
`scripts/migrate_user_roles.py promote`; there is no role-changing endpoint.

New staff signups are gated by `AGENCY_EMAIL_DOMAINS` (comma-separated allowed email domains); an
empty value blocks *new* signups but doesn't revoke existing accounts.
