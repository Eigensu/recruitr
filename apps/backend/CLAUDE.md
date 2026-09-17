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
  (conflicting/quota-exceeded indexes), it falls back to `skip_indexes=True` for *all* models and
  flips `/health` to `"degraded"` — see `scripts/inspect_indexes.py` / `fix_ttl_indexes.py` /
  `fix_index_conflicts.py`.
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
