# UAT environment setup

One-time provisioning for the UAT environment at **https://uat.recruitr.in**, deployed by
[`.github/workflows/deploy-uat.yml`](../.github/workflows/deploy-uat.yml).

Nothing here can be done from CI — every step needs a dashboard, a registrar, or a repository
secret. Once it is done, `git push origin uat` is the whole deploy story.

## What gets built

| | Production | UAT |
| --- | --- | --- |
| Frontend | Vercel (existing project) | Vercel project `recruitr-uat` → `uat.recruitr.in` |
| Backend | Railway `production` → `api.recruitr.eigensu.in` | Railway `uat` → `api.uat.recruitr.in` |
| Database | production Atlas cluster | **separate** Atlas cluster, db `recruitr_uat` |
| Redis | `redis` service, `production` env | `redis` service, `uat` env |
| Deployed by | Railway/Vercel git auto-deploy | GitHub Actions, on push to `uat` |

The two environments sit on **different apex domains** — production on `eigensu.in`, UAT on
`recruitr.in`. That is why the UAT API is `api.uat.recruitr.in` rather than something under
`eigensu.in`: login is an HttpOnly `access_token` cookie set by the API and read by Next.js
middleware, so the API and the app have to share a parent domain (`COOKIE_DOMAIN=.recruitr.in`).
Put the UAT API anywhere else and sign-in appears to succeed but every page bounces back to
`/sign-in`.

Order the steps as written — DNS is slowest, so it goes early.

---

## 1. MongoDB Atlas — dedicated UAT cluster

1. Create a new cluster (M0 is fine for UAT).
2. Add a database user, and under **Network Access** allow `0.0.0.0/0`. Railway does not publish
   static egress IPs, so an allowlist is not an option here.
3. Keep the connection string for `MONGODB_URI`. The database name is `recruitr_uat`.

The app creates its own collections and indexes on first boot — there is no migration to run.

## 2. DNS — at the `recruitr.in` registrar

| Record | Type | Value |
| --- | --- | --- |
| `uat` | CNAME | `cname.vercel-dns.com` |
| `api.uat` | CNAME | the target Railway shows after step 4 |

Add the `uat` record now; come back for `api.uat` once Railway gives you the target.

## 3. Railway — the `uat` environment

In project **Eigensu Recruitment**:

1. Duplicate the `production` environment into a new one named exactly **`uat`** (the workflow
   passes `--environment uat`). This copies both the `backend` and `redis` services.
2. **Disconnect the GitHub source on the `uat` `backend` service.** This one is easy to skip and
   causes real confusion: the duplicated service inherits production's repo connection, so every
   push would deploy twice — once by Railway's own autodeploy and once by the Action — and the two
   builds race to be last.
3. Under the `backend` service's **Settings → Networking**, add the custom domain
   `api.uat.recruitr.in` targeting port **8000**. Copy the CNAME target it gives you back to step 2.
4. Set the service variables from [`.env.uat.example`](../.env.uat.example). Generate fresh
   `JWT_SECRET` / `SESSION_SECRET` values (`openssl rand -hex 32`) — do not copy production's.
5. Create a **project token scoped to the `uat` environment** (Project Settings → Tokens). An
   environment-scoped token is what keeps this pipeline structurally unable to touch production.

## 4. Vercel — the `recruitr-uat` project

1. Create a new project from `Eigensu/recruitr`, named `recruitr-uat`.
2. Set **Settings → Git → Ignored Build Step** to `exit 0`, or disconnect Git entirely. Otherwise
   Vercel builds on push *and* the Action builds, same double-deploy problem as Railway.
3. Add `uat.recruitr.in` as a domain and assign it to the **production** branch/target. The
   workflow deploys with `--prod`, which is what keeps that domain pointing at the newest build
   rather than at a rotating preview URL.
4. Add the `NEXT_PUBLIC_*` variables from [`.env.uat.example`](../.env.uat.example) to the
   **Production** scope.
5. Build settings should mirror the existing production frontend project. If you are starting from
   scratch: Root Directory `apps/frontend`, framework preset Next.js, install command inherited
   from the pnpm workspace root.

   > Worth checking against the prod project rather than trusting the default — the repo-root
   > `vercel.json` sets `installCommand: corepack pnpm install --frozen-lockfile`, which suggests
   > production may use the repo root as its Root Directory instead. Whatever prod does, match it.

6. From **Settings → General**, copy the Project ID; from the team settings, copy the Team/Org ID.

## 5. Google OAuth

In the Google Cloud console, on the OAuth client the app already uses, add:

- Authorized redirect URI: `https://api.uat.recruitr.in/api/v1/auth/google/callback`
- Authorized JavaScript origin: `https://uat.recruitr.in`

Skip this and email/password login works while "Continue with Google" returns `redirect_uri_mismatch`.

## 6. GitHub secrets

`Settings → Secrets and variables → Actions`:

| Secret | Where it comes from |
| --- | --- |
| `RAILWAY_UAT_TOKEN` | step 3.5 — project token scoped to `uat` |
| `VERCEL_TOKEN` | Vercel account settings → Tokens |
| `VERCEL_ORG_ID` | step 4.6 |
| `VERCEL_PROJECT_ID_UAT` | step 4.6 — the `recruitr-uat` project |

Optionally create a GitHub **environment** named `uat` (`Settings → Environments`) to get a
deployment history and, if you want one, a required-reviewer gate on the frontend job.

## 7. Create the branch

```bash
git switch main && git pull
git switch -c uat && git push -u origin uat
```

---

## Deploying

```bash
git switch uat && git merge main && git push
```

or run **Actions → Deploy UAT → Run workflow**.

The run does three things in order:

1. **Verify (advisory)** — ruff lint + format check, the pytest suite against a throwaway Mongo
   replica set, and eslint on the frontend. Results land on the run summary but **do not block the
   deploy** — see [Why verify is advisory](#why-verify-is-advisory).
2. **Deploy backend** — `railway up` into the `uat` environment, then polls
   `https://api.uat.recruitr.in/health` for up to five minutes.
3. **Deploy frontend** — `vercel build --prod` + `vercel deploy --prebuilt --prod`.

The frontend only ships if the backend answered `/health`, so UAT never ends up serving a new UI
against a backend that failed to boot.

## Why verify is advisory

Every check in the verify job fails on `main` today, so wiring it as a blocking gate would have
meant UAT could never deploy at all. Measured on `main` at the time this pipeline was written:

| Check | State |
| --- | --- |
| `ruff check` | 4 errors — 3× UP042 (`class X(str, Enum)`), 1× unsorted imports in `fix_index.py` |
| `ruff format --check` | 1 file unformatted |
| `pytest` | 39 of 89 failing |
| `pnpm --filter frontend lint` | 1 error — `set-state-in-effect` in `ClientMessagingBanner.tsx` |

Most of the pytest failures are HTTP 422s: the fixtures build candidate payloads without a
`communication` field the schema now requires. The remainder compare timestamps — Mongo truncates
datetimes to milliseconds and drops the `Z`, so a value read back never equals the one just sent.
None of that is caused by the UAT work; the pre-commit hook only lints *staged* files, so the rest
of the tree drifted.

Fixing those is worth its own PR. When it lands, delete the four `continue-on-error: true` lines
in `.github/workflows/deploy-uat.yml` and the job becomes a real gate — no other change needed.

## Health

A `"degraded"` health response does **not** fail the deploy. It means index sync was skipped after
a startup failure — the API still serves every request, so the run passes with a warning on the job
summary. Investigate with `apps/backend/scripts/inspect_indexes.py` when you see it.

## Verifying a deploy by hand

```bash
curl -s https://api.uat.recruitr.in/health          # {"status":"ok","version":"1.0.0"}
curl -sI https://uat.recruitr.in | head -1          # HTTP/2 200
```

Then in a browser: sign in, confirm the `access_token` cookie is scoped to `.recruitr.in`, and
confirm the dashboard loads data from `api.uat.recruitr.in` with no CORS errors in the console.

## Troubleshooting

| Symptom | Cause |
| --- | --- |
| Sign-in succeeds, then every page redirects to `/sign-in` | `COOKIE_DOMAIN` is not `.recruitr.in`, so the cookie never reaches the frontend host |
| Browser console shows CORS errors | `CORS_ORIGINS` must be the JSON array `["https://uat.recruitr.in"]`, not a bare string |
| Sign-up rejected for everyone | `AGENCY_EMAIL_DOMAINS` is empty, which blocks all new accounts |
| Cookies missing `Secure` over HTTPS | `DEBUG` is `true`; the app derives cookie security from it |
| Frontend calls `localhost:8000` | `NEXT_PUBLIC_API_URL` is unset in the Vercel project — it falls back silently |
| Two deploys per push | the `uat` Railway service or the Vercel project still has Git auto-deploy on |
| `railway up` fails with a project/environment error | the token is not scoped to the `uat` environment |
