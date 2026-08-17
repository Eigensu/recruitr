# CI

[`.github/workflows/ci.yml`](../.github/workflows/ci.yml) runs on every pull request and on pushes
to `main` and `uat`. `deploy-uat.yml` calls the same workflow via `workflow_call`, so a check added
here automatically gates the UAT deploy — there is one definition of "green", not two.

Three jobs run in parallel:

| Job | Checks |
| --- | --- |
| **Backend** | `ruff check` → `ruff format --check` → `pytest` |
| **Frontend** | `eslint` → `prettier --check` → `tsc --noEmit` → `next build` |
| **Workflows** | `actionlint` (which also shellchecks every `run:` block) |

Lint runs before tests in each job: a ten-second failure shouldn't wait on a three-minute suite.

## Running the same checks locally

```bash
# Backend — needs a Mongo replica set (see below)
cd apps/backend
pip install -r requirements-dev.txt      # or: uv pip install -r requirements-dev.txt
ruff check . && ruff format --check .
pytest -q

# Frontend
pnpm install --frozen-lockfile
pnpm --filter frontend lint
pnpm --filter frontend format:check
pnpm --filter frontend typecheck
pnpm --filter frontend build
```

`requirements-dev.txt` is the manifest for CI and local dev: it pulls in `requirements.txt` and adds
pytest, pytest-asyncio and ruff. `uv.lock` pins nothing — `pyproject.toml` declares no dependency
list — so `uv sync` alone will not give you a working test environment despite what older docs say.

## The Mongo replica set

`tests/conftest.py` creates `{MONGODB_DB_NAME}_test` per test and Beanie opens transactions, which
MongoDB only permits on a replica set. `docker-compose up -d` from the repo root gives you a
single-node `rs0` on `:27017` (plus Redis); CI starts the equivalent by hand, because a GitHub
`services:` container has no way to run `rs.initiate`.

Against a standalone mongod the suite does not fail cleanly — it hangs on server selection until
each operation times out.

## xfails

Two tests in `tests/test_recruitment/test_candidates_api.py` are marked `xfail(strict=True)`:

- `test_create_without_email_succeeds`
- `test_two_emailless_candidates_in_one_brand_do_not_collide`

They assert that a candidate can be created without an email address. #38 made `email` required on
`CandidateCreateStrict`, and the public `/apply` form requires it too, so no HTTP path does that any
more — both now get a 422.

They are xfailed rather than deleted because the partial unique index they describe is still on the
model and still load-bearing (`d3c3dbc` fixed exactly this for referee invites). Resolve it one way
or the other: if email is genuinely mandatory everywhere now, delete both tests and the partial
index becomes dead weight. If it is not, these are a live regression. `strict=True` means the
markers fail loudly the day the behaviour comes back, so they cannot rot silently.

## Test payloads

`POST /api/v1/candidates` validates against `CandidateCreateStrict`, which requires every
recruiter-presented field — a partial body is rejected with 422 before it reaches the handler.
`tests/test_recruitment/payloads.py` holds the one complete payload every recruitment test builds
on, so the next schema change breaks a single constant rather than five test modules.
