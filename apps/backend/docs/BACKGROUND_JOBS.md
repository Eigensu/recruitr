# Background jobs

Everything asynchronous in the product runs through Celery. **A Celery worker
and a Celery beat process must be running, or none of it happens.** The API
server does not execute tasks — it only enqueues them.

## What depends on this

| Behaviour | Task | Trigger |
| --- | --- | --- |
| New-position notification (email to every active employee in the brand, plus an `ActivityLog` entry) | `recruitment.process_new_position_notifications` | `.delay()` from `POST /positions` |
| "Client has not actioned in 2 days" reminder | `recruitment.process_reminders` | beat, 01:30 UTC daily |
| "Interview was 2 days ago, decide" reminder | `recruitment.process_reminders` | beat, 01:30 UTC daily |
| "Selected 2 days ago, upload the offer letter" reminder | `recruitment.process_reminders` | beat, 01:30 UTC daily |
| Candidate auto-moves to `joined` on their joining date | `recruitment.process_joining_dates` | beat, 02:00 UTC daily |
| Leaderboard cache refresh and monthly snapshot | `leaderboard.*` | beat |
| Daily referee processor | `dashboard.daily_referee_processor` | beat, 01:00 UTC daily |

The three reminders each write **two** in-app notifications — one for the
client and one brand-wide for staff (`client_id=None`) — so the team can act
when the client is unavailable. That staff fallback is in
`recruitment/tasks.py::_send_client_reminders`.

## Failure mode when they are not running

Nothing errors. `.delay()` succeeds — it only writes to Redis — and returns.
The message then sits in the queue with no consumer, indefinitely. Beat
schedules never fire at all because no beat process exists to fire them. The
API keeps serving normally, `/health` stays `ok`, and the logs are silent.

The symptom is entirely on the product side: no notification email ever
arrives, the bell never populates, no reminder is sent, and candidates never
transition to `joined` on their joining date. It looks like unimplemented
features rather than undeployed processes.

## Running them locally

Both are part of the compose stack:

```
docker-compose up -d worker beat
docker-compose logs -f worker beat
```

Or directly, from `apps/backend`, with `uv run celery` against
`app.core.celery_app.celery_app` — `worker` for the queue consumer and `beat`
for the scheduler, both at `--loglevel=info`.

## Provisioning them in production

Production needs **two additional services** in the `Eigensu Recruitment`
project, alongside `backend` and `redis`. Neither serves HTTP, so neither
needs a domain or a `PORT`.

For each of `worker` and `beat`:

1. **New Service → GitHub Repo → `Eigensu/recruitr`.**
2. **Settings → Source:** set *Root Directory* to `/apps/backend`, and the
   branch to whatever `backend` currently deploys. The builder is the same
   `apps/backend/Dockerfile` the API uses — only the start command differs.
3. **Settings → Deploy → Custom Start Command:**

   | Service | Start command |
   | --- | --- |
   | `worker` | `celery -A app.core.celery_app.celery_app worker --loglevel=info` |
   | `beat` | `celery -A app.core.celery_app.celery_app beat --loglevel=info` |

4. **Variables.** Reference the API's rather than pasting secret values, so
   there is one copy to rotate:

   ```
   MONGODB_URI=${{backend.MONGODB_URI}}
   MONGODB_DB_NAME=${{backend.MONGODB_DB_NAME}}
   CELERY_BROKER_URL=${{backend.CELERY_BROKER_URL}}
   CELERY_RESULT_BACKEND=${{backend.CELERY_RESULT_BACKEND}}
   REDIS_URL=${{backend.REDIS_URL}}
   FRONTEND_URL=${{backend.FRONTEND_URL}}
   ```

   Plus whichever variable holds the Resend API key on `backend` — the worker
   sends the reminder and new-position emails.

   It never issues cookies or JWTs, so it does not need `JWT_SECRET`,
   `SESSION_SECRET`, `COOKIE_DOMAIN`, `CORS_ORIGINS` or the Google OAuth
   variables. `CLOUDINARY_*` is only needed if a task is later given file
   uploads; none of the current ones upload.

5. **Replicas: `beat` must stay at 1.** Two schedulers fire every scheduled
   task twice, which means duplicate reminder emails to clients. `worker` can
   scale horizontally — `Mapping.reminders_sent` records a key per (mapping,
   reminder type) before a reminder counts as sent, so extra workers will not
   double-send.

### Confirming it worked

After the first deploy, `worker` logs should show `celery@… ready.` followed
by the registered task list, and `beat` should log a due-task line for
`recruitment-reminders` at 01:30 UTC.

Rather than waiting a day, the fastest proof is to create a position: the
worker should log `recruitment.process_new_position_notifications` within
seconds and the email should arrive.

## Checking whether they are alive

A growing queue length on the broker's `celery` list means messages are being
produced with nothing consuming them — the exact state production was in
before these services existed. `celery … inspect ping` against the same app
returns the workers currently responding, and an empty reply means none.
