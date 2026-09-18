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

## Running them

Local (both are part of `docker-compose up -d`):

```bash
docker-compose up -d worker beat
docker-compose logs -f worker beat
```

Directly, without compose:

```bash
cd apps/backend
uv run celery -A app.core.celery_app.celery_app worker --loglevel=info
uv run celery -A app.core.celery_app.celery_app beat   --loglevel=info
```

Production (Railway) needs **two additional services** in the same project,
both built from `apps/backend` with the same environment variables as the
`backend` service — they need `MONGODB_URI`, `CELERY_BROKER_URL`,
`CELERY_RESULT_BACKEND` and the Resend/email credentials:

| Service | Start command |
| --- | --- |
| `worker` | `celery -A app.core.celery_app.celery_app worker --loglevel=info` |
| `beat` | `celery -A app.core.celery_app.celery_app beat --loglevel=info` |

Run exactly **one** beat replica. Two schedulers means every scheduled task
fires twice, which means duplicate reminder emails.

The worker can scale horizontally. Task idempotency is handled by
`Mapping.reminders_sent`, which records a key per (mapping, reminder type)
before the reminder is considered sent.

## Checking whether they are alive

```bash
# Queued but unconsumed messages — a growing number means no worker.
redis-cli -u "$CELERY_BROKER_URL" llen celery

# Workers currently responding.
cd apps/backend && uv run celery -A app.core.celery_app.celery_app inspect ping
```
