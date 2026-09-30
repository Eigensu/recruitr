# Phase A — Binge Connect follow-ups (30 Sep 2026 call)

**Status:** Planned, nothing built · **Source:** the 30 Sep 2026 Binge Connect call, narrowed to
eight items by Aagam, with every decision answered in the planning conversation (§2).

**Depends on unmerged work.** The review step (`pending_review`, team assignment) lives in PR #94
(`feat/intake-review-teams`), and PRs #95/#96 touch the same leads screens. Every lead-related PR
below (A5–A7) must branch from `main` *after* those merge, or be stacked on them.

---

## 1. The eight items and what already exists

| # | Item | What the code has today | Real work |
|---|---|---|---|
| 1 | Establishment tag on the client form; communication + brand-experience tags on the position form | Client create **and** edit already have `establishment_tag` (`clients/page.tsx:308`, `clients/[id]/page.tsx:311`). `Position` has neither tag. Candidates have both, as `Basic/Good/Excellent` and `Low/Mid/Premium` (`lib/constants/candidate.ts:53,63`) | Position only |
| 2 | Ingest `Captains Data Naukri.xlsx` as leads | Sheet ingest pipeline: `ParsedLead` → `plan_ingest` → `ingest_leads` (`service/intake_service.py:327,646`) with duplicate detection and telecaller round-robin | A second parser + an upload screen |
| 3 | Current and expected salary on all external forms | One form component, `components/public/ApplicationForm`, serves `/form`, `/form/[brand]` and the referee refer page. It has no salary fields; `public_apply` takes none | Two fields, both ends |
| 4 | Recruiters see only their own dashboard data; line graph replaced by an actions panel | `employee_id` is a free query param on every `/dashboard/*` route (`dashboard/controller.py:46`), so a recruiter can read company-wide numbers. Position KPIs ignore `employee_id` altogether (`dashboard/repository.py:190`) | Enforce scope server-side; new panel |
| 5 | Joined cards: offer-letter button beside the reject button; click → joining date + full history | Joined cards already carry a staff-only **"Mark as Rejected"** (`kanban/CandidateCard.tsx:218`). Staff may already upload an offer letter and set a joining date at any stage (`pipeline.py:690,752`). `CandidateDrawer` already renders `/candidates/{id}/history` | Frontend only |
| 6 | Archive joined candidates 100 days after joining | The board shows every `joined` mapping forever (`KANBAN_STAGES`) | New field + board filter + Archived tab |
| 7 | "New lead" box: upload resumes, auto-parse, submit as leads | Bulk resume upload + parser exist (`candidates.py:590`, `service/resume_service.py`), capped at 50 files with **no per-file size limit**. The parser extracts email, phone, experience, company, skills — **not** name, city, role or salary. Recruiters have no leads page | Parser extension, two endpoints, a dialog |
| 8 | Checklist start and end date; only activity inside the range counts | Backend already counts `start_date ≤ activity ≤ due_date` (`controller/tasks.py:60-70`). The form has **no start-date input**: start is silently "today 00:00" at creation (`ChecklistSettingsTab.tsx:364`) | Start-date picker + validation |

---

## 2. Decisions (settled — do not re-open without Aagam)

| Topic | Decision |
|---|---|
| Naukri import destination | **Telecaller queue** — same round-robin, review step and SLA clocks as Meta sheet leads |
| Naukri import mechanism | **Upload screen**, reusable for every future Naukri export (not a one-off script) |
| Who can import | **Everyone** on staff (recruiters, maintainers, admins); **not telecallers** |
| Salary unit | **₹/month** for candidate **current** (`salary`) and **expected** (`expected_salary`) salary, for everything entered from now on |
| Existing salary data | **Not touched.** No migration, no division of prod values. Only the Naukri import converts (its yearly figures → monthly at parse time) |
| Position salary, `salary_offered` | **Unchanged** |
| Salary filter | **Actual numbers** (min / max ₹ per month), not bands |
| Recruiter-added leads (manual or resume) | **Telecaller queue**, full telecaller → review → team flow |
| Duplicates (Excel or resume) | **Marked `duplicate`**, linked to the existing candidate, not queued — same as sheet leads |
| Resume upload | **Several at once**: each file becomes an editable draft; recruiter submits them together |
| Resume batch limit | **20 files per upload, 5 MB per file** — and the existing bulk resume upload moves to the same limits (from 50 files, no size cap) |
| Recruiter dashboard | Scope everything to the recruiter; **remove** line graph, client-profiles table, sourcing table and the per-recruiter split in the pipeline pie |
| Recruiter's "own data" | **Everything they are part of** — defined precisely in A7 |
| Actions panel | Add lead · Add position · Add candidate · Go to pipeline · Check leaderboard |
| Joined card | Two buttons: **"Rejected"** (renamed from "Mark as Rejected") and **Offer letter** |
| Card history | **Everything on the candidate** (all positions, lead/intake steps) |
| Archive clock | **100 days from when the card was moved to Joined** (not the joining date) |
| Archive location | An **"Archived" tab on the staff pipeline page**; nothing is deleted |
| Archive and clients | **Clients are not affected** — the client pipeline keeps every joined card, so their Joined count never drops |
| Position tags | **Single value each**, read as the **minimum** required |
| External-form salary | **Current salary required**, expected salary optional |
| Checklist start date | **Today or later** (no back-dating) |

**Why 20 × 5 MB.** Both upload paths handle files one after another inside a single request, and
each file costs text extraction plus a Cloudinary upload (~1–3 s). 20 files is under a minute;
50 can run several minutes and risks a proxy timeout mid-batch. 20 drafts is also about as many as
one person will realistically review on one screen. The browser posts straight to the backend
(`NEXT_PUBLIC_API_URL`), so Vercel's 4.5 MB body limit does not apply, but with no per-file cap a
single scanned PDF can be tens of MB; 5 MB comfortably fits any text resume.

---

## 3. PR breakdown

```
            main (+ #94, #95, #96 merged)
   ┌───────────┬───────────┼───────────────┐
  A1          A2          A3              A8
 checklist   position   monthly salary   joined card
 dates       tags       labels + filter    │
                ┌──────────┴──────┐       A9
               A4                A5      archive
            ext. form        Naukri import
             salary       (+ Leads page for recruiters)
                                  │
                                 A6  add lead + resumes (20 × 5 MB, bulk upload too)
                                  │
                                 A7  recruiter dashboard + actions
```

| PR | Title | Items | Size | Needs |
|---|---|---|---|---|
| A1 | Let a checklist start on a chosen date | 8 | S | — |
| A2 | Add communication and brand-experience minimums to positions | 1 | S | — |
| A3 | Show candidate salaries per month, and filter by real amounts | 3 (foundation) | S | — |
| A4 | Ask for current and expected salary on the external forms | 3 | S | A3 |
| A5 | Import Naukri exports as leads, from a Leads page everyone can open | 2 | L | A3, #94 |
| A6 | Let recruiters add leads, from a form or a stack of resumes | 7 | L | A5 |
| A7 | Give recruiters their own dashboard, and an actions panel | 4 | M | A6 (for "Add lead") |
| A8 | Offer letter and Rejected on joined cards, and their history | 5 | S–M | — |
| A9 | Archive joined candidates after 100 days | 6 | M | A8 (same files) |

A1, A2, A3 and A8 can be worked in parallel. A7 can ship before A6 if "Add lead" is hidden until
A6 lands.

---

## 4. PR details

### A1 — Checklist start date (item 8) · S

**Backend** (`schemas/tasks.py`, `controller/tasks.py`)
- `TaskCreate`: reject `start_date` earlier than today. **Timezone trap:** the browser sends local
  midnight, which for IST is `18:30Z` the *previous* UTC day, so "≥ today UTC midnight" would
  refuse every valid IST request. Validate against `now − 24h`, or send a `YYYY-MM-DD` date and
  validate in the brand's zone (Asia/Kolkata) — pick one and test both sides of midnight.
- `TaskUpdatePayload`: allow changing `start_date` only while the task has not started yet
  (`task.start_date > now`); the same "today or later" rule applies. Keep `due_date ≥ start_date`.
- Counting is already range-bounded (`tasks.py:60-70`); no change.

**Frontend** (`components/settings/ChecklistSettingsTab.tsx`)
- Add a **Start date** input next to Due date: `min = today`; default today.
- On edit of a task that has already started, show the start date read-only.
- Due date `min` = chosen start date. Start sent as local 00:00, due as local 23:59:59.999 (as today).
- Show "Start – Due" on the task row (`:217` shows only Due).

**Tests:** create with start today / tomorrow / yesterday (422); IST-midnight boundary; edit of a
started task cannot move its start; activity before start and after due is not counted.

---

### A2 — Position communication & brand-experience minimums (item 1) · S

**Backend**
- `Position` (`models.py:232`): `communication: str | None`, `brand_experience: str | None`.
- `schemas/position.py` create / update / list item: same fields, validated as
  `Literal["Basic","Good","Excellent"]` and `Literal["Low","Mid","Premium"]` (the candidate values).
- No migration: absent = "no minimum".

**Frontend**
- `AddPositionModal.tsx` (create + edit): two selects labelled **"Minimum communication"** and
  **"Minimum brand experience"**, reusing `COMMUNICATION_OPTIONS` / `BRAND_EXPERIENCE_OPTIONS`.
- Position detail page: show both.
- Client form: **no change** — establishment tag is already on create and edit. Pranay tags the
  existing clients (his action item).

**Not in scope:** using these in matching (Phase B weighted matching).

**Tests:** create/update round-trip; invalid value → 422; list returns the fields.

---

### A3 — Monthly salary labels and a real-number filter · S

Foundation for A4–A6, which all write salaries. **No data migration; prod salary values are not
modified.**

**Backend**
- `Candidate.salary_period: Literal["monthly"] | None = None`. Every API path that writes
  `salary` or `expected_salary` (candidate create/update, telecaller accept, public apply, lead
  import, resume leads) sets it to `"monthly"`. Existing documents keep it absent.
  - Default is `None`, **not** `"monthly"`: a Beanie default would be written back the next time
    any old candidate is saved for an unrelated reason, silently stamping a yearly figure as
    monthly. Absent must keep meaning "entered before the switch, unit unknown", so a later
    migration — if one is ever wanted — can find exactly those rows.
- Candidate list filter (`controller/candidates.py:368,459-472`): replace the
  `lt3 / 3to5 / 5to8 / 8to12 / gt12` bands with `salary_min: float | None` and
  `salary_max: float | None` (₹/month, inclusive, `ge=0`), applied to current salary (`salary`)
  through the existing `$convert` expression. Either bound may be given alone; `min > max` → 422.
- Schema field descriptions say "per month".

**Frontend**
- Labels "Current salary (₹/month)" / "Expected salary (₹/month)" in `AddCandidateForm`,
  `AddCandidateModal`, `CandidateDrawer`, both `CandidateCard`s, `AcceptLeadDialog`.
- `CandidateFilterBar`: the salary band dropdown becomes two number inputs, **Min ₹/month** and
  **Max ₹/month**.
- `AddPositionModal` and `ClientActionModal` (position salary / salary offered): untouched.

**Known consequence (accepted):** candidates saved before A3 keep whatever number was typed. If
some of those were yearly, they will now display under a "/month" label and sit at the top of a
salary filter until corrected by hand. `salary_period` is what makes that fixable later without
guesswork.

**Tests:** min only, max only, both, min > max (422), non-numeric stored values ignored;
`salary_period` set on every write path and absent on an untouched legacy doc after an unrelated
update.

---

### A4 — Salary fields on the external forms (item 3) · S · after A3

**Backend** (`controller/public_controller.py:159`)
- `public_apply`: add `current_salary: Form(ge=0)` (**required**) and
  `expected_salary: Form(ge=0) | None`. Store as `Candidate.salary` / `expected_salary` with
  `salary_period = "monthly"`.
- The lead opened by `open_lead_for_application` then carries them to the telecaller form.

**Frontend** (`components/public/ApplicationForm.tsx`)
- "Current salary (₹/month) *" and "Expected salary (₹/month)", numeric, with a hint
  ("e.g. 25000"). One component → covers `/form`, `/form/[brand]` and the referee refer page.

**Tests:** `tests/test_recruitment/test_public_apply.py` — missing current salary → 422; both
stored; expected optional; referral (connect code) path also stores them.

---

### A5 — Import Naukri exports as leads (item 2) · L · after A3, #94

**The file** (`Captains Data Naukri.xlsx`, one sheet, 49 rows, 22 columns):

| Naukri column | Maps to | Parsing |
|---|---|---|
| Candidate Name | `full_name` | trimmed; row skipped if empty |
| Contact No. | `phone` / `phone_normalized` | existing `utils/phone.py`; row skipped if unusable |
| Email | `email` | lower-cased |
| Work Exp | `experience_years` | `"3Y 5 M"` → 3.42 |
| Annual Salary | `salary` (current, **monthly**) | `"INR 3.8 L"` → 380000 / 12 → **31,667**. The only place a yearly figure is converted |
| Current Location | `city` | |
| Preferred Location | kept in `raw` + shown in notes | |
| Current Employer | `previous_company` | (displayed as current company) |
| Designation | `current_role` | |
| U.G. / P. G. / Post P. G. Course | `education` (text), `education_level` best-effort | |
| Age/Date of Birth | `age` | `"29 y\n(06 May 1997)"` → 29 |
| Resume Title | `notes` | |
| Last Active, Comment 1–5, Postal Address, # | `raw` only | |

Headers are matched **by name**, not position, so a re-ordered export still imports; a missing
required header (name, contact) fails the whole file with a clear message.

**Backend**
- Dependency: `openpyxl` → `requirements.txt`.
- `utils/naukri_sheet.py`: `parse_naukri_xlsx(bytes) -> (list[ParsedLead], list[SkippedRow])`.
- `ParsedLead` gains `current_company`, `salary`, `expected_salary`, `age`, `notes`
  (optional — the sheet parser keeps working unchanged).
- `IntakeSource.naukri_import`. `external_id = "naukri:" + phone_normalized`, so the unique
  `(brand_id, external_id)` index makes **re-uploading the same file a no-op**.
- `IntakeLead.submitted_by_id` — the employee who uploaded (reused by A6 for manual leads).
- Duplicates (phone/email already in the pool) → `duplicate` status, exactly like sheet leads.
- Endpoints (in `controller/intake.py`), on plain `get_tenant` — **every staff role**:
  - `POST /intake/imports/naukri/preview` — multipart; returns `plan_ingest` output per row:
    *new / duplicate / already imported / skipped (reason)*, plus warnings. Writes nothing.
  - `POST /intake/imports/naukri` — same file; ingests; returns counts.
  - `GET /intake/leads/submitted` — the caller's own submitted leads and their current status.
  - File cap: 5 MB (a 49-row export is ~20 KB).
- New leads go through `ingest_leads` → telecaller round-robin; **telecaller SLA clocks start at
  upload time** (49 leads at once is 49 clocks — worth telling the telecallers).
- `IntakeSourceConfig.activated_at` cutoff does **not** apply to uploads.
- Warning (non-blocking) when monthly salary < ₹5,000 — row 1 of this file is `INR 0.2 L`
  (₹1,667/month), almost certainly bad data.

**Frontend**
- The Leads page opens to **recruiters** for the first time (sidebar entry + `RouteGuard`). Their
  view: "Import Naukri file" and **My submitted leads** (status column). Maintainers/admins keep
  today's view plus the same import button.
- Import dialog: choose `.xlsx` → preview table with row status and warnings → **Import N leads**
  → summary. Rows are not editable in the preview.

**Tests:** parser unit tests on a fixture workbook generated in the test (every format above,
missing headers, blank phone), preview writes nothing, import round-robins, re-upload no-op,
duplicate path, a recruiter can import, `submitted_by_id` set, a telecaller is refused.

---

### A6 — Recruiters add leads, manually or from resumes (item 7) · L · after A5

**Shared limits** — `RESUME_BATCH_MAX_FILES = 20`, `RESUME_MAX_BYTES = 5 * 1024 * 1024` in
`utils/constants.py`, and the same pair in a frontend constants file. Used by:
- the new resume-lead endpoints below, and
- the **existing** bulk resume upload: `_BULK_MAX = 50` (`controller/candidates.py:581`) → the
  shared constant, plus the size check it never had; `BulkUploadDrawer.tsx:45,110` text and check
  ("max 20, 5 MB each"). An oversized file fails that file, not the batch.

**Backend**
- `IntakeSource.recruiter_manual`.
- `resume_parser.py`: add best-effort `full_name`, `city`, `current_role`. They only prefill a
  draft the recruiter reviews, so a wrong guess is harmless.
- `POST /intake/leads/parse-resumes` — multipart, ≤ 20 files, ≤ 5 MB each. Returns one draft per
  file (parsed fields + per-file error). **Stores nothing**, uploads nothing — so an abandoned
  dialog leaves no orphan Cloudinary files.
- `POST /intake/leads/manual` — multipart: a JSON array of drafts + the matching resume files
  (same limits). For each: upload resume (existing `resume_service`), create candidate +
  `IntakeLead` (`recruiter_manual`, `submitted_by_id`, `external_id = "manual:" + uuid`,
  `salary_period = "monthly"`), dedupe, round-robin to telecallers. Returns a per-draft result
  (queued / duplicate / error).
- Access: plain `get_tenant`. Telecallers stay on their own door.

**Frontend**
- `components/leads/AddLeadDialog.tsx`: a drop zone (≤ 20 files, 5 MB each, rejected files listed
  with the reason) plus "Add without resume". Each file → a draft card prefilled from parsing with
  the lead fields (name*, phone*, email, city, current role, department, current company,
  current salary ₹/month*, expected salary ₹/month). Recruiter edits, removes drafts,
  **Submit all** → per-draft result.
- "Add lead" button on the Leads page (next to the A5 import); submitted leads appear in
  **My submitted leads**.

**Tests:** parse endpoint returns drafts and stores nothing; 21 files → 400; a 6 MB file fails
alone; submit creates leads in the telecaller queue with `submitted_by_id`; duplicate by phone;
one bad file doesn't fail the batch; a telecaller cannot call these routes; bulk upload now
refuses 21 files.

---

### A7 — Recruiter dashboard and actions panel (item 4) · M · after A6

**What a recruiter is "part of"** — resolved once per request:
- **Positions:** `assigned_employee_id == me`, **or** any position holding a mapping they are
  part of.
- **Mappings:** on a position assigned to them, **or** `employee_id == me` (the recruiter who
  last acted), **or** they appear anywhere in the mapping's stage history
  (`history.by_employee_id == me`) — so a candidate someone else moved later still counts for
  the recruiter who worked on it.
- **Activity:** `ActivityLog.employee_id == me`.

**Backend** (`dashboard/controller.py::_filters`, the single choke point)
- For a recruiter (role `employee`): ignore any `employee_id` query value and attach a
  `RecruiterScope` (position ids + the mapping `$or` above) to `DashboardFilters` — the same
  "override, don't merge" pattern already used for `client_id`. `_filters` becomes async
  (it now reads positions).
- `dashboard/repository.py`: `_base_mapping_match`, `_activity_match` **and** the position
  aggregation in `fetch_overview` (`:190`, which ignores `employee_id` today) apply the scope.
- Index on `candidate_mappings.history.by_employee_id` for the history branch.
- Refuse (403) `/dashboard/employees`, `/dashboard/client-profiles` and `/dashboard/sourcing` for
  recruiters: the UI no longer calls them, and they list other people's data.
- Maintainer/admin behaviour unchanged, including the optional `employee_id` filter.

**Frontend** (`app/(dashboard)/page.tsx`)
- Recruiter branch: KPIs, pipeline pie **without** the per-recruiter split, analytics widgets,
  and a new **QuickActions** panel in the line graph's slot.
- Hidden for recruiters: `RecruiterLineSection`, `ClientProfilesSection`, `SourcingAnalyticsSection`.
- `components/dashboard/organisms/QuickActions.tsx`: Add lead (`AddLeadDialog`, A6) ·
  Add position (`AddPositionModal`) · Add candidate (`AddCandidateModal`) · Go to pipeline
  (`/pipeline`) · Check leaderboard (`/leaderboard`).

**Tests:** recruiter passing another `employee_id` still gets their own numbers; each of the three
"part of" routes counts (assigned position, last actor, history only); a mapping on someone
else's position they never touched does not count; open-positions KPI is scoped; the three
refused endpoints 403 for a recruiter and 200 for a maintainer.

---

### A8 — Joined card actions and history (item 5) · S–M

Frontend only; the endpoints exist and already allow staff.

- `kanban/CandidateCard.tsx:218`: rename **"Mark as Rejected" → "Rejected"**; add an
  **Offer letter** button beside it — "Upload offer letter" when none, "Offer letter" (view /
  replace) when present. Both staff-only (the client board is unchanged).
- Offer-letter upload: small modal posting to `PUT /pipeline/mappings/{id}/offer-letter`.
- Clicking a **Joined** card on the staff board opens `CandidateDrawer` (full candidate history
  via `/candidates/{id}/history`, all positions) with a **Joining details** section on top:
  joining date + salary offered, saved through `PUT /pipeline/mappings/{id}/joining-date`.
  Other stages keep opening `ClientActionModal` as today.

"Rejected" on a joined card stays one click, as today.

---

### A9 — Archive joined candidates after 100 days (item 6) · M · after A8

**Backend**
- `Mapping.joined_at: datetime | None` — set whenever a mapping enters `joined` (the move
  endpoint, client moves, and the auto-join Celery task at `recruitment/tasks.py:271`), cleared
  if it leaves `joined`.
- `scripts/backfill_joined_at.py`: from the latest `history` entry with `stage == joined`
  (fallback `updated_at`). Idempotent, `--dry-run`. Only writes the new field.
- `JOINED_ARCHIVE_DAYS = 100` in `utils/constants.py`.
- `GET /pipeline/board`, **staff viewers only**: excludes joined mappings with
  `joined_at < now − 100 days`; `GET /pipeline/board?archived=true` returns only those.
  **Client viewers:** the cut-off is never applied and `archived=true` is refused, so a client's
  Joined column keeps every placement. Index `(brand_id, stage, joined_at)`.
- **Automatic without a job:** the cut-off is applied when the board is read, so it works even
  when Celery beat is down. Nothing is deleted; dashboard and leaderboard counts are unaffected.

**Frontend** (`GlobalPipelineBoard.tsx`)
- "Active | Archived" toggle, staff board only. Archived shows the archived joined cards
  read-only (no drag), still clickable into `CandidateDrawer`.
- `ClientPipelineBoard.tsx`: no change.

**Tests:** 99 vs 101 days; card moved out of joined and back resets the clock; backfill;
archived view returns only archived; a client viewer still sees a 101-day-old joined card and
gets 403 on `archived=true`.

---

## 5. Still to confirm

Nothing. Telecallers are confirmed out of Naukri imports: they only reach their own queue by
design (`get_telecaller_tenant`), and imported leads round-robin back into telecaller queues.

---

## 6. Rollout

1. Merge #94, #95, #96.
2. A1, A2, A3, A8 any time. None of them rewrites existing data.
3. A4, then A5, A6, A7.
4. A9 + run `backfill_joined_at.py` in the same release (dry-run first; it adds a field, changes
   nothing else).

Go-live is Mon 5 Oct with a one-week freeze after it: whatever is not merged by Sat 3 Oct waits
until ~12 Oct.
