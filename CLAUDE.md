# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

Eigensu ("Binge Consulting Recruitment Platform") — a gamified recruitment CRM. Monorepo with a
Next.js frontend and a FastAPI/MongoDB backend, managed with pnpm workspaces + Turborepo.

- `apps/frontend` — Next.js 16 (App Router), React 19, TypeScript, Tailwind v4, Zustand.
- `apps/backend` — FastAPI, Python 3.11+, MongoDB via Beanie ODM, Redis (cache + Celery broker).
- `specs/` — design/implementation docs. Treat these as historical context, not ground truth —
  several (`ONBOARDING.md`, `handovers/handover1.md`) predate the current module layout (e.g. they
  describe separate `positions`/`candidates`/`pipeline` modules that have since been unified into
  `app/modules/recruitment`). Verify against the actual code before trusting specifics in them.

## Commands

Run from the repo root unless noted.

```bash
# Install everything (frontend workspace + root)
pnpm install

# Run both apps via Turborepo
pnpm dev

# Frontend only
pnpm dev:frontend               # or: pnpm --filter frontend dev
pnpm build:frontend
pnpm --filter frontend lint     # eslint
pnpm --filter frontend format   # prettier --write .

# Backend only (from repo root, uses uv)
pnpm dev:backend                 # uvicorn app.core.main:app --reload --port 8000
cd apps/backend && uv sync       # install deps (uv.lock is the source of truth; requirements.txt is kept in sync for Docker)
# Tests refuse to run unless MONGODB_URI is local — see the note below.
cd apps/backend && MONGODB_URI="mongodb://localhost:27017/recruitr" uv run pytest             # full suite
cd apps/backend && MONGODB_URI="mongodb://localhost:27017/recruitr" uv run pytest tests/test_recruitment/test_candidates_api.py           # single file
cd apps/backend && MONGODB_URI="mongodb://localhost:27017/recruitr" uv run pytest tests/test_recruitment/test_candidates_api.py::test_name -v  # single test
cd apps/backend && uv run ruff check .                    # lint
cd apps/backend && uv run ruff format .                    # format
```

Backend tests spin up a real MongoDB (`{MONGODB_DB_NAME}_test`) per test via a `pytest_asyncio`
autouse fixture in `tests/conftest.py` — a Mongo instance must be reachable at `MONGODB_URI`. Use
`docker-compose up -d` (starts a single-node Mongo *replica set* on `:27017`, required for Beanie
transactions, plus Redis on `:6379`) if nothing is running locally.

**That fixture drops its database on teardown, and the repo-root `.env` points `MONGODB_URI` at the
live Atlas cluster** — so it calls `assert_local_database()` first and refuses to run against a
non-local host, the same guard the seeders use. Override `MONGODB_URI` on the command line (env
vars beat `.env`) as shown above, or set `SEED_ALLOW_REMOTE_DB=1` if you really mean to target a
remote scratch cluster.

`pyproject.toml` is the source of truth for lint/test config: ruff targets py311, line-length 100,
`E501`/`B008` ignored (B008 is the FastAPI `Depends()` default-arg idiom); pytest uses
`asyncio_mode = "auto"`.

A husky `pre-commit` hook runs `lint-staged` (eslint --fix + prettier) on staged frontend files and
`ruff check --fix` + `ruff format` on staged backend `.py` files.

## Environment

Single `.env` at the repo root is the source of truth for both apps (see `.env.example`):
Backend reads it via `pydantic-settings` (`app/core/config.py` finds the root by walking up for
`pnpm-workspace.yaml`, so it works regardless of cwd and survives the file being moved). Frontend
reads `NEXT_PUBLIC_*`-prefixed vars via `next.config.ts`.

Note: `.env.example` lists Clerk keys (`NEXT_PUBLIC_CLERK_*`), but auth is **not** Clerk-based —
see Auth below. Those vars are currently unused; don't assume Clerk is wired up anywhere.

Backend architecture and auth model → `apps/backend/CLAUDE.md`. Frontend architecture →
`apps/frontend/CLAUDE.md`. Both load automatically when working under those directories.

## Cross-cutting notes

- MongoDB is accessed through Beanie almost everywhere; the recruitment module's `TenantScope`
  pattern (always filter by `brand_id`, narrow further with `.scoped()` for client viewers) is the
  main tenant-isolation mechanism — replicate it rather than inventing a new scoping approach.
  `Counter` documents back sequential IDs used across the recruitment domain. `AsyncMongoClient`
  (pymongo's native async driver) plus Beanie is the whole data layer — there is no separate ORM;
  code needing a raw transaction gets the client via `database.get_client()`.
- File uploads (resumes/CVs) go through Cloudinary (`app/modules/storage`), not local disk or S3
  despite some older specs mentioning S3 presigned URLs.
  `NEXT_PUBLIC_CLOUDINARY_*` env vars are used for direct-from-browser upload widgets.
- Redis is optional in dev (`REDIS_ENABLED` flag) and backs the dashboard/leaderboard cache
  (`app/common/extras/redis_cache.py`) plus the Celery broker/result backend for background jobs
  (`app/core/celery_app.py`).
