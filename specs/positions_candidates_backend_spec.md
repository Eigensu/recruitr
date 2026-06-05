# Tech Spec — Backend for Positions, Candidates & Pipeline Pages

> **Status:** Draft for review
> **Author:** Generated with Claude Code
> **Date:** 2026-06-03
> **Scope:** Wire the Positions (drag‑and‑drop), Candidates (directory + drawer + add), and Kanban Pipeline pages to a real backend, replacing the Zustand mock stores. Build a single **fresh unified data module** that also becomes the source of truth for the existing Dashboard and Leaderboard.

---

## 0. Decisions locked (from review)

| # | Decision | Choice |
|---|----------|--------|
| 1 | Data model strategy | **Fresh unified module** — one clean canonical schema; migrate Dashboard + pages onto it; retire the stale `positions`/`candidates`/`pipeline` modules. |
| 2 | Kanban scope & stages | **In scope.** Custom 6‑stage pipeline: **Sent to Client → Interview → Decision Pending (selected/rejected) → Offer → Offer Accepted → Position Close**, plus **slicers/filters** on the board. |
| 3 | Recruiter attribution | **Login = employee.** On login, find‑or‑create an `employees` record by email and link it to the auth `User`. Drag/drop actions are credited to that employee and surface on the leaderboard. |
| 4 | Schema fidelity | **Extend models to match the UI** (city, department, seniority, requirement keywords, target‑close date, assigned recruiter) and power **real `$setIntersection` match scoring**. |
| 5 | Multi-tenancy | **Strict tenant isolation.** Every domain document carries a `brand_id`; every query is auto-scoped to the current employee's brand. One user ↔ one brand. (See §2.3.) |

---

## 1. Current state (what we're replacing)

### 1.1 Frontend — three mock-backed surfaces

| Page | File | State source | Behaviour |
|------|------|--------------|-----------|
| Positions (split-pane DnD) | `apps/frontend/src/app/(dashboard)/positions/page.tsx` | `usePositionsStore` (Zustand mock) | Left = positions list (search + client filter). Right = candidate pool or, when a position is selected, "Top 10 Matches (AI Ranked)". Drag candidate → position card to map; Map/Unmap toggle; fill progress; mapped avatars; footer link to Kanban. Scoring is a client-side `computeScore()` heuristic. |
| Candidates (directory) | `apps/frontend/src/app/(dashboard)/candidates/page.tsx` | `usePositionsStore` | Grid of cards, search + experience filter, `CandidateDrawer` (detail + active mappings), `AddCandidateModal`. |
| Kanban pipeline | `apps/frontend/src/app/(dashboard)/positions/[id]/pipeline/page.tsx` | `usePipelineStore` (Zustand mock) | 3 columns `pending / accepted / rejected`. Already calls `PATCH /api/v1/pipeline/match` (stale endpoint) on drop. |

Mock shapes (to be replaced by API types):

```ts
// usePositionsStore.ts
MockPosition  { id, clientName, role, department, city, seniority,
                dateOpened, targetClose, assignedTo, openingsCount,
                status: "Open"|"Closed", notes? }
MockCandidate { id, name, email, phone, skills[], matchScore,
                previousCompany?, experienceYears }
mappings: Record<positionId, candidateId[]>

// usePipelineStore.ts / types/index.ts
CandidateCard { id, name, email, extracted_skills[], resume_url,
                match_score?, status: "pending"|"accepted"|"rejected" }
```

The API client wrapper already exists: `apps/frontend/src/lib/api/index.ts` → `useApiFetch()` (sends `credentials: "include"`), and a server-side `dashboardFetch` pattern in `apps/frontend/src/lib/api/dashboard.ts`.

### 1.2 Backend — two colliding data models

**Canonical / seeded (the Dashboard model)** — `app/modules/dashboard/`:
- `employees` (`DashboardEmployee`), `candidates` (`DashboardCandidate`: full_name, skills, experience, current_stage), `job_openings` (`JobOpening`: client_name, role, seats, status), `candidate_mappings` (`CandidateMapping`: employee_id, candidate_id, job_opening_id, pipeline_stage), `activities` (`ActivityLog`), `documents`.
- Mature read layer (`repository.py` aggregations + Redis cache in `service.py`) and write helpers `create_candidate_mapping`, `create_activity_log`.
- Seeded by `app/modules/dashboard/seed.py` (12 employees, 120 candidates, 24 clients/job_openings, 260 mappings).

**Stale scaffolding (original spec)** — `app/modules/positions/`, `app/modules/candidates/`, `app/modules/pipeline/`:
- `Position` (brand_id, title, requirements, status, matched_candidates[]) and `Candidate` (name, email, extracted_skills, resume_*).
- **Bugs / dead code:** `positions/router.py` reads `current_user.org_id` which does **not** exist on `TokenPayload` (only `sub`); `pipeline/service.py` references an undefined `position.brand_id`. These endpoints would 500 if hit.

**⚠️ The collision:** both `DashboardCandidate` **and** `Candidate` register Beanie on the **same `candidates` collection** with incompatible schemas (`full_name` vs `name`, `experience` vs none, `skills` vs `extracted_skills`) and both declare a unique `email` index. The seed writes the `DashboardCandidate` shape; the old `Candidate` model reads garbage against it. This **must** be resolved (it's a latent production landmine even before this work).

Gamification hooks already exist and are reusable:
- `app/modules/leaderboard/repository/writes.py::record_activity_atomic(...)` — transactional: inserts `RecruiterActivity`, upserts `EmployeeStat` (`employee_stats` collection, unique `employee_id`), updates Redis rank, evaluates badges. Idempotent via unique `activity_reference_id`.
- Points (`leaderboard/utils/ranking_calculator.py`): `MAPPING=4`, `OFFER=8`, `JOINED=15`, `REJECTION=-2`.
- `ActivityTypeEnum`: `MAPPING_COMPLETED`, `OFFER_RECEIVED`, `CANDIDATE_JOINED`, `CANDIDATE_REJECTED`.

Auth: Google OAuth + email/password → local JWT in HttpOnly `access_token` cookie; `TokenPayload { sub }`; `get_current_user` dependency in `app/dependencies.py`. Login + Google callback live in `app/modules/auth/router.py`.

---

## 2. Target architecture

### 2.1 The unified `recruitment` module

Create **one** module that owns the core domain and exposes sub-routers. The Dashboard and Leaderboard read from the **same** collections (no parallel models).

```
app/modules/recruitment/
  __init__.py
  enums.py                 # PipelineStage, PositionStatus, Seniority, ...
  models.py                # Client, Position, Candidate, Mapping, Employee, Activity, Document
  schemas.py               # request/response DTOs (snake_case, matches API contract)
  repository.py            # Mongo aggregations + atomic transactional writes
  service.py               # business logic, gamification + cache-invalidation orchestration
  matching.py              # $setIntersection scoring engine
  seed.py                  # fresh seed for the unified collections
  routers/
    __init__.py
    positions.py           # /api/v1/positions
    candidates.py          # /api/v1/candidates
    pipeline.py            # /api/v1/pipeline
  events.py                # cache invalidation + activity logging side-effects
```

**Module boundaries**
- `recruitment` owns the *write* side and CRUD reads for the three pages.
- `dashboard` keeps its analytics endpoints but its `repository.py` is re-pointed at the unified collections + enum (it becomes a *read projection* over `recruitment`'s data).
- `leaderboard` is unchanged except that `employee_id` now reliably maps to a real, login-linked employee.
- `storage` (Cloudinary) is reused unchanged for resume uploads.

### 2.2 Collection naming

To do a clean cut without fighting Beanie's "two models, one collection" problem, the unified models use **new, unambiguous collection names** and we migrate data in (Section 9). Old collections are dropped after migration.

| Concept | New collection | Replaces |
|---------|----------------|----------|
| Recruiter (login-linked) | `employees` | `employees` (reused; add `user_id`) |
| Client / brand account | `clients` | *(new — was just a `client_name` string)* |
| Position / hiring mandate | `positions_v2` → renamed to `positions` post-migration | `job_openings` + old `positions` |
| Candidate (talent) | `candidates` (reused, unified schema) | `candidates` (both old models) |
| Pipeline entry | `candidate_mappings` (reused) | `candidate_mappings` |
| Activity log | `activities` | `activities` |
| Resume/doc | `documents` | `documents` |

> During migration we write to a temp name (`positions_v2`) to avoid the live `positions`/`job_openings` collision, then atomically swap. See §9.

### 2.3 Multi-tenancy (strict brand scoping)

**Boundary:** the tenant is the **Brand** (the workspace/org using the platform — reuses the existing `Brand` model). A **Client** (Hunger Inc, Foodmatters…) is a company *inside* a brand; a brand has many clients. **Every Employee belongs to exactly one brand** (`employee.brand_id`), enforcing the "one user ↔ one brand" rule. A recruiter can still work multiple **clients** within their brand.

> **Interpretation flag:** the review said "the current employee's associated *client* ID." This spec scopes by **`brand_id`** (the org), not by a single client company, so that candidates/positions are shared across the brand's recruiters and clients. If instead each login must be locked to one *client company* (candidates **not** shareable across clients), swap `brand_id → client_id` on every model/query below — the mechanism is identical. **Confirm before Phase A.**

**Hard rules**
1. Every domain document carries a non-nullable `brand_id`: `clients`, `positions`, `candidates`, `candidate_mappings`, `activities`, `documents`, `employees`, `counters`.
2. **No repository function may run an unscoped query.** A single dependency resolves the tenant and is threaded into *every* read and write:
   ```python
   # dependencies.py
   async def get_tenant(employee: Employee = Depends(get_current_employee)) -> TenantScope:
       if employee.brand_id is None:
           raise HTTPException(403, "User is not assigned to a brand")
       return TenantScope(brand_id=employee.brand_id, employee_id=employee.id)
   ```
   Repository signatures become `fetch_positions(scope: TenantScope, filters, ...)` and **always** prepend `{"brand_id": scope.brand_id}` to the `$match`. A lint/review checklist item: grep that no `get_motor_collection().aggregate`/`.find` in `recruitment`/`dashboard` omits `brand_id`.
3. **Cross-tenant access → 404, not 403.** Fetching a position/candidate/mapping by id always adds `brand_id` to the filter; a miss returns 404 (don't reveal existence).
4. **Uniqueness is per-brand.** `candidates.email`, `clients.code`, `positions.code` are unique **within a brand**, not globally → compound indexes `(brand_id, email)`, `(brand_id, code)`.
5. **Brand assignment:** set during onboarding (the existing `onboarding/page.tsx` flow — currently incomplete). `ensure_employee_for_user` creates the employee; the onboarding step assigns/creates the brand and stamps `employee.brand_id`. Until assigned, write endpoints 403 (rule 2). The seed assigns all demo employees + data to one demo brand.
6. **Dashboard & Leaderboard** read paths must also take `brand_id` (the dashboard repository gains the same scope arg; the leaderboard board filters `employee_stats` to the brand's employees). Flagged in §9.

---

## 3. Canonical data model

All timestamps UTC. All `id` exposed to the frontend are stringified ObjectIds. Human-readable codes (`CLI-031`, `CLI-031-POS-001`) are separate `code` fields for display.

### 3.1 Enums (`recruitment/enums.py`)

```python
class PipelineStage(StrEnum):
    sourced         = "sourced"          # mapped on Positions page; pre-Kanban backlog
    sent_to_client  = "sent_to_client"   # Kanban col 1
    interview       = "interview"        # Kanban col 2
    decision_pending = "decision_pending"# Kanban col 3 (selected/rejected sub-decision)
    offer           = "offer"            # Kanban col 4
    offer_accepted  = "offer_accepted"   # Kanban col 5
    position_close  = "position_close"   # Kanban col 6 (joined / seat filled)
    rejected        = "rejected"         # terminal (leaves the board)
    on_hold         = "on_hold"          # parked

# Ordered list used for board layout + analytics
KANBAN_STAGES = [sent_to_client, interview, decision_pending, offer, offer_accepted, position_close]
TERMINAL_STAGES = {position_close, rejected}

class Decision(StrEnum):
    pending  = "pending"
    selected = "selected"
    rejected = "rejected"

class PositionStatus(StrEnum):
    open = "open"; on_hold = "on_hold"; closed = "closed"

class Seniority(StrEnum):
    junior = "Junior"; mid = "Mid"; senior = "Senior"
```

**Decision Pending semantics:** stage `decision_pending` carries a `decision` field on the mapping. Advancing to `offer` sets `decision=selected`; a Reject action sets `stage=rejected, decision=rejected`. This satisfies "decision pending stage (selected/rejected)" as one column with two outcomes.

**Where do `sourced` candidates appear on the board?** The 6 Kanban columns are exactly the status columns. Freshly *mapped* candidates (stage `sourced`) render in a collapsible **"Sourced" tray** on the left of the board (not a 7th status column), and are dragged into "Sent to Client" to enter the flow. *(Confirm-on-review; default = tray.)*

### 3.2 `Client` (collection `clients`)

```python
class Client(Document):
    brand_id: PydanticObjectId     # tenant scope (required)
    code: str                      # "CLI-031" (unique within brand)
    name: str                      # "Hunger Inc"
    city: str | None = None
    logo_url: str | None = None
    is_active: bool = True
    created_at / updated_at: datetime
    # indexes: (brand_id, code) unique, brand_id, (brand_id, name), is_active
```

### 3.3 `Position` (collection `positions`)

```python
class Position(Document):
    brand_id: PydanticObjectId     # tenant scope (required)
    code: str                      # "CLI-031-POS-001" (unique within brand; see §3.8)
    client_id: PydanticObjectId
    client_name: str               # denormalized for list rendering
    role: str                      # "Cafe Steward"
    department: str | None         # "F&B - Service"
    city: str | None               # "Mumbai"
    seniority: Seniority = mid
    requirements: list[str] = []   # lowercased keywords → match engine
    total_seats: int = 0           # = openingsCount
    filled_seats: int = 0          # auto from position_close mappings
    remaining_seats: int = 0       # total - filled
    status: PositionStatus = open
    assigned_employee_id: PydanticObjectId | None  # recruiter owner ("assignedTo")
    date_opened: datetime
    target_close: datetime | None
    notes: str | None
    is_active: bool = True
    created_at / updated_at: datetime
    # indexes: (brand_id, code) unique, brand_id, (brand_id, client_id),
    #          (brand_id, status), assigned_employee_id, is_active, created_at
```

### 3.4 `Candidate` (collection `candidates`, unified)

Reconciles `DashboardCandidate` + old `Candidate`:

```python
class Candidate(Document):
    brand_id: PydanticObjectId     # tenant scope (required)
    full_name: str                 # was MockCandidate.name
    email: str                     # unique within brand
    phone: str | None
    previous_company: str | None
    experience_years: float = 0    # was experience / experienceYears
    skills: list[str] = []         # was extracted_skills (lowercased copy in skills_normalized)
    skills_normalized: list[str] = []  # lowercased, for $setIntersection
    resume_url: str | None
    resume_public_id: str | None   # Cloudinary
    resume_raw_text: str | None
    current_stage: PipelineStage = sourced   # denormalized latest stage across mappings
    is_active: bool = True
    created_at / updated_at: datetime
    # indexes: (brand_id, email) unique, brand_id, skills_normalized,
    #          (brand_id, current_stage), is_active, created_at
```

> `matchScore` in the UI is **computed per selected position** (not stored). The static `matchScore` in the mock is dropped.

### 3.5 `Mapping` (collection `candidate_mappings`)

The pipeline entry; one per (candidate, position).

```python
class Mapping(Document):
    brand_id: PydanticObjectId         # tenant scope (required)
    candidate_id: PydanticObjectId
    position_id: PydanticObjectId
    client_id: PydanticObjectId        # denormalized for filtering
    employee_id: PydanticObjectId      # recruiter who owns/last-moved
    stage: PipelineStage = sourced
    decision: Decision = pending
    match_score: float | None = None   # snapshotted at map time (0..1)
    feedback: str | None = None
    history: list[StageEvent] = []     # [{stage, decision, by_employee_id, at}]
    mapped_at: datetime
    updated_at: datetime
    # indexes: (candidate_id, position_id) unique, brand_id, (brand_id, position_id),
    #          (brand_id, candidate_id), client_id, employee_id, (brand_id, stage), mapped_at
```

### 3.6 `Employee` (collection `employees`, login-linked)

```python
class Employee(Document):
    brand_id: PydanticObjectId | None  # tenant the recruiter belongs to (set at onboarding)
    user_id: PydanticObjectId | None   # FK → users._id (the login). NEW.
    name: str
    email: str                         # globally unique (1 login ↔ 1 employee ↔ 1 brand)
    avatar_url: str | None
    is_active: bool = True
    created_at / updated_at: datetime
    # indexes: email(unique), user_id(sparse), brand_id, is_active
```

> `email` stays **globally** unique here (a person has one login and one brand), unlike the per-brand uniqueness on `candidates`/`clients`/`positions`. `brand_id` is nullable only between signup and onboarding; write endpoints 403 until it is set (§2.3 rule 5).

> Per-recruiter score/badges live in `employee_stats` (leaderboard module), keyed by `employee_id`. We do **not** duplicate counters here.

### 3.7 `Activity` (collection `activities`) & `Document` (collection `documents`)

Same shape as the dashboard model (`activity_type`, `target_entity_*`, `description`, `created_at`; resume docs) **plus a required `brand_id`** for tenant scoping. Indexes gain a leading `brand_id` (e.g. `(brand_id, created_at)`).

### 3.8 `Counter` (collection `counters`) — atomic sequential codes

Human-readable codes (`CLI-031`, `CLI-031-POS-007`) must be generated atomically. A `count()` of documents races and produces duplicates when two recruiters create simultaneously. Use a per-brand `counters` collection with `findOneAndUpdate($inc, upsert, returnDocument=AFTER)`:

```python
class Counter(Document):
    brand_id: PydanticObjectId
    key: str                # "client" | f"position:{client_id}"
    seq: int = 0
    # indexes: (brand_id, key) unique

async def next_seq(brand_id, key) -> int:
    doc = await Counter.get_motor_collection().find_one_and_update(
        {"brand_id": brand_id, "key": key},
        {"$inc": {"seq": 1}},
        upsert=True, return_document=ReturnDocument.AFTER,
    )
    return doc["seq"]
```

- **Client code:** `CLI-{next_seq(brand, "client"):03d}` → `CLI-032`.
- **Position code:** `{client.code}-POS-{next_seq(brand, f"position:{client_id}"):03d}` → `CLI-031-POS-007`.
- The `$inc`+`upsert` is a single atomic document operation — safe under concurrency without a transaction. When this runs **inside** a create-position transaction, it participates in that session and rolls back with it (so a failed create won't burn a sequence number — acceptable either way; gaps are harmless).
- Migration seeds each counter's `seq` to the current max observed code per brand/client (§9).

---

## 4. Recruiter ↔ Employee linking ("login = employee")

**Goal:** every authenticated action resolves to a real `Employee`, so the leaderboard counts it.

1. **On login / Google callback** (`auth/router.py`): after the `User` is found/created, call `recruitment.service.ensure_employee_for_user(user)`:
   - Find `Employee` by `email`; if missing, create `{ name: user.full_name or email, email, user_id: user.id }`.
   - If found but `user_id` is null, backfill `user_id`.
   - Returns the `Employee`.
2. **New dependency** `get_current_employee` (in `dependencies.py`): decode JWT → load `User` by `sub` → resolve `Employee` (find-or-create by email, cached). Returns `Employee`. `get_tenant` (§2.3) wraps it to produce the `TenantScope` every endpoint uses; `employee.id` is the attribution id.
3. **Brand assignment** happens at onboarding (§2.3 rule 5): the user creates or joins a `Brand`, which stamps `employee.brand_id`. `ensure_employee_for_user` does **not** guess a brand — until onboarding completes, the employee has `brand_id = null` and write/scoped-read endpoints return 403 ("User is not assigned to a brand"). `/auth/me` and onboarding endpoints stay reachable so the UI can drive the user into the flow.
4. **Seeded demo employees** (Edwin, Mohit, …) keep `user_id = null` until someone logs in with a matching email; they're all pre-assigned to the demo brand so the seeded board/leaderboard render. They still appear on the leaderboard with their seeded stats.

> Edge case: a logged-in user whose email matches no seeded employee gets a fresh `Employee` (brand_id null → onboarding) and a zeroed `employee_stats` row on first credited action (upserted by `record_activity_atomic`).

---

## 5. Match scoring engine (`recruitment/matching.py`)

Implements the spec formula at the DB layer:

```
score = | skills_normalized(candidate) ∩ requirements(position) | / | requirements(position) |
```

Aggregation over `candidates` (NOT loaded into Python):

```python
async def top_candidates(position: Position, limit: int = 10, exclude_mapped=True):
    reqs = [r.lower() for r in position.requirements]
    pipeline = [
        {"$match": {"brand_id": scope.brand_id, "is_active": True}},  # tenant-scoped
        # (optional) exclude already-mapped candidate_ids for this position
        {"$addFields": {"match_score": {
            "$cond": [{"$gt": [len(reqs), 0]},
                {"$divide": [
                    {"$size": {"$setIntersection": ["$skills_normalized", reqs]}},
                    len(reqs)]},
                0]}}},
        {"$sort": {"match_score": -1, "experience_years": -1, "created_at": -1}},
        {"$limit": limit},
        {"$project": { "id": {"$toString": "$_id"}, "full_name":1, "email":1,
                       "phone":1, "previous_company":1, "experience_years":1,
                       "skills":1, "resume_url":1, "match_score":1 }},
    ]
    return await Candidate.get_motor_collection().aggregate(pipeline).to_list(None)
```

- `match_score` returned as `0..1`; the UI renders `Math.round(score*100)`.
- When a position has **no `requirements`**, fall back to recency/experience sort and return `match_score = null` (not `0`). **UI contract:** a `null` score means the candidate card renders **without** the score ring/badge entirely — never a `0%` ring and never a broken/empty graphic. The score ring component must treat `match_score == null` as "hide", and `0..1` as "render `Math.round(score*100)`". Seed will populate `requirements` from role keyword templates (e.g. chef → `["chef","oven","cuisine","food safety"]`) so the demo "AI Ranked" panel is populated immediately.
- `match_score` is **snapshotted** onto the `Mapping` at map time so the Kanban card can show the score the candidate was matched at.

---

## 6. API contract

Prefix `/api/v1`. All endpoints require auth (`get_current_user`); write endpoints additionally use `get_current_employee`. List endpoints use the existing `PaginatedResponse[T]` (`items` + `meta`). All bodies snake_case.

### 6.1 Positions page

| Method | Path | Purpose |
|--------|------|---------|
| `GET` | `/positions` | List positions. Query: `search`, `client_id`, `status`, `assigned_employee_id`, `page`, `limit`. Each item carries `mapped_count`, `filled_seats`, `total_seats`, and `mapped_preview[]` (up to 5 `{id, full_name, initials}`). |
| `POST` | `/positions` | Create position (New Position button). |
| `GET` | `/positions/{id}` | Position detail. |
| `PATCH` | `/positions/{id}` | Update (status, seats, requirements, assignment, …). |
| `DELETE` | `/positions/{id}` | Soft-delete (`is_active=false`). |
| `GET` | `/positions/{id}/top-candidates?limit=10` | Ranked matches (§5). |
| `GET` | `/positions/{id}/candidates` | Candidates mapped to this position (+stage, +match_score). |
| `POST` | `/positions/{id}/candidates` | **Map** a candidate (drag/drop or Map button). Body `{candidate_id}`. Creates `Mapping(stage=sourced)`, snapshots score, credits recruiter, logs activity. Idempotent (409 if already mapped). |
| `DELETE` | `/positions/{id}/candidates/{candidate_id}` | **Unmap** (deletes the mapping; recomputes seats). |
| `GET` | `/positions/filters` | Distinct clients + statuses for the filter dropdowns. |

**`PositionListItem` response**
```json
{
  "id": "665...", "code": "CLI-031-POS-001",
  "client_id": "664...", "client_name": "Hunger Inc",
  "role": "Cafe Steward", "department": "F&B - Service", "city": "Mumbai",
  "seniority": "Junior", "status": "open",
  "total_seats": 7, "filled_seats": 2, "remaining_seats": 5,
  "mapped_count": 2,
  "mapped_preview": [{"id":"...","full_name":"Priya Nair","initials":"PN"}],
  "assigned_employee_id": "...", "assigned_employee_name": "Edwin",
  "date_opened": "2026-05-01T00:00:00Z", "target_close": "2026-06-01T00:00:00Z",
  "notes": null
}
```

**Map response** (`POST /positions/{id}/candidates`)
```json
{ "mapping_id":"...", "position_id":"...", "candidate_id":"...",
  "stage":"sourced", "match_score":0.75, "recruiter_score_delta":4 }
```

### 6.2 Candidates page

| Method | Path | Purpose |
|--------|------|---------|
| `GET` | `/candidates` | List/search. Query: `search` (name/email/company/skill), `experience` (`lt2`/`2to5`/`gt5`), `stage`, `page`, `limit`. |
| `POST` | `/candidates` | Add candidate (modal). Body: `full_name, email, phone, previous_company, experience_years, skills[]`. 409 on duplicate email. |
| `GET` | `/candidates/{id}` | Detail for the drawer. |
| `PATCH` | `/candidates/{id}` | Edit. |
| `GET` | `/candidates/{id}/mappings` | Positions this candidate is mapped to → drawer "Active Mappings" (`{position_id, code, role, client_name, city, stage}[]`). |
| `POST` | `/candidates/{id}/resume` | Confirm Cloudinary upload (reuse storage flow): `{resume_public_id, resume_url}`. |

**`CandidateResponse`**
```json
{ "id":"...", "full_name":"Priya Nair", "email":"...","phone":"+91...",
  "previous_company":"The Taj Mahal Palace", "experience_years":2,
  "skills":["Guest Relations","Table Service"], "resume_url":null,
  "current_stage":"sourced",
  "mappings_count": 3,
  "created_at":"..." }
```

### 6.3 Kanban pipeline page

| Method | Path | Purpose |
|--------|------|---------|
| `GET` | `/pipeline/board` | Board for a position **or** across all. Query (slicers): `position_id?`, `client_id?`, `employee_id?`, `role?`, `seniority?`, `search?`. Returns 6 columns keyed by `KANBAN_STAGES` + a `sourced` tray. |
| `PATCH` | `/pipeline/mappings/{mapping_id}/stage` | Move a card. Body `{ stage, decision? }`. Transactional: update stage+history, recompute position seats on terminal, credit recruiter, log activity, invalidate caches. |
| `GET` | `/pipeline/filters` | Distinct clients / recruiters / roles for slicer dropdowns (respecting `position_id` if given). |

**`BoardResponse`**
```json
{
  "position": { "id":"...","code":"...","role":"...","client_name":"...",
                "total_seats":7,"filled_seats":2 },
  "sourced": [ { "mapping_id":"...","candidate_id":"...","full_name":"...",
                 "skills":[...],"match_score":0.75,"resume_url":null } ],
  "columns": {
    "sent_to_client":   [ ...cards... ],
    "interview":        [ ... ],
    "decision_pending": [ {"...":"...","decision":"pending"} ],
    "offer":            [ ... ],
    "offer_accepted":   [ ... ],
    "position_close":   [ ... ]
  },
  "counts": { "sent_to_client": 4, "interview": 2, ... }
}
```

**Stage-move rules (`PATCH .../stage`)**
- Validate the transition target is a real stage.
- `→ offer`: set `decision=selected` if coming from `decision_pending`.
- `→ rejected`: terminal; set `decision=rejected`; card leaves columns (shows under a Rejected filter).
- `→ position_close`: increment `position.filled_seats`; if `remaining_seats==0` → `position.status=closed`.
- Append `{stage, decision, by_employee_id: current_employee.id, at: now}` to `history`.
- Update `candidate.current_stage` (denormalized).
- **Gamification** (via `record_activity_atomic`, idempotent on `activity_reference_id = f"{mapping_id}:{stage}"`):

  | Target stage | ActivityType | Δ points |
  |---|---|---|
  | `sourced` (map) | `MAPPING_COMPLETED` | +4 |
  | `offer` | `OFFER_RECEIVED` | +8 |
  | `position_close` | `CANDIDATE_JOINED` | +15 |
  | `rejected` | `CANDIDATE_REJECTED` | −2 |

  Other transitions log an `Activity` for the feed but award 0 points.

### 6.4 Transactions & write ordering

`POST /positions/{id}/candidates` and `PATCH .../stage` wrap their multi-collection writes in a replica-set session transaction (Mongo URI already sets `replicaSet=rs0`). Pattern mirrors the existing `record_activity_atomic`. Gamification credit runs **inside** the same transaction but tolerates `record_activity_atomic` returning `False` (duplicate `activity_reference_id`) without failing the move.

**Strict ordering — cache invalidation lives OUTSIDE the transaction:**

```
1. async with session.start_transaction():
       - update mapping stage/decision/history
       - recompute position seats / status
       - (optional) next_seq for codes
       - record_activity_atomic(...)        # gamification
   # ← transaction commits here
2. if commit succeeded:                      # only now
       await invalidate_caches(brand_id)     # delete_pattern, best-effort
3. build & return the response
```

- **Never** call Redis `delete_pattern`/`delete` inside the `start_transaction()` block. A Mongo transaction can abort/retry after the cache call has already fired, leaving the cache cleared while the DB rolled back — readers would re-populate the cache from *stale* committed state and the change would appear lost.
- Cache invalidation is **best-effort**: wrap in try/except, log on failure, never fail the request because Redis was unavailable (the TTL is the backstop). It runs *after* commit so a cleared cache always reflects committed data.
- If using FastAPI `BackgroundTasks`, schedule invalidation as a post-response task — it still only runs after the handler (and thus the committed transaction) returns.

---

## 7. Caching & invalidation

Reuse `app/common/extras/redis_cache.py` (`dashboard_cache`). The dashboard caches read responses with `REDIS_CACHE_TTL_SECONDS=300`.

- **Invalidate only after the DB transaction commits** (§6.4) — best-effort, never inside the transaction, never request-fatal.
- **Scope cache keys by brand** so one tenant's write doesn't flush another tenant's cache. Cache keys already hash the filter set; include `brand_id` in that hash and invalidate with a brand-scoped pattern: `dashboard_cache.delete_pattern(f"dashboard:{brand_id}:*")` (and `recruitment:{brand_id}:*` if list endpoints get cached). This keeps invalidation O(one tenant) and avoids cross-tenant cache stampedes.
- After any map/unmap/stage-move/create/update, invalidate the writing employee's `brand_id` namespace so that brand's dashboard KPIs + pipeline funnel reflect the change on the next read.
- Positions/Candidates **list** endpoints are not cached initially (filter-heavy and cheap); add caching later if needed.
- `top-candidates` may be cached per `(brand_id, position_id, requirements_hash)` with a short TTL.

---

## 8. Frontend integration plan

Replace the Zustand **mock data** with API-backed data while keeping the same component tree. Two clean options; **recommended:** keep Zustand for UI/optimistic state but hydrate from the API and persist via fetches (minimal component churn).

### 8.1 New API client modules (`apps/frontend/src/lib/api/`)
- `positions.ts` — `listPositions`, `getPosition`, `createPosition`, `updatePosition`, `topCandidates`, `getPositionCandidates`, `mapCandidate`, `unmapCandidate`.
- `candidates.ts` (replace stub) — `listCandidates`, `getCandidate`, `createCandidate`, `getCandidateMappings`, `confirmResume`.
- `pipeline.ts` — `getBoard`, `moveStage`, `getFilters`.

All client-side calls go through `useApiFetch()` (already sends cookies). Server components can use the `dashboardFetch` cookie-forwarding pattern.

- **Tenancy is invisible to the client.** The frontend never sends a `brand_id`; the server derives it from the session (`get_tenant`). No query params or store changes are needed for scoping. If `get_tenant` 403s ("not assigned to a brand"), the client routes the user to `/onboarding`.
- **Score ring component** (`positions/page.tsx` and the Kanban card): treat `match_score == null` as **hidden** (render no ring/badge), and `0..1` as `Math.round(score*100)%`. Do not render a `0%` ring for a null score (§5).

### 8.2 Store refactors
- **`usePositionsStore`** → drop `MOCK_*` arrays. Holds `positions`, `candidates`, `mappings`, `selectedPositionId`, plus async actions that call the API and update local state optimistically:
  - `loadPositions(filters)`, `loadCandidates(filters)`
  - `mapCandidate(positionId, candidateId)` → optimistic add + `POST`; rollback on error
  - `unmapCandidate(...)` → optimistic remove + `DELETE`
  - `loadTopCandidates(positionId)` → replaces the client-side `computeScore()`; the server returns `match_score`.
- **Delete `computeScore()`** from `positions/page.tsx`; render `cand.match_score*100` from the API.
- **`usePipelineStore`** → columns become the 6 stages keyed by `PipelineStage`; `setBoard(board)`; `moveCard(mappingId, from, to)` optimistic + `PATCH`; rollback on failure (the current Board.tsx already has the optimistic skeleton + a TODO for rollback — implement it).

### 8.3 Type alignment (mock → API)

| UI (mock, camelCase) | API (snake_case) | Note |
|---|---|---|
| `position.id` | `position.code` (display) + `position.id` (API key) | UI shows `code` (e.g. `CLI-031-POS-001`), calls API with ObjectId `id`. `CandidateDrawer` currently shows `pos.id` as the code — switch to `pos.code`. |
| `clientName` | `client_name` | |
| `openingsCount` | `total_seats` | |
| `status: "Open"\|"Closed"` | `status: "open"\|"on_hold"\|"closed"` | map for badge colors |
| `seniority` | `seniority` | values already `Junior/Mid/Senior` |
| `assignedTo` | `assigned_employee_name` | |
| `candidate.name` | `full_name` | |
| `experienceYears` | `experience_years` | |
| `skills` | `skills` | |
| `matchScore` (static) | `match_score` (per-position, 0..1) | compute server-side |
| pipeline `status` pending/accepted/rejected | `stage` (6-stage) | new columns |

> Recommend a thin `adapters.ts` mapping API DTOs → the camelCase view models the components already use, to minimize edits inside the JSX.

### 8.4 Kanban slicers/filters (new UI)
Add a filter bar to `positions/[id]/pipeline/page.tsx` (and a global `/pipeline` view if desired): Client, Recruiter, Role, Seniority dropdowns + search, sourced from `GET /pipeline/filters`, pushed as query params to `GET /pipeline/board`. Filtering is server-side; the board re-fetches on filter change.

---

## 9. Migration & cutover plan

The collision (`candidates` shared by two models) makes "just add models" unsafe. Steps:

1. **Freeze writes** to old `positions`/`candidates`/`pipeline` routers (they're unused/buggy — remove them from `main.py` + `database.py`).
2. **Introduce unified models** registered in `database.py` (`Client`, `Position`→temp `positions_v2`, `Candidate` unified, `Mapping`, `Employee`, `Activity`, `Document`). Remove `DashboardCandidate`, `JobOpening`, old `Position`, old `Candidate` from Beanie registration.
3. **Migration script** `recruitment/migrate.py`:
   - **Default brand:** create (or look up) a single demo `Brand`; capture its `_id` as `DEMO_BRAND_ID`. **Stamp `brand_id = DEMO_BRAND_ID` on every migrated doc** (clients, positions, candidates, mappings, employees, activities, documents). All existing seed data belongs to one tenant.
   - `clients`: derive from distinct `job_openings.client_name` → create `Client` docs with generated `code` (`CLI-XXX`) **scoped to `DEMO_BRAND_ID`**.
   - `positions_v2`: from `job_openings` → set `client_id`, `client_name`, `role`, `total/filled/remaining_seats`, `status` (map `JobStatus.open→open`, `closed→closed`, `on_hold→on_hold`); generate `code` (`{client.code}-POS-00N`); backfill `requirements` from a role→keywords template; default `seniority`, `city`, `department` where missing.
   - `candidates`: already the `DashboardCandidate` shape → add `experience_years` (copy `experience`), `skills_normalized` (lowercased `skills`), keep `current_stage` (remapped per below).
   - `candidate_mappings`: map `job_opening_id → position_id`, add `client_id`, remap `pipeline_stage → stage`:
     | old stage | new stage |
     |---|---|
     | added, shortlisted | sourced |
     | sent_to_client | sent_to_client |
     | offer_sent | offer |
     | offer_accepted | offer_accepted |
     | joined | position_close |
     | rejected, dropped | rejected |
     | hold | on_hold |
   - `employees`: add `user_id: null`, `brand_id = DEMO_BRAND_ID`.
   - `counters`: after codes are assigned, seed each counter `seq` to the current max per brand/client (e.g. `position:{client_id}` → highest `POS-NNN` issued) so post-migration creates continue the sequence without collision.
4. **Re-point `dashboard/repository.py`** to read `positions`/`candidates`/`candidate_mappings` with the new `PipelineStage` (update `_PIPELINE_ORDER`, `_TERMINAL_STAGES`, `_ACTIVITY_STAGE_MAP`) **and accept a `brand_id` scope** — every dashboard `$match` prepends `brand_id` (the dashboard controller derives it via `get_tenant`). Note the dashboard's existing `client_id` filter currently means *job_opening_id* — switch it to real `client_id` now that Clients exist. Update `dashboard/enums.py` to import the unified enum (or alias). The leaderboard board likewise filters `employee_stats` to the brand's employees.
5. **Swap** `positions_v2` → `positions`: drop the old `positions` collection, `renameCollection` `positions_v2 → positions`.
6. **Fresh seed** (`recruitment/seed.py`) for a clean dev DB: clients (with codes), positions (with `requirements`, seniority, city, dept, target dates, assigned recruiter), candidates (unified), mappings across the 6 stages, employees, activities. Keep the recognizable demo names (Edwin, Hunger Inc, etc.).
7. **Delete** `app/modules/positions`, `app/modules/candidates`, `app/modules/pipeline` and their tests; move/retarget any kept tests under `tests/test_recruitment/`.

> The dashboard frontend keeps working throughout because its API shape (`/api/v1/dashboard/*`) is preserved — only the underlying collections/enum change.

---

## 10. Phased delivery

**Phase A — Foundation (no UI change)**
- Unified models (incl. `brand_id` everywhere + `counters`) + enums + `database.py` registration; remove stale modules from `main.py`.
- `ensure_employee_for_user` + `get_current_employee` + `get_tenant` (`TenantScope`); hook into login + Google callback; 403 when `brand_id` unset.
- `next_seq` atomic code generator.
- Migration script (brand backfill + counter seeding) + fresh seed; re-point dashboard repository to take `brand_id` scope; verify dashboard + leaderboard unchanged for the demo brand.

**Phase B — Candidates page**
- `/candidates` CRUD + `/candidates/{id}/mappings`; resume confirm.
- Frontend: `lib/api/candidates.ts`, refactor `usePositionsStore` candidate slice + `AddCandidateModal`/`CandidateDrawer`/`CandidateCard` to API. (Lowest risk — read-mostly.)

**Phase C — Positions page + matching**
- `/positions` CRUD, `/top-candidates`, map/unmap.
- Matching engine + score snapshot + gamification credit on map.
- Frontend: `lib/api/positions.ts`, refactor positions store + `positions/page.tsx` (delete `computeScore`), wire drag-to-map + Map/Unmap to API with optimistic update + rollback.

**Phase D — Kanban pipeline + slicers**
- `/pipeline/board`, `/pipeline/mappings/{id}/stage`, `/pipeline/filters`; seat recompute + gamification per stage.
- Frontend: 6-stage columns + Sourced tray + filter bar; implement rollback in `Board.tsx`; remove the old `/pipeline/match` call.

**Phase E — Polish**
- Cache invalidation on all writes; activity feed entries; loading/empty/error states; e2e pass.

Each phase is independently shippable; A is a prerequisite for B–D.

---

## 11. Testing plan

- **Unit (pytest, `tests/test_recruitment/`)**: matching aggregation (intersection math, empty requirements → `null` score, tie-break); `ensure_employee_for_user` (create/backfill/idempotent); stage-move rules (seat recompute, terminal handling, decision flag); idempotent gamification (`activity_reference_id` dedupe); `next_seq` (monotonic, per-brand/client isolation).
- **Tenant isolation (critical)**: seed two brands A & B; assert every list/detail/match/board endpoint returns **only** the caller's brand data; cross-brand id fetch → 404; cross-brand map attempt → 404; per-brand uniqueness lets the same email/code exist in both brands. A test that fails if any repository `$match` is missing `brand_id`.
- **Concurrency**: N parallel `POST /positions` in one brand → N unique sequential codes, zero duplicates (validates `counters` vs naive count).
- **Transaction/cache ordering**: simulate a transaction abort → assert cache was **not** cleared; simulate Redis down during post-commit invalidation → request still 200; assert invalidation is brand-scoped (brand B's cache survives a brand A write).
- **Integration**: full map → move-through-6-stages → position auto-closes; unmap recomputes seats; duplicate-map → 409; dashboard KPIs reflect a move after (post-commit) cache invalidation.
- **Migration**: run against a seeded copy; assert counts preserved, stages remapped, codes unique, every doc has `brand_id`, counters seeded to max, no orphan mappings.
- **Frontend**: optimistic update + rollback on simulated API failure for map and stage-move; type adapters round-trip.
- **Manual**: log in (Google) → confirm an `Employee` is created/linked → map a candidate → see leaderboard score increment → drag through Kanban → see Position Close fill a seat.

---

## 12. Open items / confirm-on-review

1. ✅ **Sourced tray vs 7th column** — *Decided:* collapsible "Sourced" tray feeding "Sent to Client" (a 7th column pushes the board off-screen).
2. ✅ **Decision Pending UX** — *Decided:* **both** explicit Select/Reject buttons **and** drag-zones. Buttons guard critical offer decisions against accidental drops; drag-zones keep the gamified feel.
3. ✅ **Position `code` generation** — *Decided:* atomic per-brand `counters` collection via `next_seq` (§3.8), **not** a document count (which races). Format `CLI-NNN` / `CLI-NNN-POS-NNN`; migration seeds counters to the current max.
4. ✅ **Multi-tenancy** — *Decided:* strict per-brand isolation (§2.3); every query scoped by `brand_id`. **One thing to confirm:** that the tenant boundary is **Brand** (org, many clients) and not a single **Client** company — see the interpretation flag in §2.3.
5. **`requirements` keyword source** — seed from a role→keywords template now; later, derive from resume parsing / JD. Confirm the template approach for the demo.
6. **Real-time** — `DashboardRealtimeStatus` exists; default here is refetch/optimistic. SSE/websocket push is a later enhancement.
7. **Daily/weekly score reset** — leaderboard uses cumulative `total_score`/`xp_points`; the original "daily reset" concept isn't in the current leaderboard module. Out of scope unless desired.

---

## 13. Appendix — endpoint summary

```
# Positions
GET    /api/v1/positions
POST   /api/v1/positions
GET    /api/v1/positions/{id}
PATCH  /api/v1/positions/{id}
DELETE /api/v1/positions/{id}
GET    /api/v1/positions/filters
GET    /api/v1/positions/{id}/top-candidates
GET    /api/v1/positions/{id}/candidates
POST   /api/v1/positions/{id}/candidates          # map
DELETE /api/v1/positions/{id}/candidates/{cid}     # unmap

# Candidates
GET    /api/v1/candidates
POST   /api/v1/candidates
GET    /api/v1/candidates/{id}
PATCH  /api/v1/candidates/{id}
GET    /api/v1/candidates/{id}/mappings
POST   /api/v1/candidates/{id}/resume

# Pipeline
GET    /api/v1/pipeline/board
PATCH  /api/v1/pipeline/mappings/{mapping_id}/stage
GET    /api/v1/pipeline/filters

# (removed) /api/v1/pipeline/match  ← old stale endpoint
```
