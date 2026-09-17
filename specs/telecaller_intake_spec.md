# Telecaller Intake Pipeline — Technical Specification

**Status:** Draft for review · **Branch:** `claude/cool-ptolemy-9a4fsq`

Adds a **Telecaller** role, a **live Google Sheets ingest** of Meta (Instagram) lead-ad
candidates, a **two-leg review workflow** (telecaller → recruiter), **admin observability** on
time-to-action for both legs, and an **SLA breach alert** when a telecaller sits on a lead for
more than a day.

---

## 1. Context and constraints

Read `CLAUDE.md`, `apps/backend/CLAUDE.md` first. The design below leans on four existing
mechanisms rather than inventing parallel ones:

| Existing mechanism | Where | Reused for |
|---|---|---|
| `TenantScope` + `brand_id` on every query | `core/dependencies.py`, `utils/scoping.py` | Tenant isolation of leads |
| `Counter` + `next_seq()` atomic sequence | `repository/_impl.py:45` | Round-robin assignment cursor |
| `Notification` + Celery reminder sweep | `models.py`, `recruitment/tasks.py` | SLA breach alerts |
| Stage-timing aggregations | `dashboard/repository.py:503` | Time-to-action math conventions |

**Decisions already settled** (from the requirements conversation):

1. Telecaller is a **staff role in the data model** — real `Employee` record, `brand_id`,
   tenant-scoped — not an outsider grant like `client`/`referee`.
2. Sheet connection is **service account + Sheets API, polled** by a Celery beat job.
3. Assignment is **round-robin** on both legs (ingest → telecaller, accept → recruiter).
4. Telecaller reject **marks the candidate `REJECTED` and keeps it in the pool** (auditable).
5. "Recruiter actioned" = **the first pipeline mapping** for that candidate.
6. SLA alert = **in-app `Notification` per breach (deduped) + one daily email digest to admins**.
7. Scope = **backend + frontend in one PR**.

---

## 2. Source data

The sheet is a **Meta Lead Ads export**. Confirmed header row (21 columns):

```
id · created_time · ad_id · ad_name · adset_id · adset_name · campaign_id · campaign_name
form_id · form_name · is_organic · platform · highest_educational_qualification
what_role_are_you_interested_in? · experience_working_in_the_f&b_industry_(in_years)?_(...)
your_current_role? · your_current_location? · full_name · email · phone_number · lead_status
```

### 2.1 Column mapping

Headers are matched **normalized** — lowercased, non-alphanumerics collapsed to `_`, trimmed —
so Meta renaming `your_current_role?` to `your current role?` does not break ingest. The map
lives in one table in `utils/lead_sheet.py`:

| Sheet column | Target | Transform |
|---|---|---|
| `id` | `IntakeLead.external_id` | verbatim; **idempotency key** |
| `created_time` | `IntakeLead.external_created_at` | ISO-8601 parse, tz-aware, `None` on failure |
| `platform` | `Candidate.source_channel` | `ig`→`Instagram`, `fb`→`Facebook`, else title-cased raw |
| — | `Candidate.source` | constant `"external"` |
| `full_name` | `Candidate.full_name` | trimmed; **row skipped if blank** |
| `phone_number` | `Candidate.phone` | normalized (see 2.2); **row skipped if blank** |
| `email` | `Candidate.email` | lowercased; `None` if blank or not `x@y.z` |
| `your_current_location?` | `Candidate.city` | trimmed |
| `your_current_role?` | `Candidate.current_role` | trimmed |
| `experience_working_in_the_f&b_industry_...` | `Candidate.experience_years` | first number in the string (`"2-3 years"`→`2.0`, `"fresher"`→`0.0`) |
| `highest_educational_qualification` | `Candidate.education_level` + `.education` | fuzzy→`EducationLevel`; raw text always kept in `.education` |
| `what_role_are_you_interested_in?` | `Candidate.specialization` + `.department` | raw to `specialization`; matched against `ROLES_BY_CATEGORY` to infer `Department` |
| `is_organic` | `IntakeLead.is_organic` | `"true"/"yes"/"1"` → `True` |
| `ad_id`/`ad_name`/`adset_*`/`campaign_*`/`form_*` | `IntakeLead.attribution` | embedded sub-document, verbatim |
| `lead_status` | `IntakeLead.external_status` | verbatim, read-only |
| *(every column, verbatim)* | `IntakeLead.raw` | full row as `dict[str, str]` |

Unmapped/new columns land in `raw` and are never lost. An env override,
`INTAKE_SHEET_COLUMN_OVERRIDES` (JSON `{"sheet_header": "candidate_field"}`), lets you retarget a
column without a deploy.

### 2.2 Phone normalization

Indian numbers arrive as `+919876543210`, `919876543210`, `9876543210`, `98765 43210`. One pure
function, `utils/phone.py:normalize_phone()`, reduces them all to the **last 10 digits**; `None` when
fewer than 10 digits remain. `Candidate.phone` itself is stored exactly as received.

**No stored normalized field.** Each ingest run (poll or backfill) loads a projection of every live
candidate's `phone` and `email` for the brand, normalizes in Python, and builds an in-memory lookup.

A stored `Candidate.phone_normalized` was the first design and was dropped once the real data was in
view. The brand already holds **757 candidates** with no such field, so a stored field would need a
backfill before dedupe matched *any* of them. It would also have to be kept in sync at every write
path: `controller/candidates.py:537` (create), `:674` (bulk upload), `public_controller.py:201`
(public apply) and the update endpoint. Beanie's `@before_event` hooks can't carry that. `doc.set()`
sends only the fields it is given, which is why `referees.py:_stamp` adds `updated_at` by hand. Any
path that missed the sync would silently let duplicates through.

The in-memory lookup has none of those failure modes. It is always computed from the current
`phone`, whoever wrote it and however. The cost is one projected query per run: under 100 KB at
today's size, every 10 minutes. **Revisit past ~50k candidates**, where a stored field plus index
becomes worth its sync burden.

The lookup is also updated **as rows are ingested within the run**. Meta produces two lead IDs when
someone submits the same form twice. Without this, both rows would pass the dedupe check against
the pre-run snapshot and create two candidates.

### 2.3 Deduplication

Two layers, in order:

1. **`external_id`** — `(brand_id, external_id)` unique index on `IntakeLead`. Re-reading the same
   sheet row is a no-op. This makes the poll safely re-runnable and lets it read the whole range
   every time instead of tracking a cursor.
2. **Existing candidate**: if a live candidate in the brand matches on normalized phone, or on email
   when the lead has one (§2.2), the lead links to **that** candidate rather than creating a second one, and is
   filed `status = duplicate`. It is **not** assigned to a telecaller, and it surfaces in the admin
   dashboard's duplicate count.

A repeat lead for someone already in the pool is **never re-reviewed**, however old the original —
telecallers should not re-dial people the desk already knows. The duplicate count is reported per
campaign, which is the useful signal here: it tells you how much ad spend is re-reaching people you
already have.

---

## 3. Data model

### 3.1 New: `IntakeLead` (collection `intake_leads`)

One row per ingested lead: the workflow state, the timing record, and the campaign attribution.
Deliberately **a separate document, not fields bolted onto `Candidate`** — `Candidate` already
carries ~45 fields and this workflow applies to a subset of it. It mirrors how `Mapping`,
`ReferralRecord` and `CandidateEvent` are separate documents over the same candidate.

```python
class IntakeAttribution(BaseModel):          # embedded
    ad_id / ad_name / adset_id / adset_name: str | None
    campaign_id / campaign_name: str | None
    form_id / form_name: str | None

class IntakeLead(Document):
    brand_id: PydanticObjectId
    candidate_id: PydanticObjectId                    # FK → candidates._id
    source: IntakeSource = google_sheet
    source_channel: str | None                        # "Instagram" | "Facebook"
    external_id: str                                  # Meta lead id — idempotency key
    external_created_at: datetime | None
    external_status: str | None                       # sheet's own lead_status, read-only
    is_organic: bool | None
    attribution: IntakeAttribution
    raw: dict[str, str]                               # full sheet row, verbatim

    status: IntakeLeadStatus = pending_telecaller
    ingested_at: datetime

    # ── Telecaller leg ──
    telecaller_id: PydanticObjectId | None            # FK → employees._id
    telecaller_assigned_at: datetime | None
    telecaller_actioned_at: datetime | None
    telecaller_decision: IntakeDecision | None        # accept | reject
    telecaller_notes: str | None
    telecaller_response_seconds: int | None           # denormalized at action time
    telecaller_sla_breached_at: datetime | None       # set once; the alert dedupe key

    # ── Recruiter leg ──
    recruiter_id: PydanticObjectId | None
    recruiter_assigned_at: datetime | None
    recruiter_actioned_at: datetime | None            # stamped on first Mapping
    recruiter_action_mapping_id: PydanticObjectId | None
    recruiter_response_seconds: int | None
    recruiter_sla_breached_at: datetime | None

    reassignment_count: int = 0
    created_at / updated_at: datetime
```

`*_response_seconds` are **denormalized** rather than computed with `$subtract` at read time so the
analytics aggregations can `$avg`/`$percentile` a plain field and sort on it.

**Indexes**

```python
IndexModel([("brand_id", 1), ("external_id", 1)], unique=True)   # idempotency
IndexModel([("brand_id", 1), ("status", 1), ("telecaller_assigned_at", 1)])  # SLA sweep
IndexModel([("brand_id", 1), ("telecaller_id", 1), ("status", 1)])           # telecaller queue
IndexModel([("brand_id", 1), ("recruiter_id", 1), ("status", 1)])            # recruiter queue
IndexModel([("brand_id", 1), ("candidate_id", 1)])
IndexModel([("brand_id", 1), ("ingested_at", -1)])
```

No TTL — this is the permanent audit record, like `CandidateEvent`.

### 3.2 New: `IntakeSourceConfig` (collection `intake_source_configs`)

Sheet wiring, editable by an admin in the UI instead of requiring a redeploy to change a tab name or
range. **Credentials never live here**; they stay in env.

**One brand for now.** Production has a single brand (Binge Consulting), so there is exactly one
config row, attached to the sole `Brand` the same way `ensure_employee_for_user` resolves it: fetch
two, act only when there is exactly one. The admin UI has **no brand picker**. The row still carries
`brand_id` under a unique index, and every lead is still stamped and queried by it. That keeps a
future second brand a matter of inserting another config row, not a data migration. The brand `_id`
is never hardcoded.

```python
class IntakeSourceConfig(Document):
    brand_id: PydanticObjectId                # unique
    spreadsheet_id: str
    sheet_range: str = "Sheet1!A:U"
    enabled: bool = False
    default_source_channel: str = "Instagram"
    activated_at: datetime | None             # stamped when enabled first flips true;
                                              # the live poll ignores leads older than this
    last_synced_at / last_success_at: datetime | None
    last_row_count / last_ingested_count / last_skipped_count: int
    last_error: str | None                    # surfaced in the admin UI
    consecutive_failures: int = 0
```

### 3.3 New enums (`recruitment/enums/`)

```python
class IntakeLeadStatus(StrEnum):
    pending_telecaller = "pending_telecaller"   # assigned, awaiting decision
    unassigned        = "unassigned"            # ingested, no active telecaller to take it
    rejected          = "rejected"              # telecaller rejected — terminal
    pending_recruiter = "pending_recruiter"     # accepted, awaiting first mapping
    actioned          = "actioned"              # recruiter mapped them — terminal
    duplicate         = "duplicate"             # matched an existing candidate — terminal

class IntakeDecision(StrEnum):
    accept = "accept"
    reject = "reject"

class IntakeSource(StrEnum):
    google_sheet = "google_sheet"

class IntakeRejectReason(StrEnum):     # optional on reject; drives the admin breakdown
    wrong_number / not_reachable / not_interested / not_eligible / duplicate / other
```

`unassigned` is not an edge case to ignore: leads arriving when no telecaller is active must still
be ingested and must be visible to an admin, not silently dropped.

### 3.4 Changes to existing models

| Model | Change | Why |
|---|---|---|
| `auth.UserRole` | `+ telecaller = "telecaller"` | the new role |
| `Candidate` | `+ assigned_recruiter_id: ObjectId \| None` | recruiter ownership of a lead (no phone field; see §2.2) |
| `Notification` | `+ employee_id: ObjectId \| None`, `+ intake_lead_id: ObjectId \| None` | target a single admin, link to the lead |
| `NotificationKind` | `+ telecaller_sla_breach`, `+ recruiter_sla_breach` | the two new alerts |

`assigned_recruiter_id` is **separate from `created_by_id`**, not a reuse of it: `created_by_id`
means "who sourced this person" and gates CV visibility (`utils/cv_access.py`). A lead was sourced
by an ad, not a recruiter — leaving it `None` keeps the CV shared, which is correct. Overloading it
would silently lock the lead's CV to one recruiter.

`Notification.employee_id` requires a matching change in `notifications_router._scope_match`: staff
currently match `{"client_id": None}`, which must become "client_id is None **and** (employee_id is
None or employee_id == me)". The existing `_id` injection in `mark_notification_read` must survive
that rewrite — the docstring there already warns about it.

Both new documents go into `core/database.py`'s `document_models` **and** `tests/conftest.py`'s
fixture list, or they fail at query time with `CollectionWasNotInitialized`.

---

## 4. The Telecaller role and access control

### 4.1 Route access is deny-by-default

A telecaller gets an `Employee` record and a `brand_id` — but **`get_tenant` will reject the
telecaller role, exactly as it rejects `client`.**

This is the one place I am reading past the literal "staff role in the hierarchy" answer, and it is
deliberate. `get_tenant` is the guard on nearly every staff endpoint. If it admitted telecallers,
the new role would immediately have read/write access to the full candidate directory, every
position, the pipeline board and the client list — because those endpoints were written when every
`get_tenant` caller was a recruiter. The codebase's documented containment strategy is *"forgetting
a guard locks a client out; it never leaks"*, and telecallers should inherit it.

So: **staff in the data model, deny-by-default at the route layer.** New dependency:

```python
def get_telecaller_tenant(...)   # telecaller | maintainer | admin → TenantScope
```

Added in step 5 alongside the lead-queue endpoints that use it, not in step 1, so no commit
carries an unused guard. Step 1 did add `_staff_scope()`, the brand check extracted out of
`get_tenant`, so this and `get_inbox_viewer` share a single copy of it.

Telecaller-reachable surface, and nothing else:

- `GET /api/v1/auth/me`
- `GET /api/v1/intake/leads/mine` — their own queue
- `POST /api/v1/intake/leads/{id}/accept` · `/reject`
- `GET /api/v1/notifications` · `POST /{id}/read`
- `GET|PATCH /api/v1/settings` (own profile)

`TenantScope` gains `is_telecaller`. `is_recruiter` already returns `True` only for `employee`, so
telecallers are automatically excluded from leaderboard credit and the activity feed with no change.

**`get_viewer` needs the same care.** It delegates to `get_tenant` for every non-client role, so
once `get_tenant` refuses telecallers, every `get_viewer` endpoint refuses them too. That is correct
for six of its seven users: `pipeline`, `positions`, `clients`, `tasks`, `client_messaging` and the
`dashboard` controller. The exception is **`notifications_router`**. It is on the telecaller surface
above, and it would 403 them. It switches to a dependency that admits telecallers explicitly, and
`_scope_match` gains a telecaller branch: their own `employee_id`-targeted rows only, never the
brand-wide staff rows. `test_telecaller_access.py` asserts both halves: a 200 on notifications and
403s on the other six.

### 4.2 `deny_clients` → `deny_outsiders`

`deny_clients` guarded routes that authenticate but never resolve a tenant, where `get_tenant`'s
refusal cannot run. Rather than a function named `deny_clients` that quietly also denies
telecallers, it is **renamed `deny_outsiders`** and denies `{client, referee, telecaller}`. It
guards three routes:

| Route | Why |
|---|---|
| leaderboard router (`core/main.py`) | recruiters' names and scores |
| `GET /api/v1/storage/sign` | a write credential for the agency's Cloudinary account |
| `POST /api/v1/brands` | **found by the step-1 sweep.** See below |

`POST /api/v1/brands` is onboarding and runs before any brand exists. Its only guard was "agency
email address", which a telecaller on `@binge.consulting` passes, so a telecaller could have created
a second brand. Per that handler's docstring, a second brand breaks the public application form. It
also stops `ensure_employee_for_user` auto-assigning a brand to new signups, because that only acts
when exactly one brand exists.

> ⚠️ **Pre-existing, not fixed here:** any *recruiter* on the agency domain can still create a
> second brand the same way. Closing that means changing the onboarding flow (e.g. refusing anyone
> whose `Employee` already has a brand), which is outside this feature's scope.

Referees were not denied by `deny_clients`. Nothing in the referee portal calls any of these three
routes, so refusing them closes a gap that `storage/uploads.py`'s docstring already assumed was
closed.

### 4.2a Not a recruiter: `NON_RECRUITER_ROLES`

Every recruiter roster in the codebase excluded `role $nin ["admin", "maintainer"]`, a deny-list, so
any new role counted as a recruiter by default. A telecaller would have appeared on the leaderboard,
in task progress, in the dashboard employee table and in recruiter pickers. The six copies are now
one tuple, `auth/models.py: NON_RECRUITER_ROLES`. It stays a `$nin` rather than
`role == "employee"` because `Employee` rows that predate the role field have none, and an equality
match would silently drop those recruiters.

### 4.3 Provisioning

**No new API endpoint.** Role assignment in this codebase is deliberately manual, with no
self-serve UI (`scripts/migrate_user_roles.py` docstring), and a role-escalation endpoint is attack
surface this feature does not need. Telecallers follow the same path maintainers and admins do:

```bash
python -m scripts.migrate_user_roles promote --email caller@binge.consulting --role telecaller
```

That needs one change: `"telecaller"` added to the script's hardcoded `_VALID_ROLES`. Everything
downstream already works. On the next login, `ensure_employee_for_user` copies `User.role` onto
`Employee.role` and attaches the sole brand for an agency-domain address. `_post_login_path` gains a
telecaller branch that redirects to `/leads`.

> ⚠️ **Exposure window (open, §12).** A new staff signup lands as a full `employee` and stays one
> until someone runs `promote`. For a recruiter that is harmless. For a telecaller it means full
> candidate, client and pipeline access in between. This is not new; every agency-domain signup
> works this way today. It matters more if telecallers are contract callers than if they are
> in-house staff.

---

## 5. Ingest pipeline

```
Google Sheet (Meta lead ads)
        │  Sheets API v4, service account, read-only scope
        ▼
[celery beat] intake.poll_google_sheet          every INTAKE_POLL_MINUTES (default 10)
        │
        ├── read whole range → normalize headers → parse rows
        ├── skip rows with created_time < config.activated_at   (history → §5.4 script)
        ├── skip rows with no full_name or no phone
        ├── skip external_ids already ingested          (unique index = idempotent)
        ├── match existing candidate by phone/email     → status=duplicate, link, stop
        ├── create Candidate(status=PENDING, source=external, source_channel=Instagram)
        ├── create IntakeLead(status=pending_telecaller)
        ├── round-robin assign a telecaller             (or status=unassigned)
        └── record CandidateEvent(applied)
```

The live poll deliberately handles **only leads created after the integration was switched on**
(`IntakeSourceConfig.activated_at`, stamped when `enabled` first flips true). Everything already
sitting in the sheet is the backfill script's job — see §5.4. Without that cutoff, switching the
feature on would round-robin the sheet's entire history into telecaller queues in one tick and start
a 24-hour SLA clock on every one of them.

### 5.1 Sheets client

`utils/google_sheets.py` — a thin async wrapper: `google-auth` mints a service-account JWT and
exchanges it for an access token; `httpx` (already a dependency) calls
`GET /v4/spreadsheets/{id}/values/{range}`. Scope `spreadsheets.readonly`.

> `gspread` was considered and rejected: it is synchronous and would block the event loop or force
> `run_in_executor`, for one HTTP GET. New dependency is **`google-auth` only**, added to both
> `pyproject.toml` and `requirements.txt` (kept in sync for Docker).

New settings in `core/config.py` / `.env.example`:

```bash
GOOGLE_SHEETS_ENABLED=false
GOOGLE_SERVICE_ACCOUNT_JSON=          # raw or base64 service-account JSON
INTAKE_SPREADSHEET_ID=1JMg0WtubG9lWeKSoWHsF7M2zOJfsgIWdBQYvOb0X0yM
INTAKE_SHEET_RANGE=Sheet1!A:U
INTAKE_POLL_MINUTES=10
INTAKE_SHEET_COLUMN_OVERRIDES=        # optional JSON remap
TELECALLER_SLA_HOURS=24
RECRUITER_SLA_HOURS=24
```

**Setup you must do:** create a GCP service account, enable the Google Sheets API, download its JSON
key into `GOOGLE_SERVICE_ACCOUNT_JSON`, and **share the spreadsheet with the service account's
email address as Viewer**. Without that share the API returns 403 and ingest stays empty.

### 5.2 Failure behaviour

A failed poll increments `consecutive_failures` and writes `last_error` (surfaced in the admin UI).
It never partially commits: each row is independent, so a malformed row is skipped and counted, not
fatal. After 3 consecutive failures an in-app notification goes to admins. Because ingest is
idempotent, a failed run is simply retried by the next tick.

### 5.3 Round-robin

```python
seq = await next_seq(brand_id, "intake_telecaller_rr")   # atomic $inc, existing primitive
roster = active telecallers for brand, sorted by _id     # stable order
assignee = roster[seq % len(roster)] if roster else None
```

Same for recruiters with key `intake_recruiter_rr`. Atomic under concurrency, no locks, and gaps are
harmless. If the roster is empty → `status = unassigned`, surfaced to admins.

### 5.4 Historical backfill — `scripts/backfill_intake_leads.py`

A separate, explicit, operator-run script rather than anything automatic. It follows the conventions
of the existing `scripts/backfill_*.py` family: **dry run by default, `--confirm` to write, safe to
re-run** (the `external_id` unique index makes a second run a no-op on rows it already imported).

**Report mode (the default) writes nothing** and prints what you need in order to decide. The
candidate count below is real, from `inspect_brands.py` on 2026-09-17. **Every sheet figure is
illustrative**, because the sheet has not been read yet:

```
$ python3 scripts/backfill_intake_leads.py

Brand: Binge Consulting (6a25b766…)
  candidates in system            757
    with a usable phone          ~???   ← dedupe coverage: only these can be matched
  sheet rows read                 ???
    unusable (no name/phone)      ???
    already ingested                0
    duplicate within the sheet    ???   ← same person, two Meta lead ids
    match an existing candidate   ???   ← would link, not create
    genuinely new                 ???
  date range in sheet       ???? … ????

Nothing written. Re-run with --confirm to import.
```

That report is the answer to "how many candidates are already in the system, and how much of this
sheet do we already have" — and it is obtainable before a single row is imported.

**Flags:**

| Flag | Effect |
|---|---|
| *(none)* | report only, no writes |
| `--confirm` | actually import |
| `--since YYYY-MM-DD` | only rows with `created_time` on or after this date |
| `--assign` | round-robin the imported leads to telecallers (starts their SLA clocks) |
| `--unassigned` | import as `status=unassigned` — **default**; visible to admins, in analytics, nobody's queue |
| `--limit N` | import at most N rows, for a cautious first pass |

Default is `--unassigned` because importing history with `--assign` immediately breaches the SLA on
every row older than a day and buries the admin dashboard in alerts. Import first, look at what
landed, then bulk-assign from the admin UI if the backlog is worth working.

> The repo-root `.env` points `MONGODB_URI` at the live Atlas cluster, and `assert_local_database()`
> refuses a non-local host. Running this against production needs `SEED_ALLOW_REMOTE_DB=1`,
> deliberately. The script also takes a read-only path through `inspect_brands.py`-style counting in
> report mode, so the report itself is safe to run against production without the override.

`scripts/inspect_brands.py` already exists and answers the candidate-count half of this today,
read-only, with no new code:

```bash
cd apps/backend && python3 scripts/inspect_brands.py
```

---

## 6. Workflow

### 6.1 Telecaller accepts

`POST /api/v1/intake/leads/{id}/accept` (body: optional `notes`)

1. 409 unless `status == pending_telecaller` and `telecaller_id == me` (admins may act on any).
2. Stamp `telecaller_actioned_at`, `telecaller_decision=accept`,
   `telecaller_response_seconds = actioned_at − assigned_at`.
3. `Candidate.status → APPROVED` (it now enters the recruiter directory, which already filters to
   `APPROVED` by default — so pending and rejected leads never pollute it).
4. Round-robin a recruiter → `recruiter_id`, `recruiter_assigned_at`, `Candidate.assigned_recruiter_id`.
5. `status → pending_recruiter` (or `unassigned` if no recruiter roster).
6. `CandidateEvent(approved)` + `ActivityLog`.

### 6.2 Telecaller rejects

`POST /api/v1/intake/leads/{id}/reject` (body: optional `reason: IntakeRejectReason`, `notes`)

Same stamping, then `Candidate.status → REJECTED`, `status → rejected`, `CandidateEvent(declined)`.
The candidate row **stays live and searchable** (`is_active` untouched) so rejections remain
reportable; the directory hides it because it filters to `APPROVED`.

### 6.3 Recruiter actions

The clock stops at the **first `Mapping`** for that candidate. Hooked in
`service/_impl.py:map_candidate`, immediately after `_open_referral_record` and following the same
rule as gamification and the referral ledger:

```python
await _close_intake_lead(mapping)   # fire-and-forget
```

> "Fire-and-forget" is the module's established contract: *a duplicate award or Redis failure must
> never roll back the domain write that triggered it.* A metrics stamp is no different — if the
> stamp fails, the mapping still stands.

It stamps `recruiter_actioned_at`, `recruiter_response_seconds`, `recruiter_action_mapping_id`, and
`status → actioned`, only when a `pending_recruiter` lead exists for that candidate.

### 6.4 Admin reassignment

`POST /api/v1/intake/leads/{id}/reassign` (admin/maintainer) — move a lead to a different telecaller
or recruiter, e.g. when someone is away. **Resets the relevant `*_assigned_at`** (the SLA clock
restarts for the new owner — a fresh assignee should not inherit someone else's overdue clock),
clears `*_sla_breached_at`, and increments `reassignment_count` so a lead cannot be passed around to
dodge the SLA unnoticed.

---

## 7. Observability

### 7.1 Metrics

**Funnel** (counts by status, over a date range): ingested → assigned → accepted/rejected →
recruiter-assigned → actioned, plus duplicates and unassigned.

**Telecaller leg** — overall and per telecaller:
- avg / **median** / p90 time-to-action (hours)
- pending count, and of those how many are **overdue** (> `TELECALLER_SLA_HOURS`)
- accepted / rejected counts and accept-rate
- oldest pending lead's age
- SLA compliance % = actioned-within-SLA ÷ actioned

> Median and p90 are reported alongside the mean because one lead left over a weekend drags an
> average far enough to hide a team that is otherwise fine.

**Recruiter leg** — the same shape, keyed on the recruiter leg's timestamps.

**Campaign breakdown** — leads, accept-rate and actioned-rate grouped by `campaign_name` /
`ad_name` / `source_channel`. Effectively free (the attribution is already stored) and it answers
"which ad spend produces candidates that actually convert".

### 7.2 Endpoints (admin/maintainer)

```
GET /api/v1/intake/analytics/overview     funnel + headline SLA numbers
GET /api/v1/intake/analytics/telecallers  per-telecaller table
GET /api/v1/intake/analytics/recruiters   per-recruiter table
GET /api/v1/intake/analytics/campaigns    attribution breakdown
GET /api/v1/intake/leads                  paginated, filter by status/telecaller/recruiter/
                                          overdue/date-range/campaign
GET /api/v1/intake/leads/{id}             one lead + its full timing trail
GET /api/v1/intake/config                 sheet config + last sync status
PUT /api/v1/intake/config                 update config (admin)
POST /api/v1/intake/sync                  "Sync now" — enqueue an immediate poll (admin)
```

All are Mongo aggregations following `dashboard/repository.py` conventions (`$match` on `brand_id`
first, `$facet` for multi-metric single round-trips). Cached through the existing
`dashboard_cache` Redis helper with a 5-minute TTL, invalidated on any lead write.

---

## 8. SLA alerting

### 8.1 Hourly breach sweep — `intake.sla_sweep`, `crontab(minute=15)`

Hourly, not daily: a daily job could let a breach sit for up to 24 extra hours before anyone hears
about it, which defeats a 24-hour SLA.

```
for each lead where status == pending_telecaller
                and telecaller_assigned_at < now − TELECALLER_SLA_HOURS
                and telecaller_sla_breached_at is None:
    → one Notification(kind=telecaller_sla_breach, employee_id=<each admin>) per admin
    → stamp telecaller_sla_breached_at = now        # fires exactly once per lead
```

The same sweep covers `pending_recruiter` against `RECRUITER_SLA_HOURS` with
`recruiter_sla_breach` — **confirmed in scope**, so an admin is alerted when a recruiter sits on an
accepted candidate past 24h just as they are for a telecaller.

**The clock runs on 24 calendar hours**, nights and weekends included: a lead assigned 6pm Friday
breaches Saturday evening and alerts then. No working-calendar config, no holiday table. If the
weekend noise turns out to be a problem in practice, the cheapest fix later is to hold *delivery* of
breach notifications until the next working morning while leaving the measured times untouched —
that keeps the analytics honest, which a paused clock would not.

The `*_sla_breached_at` stamp is the dedupe key — the same guarantee `Mapping.reminders_sent` gives
the existing reminder job. A lead stuck for a week raises one notification, not 168.

### 8.2 Daily digest — `intake.sla_digest`, `crontab(minute=0, hour=3)`

One email per admin listing every currently-overdue lead, grouped by telecaller, with ages and a
deep link to `/leads?overdue=true`. New `EmailService.send_intake_sla_digest`, following the
existing HTML-escaping and never-raise conventions in that class. **No email is sent when nothing
is overdue** — a daily "all clear" trains people to ignore the alert.

---

## 9. Frontend

### 9.1 Routes

| Route | Who | Contents |
|---|---|---|
| `/leads` | telecaller | Their queue only. Card list: name, phone (click-to-call `tel:`), city, current role, experience, role interest, time remaining on SLA. Accept / Reject buttons, reject-reason picker, notes. |
| `/leads` | admin/maintainer | All leads + filters (status, telecaller, recruiter, overdue, campaign, date range). Reassign action. |
| `/leads/analytics` | admin/maintainer | The observability dashboard (§7.1). |

### 9.2 Wiring

- **Sidebar**: a `TELECALLER_NAV_CONFIG` array in `nav-config.ts`, mirroring the existing
  `REFEREE_NAV_CONFIG` pattern rather than adding two more booleans to `NavItemConfig` (which
  already carries three). Staff nav gains a `Leads` item, maintainer-gated.
- **RouteGuard**: a telecaller branch — anything outside `/leads` and `/settings` redirects to
  `/leads`, mirroring the existing referee branch.
- **`useCurrentUser`**: `+ isTelecaller`.
- **`types/index.ts`**: `UserRole` union gains `"telecaller"`.
- Charts follow the repo's existing dashboard component structure (`atoms`/`molecules`/`organisms`)
  and the project's `dataviz` conventions.

---

## 10. Testing

New `tests/test_intake/`, following the existing per-area layout:

| File | Covers |
|---|---|
| `test_sheet_mapping.py` | header normalization, the `f&b (in years)` column, `"2-3 years"`/`"fresher"` parsing, blank-name/blank-phone skips, phone normalization |
| `test_ingest_idempotency.py` | same `external_id` twice ⇒ one lead, one candidate; an existing candidate stored as `+91 98765 43210` matches a lead's `9876543210`; two lead ids for one phone *in the same run* ⇒ one candidate; rows older than `activated_at` are skipped by the poll |
| `test_backfill_script.py` | report mode writes nothing; `--confirm` imports; re-running imports nothing new; `--unassigned` default leaves SLA clocks unstarted |
| `test_round_robin.py` | even distribution; empty roster ⇒ `unassigned`, not a crash; concurrent assignment does not collide |
| `test_telecaller_decisions.py` | accept ⇒ candidate APPROVED + recruiter assigned + timings; reject ⇒ REJECTED, still `is_active`, no recruiter; wrong-telecaller and wrong-status ⇒ 409/403 |
| `test_recruiter_action_stamp.py` | first mapping stamps `actioned`; a second mapping does not re-stamp; a failing stamp does not roll back the mapping |
| `test_sla_sweep.py` | breach fires exactly once per lead; re-running the sweep adds nothing; reassignment resets the clock |
| `test_telecaller_access.py` | **containment** — a telecaller is 403'd on candidates, positions, pipeline, clients, leaderboard, activity. Mirrors `test_pipeline/test_referee_portal_is_read_only.py` |
| `test_intake_analytics.py` | funnel counts, median/p90 math, per-person grouping, brand isolation |

Plus `pnpm --filter frontend lint`, `uv run ruff check .`, `ruff format`.

Tests need a local Mongo — `MONGODB_URI="mongodb://localhost:27017/recruitr" uv run pytest`. The
autouse fixture drops its database on teardown and `assert_local_database()` refuses a non-local
host, so the command-line override is mandatory.

---

## 11. Build order

1. **Role + access** — `UserRole.telecaller`, `get_tenant` refusal, `deny_outsiders` (3 routes),
   `NON_RECRUITER_ROLES`, `get_inbox_viewer` + `Notification.employee_id`, `TenantScope.is_telecaller`,
   promote support, login redirects, frontend guard/nav + `/leads` landing page.
   *Ship with `test_telecaller_access.py` green before anything else touches data.*
2. **Models + enums** — `IntakeLead`, `IntakeSourceConfig`, enums, `Candidate`/`Notification`
   changes, registration in `database.py` + `conftest.py`.
3. **Sheet client + mapping** — `google_sheets.py`, `lead_sheet.py`, unit tests (no network).
4. **Ingest service + poll task** — round-robin, dedupe, `activated_at` cutoff, Celery beat entry, `POST /intake/sync`. Plus `scripts/backfill_intake_leads.py` (report mode first).
5. **Workflow endpoints** — accept / reject / reassign, `map_candidate` hook.
6. **Analytics** — aggregations + endpoints + cache invalidation.
7. **SLA sweep + digest** — Celery tasks, `Notification` targeting, email template.
8. **Frontend** — telecaller queue → admin lead list → analytics dashboard → nav/guard wiring.
9. **Docs** — update `apps/backend/CLAUDE.md` (role table, new module) and `.env.example`.

Steps 1–2 are a safe first commit; 3–5 are the functional core; 6–8 are additive.

---

## 12. Decisions log

Settled in review — recorded here so the reasoning is not lost:

| Question | Decision |
|---|---|
| Telecaller role shape | Staff in the data model (`Employee` + `brand_id`), **deny-by-default at the route layer** (§4.1) |
| Sheet connection | Service account + Sheets API, polled every 10 min |
| Assignment | Round-robin on both legs, via the atomic `Counter` primitive |
| Telecaller reject | `Candidate.status = REJECTED`, row stays live and reportable |
| "Recruiter actioned" | The first `Mapping` for that candidate |
| SLA alerting | In-app `Notification` per breach (deduped) + one daily email digest to admins |
| SLA clock | **24 calendar hours**, nights and weekends included (§8.1) |
| Duplicates | Link to the existing candidate, file as `duplicate`, **never re-review** (§2.3) |
| Recruiter SLA alerts | **In scope** — same sweep, same dashboard (§8.1) |
| Sheet write-back | **Out of scope.** The service account stays read-only, so no code path can modify your spreadsheet |
| Historical backfill | **Not automatic.** Live poll handles new leads only; history goes through `scripts/backfill_intake_leads.py`, dry-run by default (§5.4) |
| Brand | **One brand for now** (Binge Consulting). No brand picker, but `brand_id` scoping kept everywhere so a second brand stays cheap (§3.2) |
| Phone dedupe | **In-memory lookup per run**, not a stored field. Matches all 757 existing candidates with no backfill or write-path sync (§2.2) |
| Provisioning | **Existing `migrate_user_roles.py promote`**, no new API endpoint (§4.3) |
| Telecaller email domain | **In-house, `@binge.consulting`.** Promote-based provisioning stands. The §4.3 exposure window is accepted: it is the same one every recruiter signup already has |
| Build scope | Backend + frontend, one PR |

Nothing is open.
