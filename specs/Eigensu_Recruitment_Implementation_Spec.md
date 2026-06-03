# Eigensu v1.0 — Gamified Recruitment CRM: Implementation Specification

## 1. Overview

Build a gamified, multi-tenant recruitment CRM called **Eigensu** with:

- **Frontend** — Next.js 14+ (App Router, Tailwind CSS, Zustand, @dnd-kit)
- **Backend** — FastAPI (Python, domain-driven modules, Beanie ODM)
- **Database** — MongoDB Atlas (Replica Set for ACID transactions)
- **Auth** — Custom HttpOnly JWT Authentication
- **Storage** — AWS S3 (presigned URL uploads for resumes)
- **Deployment** — Vercel (frontend) · Railway (backend) · S3 (assets)

---

## 2. Product & Architecture Rules (v1.0)
Based on project requirements, the following rigid boundaries are set:
1. **1 User = 1 Brand**: Each User gets exactly one Brand. Each Brand belongs to exactly one User. No multi-tenancy or shared-brand access in v1.
2. **Backend-Managed Auth**: No `js-cookie` or frontend JavaScript reading the token. The backend sets an `HttpOnly` cookie.
3. **API Base Standard**: The core auth schema consists strictly of `POST /signup`, `POST /login`, `POST /logout`, and `GET /me`.
4. **Strong User Models**: The `User` model includes `is_active`, `created_at`, `updated_at`, and enforces lowercase, uniquely indexed emails.
5. **Basic Abuse Protection**: Password length minimums (8 chars) and generic "Incorrect email or password" responses are enforced.

> [!WARNING]
> Local storage of hashed passwords and JWT secrets requires environment variables to be managed manually (`JWT_SECRET`).
> [!WARNING]
> **MongoDB Atlas**: The cluster must be a Replica Set (not a standalone instance) to support multi-document ACID transactions used by the gamification engine. The free M0 tier **does** support replica sets.

---

## 3. Monorepo Structure

```text
Recuritement/
├── frontend/                  # Next.js app (created via create-next-app)
│   ├── public/
│   ├── src/
│   │   ├── app/               # App Router pages & layouts
│   │   │   ├── (auth)/        # Auth route group
│   │   │   │   ├── sign-in/page.tsx
│   │   │   │   └── sign-up/page.tsx
│   │   │   ├── (dashboard)/   # Authenticated route group
│   │   │   │   ├── layout.tsx
│   │   │   │   ├── page.tsx                    # Dashboard home
│   │   │   │   ├── positions/
│   │   │   │   │   ├── page.tsx                # List positions
│   │   │   │   │   ├── new/page.tsx            # Create position
│   │   │   │   │   └── [id]/page.tsx           # Position detail
│   │   │   │   ├── pipeline/page.tsx           # Pipeline / Kanban Board
│   │   │   │   ├── candidates/
│   │   │   │   │   ├── page.tsx                # Candidate search
│   │   │   │   │   └── [id]/page.tsx           # Candidate profile
│   │   │   │   ├── leaderboard/page.tsx        # Gamification board
│   │   │   │   └── settings/page.tsx           # Brand settings
│   │   │   ├── layout.tsx     # Root layout (fonts)
│   │   │   └── globals.css
│   │   ├── components/
│   │   │   ├── ui/            # Primitives (Button, Card, Badge, Modal, Input)
│   │   │   ├── kanban/        # Kanban board components (@dnd-kit)
│   │   │   │   ├── Board.tsx
│   │   │   │   ├── Column.tsx
│   │   │   │   ├── CandidateCard.tsx
│   │   │   │   └── DragOverlay.tsx
│   │   │   ├── layout/        # Sidebar, Navbar
│   │   │   └── forms/         # PositionForm, CandidateUploadForm
│   │   ├── lib/
│   │   │   ├── api.ts         # Typed fetch wrapper for FastAPI (credentials: "include")
│   │   │   ├── constants.ts
│   │   │   └── utils.ts
│   │   ├── stores/
│   │   │   ├── useAuthStore.ts      # User state
│   │   │   ├── useDashboardStore.ts # Dashboard state (activePositionId)
│   │   │   └── usePipelineStore.ts  # Kanban pipeline state
│   │   └── types/
│   │       └── index.ts       # Shared TypeScript interfaces
│   ├── middleware.ts          # Checks for 'access_token' cookie
│   ├── .env.local
│   ├── next.config.ts
│   ├── tailwind.config.ts
│   ├── tsconfig.json
│   └── package.json
│
├── backend/                   # FastAPI application
│   ├── app/
│   │   ├── main.py            # FastAPI app entry, lifespan, router inclusion, CORS, SessionMiddleware
│   │   ├── config.py          # Pydantic BaseSettings (env vars, JWT_SECRET)
│   │   ├── database.py        # MongoDB / Beanie connection & init
│   │   ├── dependencies.py    # Global deps (get_current_user reading cookie, get_db)
│   │   │
│   │   ├── auth/              # ── Auth Module ──
│   │   │   ├── __init__.py
│   │   │   ├── router.py      # POST /signup, /login, /logout, GET /me, OAuth callback
│   │   │   ├── schemas.py     # UserCreate, UserLogin, TokenPayload
│   │   │   └── models.py      # Beanie Document: User
│   │   │
│   │   ├── brands/            # ── Brands Module ──
│   │   │   ├── __init__.py
│   │   │   ├── router.py      # CRUD endpoints for brands
│   │   │   ├── service.py     # Brand business logic
│   │   │   ├── schemas.py     # BrandCreate, BrandResponse
│   │   │   └── models.py      # Beanie Document: Brand
│   │   │
│   │   ├── positions/         # ── Positions Module ──
│   │   │   ├── __init__.py
│   │   │   ├── router.py      # POST /positions, GET /positions, PATCH etc.
│   │   │   ├── service.py     # Position CRUD + matching orchestration
│   │   │   ├── schemas.py     # PositionCreate, PositionResponse, MatchedCandidate
│   │   │   └── models.py      # Beanie Document: Position
│   │   │
│   │   ├── candidates/        # ── Candidates Module ──
│   │   │   ├── __init__.py
│   │   │   ├── router.py      # GET /candidates, candidate profile
│   │   │   ├── service.py     # Candidate search, skill extraction
│   │   │   ├── schemas.py     # CandidateCreate, CandidateResponse
│   │   │   └── models.py      # Beanie Document: Candidate
│   │   │
│   │   ├── pipeline/          # ── Pipeline / Matching Module ──
│   │   │   ├── __init__.py
│   │   │   ├── router.py      # PATCH /pipeline/match (transactional)
│   │   │   ├── service.py     # Match logic, aggregation pipeline, transaction
│   │   │   └── schemas.py     # MatchRequest, MatchResponse
│   │   │
│   │   ├── gamification/      # ── Gamification Module ──
│   │   │   ├── __init__.py
│   │   │   ├── router.py      # GET /gamify/leaderboard
│   │   │   ├── service.py     # Score calculation, badge assignment, lazy daily reset
│   │   │   ├── schemas.py     # LeaderboardEntry, RecruiterStats
│   │   │   └── models.py      # Beanie Document: RecruiterProfile
│   │   │
│   │   └── storage/           # ── Storage / S3 Module ──
│   │       ├── __init__.py
│   │       ├── router.py      # GET /storage/presign
│   │       ├── service.py     # boto3 presigned URL generation
│   │       ├── schemas.py     # PresignRequest, PresignResponse
│   │       └── webhook.py     # EventBridge / S3 event handler
│   │
│   ├── tests/                 # Mirrors app/ structure
│   ├── Dockerfile
│   ├── requirements.txt
│   ├── .env
│   └── pyproject.toml
│
├── docker-compose.yml         # Local dev: MongoDB replica set
├── .github/
│   └── workflows/
│       ├── frontend-ci.yml
│       └── backend-ci.yml
└── README.md
```

---

## 4. Phase-by-Phase Execution Plan

### Phase 1: Project Scaffolding & Dev Environment

#### 1a. Frontend — Create Next.js App

```bash
cd Recuritement
npx -y create-next-app@latest ./frontend   --typescript   --tailwind   --eslint   --app   --src-dir   --import-alias "@/*"   --turbopack   --use-npm
```

Install dependencies:
```bash
cd frontend
npm install zustand swr @dnd-kit/core @dnd-kit/sortable @dnd-kit/utilities framer-motion
npm install -D @types/node
```

#### 1b. Backend — FastAPI Scaffold
Setup the backend directory structure as defined in the Monorepo Structure.

**`requirements.txt`** (initial):
```text
fastapi>=0.115.0
uvicorn[standard]>=0.32.0
gunicorn>=23.0.0
beanie>=1.27.0
motor>=3.6.0
pydantic-settings>=2.6.0
python-jose[cryptography]>=3.3.0
passlib[bcrypt]>=1.7.4
bcrypt>=4.0.1
authlib>=1.3.0
httpx>=0.28.0
boto3>=1.35.0
python-multipart>=0.0.16
```

#### 1c. Docker Compose — Local MongoDB Replica Set
Use a replica set for local development to support ACID transactions.

```yaml
# docker-compose.yml
services:
  mongo:
    image: mongo:7
    command: ["--replSet", "rs0", "--bind_ip_all"]
    ports:
      - "27017:27017"
    volumes:
      - mongo_data:/data/db

  mongo-init:
    image: mongo:7
    depends_on:
      - mongo
    entrypoint: >
      mongosh --host mongo --eval "rs.initiate({ _id: 'rs0', members: [{ _id: 0, host: 'mongo:27017' }] })"
    restart: "no"

volumes:
  mongo_data:
```

---

### Phase 2: Authentication Layer (Custom JWT + Google OAuth)

#### 2a. Backend Auth Implementation

**`app/main.py`** (CORS Middleware):
```python
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.config import settings

app = FastAPI(title="Eigensu API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"], # Add production domain later
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

**`app/auth/router.py`** (Setting HttpOnly Cookies):
```python
from fastapi import Response, Depends
from app.modules.auth.schemas import UserLogin
from app.modules.auth.router import _set_auth_cookie

@router.post("/login")
async def login(user_in: UserLogin, response: Response):
    # ... verify user ...
    _set_auth_cookie(response, str(user.id))
    return {"status": "ok", "message": "Logged in successfully"}

@router.post("/logout")
async def logout(response: Response):
    response.delete_cookie(key="access_token", httponly=True, secure=_COOKIE_SECURE, samesite="lax")
    return {"status": "ok", "message": "Logged out successfully"}
```

#### 2b. Frontend Auth Integration

**`src/lib/api.ts`** (Credentials include):
```typescript
export async function apiFetch<T>(path: string, options?: RequestInit): Promise<T> {
  const res = await fetch(`${process.env.NEXT_PUBLIC_API_URL}${path}`, {
    ...options,
    credentials: "include", // Crucial for sending HttpOnly cookies
    headers: {
      "Content-Type": "application/json",
      ...options?.headers,
    },
  });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}
```

**`src/middleware.ts`**:
```typescript
import { NextResponse } from 'next/server';
import type { NextRequest } from 'next/server';

export function middleware(request: NextRequest) {
  const token = request.cookies.get('access_token')?.value;

  if (!token && request.nextUrl.pathname.startsWith('/pipeline')) {
    return NextResponse.redirect(new URL('/sign-in', request.url));
  }
  return NextResponse.next();
}

export const config = {
  matcher: ['/pipeline/:path*', '/positions/:path*', '/candidates/:path*', '/settings/:path*'],
};
```

---

### Phase 3: Recruiter Dashboard Frontend (Pipeline)

**`src/app/(dashboard)/pipeline/page.tsx`**:
Implements a 35/65 Master-Detail layout.

```tsx
"use client";
import { PositionList } from '@/components/kanban/PositionList';
import { MatchPanel } from '@/components/kanban/MatchPanel';

export default function PipelinePage() {
  return (
    <div className="flex h-screen bg-gray-50 font-inter">
      <div className="w-[35%] border-r border-gray-200 overflow-y-auto bg-white">
        <PositionList />
      </div>
      <div className="w-[65%] overflow-y-auto bg-gray-50 p-6">
        <MatchPanel />
      </div>
    </div>
  );
}
```

**`src/components/kanban/MatchPanel.tsx`** (Using SWR):
```tsx
"use client";
import useSWR from 'swr';
import { useDashboardStore } from '@/stores/useDashboardStore';
import { apiFetch } from '@/lib/api';

export function MatchPanel() {
  const activePositionId = useDashboardStore((state) => state.activePositionId);

  const { data, error, isLoading } = useSWR(
    activePositionId ? `/api/v1/positions/${activePositionId}/top-candidates` : null,
    apiFetch
  );

  if (!activePositionId) return <div>Select a position to view matches.</div>;
  if (isLoading) return <div>Loading...</div>;
  if (error) return <div>Failed to load matches.</div>;

  return (
    <div className="flex flex-col gap-4">
      <h2 className="text-xl font-bold mb-4">Top 10 Matches</h2>
      {data.candidates.map((candidate: any) => (
         <div key={candidate.id} className="p-4 bg-white rounded-lg shadow">
             {/* Render Candidate Details */}
             <h3 className="font-semibold">{candidate.name}</h3>
             <p>Score: {(candidate.match_score * 100).toFixed(0)}%</p>
         </div>
      ))}
    </div>
  );
}
```

---

### Phase 4: Core Business Logic (FastAPI)

#### 4a. Keyword Matching Engine (MongoDB Aggregation)
The match calculation ($Score = \frac{|Keywords_{Candidate} \cap Keywords_{Job}|}{|Keywords_{Job}|}$) must be executed at the database layer.

```python
# app/pipeline/service.py
async def find_top_candidates(position_id: str, limit: int = 10) -> list[dict]:
    position = await Position.get(PydanticObjectId(position_id))
    job_keywords = [kw.lower() for kw in position.requirements]

    pipeline = [
        {
            "$addFields": {
                "normalized_skills": {
                    "$map": {
                        "input": "$extracted_skills",
                        "as": "s",
                        "in": {"$toLower": "$$s"},
                    }
                }
            }
        },
        {
            "$addFields": {
                "match_score": {
                    "$cond": {
                        "if": {"$gt": [len(job_keywords), 0]},
                        "then": {
                            "$divide": [
                                {
                                    "$size": {
                                        "$setIntersection": [
                                            "$normalized_skills",
                                            job_keywords,
                                        ]
                                    }
                                },
                                len(job_keywords),
                            ]
                        },
                        "else": 0,
                    }
                }
            }
        },
        {"$match": {"match_score": {"$gt": 0}}},
        {"$sort": {"match_score": -1}},
        {"$limit": limit},
        {
            "$project": {
                "id": {"$toString": "$_id"},
                "name": 1,
                "email": 1,
                "resume_url": 1,
                "extracted_skills": 1,
                "match_score": 1,
            }
        },
    ]

    return await Candidate.aggregate(pipeline).to_list()
```

#### 4b. Transactional Match (Gamification + Pipeline)
When a recruiter matches a candidate, the system updates both Position and Recruiter simultaneously using `ClientSession.start_transaction()`.

---

### Phase 5: Storage & S3

#### 5a. S3 Presigned URL Flow
Use `boto3.client('s3').generate_presigned_url` to allow the Next.js frontend to upload resumes directly to S3, bypassing FastAPI.

---

## 6. API Contract Summary

| Endpoint | Method | Auth | Description | Status |
|:---|:---|:---|:---|:---|
| `/api/v1/auth/login` | `POST` | None | Verify credentials, return `access_token` HttpOnly cookie | ✅ Implemented |
| `/api/v1/auth/logout` | `POST` | Cookie | Clear `access_token` cookie | ✅ Implemented |
| `/api/v1/auth/me` | `GET` | Cookie | Validate token, return user info | ✅ Implemented |
| `/api/v1/auth/google/login` | `GET` | None | Redirects to Google Consent Screen | ✅ Implemented |
| `/api/v1/auth/google/callback` | `GET` | None | Google OAuth authorization code callback | ✅ Implemented |
| `/api/v1/positions` | `GET` | Cookie | List positions for active brand | ✅ Implemented |
| `/api/v1/pipeline/top-candidates` | `GET` | Cookie | Run aggregation, return top matches | ✅ Implemented |
| `/api/v1/pipeline/match` | `PATCH` | Cookie | Move candidate → position (transaction) | ✅ Implemented |
| `/api/v1/candidates` | `POST` | Cookie | Create candidate record | ✅ Implemented |
| `/api/v1/gamify/leaderboard` | `GET` | Cookie | Recruiter rankings | ✅ Implemented |
| `/api/v1/storage/presign` | `GET` | Cookie | Generate S3 presigned upload URL | ✅ Implemented |

---

## 7. Environment Variables

### Frontend (`.env.local`)
```env
NEXT_PUBLIC_API_URL=http://localhost:8000
```

### Backend (`.env`)
```env
JWT_SECRET=your_generated_secret_key
MONGODB_URI=mongodb://localhost:27017/eigensu?replicaSet=rs0
MONGODB_DB_NAME=eigensu
GOOGLE_CLIENT_ID=...
GOOGLE_CLIENT_SECRET=...
GOOGLE_REDIRECT_URI=http://localhost:8000/api/v1/auth/google/callback
AWS_ACCESS_KEY_ID=...
AWS_SECRET_ACCESS_KEY=...
AWS_REGION=us-east-1
S3_BUCKET_NAME=eigensu-resumes
```
