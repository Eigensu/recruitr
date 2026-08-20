# apps/backend/CLAUDE.md

Module-specific guidance for the backend. See the root `CLAUDE.md` for commands, environment, and
cross-cutting notes.

## Backend architecture (`apps/backend/app`)

- `main.py` — FastAPI app assembly: middleware, router mounts, `/health`. Read this first to see
  which routers exist and what dependency guards are attached at the router level (e.g. the
  leaderboard router blanket-denies the `client` role via `dependencies=[Depends(deny_clients)]`
  so no endpoint added later can forget it).
- `config.py` — `Settings` (pydantic-settings), loaded once as the `settings` singleton.
- `database.py` — Beanie/Mongo init. **Every Beanie Document model must be registered in the
  `document_models` list here** (and mirrored in `tests/conftest.py`'s fixture) or it fails at
  query time with `CollectionWasNotInitialized` instead of at startup. If Mongo index sync fails
  (conflicting/quota-exceeded indexes), it falls back to `skip_indexes=True` for *all* models and
  flips `/health` to `"degraded"` — see `scripts/inspect_indexes.py` / `fix_ttl_indexes.py` /
  `fix_index_conflicts.py`.
- `dependencies.py` — the auth/tenant dependency chain used across nearly every route. Understand
  this before touching any endpoint:
  - `get_current_user` → decodes the `access_token` HttpOnly cookie (or `Authorization: Bearer`)
    as a local JWT.
  - `get_current_user_doc` → loads the full `User`.
  - `get_current_employee` → resolves to an `Employee` record (auto-provisions one if missing).
  - `get_tenant` → the main guard. Returns a `TenantScope(brand_id, employee_id, role)` and
    **rejects the `client` role outright**. Most staff endpoints depend on this, so a client is
    denied by default everywhere and access must be deliberately opened per-endpoint — the
    containment strategy is "forgetting a guard locks a client out; it never leaks."
  - `get_client_scope` / `get_viewer` → the opposite path, for endpoints both staff and clients
    may hit. `get_viewer` returns a `TenantScope` with `client_id` set for clients; handlers using
    it **must** call `scope.scoped(match)` to narrow their Mongo query, since nothing else stops a
    client reading another company's data.
  - `require_admin`, `require_maintainer`, `deny_clients` — narrower role guards.
- `app/modules/<name>/` — one package per bounded context: `auth`, `brands`, `recruitment`,
  `dashboard`, `gamification`, `leaderboard`, `storage`. `recruitment` is the core domain
  (candidates, positions, pipeline, clients, client-messaging, teams, tags, activity — all unified
  into one module because they share tenant-scoping and cross-reference each other constantly).
  Within a module the convention is `router`/`controller` (HTTP layer) → `service` (business logic)
  → `repository` (Mongo access) → `models` (Beanie documents) → `schemas` (Pydantic I/O). In
  `recruitment` specifically, `repository/__init__.py` and `service/__init__.py` are thin re-export
  facades over `repository_impl.py` / `service_impl.py` (a mid-refactor split into per-domain
  files, in progress) — import from the package, not the `_impl` module, from outside the package.
  Every repository function takes a `TenantScope` and prepends `brand_id` to its query; never call
  `get_motor_collection()` directly outside `repository_impl.py`.
- Gamification/leaderboard credit is fire-and-forget from the recruitment service layer — a
  duplicate award or Redis failure must never roll back the domain write that triggered it.

## Auth model

Custom JWT (not Clerk, not a third-party auth provider), issued on `/api/v1/auth/login` or
`/signup` and set as an HttpOnly `access_token` cookie; `COOKIE_DOMAIN` is set to a shared parent
domain in prod so the frontend and backend subdomains both receive it. Google OAuth
(`/api/v1/auth/google/*`) is a secondary login path onto the same `User`/JWT model, not a
replacement for it. Roles (`app/modules/auth/models.py: UserRole`) form a staff hierarchy plus one
outsider role: `admin ⊇ maintainer ⊇ employee` (all recruiters/agency staff, with `employee` being
the leaderboard-earning recruiter), and `client` — an employer contact with no `Employee` record,
scoped to exactly one company via `ClientUser`, and excluded from every staff endpoint unless a
route explicitly opts in via `get_viewer`/`get_client_scope`. New staff signups are gated by
`AGENCY_EMAIL_DOMAINS` (comma-separated allowed email domains); an empty value blocks *new*
signups but doesn't revoke existing accounts.
