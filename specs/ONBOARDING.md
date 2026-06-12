# Eigensu Recruitr — Engineering Onboarding Guide

> **Audience:** A new engineer with zero prior context on this project.  
> **Goal:** Understand every part of the platform and be ready to contribute within a few hours.  
> **Last updated:** 2026-06-10

---

## Table of Contents

1. [Executive Summary](#1-executive-summary)
2. [System Architecture Diagram](#2-system-architecture-diagram)
3. [Feature-by-Feature Breakdown](#3-feature-by-feature-breakdown)
4. [Frontend Page Inventory](#4-frontend-page-inventory)
5. [Backend API Inventory](#5-backend-api-inventory)
6. [Database Schema & Relationships](#6-database-schema--relationships)
7. [State Management Flow](#7-state-management-flow)
8. [User Journey Flows](#8-user-journey-flows)
9. [Dependency Map](#9-dependency-map)
10. [Recommended Reading Order](#10-recommended-reading-order)

---

## 1. Executive Summary

**Recruitr** is a gamified, full-stack recruitment CRM built for internal recruiting teams. Its core job is to help recruiters:

- Track candidates through a visual pipeline (Kanban board)
- Map candidates to open job positions for client companies
- Measure recruiter performance via a leaderboard and scoring system
- Give management a real-time dashboard of hiring progress across all clients

The platform is split into two applications inside a **pnpm monorepo** orchestrated by Turbo:

| App      | Location         | Tech                                                          |
| -------- | ---------------- | ------------------------------------------------------------- |
| Frontend | `apps/frontend/` | Next.js 16 (App Router), React 19, TypeScript, Tailwind CSS 4 |
| Backend  | `apps/backend/`  | FastAPI (Python 3.12+), Beanie ODM, MongoDB 7, Redis 7        |

Infrastructure: MongoDB Atlas (production), Cloudinary (resume storage), Redis (caching + Celery broker), Docker Compose (local dev).

---

## 2. System Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────────┐
│                        Browser (User)                               │
│                                                                     │
│  Next.js 16 App Router (apps/frontend/)                             │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐              │
│  │  Auth Pages  │  │  Dashboard   │  │  Pipeline    │  ...         │
│  │  /sign-in    │  │  /           │  │  /positions  │              │
│  │  /sign-up    │  │              │  │  /[id]/pipe  │              │
│  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘              │
│         │                 │                  │                      │
│  Zustand stores   React Server Components   @dnd-kit drag/drop      │
│  (usePipelineStore, useAuthStore)                                   │
└────────────────────────────┬────────────────────────────────────────┘
                             │  fetch() + credentials:"include"
                             │  HttpOnly JWT cookie
                             ▼
┌─────────────────────────────────────────────────────────────────────┐
│                   FastAPI Backend (apps/backend/)                   │
│                                                                     │
│  app/main.py — mounts all routers at /api/v1/                       │
│                                                                     │
│  ┌──────┐ ┌────────┐ ┌───────────┐ ┌──────────┐ ┌─────────────┐   │
│  │ auth │ │brands  │ │candidates │ │positions │ │  pipeline   │   │
│  └──────┘ └────────┘ └───────────┘ └──────────┘ └─────────────┘   │
│  ┌──────────┐ ┌──────────┐ ┌─────────┐ ┌─────────┐ ┌──────────┐  │
│  │dashboard │ │leaderboard│ │gamify   │ │storage  │ │  health  │  │
│  └──────────┘ └──────────┘ └─────────┘ └─────────┘ └──────────┘  │
│                                                                     │
│  Middleware: SessionMiddleware (OAuth state) + CORSMiddleware        │
│  Auth: JWT decoded from HttpOnly cookie via get_current_user dep    │
│                                                                     │
│  Background: Celery workers (Redis broker)                          │
│   - leaderboard.refresh_cache                                       │
│   - leaderboard.create_monthly_snapshot                             │
│   - badge assignment tasks                                          │
└───────┬────────────────────────────────────┬────────────────────────┘
        │  Beanie ODM (async Motor driver)   │  httpx
        ▼                                    ▼
┌───────────────────┐              ┌──────────────────────┐
│  MongoDB Atlas    │              │  External Services   │
│                   │              │                      │
│  Collections:     │              │  Cloudinary          │
│  - users          │              │  (resume storage)    │
│  - brands         │              │                      │
│  - positions      │              │  Google OAuth2       │
│  - candidates     │              │  (recruiter login)   │
│  - recruiters     │              └──────────────────────┘
│  - employees      │
│  - job_openings   │     ┌──────────────────────┐
│  - candidate_map  │     │  Redis 7             │
│  - activities     │     │                      │
│  - employee_stats │     │  - Dashboard cache   │
│  - lboard_history │     │  - Leaderboard cache │
│  - badges         │     │  - Celery broker     │
│  - recruiter_act  │     │  - Celery results    │
│  - documents      │     └──────────────────────┘
└───────────────────┘
```

---

## 3. Feature-by-Feature Breakdown

### 3.1 Authentication & Authorization

**What it does:** Handles recruiter sign-up, login, and session management. Supports both email/password and Google OAuth2. Uses stateless JWT tokens stored in HttpOnly cookies so JavaScript cannot read the token.

**Why it exists:** The entire platform is access-controlled. Every API endpoint (except `/health`) requires a valid JWT.

**Auth flow (email/password):**

```
User submits form → POST /api/v1/auth/login
  → Backend verifies bcrypt hash
  → Issues JWT (7-day expiry)
  → Sets HttpOnly cookie "access_token"
  → Returns { status: "ok" }
  → Next.js middleware reads cookie, allows protected routes
```

**Auth flow (Google OAuth2):**

```
User clicks "Sign in with Google"
  → GET /api/v1/auth/google/login
  → Backend generates random state token, stores in session
  → Redirects browser to Google's consent screen

Google redirects back to:
  → GET /api/v1/auth/google/callback?code=X&state=Y
  → Backend validates state (CSRF protection)
  → Exchanges code for Google access token
  → Fetches user profile from Google
  → Finds or creates User document in MongoDB
  → Sets HttpOnly JWT cookie
  → Redirects to / (existing user) or /onboarding (new user)
```

**How protected routes work (frontend):**

- `apps/frontend/src/middleware.ts` inspects the `access_token` cookie
- Unauthenticated requests to `/dashboard/*` paths are redirected to `/sign-in`

**Key files:**

- `apps/backend/app/modules/auth/router.py` — All auth endpoints
- `apps/backend/app/modules/auth/security.py` — JWT creation/verification, bcrypt
- `apps/backend/app/modules/auth/models.py` — `User` document
- `apps/backend/app/dependencies.py` — `get_current_user` FastAPI dependency
- `apps/frontend/src/middleware.ts` — Route protection
- `apps/frontend/src/app/(auth)/sign-in/page.tsx` — Login page
- `apps/frontend/src/app/(auth)/sign-up/page.tsx` — Registration page

**Database reads/writes:** `users` collection

---

### 3.2 Candidate Management

**What it does:** Stores candidate profiles including their resume (uploaded to Cloudinary), extracted skills (parsed from the PDF), contact info, and allows search/filtering.

**Why it exists:** Candidates are the core entities of the recruiting workflow. They need to be stored, searched, and linked to open positions.

**How a candidate is created:**

```
Recruiter opens "Add Candidate" (currently stub UI, full form planned)
  → POST /api/v1/candidates  { name, email, phone }
  → Backend creates Candidate document in MongoDB
  → Returns candidate with new ID

To attach a resume:
  → GET /api/v1/storage/sign
  → Backend generates Cloudinary upload signature (HMAC-SHA256)
  → Frontend uploads PDF bytes directly to Cloudinary CDN
  → Cloudinary sends webhook → POST /api/v1/storage/webhook/cloudinary
  → Backend verifies HMAC signature
  → Phase 1: logs receipt
  → Phase 2 (planned): extracts text via PyMuPDF, extracts skills
  → PATCH /api/v1/candidates/{id}/resume  { resume_url, resume_public_id }
  → Candidate document updated with Cloudinary URLs
```

**Key files:**

- `apps/backend/app/modules/candidates/models.py` — `Candidate` Beanie document
- `apps/backend/app/modules/candidates/router.py` — CRUD endpoints
- `apps/backend/app/modules/candidates/service.py` — Search/filter logic
- `apps/backend/app/modules/storage/router.py` — Signed upload + webhook
- `apps/backend/app/modules/storage/service.py` — Cloudinary signature generation
- `apps/frontend/src/lib/api/candidates.ts` — Frontend API client
- `apps/frontend/src/app/(dashboard)/candidates/page.tsx` — Directory page (stub)

**Database reads/writes:** `candidates` collection

**Important note on two candidate models:** There are two separate models that both use the `candidates` collection:

- `Candidate` in `modules/candidates/models.py` — Used by the pipeline module. Fields: `name, email, phone, resume_public_id, resume_url, resume_raw_text, extracted_skills[]`
- `DashboardCandidate` in `modules/dashboard/models.py` — Used by the dashboard module. Fields: `full_name, email, phone, previous_company, experience, skills[], resume_link, current_stage`

Both point to the same MongoDB collection (`"candidates"`) but have different schemas. This is a known inconsistency in the codebase.

---

### 3.3 Candidate Directory

**What it does:** A searchable, filterable table of all candidates. Currently a stub page — the API is fully implemented but the frontend UI is minimal.

**Why it exists:** Recruiters need to browse the entire talent pool, not just candidates linked to specific positions.

**Search logic (backend):**

```python
# Case-insensitive regex across name, email, extracted_skills, tags
{ "$or": [
  { "name": { "$regex": search, "$options": "i" } },
  { "email": { "$regex": search, "$options": "i" } },
  { "extracted_skills": { "$in": [search] } },
]}
```

**Key files:**

- `apps/backend/app/modules/candidates/service.py` — `list_candidates()` with filter pipeline
- `apps/frontend/src/app/(dashboard)/candidates/page.tsx` — Page (currently stub)
- `apps/frontend/src/lib/api/candidates.ts` — `getCandidates()`, `getCandidateMappingsForDashboard()`

---

### 3.4 Position Management

**What it does:** Manages open job positions (called "positions" in the recruiter module, "job openings" in the dashboard module). Each position belongs to a brand, has a title, a list of keyword requirements, and a list of matched candidates.

**Why it exists:** Positions are the other half of the matching equation — candidates are matched _to_ positions.

**Data model:**

```python
class Position(Document):
    brand_id: PydanticObjectId
    title: str
    requirements: list[str]      # keyword strings used for scoring
    status: "open" | "filled" | "archived"
    matched_candidates: list[{
        candidate_id: ObjectId,
        status: "pending" | "accepted" | "rejected",
        feedback: str | None
    }]
```

**Key files:**

- `apps/backend/app/modules/positions/models.py` — `Position` document
- `apps/backend/app/modules/positions/router.py` — CRUD endpoints
- `apps/backend/app/modules/positions/service.py` — Business logic
- `apps/frontend/src/app/(dashboard)/positions/page.tsx` — Position list (stub)
- `apps/frontend/src/app/(dashboard)/positions/[id]/pipeline/page.tsx` — Pipeline view

**Database reads/writes:** `positions` collection

---

### 3.5 Recruitment Pipeline (Kanban Board)

**What it does:** A drag-and-drop Kanban board showing candidates for a specific position, organized into three columns: Pending Review, Accepted, Rejected. Dragging a card between columns updates the candidate's status in the database.

**Why it exists:** The visual pipeline is the primary recruiter workflow surface. It provides an at-a-glance view of where every candidate stands for a given role.

**Complete data flow — how the Kanban loads:**

```
User navigates to /positions/[id]/pipeline
  → PipelinePage (Server Component) extracts positionId from params
  → Renders <KanbanBoard positionId={id} />
  → KanbanBoard reads from usePipelineStore (Zustand)
  → On mount, fetches GET /api/v1/pipeline/top-candidates?position_id=X
  → Returns list of CandidateMatchScore objects (ranked by keyword overlap)
  → setColumns() populates the Zustand store
  → Each column renders its CandidateCard list
```

**Drag-and-drop flow (the most important flow in the app):**

See [Section 8.2](#82-drag-and-drop-kanban-flow) for the complete step-by-step.

**Key files:**

- `apps/frontend/src/app/(dashboard)/positions/[id]/pipeline/page.tsx` — Route page
- `apps/frontend/src/components/kanban/Board.tsx` — DnD context, event handlers
- `apps/frontend/src/components/kanban/Column.tsx` — Droppable column
- `apps/frontend/src/components/kanban/CandidateCard.tsx` — Draggable card
- `apps/frontend/src/stores/usePipelineStore.ts` — Zustand store
- `apps/backend/app/modules/pipeline/router.py` — `GET /top-candidates`, `PATCH /match`
- `apps/backend/app/modules/pipeline/service.py` — Matching logic + transaction

---

### 3.6 Candidate Matching

**What it does:** Ranks candidates against a position's keyword requirements using a MongoDB aggregation pipeline. The score is a decimal 0–1 representing what fraction of the position's requirements are found in the candidate's extracted skills.

**Why it exists:** With potentially thousands of candidates, recruiters need the system to surface the most relevant ones for each role automatically.

**Scoring algorithm:**

```
match_score = |intersection(candidate_skills, job_requirements)| / |job_requirements|
```

Implemented entirely in MongoDB using `$setIntersection` and `$divide` — no Python loops over data.

**How the transaction works when a recruiter moves a card:**

```python
# pipeline/service.py — match_candidate_to_position()
async with await client.start_session() as session:
    async with session.start_transaction():
        # Write 1: Add candidate to position's matched_candidates[]
        await Position.find_one(...).update(
            { "$push": { "matched_candidates": { candidate_id, status, feedback } } }
        )

        # Write 2: Credit recruiter's daily/weekly score (+10 points)
        await profile.inc({ "daily_score": 10, "weekly_score": 10 })
```

Both writes are atomic — if either fails, neither is committed.

---

### 3.7 Recruiter Dashboard

**What it does:** The home page (`/`). Displays a real-time summary of the entire recruitment operation: KPI cards, a pipeline stage pie chart, a recruiter performance line graph, analytics widgets, and a client activity table.

**Why it exists:** Management needs a single-page view of hiring health across all clients and recruiters.

**Data loading strategy:** The dashboard uses Next.js React Server Components with `Suspense` boundaries. Each section is an `async` server component that fetches its own data independently. This means the page renders progressively — fast sections appear immediately while slow ones show skeletons.

**In-memory cache (frontend):** `apps/frontend/src/lib/dashboard-data.ts` has a 60-second module-level in-memory cache (`dashboardCacheEntry`). All six API calls (overview, pipeline, clients, employees, mappings, activities) are batched in a single `Promise.allSettled()`. Individual section functions (`getDashboardOverview`, `getPipelineDashboardData`, etc.) all read from this single cached payload.

**Server-side cache (backend):** The backend service layer (`dashboard/service.py`) uses Redis with 5-minute TTL. Cache keys are SHA-256 hashes of the filter params + pagination. If Redis is disabled (`REDIS_ENABLED=false`), it falls through to MongoDB directly.

**KPI cards displayed:**

| ID                | Label             | Source                                 |
| ----------------- | ----------------- | -------------------------------------- |
| open_positions    | Open Positions    | `job_openings` count where status=open |
| total_seats_open  | Total Seats Open  | Sum of `total_seats`                   |
| seats_filled      | Seats Filled      | Sum of `filled_seats`                  |
| total_pipeline    | Total In Pipeline | Count of active CandidateMappings      |
| sent_to_client    | Sent to Client    | Pipeline stage count                   |
| offers_accepted   | Offers Accepted   | Pipeline stage count                   |
| candidate_dropped | Candidate Dropped | Pipeline stage count                   |
| joined            | Joined            | Pipeline stage count                   |

**Key files:**

- `apps/frontend/src/app/(dashboard)/page.tsx` — Main dashboard page
- `apps/frontend/src/lib/dashboard-data.ts` — Data orchestration + in-memory cache
- `apps/frontend/src/lib/api/dashboard.ts` — API client functions
- `apps/frontend/src/components/dashboard/` — All dashboard components (atoms/molecules/organisms)
- `apps/backend/app/modules/dashboard/controller.py` — Route handlers
- `apps/backend/app/modules/dashboard/service.py` — Business logic + Redis cache
- `apps/backend/app/modules/dashboard/repository.py` — MongoDB queries

---

### 3.8 Dashboard Component Architecture

Components follow atomic design — atoms, molecules, organisms:

**Atoms** (pure display, no data fetching):

- `AnimatedNumber` — Counts up to a value with a CSS animation
- `DashboardRealtimeStatus` — "Live" indicator badge
- `KpiGridSkeleton` — Loading skeleton for the KPI grid
- `PanelSkeleton` — Generic panel loading skeleton
- `SkeletonBlock` — Single block skeleton

**Molecules** (composed from atoms, single data type):

- `DashboardKpiCard` — One KPI metric card (value, label, helper text, tone color)
- `PipelineStageItem` — Single row in the pipeline breakdown
- `RecruiterLineItem` — Single recruiter row in the line graph
- `ActivityFeedItem` — Single activity event
- `ClientActivityTableRow` — Single client row in the table

**Organisms** (full feature sections):

- `PipelinePieChart` — Pie chart of pipeline stage distribution
- `RecruiterLineGraph` — Multi-line chart of recruiter performance over time
- `ClientActivityTable` — Paginated table of clients with seat fill metrics
- `AnalyticsWidgets` — Fill Rate, Pipeline Depth, Join Conversion, Seat Gap widgets
- `ActivityFeed` — Scrollable recent activity list
- `DashboardSkeleton` — Full page loading state

---

### 3.9 Leaderboard

**What it does:** A gamified rankings page showing recruiters ranked by XP points, with badges, monthly growth charts, and company-wide hiring progress.

**Why it exists:** Gamification drives recruiter motivation and healthy competition. The leaderboard quantifies effort and results into a visible score.

**Scoring model:**

- Recruiters earn points when they move candidates (`daily_score`, `weekly_score` on `RecruiterProfile`)
- A separate `EmployeeStat` document (in the leaderboard module) tracks cumulative `xp_points`, `total_score`, `level`, and `leaderboard_rank`
- Celery tasks periodically recalculate ranks and create monthly snapshots

**Badge engine (`badge_engine.py`):**

```
TOP_MAPPER        → total_mappings >= 100
HIRING_CHAMPION   → joined_candidates >= 25
OFFER_KING        → offers_received >= 50
CONSISTENCY_STAR  → streak_days >= 30 OR success_rate >= 80%
RISING_RECRUITER  → monthly_growth >= 20%
FAST_CLOSER       → joined >= 10 AND streak >= 7 days
ELITE_RECRUITER   → score >= 900 OR (success >= 85% AND total >= 75)
RECRUITMENT_NINJA → joined >= 10 AND rejected <= max(3, joined/3)
```

**Background tasks (Celery):**

- `leaderboard.refresh_cache` — Recalculates rankings, updates `leaderboard_rank` on all `EmployeeStat` documents
- `leaderboard.create_monthly_snapshot` — Takes a point-in-time snapshot into `LeaderboardHistory` for a given month, then refreshes rankings

**Key files:**

- `apps/frontend/src/app/(dashboard)/leaderboard/page.tsx` — Leaderboard page
- `apps/frontend/src/components/leaderboard/` — All leaderboard components
- `apps/frontend/src/lib/api/leaderboard.ts` — API client (with Zod validation)
- `apps/backend/app/modules/leaderboard/controller/leaderboard_controller.py` — Route handlers
- `apps/backend/app/modules/leaderboard/service/leaderboard_service.py` — Business logic
- `apps/backend/app/modules/leaderboard/repository/` — `queries.py` + `writes.py`
- `apps/backend/app/modules/leaderboard/utils/badge_engine.py` — Badge evaluation
- `apps/backend/app/modules/leaderboard/utils/ranking_calculator.py` — Rank computation
- `apps/backend/app/modules/leaderboard/utils/growth_calculator.py` — Monthly growth %
- `apps/backend/app/modules/leaderboard/tasks/periodic_tasks.py` — Celery tasks
- `apps/backend/app/celery_app.py` — Celery configuration

**Database reads/writes:** `employee_stats`, `leaderboard_history`, `badges`, `recruiter_activity`

---

### 3.10 Resume Processing & CV Uploads

**What it does:** Allows direct browser-to-Cloudinary PDF uploads (the file never passes through the FastAPI server). After upload, a webhook triggers text and skill extraction.

**Why it exists:** Resumes need to be stored durably and the text needs to be parsed to enable keyword matching.

**Upload flow:**

```
1. Frontend: GET /api/v1/storage/sign
   → Backend generates HMAC-SHA256 signature with Cloudinary credentials
   → Returns { signature, timestamp, cloud_name, api_key, upload_preset, folder }

2. Frontend: POST directly to Cloudinary CDN
   → File bytes go directly to Cloudinary — not through FastAPI
   → Cloudinary stores the PDF, returns { public_id, secure_url }

3. Cloudinary → Backend: POST /api/v1/storage/webhook/cloudinary
   → Backend verifies X-Cld-Signature header (HMAC-SHA256)
   → Phase 1: logs receipt, returns { status: "received" }
   → Phase 2 (planned): background task to extract text + skills

4. Frontend: PATCH /api/v1/candidates/{id}/resume
   → Stores { resume_public_id, resume_url } on the Candidate document
```

**Why direct upload to Cloudinary:** Avoids large file payloads hitting the API server. The backend only handles the lightweight signature and webhook, never the file bytes.

---

### 3.11 Gamification Module

**What it does:** A lightweight scoring module separate from the leaderboard. Tracks per-recruiter daily/weekly scores tied to their `brand_id`.

**Why it exists:** Provides real-time score feedback to recruiters as they work (the pipeline `PATCH /match` endpoint returns the recruiter's updated `daily_score` immediately).

**Key difference from Leaderboard module:** The `gamification` module uses `RecruiterProfile` (with `daily_score`, `weekly_score`) and resets lazily on read. The `leaderboard` module uses `EmployeeStat` (with `xp_points`, `total_score`, `level`) and is updated by Celery tasks. They are separate scoring dimensions.

**Lazy reset:** Daily/weekly scores are reset to zero the first time a recruiter's profile is read after midnight/week-boundary, not via a CRON job.

**Key files:**

- `apps/backend/app/modules/gamification/models.py` — `RecruiterProfile` document
- `apps/backend/app/modules/gamification/service.py` — Score logic + lazy reset
- `apps/backend/app/modules/gamification/router.py` — `GET /leaderboard`, `GET /me`

**Database reads/writes:** `recruiters` collection

---

### 3.12 Activity Tracking

**What it does:** Every significant action (candidate mapped, offer sent, offer accepted, joined, rejected) is logged as an `ActivityLog` record. This feeds the activity feed on the dashboard and the activity timeline on the leaderboard.

**Why it exists:** Provides an audit trail and powers the "recent activity" UI across multiple pages.

**Data model:**

```python
class ActivityLog(Document):
    employee_id: ObjectId | None    # null = system action
    activity_type: ActivityType     # mapped | offer_sent | offer_accepted | joined | rejected
    target_entity_type: TargetEntityType  # candidate | job_opening | client
    target_entity_id: str
    description: str                # human-readable summary
    created_at: datetime
```

**Key files:**

- `apps/backend/app/modules/dashboard/models.py` — `ActivityLog` document
- `apps/backend/app/modules/dashboard/service.py` — `log_dashboard_activity()`
- `apps/backend/app/modules/leaderboard/models.py` — `RecruiterActivity` (leaderboard-specific activity with `points_earned`)

---

### 3.13 Brand Management

**What it does:** A brand represents a client company (the entity doing the hiring, e.g. "Acme Corp"). Brands are the tenant-level grouping — positions belong to a brand.

**Why it exists:** The platform may serve multiple clients/companies from the same recruiter team. Brands provide that namespace.

**Key files:**

- `apps/backend/app/modules/brands/models.py` — `Brand` document
- `apps/backend/app/modules/brands/router.py` — `GET /` list, `POST /` create

**Database reads/writes:** `brands` collection

---

## 4. Frontend Page Inventory

### Layout Structure

```
apps/frontend/src/app/
├── layout.tsx                          Root layout (font loading, theme provider)
├── middleware.ts                        Auth guard — redirects unauthenticated users
│
├── (auth)/                              Auth group (no sidebar)
│   ├── sign-in/page.tsx                Login form (email/password + Google button)
│   └── sign-up/page.tsx                Registration form
│
├── onboarding/page.tsx                  First-run setup for new Google OAuth users
│
└── (dashboard)/                         Protected group (with sidebar)
    ├── layout.tsx                       Dashboard layout — DashboardSidebar + main content area
    ├── dashboard.css                    CSS custom properties for theme tokens
    │
    ├── page.tsx                         HOME: Recruitment Dashboard
    ├── leaderboard/page.tsx             Leaderboard & Analytics
    ├── candidates/page.tsx              Candidate Directory (stub)
    ├── positions/page.tsx               Position List (stub)
    └── positions/[id]/pipeline/page.tsx Kanban Pipeline for one position
```

---

### Page Details

#### `/` — Recruitment Dashboard

**File:** `apps/frontend/src/app/(dashboard)/page.tsx`  
**Type:** React Server Component (RSC) — server-rendered, no client JS for data fetching  
**What it renders:**

| Section                       | Component             | Data Source                                  |
| ----------------------------- | --------------------- | -------------------------------------------- |
| Pipeline stage breakdown      | `PipelinePieChart`    | `GET /api/v1/dashboard/pipeline`             |
| KPI cards (8 metrics)         | `DashboardKpiCard`    | `GET /api/v1/dashboard/overview`             |
| Analytics widgets (4 metrics) | `AnalyticsWidgets`    | Computed from overview                       |
| Recruiter line graph          | `RecruiterLineGraph`  | `GET /api/v1/dashboard/employees` + mappings |
| Client activity table         | `ClientActivityTable` | `GET /api/v1/dashboard/clients`              |

**Loading strategy:** Each section is wrapped in `<Suspense fallback={<Skeleton />}>`. Sections render as their data resolves — no waterfall blocking.  
**Caching:** 60-second in-memory cache in `lib/dashboard-data.ts`. All 6 API calls are batched via `Promise.allSettled`.

---

#### `/leaderboard` — Leaderboard

**File:** `apps/frontend/src/app/(dashboard)/leaderboard/page.tsx`  
**Type:** Client Component (needs interactivity for charts)  
**What it renders:**

| Section                        | Component                  | Data Source                                |
| ------------------------------ | -------------------------- | ------------------------------------------ |
| Hero spotlight (top recruiter) | `HeroSpotlight`            | `GET /api/v1/leaderboard/overview`         |
| 8 KPI cards                    | `LeaderboardKpiCard`       | `GET /api/v1/leaderboard/overview`         |
| Monthly XP trend chart         | `MonthlyLineChart`         | `GET /api/v1/leaderboard/monthly-growth`   |
| Recruiter bar chart            | `RecruiterBarChart`        | Computed from rankings                     |
| Rankings table                 | `LeaderboardTable`         | `GET /api/v1/leaderboard/rankings`         |
| Company hiring progress        | `CompanyHiringProgress`    | `GET /api/v1/leaderboard/company-progress` |
| Achievement badges             | `AchievementBadgesSection` | Stub                                       |
| Recent activity feed           | `RecentActivityFeed`       | `GET /api/v1/leaderboard/activity`         |

---

#### `/positions/[id]/pipeline` — Kanban Pipeline

**File:** `apps/frontend/src/app/(dashboard)/positions/[id]/pipeline/page.tsx`  
**Type:** Server Component wrapper, renders Client Component `KanbanBoard`  
**What it does:**  
Extracts the `positionId` from the URL params and passes it to `<KanbanBoard positionId={id} />`. The Kanban board is a client component because it requires drag-and-drop event handlers and Zustand state.

---

#### `/candidates` — Candidate Directory

**File:** `apps/frontend/src/app/(dashboard)/candidates/page.tsx`  
**Status:** Stub — minimal UI, backend fully implemented  
**Planned:** Full table with filtering, source indicators, tags, CV links (see tech spec)

---

#### `/onboarding`

**File:** `apps/frontend/src/app/onboarding/page.tsx`  
**What it does:** First-run wizard for new Google OAuth users. Collects additional profile info before redirecting to the dashboard.

---

### Shared Layout Components

#### `DashboardSidebar`

**File:** `apps/frontend/src/components/sidebar/DashboardSidebar.tsx`  
**What it does:** Left navigation rail. Links to Dashboard, Candidates, Positions, Leaderboard. Always visible inside `(dashboard)/layout.tsx`.

#### `ThemeToggle`

**File:** `apps/frontend/src/components/ui/ThemeToggle.tsx`  
**What it does:** Toggles CSS custom properties between light and dark themes. Reads/writes to `ThemeContext`.

**File:** `apps/frontend/src/context/ThemeContext.tsx`  
**What it does:** React context that manages the current theme token set. CSS variables are applied to `document.documentElement`.

---

## 5. Backend API Inventory

All routes are prefixed `/api/v1/`. All endpoints except `/health` and auth flows require a valid JWT in the `access_token` HttpOnly cookie.

The FastAPI interactive docs are at `/api/docs` (Swagger UI) and `/api/redoc`.

---

### Auth — `/api/v1/auth`

**File:** `apps/backend/app/modules/auth/router.py`

| Method | Path               | Auth Required | Description                             |
| ------ | ------------------ | ------------- | --------------------------------------- |
| POST   | `/signup`          | No            | Register new user with email + password |
| POST   | `/login`           | No            | Authenticate, set HttpOnly JWT cookie   |
| POST   | `/logout`          | No            | Clear access_token cookie               |
| GET    | `/me`              | Yes           | Return current user's profile           |
| GET    | `/google/login`    | No            | Redirect to Google consent screen       |
| GET    | `/google/callback` | No            | Google OAuth2 callback handler          |

**DB:** Reads/writes `users` collection.

---

### Brands — `/api/v1/brands`

**File:** `apps/backend/app/modules/brands/router.py`

| Method | Path | Auth Required | Description        |
| ------ | ---- | ------------- | ------------------ |
| GET    | `/`  | Yes           | List brands        |
| POST   | `/`  | Yes           | Create a new brand |

**DB:** Reads/writes `brands` collection.

---

### Candidates — `/api/v1/candidates`

**File:** `apps/backend/app/modules/candidates/router.py`

| Method | Path                     | Auth Required | Description                                              |
| ------ | ------------------------ | ------------- | -------------------------------------------------------- |
| GET    | `/`                      | Yes           | Search/list candidates. Query: `search`, `page`, `limit` |
| POST   | `/`                      | Yes           | Create a candidate                                       |
| GET    | `/{candidate_id}`        | Yes           | Get single candidate profile                             |
| PATCH  | `/{candidate_id}/resume` | Yes           | Confirm Cloudinary upload, store URLs                    |

**DB:** Reads/writes `candidates` collection.

---

### Positions — `/api/v1/positions`

**File:** `apps/backend/app/modules/positions/router.py`

| Method | Path             | Auth Required | Description                          |
| ------ | ---------------- | ------------- | ------------------------------------ |
| GET    | `/`              | Yes           | List positions for a brand           |
| POST   | `/`              | Yes           | Create a position                    |
| GET    | `/{position_id}` | Yes           | Get position with matched candidates |
| PATCH  | `/{position_id}` | Yes           | Update position                      |
| DELETE | `/{position_id}` | Yes           | Delete position                      |

**DB:** Reads/writes `positions` collection.

---

### Pipeline — `/api/v1/pipeline`

**File:** `apps/backend/app/modules/pipeline/router.py`

| Method | Path              | Auth Required | Description                                                             |
| ------ | ----------------- | ------------- | ----------------------------------------------------------------------- |
| GET    | `/top-candidates` | Yes           | Score and rank candidates for a position. Query: `position_id`, `limit` |
| PATCH  | `/match`          | Yes           | Atomically move candidate to position, credit recruiter score           |

**Body for PATCH /match:**

```json
{
  "position_id": "string",
  "candidate_id": "string",
  "target_status": "pending | accepted | rejected"
}
```

**DB:** Reads `candidates`, `positions`. Writes `positions` (push to `matched_candidates`), `recruiters` (increment scores). Uses MongoDB replica-set transaction.

---

### Gamification — `/api/v1/gamify`

**File:** `apps/backend/app/modules/gamification/router.py`

| Method | Path           | Auth Required | Description                                                     |
| ------ | -------------- | ------------- | --------------------------------------------------------------- |
| GET    | `/leaderboard` | Yes           | Get recruiter rankings for a brand. Query: `brand_id`, `period` |
| GET    | `/me`          | Yes           | Get current recruiter's stats                                   |

**DB:** Reads/writes `recruiters` collection.

---

### Storage — `/api/v1/storage`

**File:** `apps/backend/app/modules/storage/router.py`

| Method | Path                  | Auth Required      | Description                                  |
| ------ | --------------------- | ------------------ | -------------------------------------------- |
| GET    | `/sign`               | Yes                | Generate Cloudinary signed upload parameters |
| POST   | `/webhook/cloudinary` | No (HMAC verified) | Receive Cloudinary upload notifications      |

---

### Dashboard — `/api/v1/dashboard`

**File:** `apps/backend/app/modules/dashboard/controller.py`

All endpoints accept optional filter query params: `employee_id`, `start_date`, `end_date`, `client_id`, `pipeline_stage`.

| Method | Path          | Auth Required | Description                                |
| ------ | ------------- | ------------- | ------------------------------------------ |
| GET    | `/overview`   | Yes           | Summary KPIs + pipeline stage counts       |
| GET    | `/pipeline`   | Yes           | Pipeline stage breakdown with percentages  |
| GET    | `/employees`  | Yes           | Paginated recruiter stats                  |
| GET    | `/clients`    | Yes           | Paginated job openings with seat fill data |
| GET    | `/candidates` | Yes           | Paginated candidate list with stage        |
| GET    | `/mappings`   | Yes           | Paginated candidate-job mappings           |
| GET    | `/activity`   | Yes           | Paginated activity log                     |

**DB:** Reads `employees`, `job_openings`, `candidates`, `candidate_mappings`, `activities`. Uses Redis cache (5-min TTL, hash-keyed by filters).

---

### Leaderboard — `/api/v1/leaderboard`

**File:** `apps/backend/app/modules/leaderboard/controller/leaderboard_controller.py`

| Method | Path                       | Auth Required | Description                                                                           |
| ------ | -------------------------- | ------------- | ------------------------------------------------------------------------------------- |
| GET    | `/overview`                | Yes           | KPIs + top recruiter spotlight                                                        |
| GET    | `/rankings`                | Yes           | Paginated ranked recruiter list. Query: `page`, `limit`, `search`, `sort_by`, `month` |
| GET    | `/recruiter/{employee_id}` | Yes           | Detailed analytics for one recruiter                                                  |
| GET    | `/monthly-growth`          | Yes           | Monthly XP growth series for all recruiters                                           |
| GET    | `/company-progress`        | Yes           | Per-job hiring progress                                                               |
| GET    | `/activity`                | Yes           | Paginated activity feed                                                               |
| GET    | `/badges/{employee_id}`    | Yes           | Badges earned by a recruiter                                                          |

**DB:** Reads `employee_stats`, `leaderboard_history`, `recruiter_activity`, `badges`. Uses Redis cache.

---

### Health

| Method | Path      | Auth Required | Description                                |
| ------ | --------- | ------------- | ------------------------------------------ |
| GET    | `/health` | No            | Returns `{ status: "ok", version: "..." }` |

---

## 6. Database Schema & Relationships

### Collections Map

```
MongoDB Database: "eigensu"

users                    ─── Auth accounts (email/password + Google OAuth)
brands                   ─── Client company namespaces
positions                ─── Open job positions (recruiter module)
candidates               ─── Candidate profiles + resume data
recruiters               ─── Recruiter gamification profiles (daily/weekly scores)

employees                ─── Recruiter profiles for dashboard module
job_openings             ─── Job positions for dashboard module
candidate_mappings       ─── Links candidates ↔ job_openings with pipeline stage
activities               ─── Activity audit log
documents                ─── Uploaded files linked to candidates

employee_stats           ─── Leaderboard cumulative XP, rank, level, badges
leaderboard_history      ─── Monthly snapshots of recruiter performance
badges                   ─── Badge definitions (name, rarity, conditions)
recruiter_activity       ─── Leaderboard-specific activity with points_earned
```

---

### Schema Details

#### `users`

```
_id             ObjectId (PK)
email           string (unique index)
hashed_password string | null    (null = Google-only account)
full_name       string | null
google_id       string | null    (from Google OAuth)
is_active       bool
created_at      datetime
updated_at      datetime
```

#### `brands`

```
_id                  ObjectId (PK)
owner_id             ObjectId → users._id
name                 string
domain               string (unique)
branding.logo_public_id  string | null
branding.logo_url        string | null
created_at           datetime
```

#### `positions`

```
_id                  ObjectId (PK)
brand_id             ObjectId → brands._id
title                string
requirements         string[]     (keyword list for matching)
status               "open"|"filled"|"archived"
matched_candidates   [{
  candidate_id: ObjectId → candidates._id
  status: "pending"|"accepted"|"rejected"
  feedback: string | null
}]
```

#### `candidates` (pipeline module schema)

```
_id                  ObjectId (PK)
name                 string
email                string (unique index)
phone                string | null
resume_public_id     string | null   (Cloudinary)
resume_url           string | null   (Cloudinary CDN URL)
resume_raw_text      string | null   (extracted text)
extracted_skills     string[]        (multikey index)
```

#### `candidates` (dashboard module schema — same collection, different fields)

```
_id                  ObjectId (PK)
full_name            string
email                string (unique index)
phone                string | null
previous_company     string | null
experience           float
skills               string[]
resume_link          string | null
current_stage        PipelineStage enum
is_active            bool
created_at / updated_at datetime
```

> **Note:** Both schemas target the same `"candidates"` collection. This is a known inconsistency — the pipeline module's `Candidate` and the dashboard module's `DashboardCandidate` are different Python classes mapped to the same collection. In practice they work because each module only queries fields it cares about.

#### `recruiters`

```
_id            ObjectId (PK)
user_id        string → users._id
brand_id       ObjectId → brands._id
daily_score    int
weekly_score   int
badges         string[]
last_reset     datetime
```

Indexes: `user_id` (unique), `brand_id`, `(brand_id, daily_score DESC)`

#### `employees` (dashboard module)

```
_id              ObjectId (PK)
name             string
email            string (unique index)
mappings.offers_sent          int
mappings.joined_candidates    int
mappings.rejected_candidates  int
total_mappings   int
is_active        bool
created_at / updated_at datetime
```

#### `job_openings`

```
_id              ObjectId (PK)
client_name      string (index)
role             string
total_seats      int
filled_seats     int
remaining_seats  int
status           "open"|"closed"|"on_hold"
is_active        bool
created_at / updated_at datetime
```

#### `candidate_mappings`

```
_id              ObjectId (PK)
employee_id      ObjectId → employees._id
candidate_id     ObjectId → candidates._id
job_opening_id   ObjectId → job_openings._id
pipeline_stage   PipelineStage enum
mapped_at        datetime
updated_at       datetime
```

Unique compound index: `(candidate_id, job_opening_id)` — a candidate can only be mapped to one job opening once.

#### `activities`

```
_id                  ObjectId (PK)
employee_id          ObjectId | null → employees._id
activity_type        "mapped"|"offer_sent"|"offer_accepted"|"joined"|"rejected"
target_entity_type   "candidate"|"job_opening"|"client"
target_entity_id     string
description          string
created_at           datetime
```

#### `employee_stats` (leaderboard)

```
_id                  ObjectId (PK)
employee_id          string (unique index) → employees._id
mappings.offers_received     int
mappings.joined_candidates   int
mappings.rejected_candidates int
mappings.total_mappings      int
total_score          int
leaderboard_rank     int
level                int
xp_points            int
streak_days          int
badges               BadgeTypeEnum[]
is_active            bool
created_at / updated_at datetime
```

#### `leaderboard_history`

```
_id                  ObjectId (PK)
employee_id          string
month                string (YYYY-MM format)
total_mappings       int
offers_received      int
joined_candidates    int
rejected_candidates  int
success_rate         float
monthly_growth       float
leaderboard_rank     int
total_score          int
```

Unique compound index: `(employee_id, month)`

#### `recruiter_activity`

```
_id                      ObjectId (PK)
employee_id              string
activity_type            ActivityTypeEnum
title                    string
description              string
points_earned            int
candidate_id             string | null
activity_reference_id    string (unique index)
created_at               datetime
```

#### `documents`

```
_id           ObjectId (PK)
candidate_id  ObjectId → candidates._id
file_name     string
file_type     string
file_url      string
uploaded_at   datetime
```

---

### Entity Relationship Summary

```
users ──────────────────── brands (owner)
                              │
                              └── positions (brand_id)
                                      │
                                      └── matched_candidates[] → candidates

candidates ──────────────── candidate_mappings ──── job_openings
                                    │                    │
                                    │                    └── (client_name groups)
                                    └── employees (who mapped)

employees ──────────────── employee_stats (leaderboard XP)
                        ── leaderboard_history (monthly snapshots)
                        ── recruiter_activity (leaderboard events)
                        ── activities (dashboard audit log)

users ──────────────────── recruiters (gamification scores, daily/weekly)
```

---

## 7. State Management Flow

### Frontend State Layers

The frontend has three distinct state layers:

```
┌─────────────────────────────────────────────────────────────┐
│  1. React Server Components (RSC)                           │
│     Dashboard page, Leaderboard page                        │
│     No client state — data fetched server-side, HTML sent   │
└─────────────────────────────────────────────────────────────┘
         ↓ passes data as props to Client Components
┌─────────────────────────────────────────────────────────────┐
│  2. URL / Route State                                       │
│     /positions/[id]/pipeline — position ID in the URL      │
│     No component state needed for the ID                   │
└─────────────────────────────────────────────────────────────┘
         ↓ client components for interactive features
┌─────────────────────────────────────────────────────────────┐
│  3. Zustand Stores (client-only)                            │
│                                                             │
│  usePipelineStore                                           │
│  ├── columns: Record<CandidateStatus, CandidateCard[]>     │
│  ├── activeCardId: string | null  (during drag)            │
│  ├── setColumns(cols)             (initial load)           │
│  ├── moveCard(id, from, to)       (optimistic drag)        │
│  └── setActiveCardId(id)          (drag start/end)         │
│                                                             │
│  useAuthStore                                               │
│  └── (minimal — auth is primarily cookie-based)            │
└─────────────────────────────────────────────────────────────┘
```

### Zustand Pipeline Store — How It Works

The store holds the Kanban board state. There is no persistence — it's populated fresh on each page visit.

```typescript
// Initial state
columns = { pending: [], accepted: [], rejected: [] };

// On page load (in KanbanBoard useEffect or equivalent):
const cards = await apiFetch("/api/v1/pipeline/top-candidates?position_id=X");
usePipelineStore.setColumns({
  pending: cards.filter((c) => c.status === "pending"),
  accepted: cards.filter((c) => c.status === "accepted"),
  rejected: cards.filter((c) => c.status === "rejected"),
});

// On drag over (optimistic — instant UI update):
usePipelineStore.moveCard(cardId, fromColumn, toColumn);
// This mutates columns in-memory immediately. The UI re-renders.

// On drag end (async confirmation):
await apiFetch("PATCH /api/v1/pipeline/match", {
  position_id,
  candidate_id,
  target_status,
});
// If this throws, the card stays in its new column (rollback not yet implemented)
```

**Known gap:** There is a `// TODO: rollback optimistic update on error` comment in `Board.tsx:79`. If the PATCH call fails, the card stays in the wrong column until the page is refreshed.

---

## 8. User Journey Flows

### 8.1 New Recruiter Onboarding

```
1. Visit /sign-up  OR  click "Sign in with Google"

   Email/password path:
   → Fill form → POST /api/v1/auth/signup → redirect to /sign-in
   → Login → POST /api/v1/auth/login → cookie set → redirect to /

   Google path:
   → Click Google → GET /api/v1/auth/google/login
   → Consent screen → GET /api/v1/auth/google/callback
   → New user: redirect to /onboarding
   → Existing user: redirect to /
```

---

### 8.2 Drag-and-Drop Kanban Flow

This is the most important interactive flow in the app. Here is every step:

```
Step 1 — Page Load
  URL: /positions/[id]/pipeline
  Server renders PipelinePage, passes positionId to <KanbanBoard positionId="...">

Step 2 — Board Initialization
  KanbanBoard mounts (Client Component)
  Calls GET /api/v1/pipeline/top-candidates?position_id=X&limit=10
  Backend runs MongoDB aggregation:
    - Normalizes candidate skills to lowercase
    - Computes match_score = |intersection(skills, requirements)| / |requirements|
    - Filters match_score > 0
    - Sorts by match_score DESC, takes top 10
  Returns CandidateMatchScore[]
  usePipelineStore.setColumns() distributes cards into columns by status

Step 3 — User Grabs a Card
  User presses mouse down on a CandidateCard
  @dnd-kit PointerSensor activates after 8px of movement (prevents accidental drags)
  handleDragStart fires:
    → setActiveCardId(card.id)
    → DragOverlay renders a ghost copy of the card at cursor position

Step 4 — User Drags Over a Column
  handleDragOver fires repeatedly as mouse moves
  When over.id is a valid column ID (pending | accepted | rejected):
    → findCardColumn(active.id) finds the card's current column
    → If different from target: usePipelineStore.moveCard(cardId, from, to)
    → Zustand updates columns immediately → React re-renders → card visually moves
  This is the OPTIMISTIC UPDATE — the UI changes before any API call

Step 5 — User Releases the Card
  handleDragEnd fires:
    → setActiveCardId(null) — clears ghost overlay
    → If dropped on valid column:
      PATCH /api/v1/pipeline/match {
        position_id: string,
        candidate_id: active.id,
        target_status: over.id ("pending"|"accepted"|"rejected")
      }

Step 6 — Backend Processes the Match
  pipeline/service.py: match_candidate_to_position()
  Opens MongoDB replica-set transaction:
    Write 1: Position.matched_candidates.push({ candidate_id, status, feedback: null })
    Write 2: RecruiterProfile.inc({ daily_score: +10, weekly_score: +10 })
    (upserts RecruiterProfile if it doesn't exist yet)
  Transaction commits atomically

Step 7 — Response Returns to Frontend
  MatchResponse { position_id, candidate_id, status, recruiter_daily_score }
  Frontend receives — currently only logs on error
  Card remains in its new column (already moved optimistically in Step 4)

Step 8 — Error Case (if PATCH fails)
  console.error logs the failure
  Card stays in wrong column (rollback not implemented — known TODO)
  User must refresh to see correct state
```

---

### 8.3 Resume Upload Journey

```
Step 1 — Recruiter opens Add Candidate form (planned UI)
  Fills: name, email, phone
  Selects a PDF file

Step 2 — Frontend requests upload signature
  GET /api/v1/storage/sign
  Backend: generate_upload_signature()
    timestamp = int(time.time())
    params = { timestamp, folder="eigensu/resumes/", upload_preset="eigensu_resumes" }
    signature = HMAC-SHA256(sorted_param_string, CLOUDINARY_API_SECRET)
    Returns: { signature, timestamp, cloud_name, api_key, upload_preset, folder }

Step 3 — Frontend uploads directly to Cloudinary
  POST https://api.cloudinary.com/v1_1/{cloud_name}/image/upload
  Body: FormData { file, signature, timestamp, api_key, upload_preset, folder }
  Cloudinary responds: { public_id, secure_url, ... }

Step 4 — Cloudinary notifies backend via webhook
  POST /api/v1/storage/webhook/cloudinary
  Header: X-Cld-Signature: <HMAC-SHA256 of body>
  Backend verifies signature → Phase 1: returns { status: "received" }

Step 5 — Frontend updates the candidate record
  PATCH /api/v1/candidates/{id}/resume
  Body: { resume_url, resume_public_id }
  Candidate document updated in MongoDB
```

---

### 8.4 Dashboard Data Flow

```
Browser requests /  (authenticated)

Next.js Server:
  PipelinePieSection   → getPipelineDashboardData()
  LiveOverviewSection  → getDashboardOverview()
  AnalyticsSection     → getDashboardAnalyticsData()
  RecruiterLineSection → getRecruiterDashboardData()
  ClientActivitySection → getClientActivityData()

  All five call loadDashboardDemoData() which:
    ├── Checks module-level cache (60s TTL)
    ├── If stale: fires Promise.allSettled([
    │     GET /api/v1/dashboard/overview
    │     GET /api/v1/dashboard/pipeline
    │     GET /api/v1/dashboard/clients?limit=100
    │     GET /api/v1/employees (via employees API)
    │     GET /api/v1/candidates/mappings (via candidates API)
    │     GET /api/v1/dashboard/activity?limit=60
    │   ])
    └── Transforms raw API data into typed view models:
          buildKpis() → DashboardKpi[]
          buildPipelineStages() → PipelineStageMetric[]
          buildRecruiters() → RecruiterDashboardStat[]
          buildActivity() → DashboardActivityItem[]
          buildAnalytics() → DashboardAnalyticsWidget[]

FastAPI Backend (for each GET):
  → JWT validated via get_current_user dependency
  → dashboard/service.py builds Redis cache key (SHA-256 of filters)
  → Cache hit: return cached JSON (5-min TTL)
  → Cache miss: dashboard/repository.py runs MongoDB aggregation
  → Result cached in Redis, returned to client
```

---

## 9. Dependency Map

### Frontend Dependencies (key packages)

| Package               | Version | Why                                                   |
| --------------------- | ------- | ----------------------------------------------------- |
| `next`                | 16.2.4  | Framework — App Router, RSC, routing                  |
| `react`               | 19.2.4  | UI library                                            |
| `@dnd-kit/core`       | latest  | Drag-and-drop engine for Kanban                       |
| `@dnd-kit/sortable`   | latest  | Sortable lists within Kanban columns                  |
| `zustand`             | 5.0.12  | Client-side state management                          |
| `zod`                 | 4.3.6   | Runtime schema validation (leaderboard API responses) |
| `tailwindcss`         | 4       | Utility-first CSS                                     |
| `@tabler/icons-react` | latest  | Icon set                                              |
| `motion`              | latest  | Animation library                                     |

### Backend Dependencies (key packages)

| Package            | Version | Why                                             |
| ------------------ | ------- | ----------------------------------------------- |
| `fastapi`          | 0.115+  | Web framework                                   |
| `beanie`           | 1.27+   | MongoDB ODM (async, built on Motor)             |
| `motor`            | latest  | Async MongoDB driver                            |
| `pydantic`         | 2.10+   | Data validation                                 |
| `python-jose`      | latest  | JWT creation + verification                     |
| `bcrypt`           | latest  | Password hashing                                |
| `httpx`            | 0.28+   | Async HTTP client (Google OAuth token exchange) |
| `celery`           | 5.4+    | Background task queue                           |
| `redis`            | latest  | Celery broker + dashboard/leaderboard cache     |
| `pymupdf` (`fitz`) | latest  | PDF text extraction                             |
| `cloudinary`       | latest  | Cloudinary SDK (signature generation)           |

---

### Inter-Module Dependencies (Backend)

```
main.py
  imports all routers →

auth/router.py
  ← auth/models.py (User)
  ← auth/security.py (JWT, bcrypt)
  ← app/dependencies.py (get_current_user)

pipeline/router.py
  ← pipeline/service.py
      ← candidates/models.py (Candidate)
      ← positions/models.py (Position)
      ← gamification/models.py (RecruiterProfile)
      ← app/database.py (get_client for transactions)

dashboard/controller.py
  ← dashboard/service.py
      ← dashboard/repository.py
          ← dashboard/models.py (Employee, JobOpening, CandidateMapping, ActivityLog, etc.)
      ← common/extras/redis_cache.py (dashboard_cache)

leaderboard/controller/leaderboard_controller.py
  ← leaderboard/service/leaderboard_service.py
      ← leaderboard/repository/queries.py
      ← leaderboard/repository/writes.py
      ← leaderboard/utils/badge_engine.py
      ← leaderboard/utils/ranking_calculator.py
      ← leaderboard/utils/growth_calculator.py
      ← leaderboard/utils/cache_manager.py
  ← leaderboard/tasks/ (Celery background tasks)

storage/router.py
  ← storage/service.py (Cloudinary HMAC signing)
```

---

### Frontend → Backend API Dependency Map

| Frontend file                 | Calls                                                                                          |
| ----------------------------- | ---------------------------------------------------------------------------------------------- |
| `lib/api/dashboard.ts`        | `GET /api/v1/dashboard/*`                                                                      |
| `lib/api/candidates.ts`       | `GET /api/v1/candidates`, `GET /api/v1/dashboard/mappings`, `GET /api/v1/dashboard/candidates` |
| `lib/api/employees.ts`        | `GET /api/v1/dashboard/employees`                                                              |
| `lib/api/leaderboard.ts`      | `GET /api/v1/leaderboard/*`                                                                    |
| `lib/api/index.ts`            | `useApiFetch` hook — used by Kanban Board                                                      |
| `components/kanban/Board.tsx` | `GET /api/v1/pipeline/top-candidates`, `PATCH /api/v1/pipeline/match`                          |

---

## 10. Recommended Reading Order

Follow this order to build a complete mental model of the system:

### Hour 1 — Get the big picture

1. **This document** — Read Sections 1 and 2 first.
2. **`apps/backend/app/main.py`** — See all routers mounted in one place.
3. **`apps/frontend/src/app/(dashboard)/layout.tsx`** — The shell all dashboard pages render inside.
4. **`apps/frontend/src/types/index.ts`** — All shared data types. Understand `CandidateCard`, `Position`, `MatchRequest`, `KanbanColumn`.

### Hour 2 — Understand the core loop (pipeline)

1. **`apps/backend/app/modules/pipeline/service.py`** — The matching aggregation and the MongoDB transaction. This is the most important backend file.
2. **`apps/frontend/src/stores/usePipelineStore.ts`** — Zustand store with `columns`, `moveCard`, `activeCardId`.
3. **`apps/frontend/src/components/kanban/Board.tsx`** — `handleDragStart`, `handleDragOver` (optimistic), `handleDragEnd` (API call).
4. **`apps/frontend/src/components/kanban/Column.tsx`** — Droppable area.
5. **`apps/frontend/src/components/kanban/CandidateCard.tsx`** — Draggable card with sortable hook.
6. Follow the drag-and-drop journey in [Section 8.2](#82-drag-and-drop-kanban-flow) while reading these files.

### Hour 3 — Understand the dashboard

1. **`apps/frontend/src/app/(dashboard)/page.tsx`** — Suspense-based RSC layout.
2. **`apps/frontend/src/lib/dashboard-data.ts`** — Data orchestration layer, in-memory cache, transform functions.
3. **`apps/backend/app/modules/dashboard/controller.py`** — All dashboard endpoints.
4. **`apps/backend/app/modules/dashboard/service.py`** — Redis cache logic.
5. **`apps/backend/app/modules/dashboard/models.py`** — All 6 dashboard collections.

### Hour 4 — Understand auth and storage

1. **`apps/backend/app/modules/auth/router.py`** — Complete auth flow including Google OAuth2.
2. **`apps/backend/app/modules/auth/security.py`** — JWT creation, bcrypt.
3. **`apps/backend/app/dependencies.py`** — `get_current_user` — how every protected endpoint validates tokens.
4. **`apps/backend/app/modules/storage/router.py`** and **`service.py`** — Cloudinary signed uploads and webhook verification.

### Hour 5 — Understand leaderboard and gamification

1. **`apps/backend/app/modules/gamification/models.py`** — `RecruiterProfile` with daily/weekly scores and lazy reset.
2. **`apps/backend/app/modules/leaderboard/utils/badge_engine.py`** — Badge evaluation logic.
3. **`apps/backend/app/modules/leaderboard/tasks/periodic_tasks.py`** — Celery tasks for rank refresh and monthly snapshots.
4. **`apps/frontend/src/app/(dashboard)/leaderboard/page.tsx`** — Leaderboard UI.

### Hour 6 — Explore the rest

1. **`docker-compose.yml`** — How MongoDB replica set and Redis are configured for local dev.
2. **`apps/backend/app/config.py`** — All environment variables and their defaults.
3. **`apps/frontend/src/context/ThemeContext.tsx`** — Light/dark theme implementation.
4. **`apps/backend/app/modules/leaderboard/repository/queries.py`** — Complex MongoDB aggregation queries for leaderboard data.

---

### Key Concepts to Internalize

| Concept                                                            | Where to Look                                              |
| ------------------------------------------------------------------ | ---------------------------------------------------------- |
| Why two candidate schemas exist                                    | Section 3.2, `dashboard/models.py`, `candidates/models.py` |
| Why Cloudinary is used (not S3 or direct upload)                   | Section 3.10, `storage/service.py`                         |
| How optimistic updates work (and their current gap)                | Section 8.2, `kanban/Board.tsx:79`                         |
| Why MongoDB transactions are needed for pipeline matches           | `pipeline/service.py` — atomically writes to 2 collections |
| Why the dashboard has two caches (frontend + backend)              | Section 3.7 — frontend in-memory + backend Redis           |
| How the gamification module differs from the leaderboard module    | Section 3.11 — different models, different update triggers |
| Why `SessionMiddleware` must come before `CORSMiddleware`          | `app/main.py` comment                                      |
| How JWT is transmitted (HttpOnly cookie, not Authorization header) | `lib/api/index.ts` — `credentials: "include"`              |

---

_Generated from full codebase audit — June 2026._
