# CI

[`.github/workflows/ci.yml`](../.github/workflows/ci.yml) runs on every pull request and on pushes
to `main`.

Three jobs run in parallel:

| Job | Checks |
| --- | --- |
| **Backend** | `ruff check` → `ruff format --check` → `pytest` |
| **Frontend** | `eslint` → `prettier --check` → `tsc --noEmit` → `next build` |
| **Workflows** | `actionlint` (which also shellchecks every `run:` block) |

Lint runs before tests in each job: a ten-second failure shouldn't wait on a multi-minute suite.
ESLint warnings don't fail the job; errors do.

## Running the same checks locally

```bash
# Backend — needs a Mongo replica set (see below)
cd apps/backend
uv pip install -r requirements.txt -r requirements-dev.txt
uv run ruff check . && uv run ruff format --check .
MONGODB_URI="mongodb://localhost:27017/recruitr" uv run pytest -q

# Frontend
pnpm install --frozen-lockfile
pnpm --filter frontend lint
pnpm --filter frontend format:check
pnpm --filter frontend typecheck
pnpm --filter frontend build
```

`requirements-dev.txt` pulls in `requirements.txt` and adds pytest, pytest-asyncio and ruff. Don't
`uv sync` — `pyproject.toml` declares only `resend`, so it would uninstall everything else.

If a local `next build` fails typechecking on a page that no longer exists, delete
`apps/frontend/.next`: `next dev` leaves generated route types in `.next/dev/types` that outlive
deleted pages. CI builds from a clean checkout and never sees them.

## The Mongo replica set

`tests/conftest.py` creates `{MONGODB_DB_NAME}_test` per test and Beanie opens transactions, which
MongoDB only permits on a replica set. `docker-compose up -d` from the repo root gives you a
single-node `rs0` on `:27017` (plus Redis); CI starts the equivalent by hand, because a GitHub
`services:` container has no way to run `rs.initiate`.

Against a standalone mongod the suite does not fail cleanly — it hangs on server selection until
each operation times out.
