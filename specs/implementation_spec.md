# Eigensu v1.0 — Gamified Recruitment CRM: Implementation Specification

## 1. Overview

Build a gamified, multi-tenant recruitment CRM called **Eigensu** with:

- **Frontend** — Next.js 16+ (App Router, Tailwind CSS, Zustand, @dnd-kit)
- **Backend** — FastAPI (Python, domain-driven modules, Beanie ODM)
- **Database** — MongoDB Atlas (Replica Set for ACID transactions)
- **Auth** — Clerk (managed, multi-tenant B2B)
- **Storage** — AWS S3 (presigned URL uploads for resumes)
- **Deployment** — Vercel (frontend) · Railway (backend) · S3 (assets)

---

## 2. User Review Required

> [!IMPORTANT]
> **Clerk Setup**: You'll need a Clerk account and a configured application with:
>
> - An organization model for **Brands** (multi-tenant)
> - A JWT template named `fastapi` exposing `org_id`, `sub`, and custom claims
> - Webhook endpoint for `user.created` / `organization.created` sync events

> [!IMPORTANT]
> **AWS Credentials**: An S3 bucket, IAM user with `s3:PutObject` / `s3:GetObject`, and EventBridge enabled on the bucket are required before Phase 4.

> [!WARNING]
> **MongoDB Atlas**: The cluster must be a Replica Set (not a standalone instance) to support multi-document ACID transactions used by the gamification engine. The free M0 tier **does** support replica sets.

---

## 3. Monorepo Structure

```
Recuritement/
├── frontend/                  # Next.js app (created via create-next-app)
│   ├── public/
│   ├── src/
│   │   ├── app/               # App Router pages & layouts
│   │   │   ├── (auth)/        # Clerk sign-in/sign-up route group
│   │   │   │   ├── sign-in/[[...sign-in]]/page.tsx
│   │   │   │   └── sign-up/[[...sign-up]]/page.tsx
│   │   │   ├── (dashboard)/   # Authenticated route group
│   │   │   │   ├── layout.tsx
│   │   │   │   ├── page.tsx                    # Dashboard home
│   │   │   │   ├── positions/
│   │   │   │   │   ├── page.tsx                # List positions
│   │   │   │   │   ├── new/page.tsx            # Create position
│   │   │   │   │   └── [id]/
│   │   │   │   │       ├── page.tsx            # Position detail
│   │   │   │   │       └── pipeline/page.tsx   # Kanban pipeline
│   │   │   │   ├── candidates/
│   │   │   │   │   ├── page.tsx                # Candidate search
│   │   │   │   │   └── [id]/page.tsx           # Candidate profile
│   │   │   │   ├── leaderboard/page.tsx        # Gamification board
│   │   │   │   └── settings/page.tsx           # Brand settings
│   │   │   ├── layout.tsx     # Root layout (ClerkProvider, fonts)
│   │   │   └── globals.css
│   │   ├── components/
│   │   │   ├── ui/            # Primitives (Button, Card, Badge, Modal, Input)
│   │   │   ├── kanban/        # Kanban board components (@dnd-kit)
│   │   │   │   ├── Board.tsx
│   │   │   │   ├── Column.tsx
│   │   │   │   ├── CandidateCard.tsx
│   │   │   │   └── DragOverlay.tsx
│   │   │   ├── layout/        # Sidebar, Navbar, BrandSwitcher
│   │   │   └── forms/         # PositionForm, CandidateUploadForm
│   │   ├── lib/
│   │   │   ├── api.ts         # Typed fetch wrapper for FastAPI
│   │   │   ├── constants.ts
│   │   │   └── utils.ts
│   │   ├── stores/
│   │   │   ├── useAuthStore.ts      # Clerk user + org state
│   │   │   └── usePipelineStore.ts  # Kanban pipeline state
│   │   └── types/
│   │       └── index.ts       # Shared TypeScript interfaces
│   ├── .env.local
│   ├── next.config.ts
│   ├── tailwind.config.ts
│   ├── tsconfig.json
│   └── package.json
│
├── backend/                   # FastAPI application
│   ├── app/
│   │   ├── main.py            # FastAPI app entry, lifespan, router inclusion
│   │   ├── config.py          # Pydantic BaseSettings (env vars)
│   │   ├── database.py        # MongoDB / Beanie connection & init
│   │   ├── dependencies.py    # Global deps (get_current_user, get_db, etc.)
│   │   │
│   │   ├── auth/              # ── Auth Module ──
│   │   │   ├── __init__.py
│   │   │   ├── router.py      # GET /api/v1/auth/verify
│   │   │   ├── service.py     # Clerk JWT decode & validation logic
│   │   │   ├── schemas.py     # TokenPayload, UserInfo response models
│   │   │   ├── clerk.py       # Clerk JWKS fetcher & caching
│   │   │   └── webhooks.py    # Clerk organization.created → Brand sync
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
│   │   │   ├── service.py     # Score calculation, badge assignment, daily reset
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
│   │   ├── conftest.py
│   │   ├── test_auth/
│   │   ├── test_brands/
│   │   ├── test_positions/
│   │   ├── test_candidates/
│   │   ├── test_pipeline/
│   │   ├── test_gamification/
│   │   └── test_storage/
│   │
│   ├── Dockerfile
│   ├── requirements.txt
│   ├── .env
│   └── pyproject.toml
│
├── docker-compose.yml         # Local dev: MongoDB replica set + backend
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
npx -y create-next-app@latest ./frontend \
  --typescript \
  --tailwind \
  --eslint \
  --app \
  --src-dir \
  --import-alias "@/*" \
  --turbopack \
  --use-npm
```

Then install additional dependencies:

```bash
cd frontend
npm install @clerk/nextjs zustand @dnd-kit/core @dnd-kit/sortable @dnd-kit/utilities
npm install -D @types/node
```

**Font setup** — Replace the default font with **Inter** in `src/app/layout.tsx`:

```tsx
import { Inter } from "next/font/google";
const inter = Inter({ subsets: ["latin"], variable: "--font-inter" });
```

#### 1b. Backend — FastAPI Scaffold

```bash
cd Recuritement
mkdir -p backend/app/{auth,brands,positions,candidates,pipeline,gamification,storage}
mkdir -p backend/tests/{test_auth,test_brands,test_positions,test_candidates,test_pipeline,test_gamification,test_storage}
touch backend/app/__init__.py
touch backend/app/{main,config,database,dependencies}.py
```

**`requirements.txt`** (initial):

```
fastapi>=0.115.0
uvicorn[standard]>=0.32.0
gunicorn>=23.0.0
beanie>=1.27.0
motor>=3.6.0
pydantic-settings>=2.6.0
pyjwt[crypto]>=2.9.0
httpx>=0.28.0
boto3>=1.35.0
python-multipart>=0.0.16
pymupdf>=1.24.0
```

> [!NOTE]
> **No Celery/Redis** — MVP uses `FastAPI BackgroundTasks` for async work (resume parsing, email triggers). Celery can be introduced later if concurrent upload volume demands it.

**`pyproject.toml`** — Standard Python project config with linting/formatting (ruff).

#### 1c. Docker Compose — Local MongoDB Replica Set

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

### Phase 2: Authentication Layer (Clerk ↔ FastAPI)

#### 2a. Frontend — Clerk Integration

**`src/app/layout.tsx`** — Wrap with `<ClerkProvider>`:

```tsx
import { ClerkProvider } from "@clerk/nextjs";

export default function RootLayout({ children }) {
  return (
    <ClerkProvider>
      <html lang="en">
        <body className={inter.variable}>{children}</body>
      </html>
    </ClerkProvider>
  );
}
```

**Route groups**:

- `(auth)/sign-in/[[...sign-in]]/page.tsx` — `<SignIn />`
- `(auth)/sign-up/[[...sign-up]]/page.tsx` — `<SignUp />`
- `(dashboard)/layout.tsx` — Protected via Clerk middleware

**`middleware.ts`** (root) — Clerk's `authMiddleware` to protect `(dashboard)` routes.

#### 2c. Clerk Organization Webhook → Brand Sync

When a brand signs up through Clerk and creates an organization, a Clerk `organization.created` webhook will fire. The FastAPI backend must listen for this event and auto-create the corresponding `Brand` document in MongoDB.

**`app/auth/webhooks.py`**:

```python
from svix.webhooks import Webhook
from app.brands.service import create_brand_from_clerk_org

@router.post("/webhooks/clerk")
async def handle_clerk_webhook(request: Request):
    """Receives Clerk webhook events (organization.created, user.created)."""
    payload = await request.body()
    headers = dict(request.headers)

    # Verify signature using Clerk webhook signing secret
    wh = Webhook(settings.CLERK_WEBHOOK_SECRET)
    event = wh.verify(payload, headers)

    if event["type"] == "organization.created":
        org_data = event["data"]
        await create_brand_from_clerk_org(
            clerk_org_id=org_data["id"],
            name=org_data["name"],
            domain=org_data.get("slug", org_data["id"]),
        )

    return {"status": "ok"}
```

> [!NOTE]
> Add `svix>=1.40.0` to `requirements.txt`. Register the webhook URL in Clerk Dashboard → Webhooks → endpoint: `https://your-api.com/api/v1/auth/webhooks/clerk`.

**`src/lib/api.ts`** — Typed fetch wrapper that auto-attaches the Clerk JWT:

```tsx
import { useAuth } from "@clerk/nextjs";

export async function apiFetch<T>(
  path: string,
  options?: RequestInit,
): Promise<T> {
  const { getToken } = useAuth();
  const token = await getToken({ template: "fastapi" });
  const res = await fetch(`${process.env.NEXT_PUBLIC_API_URL}${path}`, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${token}`,
      ...options?.headers,
    },
  });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}
```

#### 2b. Backend — JWT Verification Module

**`app/auth/clerk.py`** — JWKS fetch with caching:

```python
import httpx
import jwt
from functools import lru_cache

CLERK_JWKS_URL = "https://{YOUR_CLERK_FRONTEND_API}/.well-known/jwks.json"

@lru_cache(maxsize=1)
def get_jwks():
    response = httpx.get(CLERK_JWKS_URL)
    return response.json()

def decode_clerk_token(token: str) -> dict:
    jwks = get_jwks()
    header = jwt.get_unverified_header(token)
    key = next(k for k in jwks["keys"] if k["kid"] == header["kid"])
    public_key = jwt.algorithms.RSAAlgorithm.from_jwk(key)
    return jwt.decode(token, public_key, algorithms=["RS256"],
                      audience=settings.CLERK_JWT_AUDIENCE)
```

**`app/dependencies.py`** — Global dependency:

```python
from fastapi import Depends, HTTPException
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

security = HTTPBearer()

async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
) -> TokenPayload:
    try:
        payload = decode_clerk_token(credentials.credentials)
        return TokenPayload(**payload)
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid token")
```

---

### Phase 3: Data Models & Core CRUD

#### 3a. Beanie Document Models

**`app/brands/models.py`**:

```python
from beanie import Document
from pydantic import Field
from datetime import datetime

class Branding(BaseModel):
    logo_url: str | None = None

class Brand(Document):
    clerk_org_id: str = Field(..., unique=True)
    name: str
    domain: str = Field(..., unique=True)
    branding: Branding = Field(default_factory=Branding)
    created_at: datetime = Field(default_factory=datetime.utcnow)

    class Settings:
        name = "brands"
        indexes = ["clerk_org_id", "domain"]
```

**`app/positions/models.py`**:

```python
class MatchedCandidate(BaseModel):
    candidate_id: PydanticObjectId
    status: Literal["pending", "accepted", "rejected"] = "pending"
    feedback: str | None = None

class Position(Document):
    brand_id: PydanticObjectId
    title: str
    requirements: list[str] = []          # keywords
    status: Literal["open", "filled", "archived"] = "open"
    matched_candidates: list[MatchedCandidate] = []

    class Settings:
        name = "positions"
        indexes = ["brand_id", "status"]
```

**`app/candidates/models.py`**:

```python
class Candidate(Document):
    name: str
    email: str
    phone: str | None = None
    resume_s3_key: str | None = None
    extracted_skills: list[str] = []

    class Settings:
        name = "candidates"
        indexes = [
            "email",
            [("extracted_skills", 1)],  # For aggregation intersection
        ]
```

**`app/gamification/models.py`**:

```python
class RecruiterProfile(Document):
    clerk_user_id: str = Field(..., unique=True)
    brand_id: PydanticObjectId
    daily_score: int = 0
    weekly_score: int = 0
    badges: list[str] = []
    last_reset: datetime = Field(default_factory=datetime.utcnow)

    class Settings:
        name = "recruiters"
        indexes = ["clerk_user_id", "brand_id"]
```

#### 3b. Database Initialization

**`app/database.py`**:

```python
from beanie import init_beanie
from motor.motor_asyncio import AsyncIOMotorClient
from app.config import settings
from app.brands.models import Brand
from app.positions.models import Position
from app.candidates.models import Candidate
from app.gamification.models import RecruiterProfile

async def init_db():
    client = AsyncIOMotorClient(settings.MONGODB_URI)
    await init_beanie(
        database=client[settings.MONGODB_DB_NAME],
        document_models=[Brand, Position, Candidate, RecruiterProfile],
    )
```

**`app/main.py`** — FastAPI lifespan:

```python
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.database import init_db

@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    yield

app = FastAPI(title="Eigensu API", version="1.0.0", lifespan=lifespan)

app.add_middleware(CORSMiddleware, allow_origins=["*"], ...)  # tighten for prod

# Include routers
from app.auth.router import router as auth_router
from app.brands.router import router as brands_router
from app.positions.router import router as positions_router
from app.candidates.router import router as candidates_router
from app.pipeline.router import router as pipeline_router
from app.gamification.router import router as gamification_router
from app.storage.router import router as storage_router

app.include_router(auth_router,         prefix="/api/v1/auth",     tags=["Auth"])
app.include_router(brands_router,       prefix="/api/v1/brands",   tags=["Brands"])
app.include_router(positions_router,    prefix="/api/v1/positions", tags=["Positions"])
app.include_router(candidates_router,   prefix="/api/v1/candidates", tags=["Candidates"])
app.include_router(pipeline_router,     prefix="/api/v1/pipeline",   tags=["Pipeline"])
app.include_router(gamification_router, prefix="/api/v1/gamify",     tags=["Gamification"])
app.include_router(storage_router,      prefix="/api/v1/storage",    tags=["Storage"])
```

---

### Phase 4: Core Business Logic

#### 4a. Keyword Matching Engine (MongoDB Aggregation)

**`app/pipeline/service.py`**:

The matching score is calculated **at the database layer** using `$setIntersection`:

```python
async def find_top_candidates(position_id: PydanticObjectId, limit: int = 10):
    position = await Position.get(position_id)
    job_keywords = position.requirements

    pipeline = [
        {
            "$addFields": {
                "match_score": {
                    "$divide": [
                        {"$size": {"$setIntersection": ["$extracted_skills", job_keywords]}},
                        max(len(job_keywords), 1),
                    ]
                }
            }
        },
        {"$match": {"match_score": {"$gt": 0}}},
        {"$sort": {"match_score": -1}},
        {"$limit": limit},
    ]

    return await Candidate.aggregate(pipeline).to_list()
```

#### 4b. Transactional Match (Gamification + Pipeline)

**`app/pipeline/service.py`** — Atomic move-to-pipeline:

```python
from motor.motor_asyncio import AsyncIOMotorClient

async def match_candidate_to_position(
    position_id: PydanticObjectId,
    candidate_id: PydanticObjectId,
    recruiter_id: str,
):
    client: AsyncIOMotorClient = Position.get_motor_collection().database.client

    async with await client.start_session() as session:
        async with session.start_transaction():
            # 1. Add candidate to position's matched list
            await Position.find_one(Position.id == position_id).update(
                {"$push": {"matched_candidates": {
                    "candidate_id": candidate_id,
                    "status": "pending",
                    "feedback": None,
                }}},
                session=session,
            )

            # 2. Increment recruiter score
            await RecruiterProfile.find_one(
                RecruiterProfile.clerk_user_id == recruiter_id
            ).update(
                {"$inc": {"daily_score": 10, "weekly_score": 10}},
                session=session,
            )
    # Transaction auto-commits or rolls back
```

#### 4c. S3 Presigned URL Flow

**`app/storage/service.py`**:

```python
import boto3
from app.config import settings

s3 = boto3.client(
    "s3",
    aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
    aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
    region_name=settings.AWS_REGION,
)

def generate_presigned_upload_url(filename: str, content_type: str) -> str:
    key = f"resumes/{uuid4()}/{filename}"
    url = s3.generate_presigned_url(
        "put_object",
        Params={
            "Bucket": settings.S3_BUCKET_NAME,
            "Key": key,
            "ContentType": content_type,
        },
        ExpiresIn=600,  # 10 minutes
    )
    return url, key
```

**`app/storage/webhook.py`** — EventBridge S3 event handler:

> [!WARNING]
> **Webhook Security**: This endpoint must verify incoming requests via either:
> - A shared secret token in the `X-Webhook-Secret` header (checked against `settings.S3_WEBHOOK_SECRET`), or
> - AWS Signature V4 verification on the request.
> Without this, anyone can hit the endpoint and trigger expensive parsing tasks.

```python
from fastapi import BackgroundTasks, Header, HTTPException

@router.post("/webhook/s3")
async def handle_s3_event(
    event: S3Event,
    background_tasks: BackgroundTasks,
    x_webhook_secret: str = Header(...),
):
    """Called by EventBridge when a resume is uploaded to S3."""
    if x_webhook_secret != settings.S3_WEBHOOK_SECRET:
        raise HTTPException(status_code=403, detail="Invalid webhook secret")

    s3_key = event.detail.object.key
    # Phase 1: stub — extract text only (pymupdf)
    # Phase 2: pipe extracted text to LLM for structured skill extraction
    background_tasks.add_task(parse_resume_and_extract_skills, s3_key)
    return {"status": "processing"}
```

---

### Phase 5: Frontend Feature Build

#### 5a. Zustand Stores

**`src/stores/useAuthStore.ts`**:

```ts
import { create } from "zustand";

interface AuthState {
  activeBrandId: string | null;
  setActiveBrand: (id: string) => void;
}

export const useAuthStore = create<AuthState>((set) => ({
  activeBrandId: null,
  setActiveBrand: (id) => set({ activeBrandId: id }),
}));
```

**`src/stores/usePipelineStore.ts`**:

```ts
interface PipelineState {
  columns: Record<string, CandidateCard[]>;
  moveCard: (cardId: string, from: string, to: string) => void;
}

export const usePipelineStore = create<PipelineState>((set) => ({
  columns: { pending: [], accepted: [], rejected: [] },
  moveCard: (cardId, from, to) =>
    set((state) => {
      const card = state.columns[from].find((c) => c.id === cardId);
      if (!card) return state;
      return {
        columns: {
          ...state.columns,
          [from]: state.columns[from].filter((c) => c.id !== cardId),
          [to]: [...state.columns[to], card],
        },
      };
    }),
}));
```

#### 5b. Kanban Board (@dnd-kit)

> [!TIP]
> **Sensor Configuration**: Default HTML5 drag-and-drop is buggy with custom React components. Always configure `PointerSensor` (or `MouseSensor` + `TouchSensor`) with an activation constraint to ensure fluid 60fps interaction and prevent accidental drags on click.

**`src/components/kanban/Board.tsx`** (key structure):

```tsx
"use client";

import {
  DndContext,
  DragOverlay,
  closestCorners,
  PointerSensor,
  useSensor,
  useSensors,
} from "@dnd-kit/core";
import { SortableContext } from "@dnd-kit/sortable";

export function KanbanBoard({ positionId }: { positionId: string }) {
  const { columns, moveCard } = usePipelineStore();
  const [activeCard, setActiveCard] = useState<CandidateCard | null>(null);

  // Require 8px of movement before activating drag — prevents accidental drags
  const sensors = useSensors(
    useSensor(PointerSensor, {
      activationConstraint: { distance: 8 },
    }),
  );

  function handleDragEnd(event: DragEndEvent) {
    const { active, over } = event;
    if (!over) return;
    const fromCol = findColumn(active.id);
    const toCol = findColumn(over.id);
    if (fromCol !== toCol) {
      moveCard(active.id as string, fromCol, toCol);
      // Fire API call: PATCH /api/v1/pipeline/match
      matchCandidate(positionId, active.id as string, toCol);
    }
    setActiveCard(null);
  }

  return (
    <DndContext
      sensors={sensors}
      collisionDetection={closestCorners}
      onDragEnd={handleDragEnd}
    >
      {Object.entries(columns).map(([colId, cards]) => (
        <SortableContext key={colId} items={cards.map((c) => c.id)}>
          <KanbanColumn id={colId} cards={cards} />
        </SortableContext>
      ))}
      <DragOverlay>
        {activeCard && <CandidateCard card={activeCard} />}
      </DragOverlay>
    </DndContext>
  );
}
```

#### 5c. Resume Upload Component

```tsx
"use client";

export function ResumeUploader() {
  async function handleUpload(file: File) {
    // 1. Get presigned URL from backend
    const { url, key } = await apiFetch<PresignResponse>(
      `/storage/presign?filename=${file.name}&content_type=${file.type}`,
    );

    // 2. Upload directly to S3
    await fetch(url, {
      method: "PUT",
      body: file,
      headers: { "Content-Type": file.type },
    });

    // 3. Confirm upload to backend
    await apiFetch("/candidates", {
      method: "POST",
      body: JSON.stringify({ resume_s3_key: key, name: "...", email: "..." }),
    });
  }

  return <DropZone onDrop={handleUpload} />;
}
```

---

### Phase 6: Deployment & CI/CD

#### 6a. Frontend → Vercel

- Connect the `frontend/` directory to Vercel
- Set environment variables:
  - `NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY`
  - `CLERK_SECRET_KEY`
  - `NEXT_PUBLIC_API_URL` (Railway backend URL)

#### 6b. Backend → Railway

**`Dockerfile`**:

```dockerfile
FROM python:3.12-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app/ app/

CMD ["gunicorn", "app.main:app", "-w", "4", "-k", "uvicorn.workers.UvicornWorker", "--bind", "0.0.0.0:8000"]
```

Railway environment variables:

- `MONGODB_URI`
- `MONGODB_DB_NAME`
- `CLERK_JWKS_URL`
- `CLERK_JWT_AUDIENCE`
- `AWS_ACCESS_KEY_ID` / `AWS_SECRET_ACCESS_KEY` / `AWS_REGION` / `S3_BUCKET_NAME`

#### 6c. GitHub Actions CI

**`.github/workflows/backend-ci.yml`**:

- Lint with `ruff`
- Type check with `mypy`
- Run `pytest` with a MongoDB service container

**`.github/workflows/frontend-ci.yml`**:

- `npm ci && npm run lint && npm run build`

---

## 5. API Contract Summary

| Endpoint                                | Method  | Auth   | Module         | Description                              |
| :-------------------------------------- | :------ | :----- | :------------- | :--------------------------------------- |
| `/api/v1/auth/verify`                   | `GET`   | Bearer | `auth`         | Validate Clerk JWT, return user info     |
| `/api/v1/brands`                        | `GET`   | Bearer | `brands`       | List brands for current org              |
| `/api/v1/brands`                        | `POST`  | Bearer | `brands`       | Create a new brand                       |
| `/api/v1/positions`                     | `GET`   | Bearer | `positions`    | List positions for active brand          |
| `/api/v1/positions`                     | `POST`  | Bearer | `positions`    | Create a new job opening                 |
| `/api/v1/positions/{id}`                | `GET`   | Bearer | `positions`    | Get position detail + matched candidates |
| `/api/v1/positions/{id}/top-candidates` | `GET`   | Bearer | `pipeline`     | Run aggregation, return top 10 matches   |
| `/api/v1/pipeline/match`                | `PATCH` | Bearer | `pipeline`     | Move candidate → position (transaction)  |
| `/api/v1/candidates`                    | `GET`   | Bearer | `candidates`   | Search / list candidates                 |
| `/api/v1/candidates`                    | `POST`  | Bearer | `candidates`   | Create candidate record                  |
| `/api/v1/candidates/{id}`               | `GET`   | Bearer | `candidates`   | Get candidate profile                    |
| `/api/v1/gamify/leaderboard`            | `GET`   | Bearer | `gamification` | Recruiter rankings (daily/weekly)        |
| `/api/v1/storage/presign`               | `GET`   | Bearer | `storage`      | Generate S3 presigned upload URL         |
| `/api/v1/storage/webhook/s3`            | `POST`  | None\* | `storage`      | EventBridge callback (IP-restricted)     |

---

## 6. Environment Variables

### Frontend (`.env.local`)

```env
NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY=pk_test_...
CLERK_SECRET_KEY=sk_test_...
NEXT_PUBLIC_CLERK_SIGN_IN_URL=/sign-in
NEXT_PUBLIC_CLERK_SIGN_UP_URL=/sign-up
NEXT_PUBLIC_API_URL=http://localhost:8000
```

### Backend (`.env`)

```env
MONGODB_URI=mongodb://localhost:27017/eigensu?replicaSet=rs0
MONGODB_DB_NAME=eigensu
CLERK_JWKS_URL=https://your-clerk-instance.clerk.accounts.dev/.well-known/jwks.json
CLERK_JWT_AUDIENCE=your-clerk-audience
AWS_ACCESS_KEY_ID=AKIA...
AWS_SECRET_ACCESS_KEY=...
AWS_REGION=us-east-1
S3_BUCKET_NAME=eigensu-resumes
```

---

## 7. Verification Plan

### Automated Tests

| What                  | How                                                                 |
| :-------------------- | :------------------------------------------------------------------ |
| Backend unit tests    | `pytest backend/tests/ -v` — each module tested in isolation        |
| Backend integration   | `pytest` with a real MongoDB replica set container (docker-compose) |
| Frontend lint + build | `cd frontend && npm run lint && npm run build`                      |
| API contract          | `httpx.AsyncClient` hitting lifespan-initialized FastAPI test app   |

### Manual Verification

1. **Auth flow**: Sign up via Clerk → redirect to dashboard → verify JWT arrives at FastAPI
2. **CRUD**: Create a brand, create a position with keywords, upload a candidate resume
3. **Matching**: Verify the aggregation pipeline returns scored candidates
4. **Kanban drag**: Drag a candidate card between columns → verify transactional update
5. **Leaderboard**: Check recruiter score increments after a match
6. **S3 upload**: Upload a resume → confirm S3 object exists → verify EventBridge triggers webhook

---

## Architectural Decisions (Finalized)

The following decisions have been locked in for the v1.0 release:

### ✅ Resume Parsing — LLM-based (Phased)

- **Phase 1**: Stub implementation — use `pymupdf` to extract raw text from uploaded PDFs. Store text in `Candidate.extracted_skills` as an empty array (manual entry fallback).
- **Phase 2**: Pipe extracted text to an LLM endpoint (OpenAI / Gemini) with a strict JSON schema to extract structured skills. Skip legacy libraries like `pyresparser`.

### ✅ Background Processing — FastAPI BackgroundTasks (No Celery)

- Use `FastAPI BackgroundTasks` exclusively for the MVP. This avoids spinning up a Redis instance and the associated DevOps overhead.
- All async work (resume parsing, email triggers) runs in-process via `background_tasks.add_task()`.
- **Upgrade path**: If the platform scales to thousands of concurrent uploads, refactor to Celery + Redis. The `service.py` functions are already decoupled, making this a drop-in swap.

### ✅ Daily Score Reset — Lazy Evaluation

No CRON job or Celery Beat. Scores are reset **lazily** on read/write:

```python
# app/gamification/service.py
from datetime import date, datetime

async def get_recruiter_with_reset(clerk_user_id: str) -> RecruiterProfile:
    """Fetch recruiter profile, lazily resetting daily score if stale."""
    recruiter = await RecruiterProfile.find_one(
        RecruiterProfile.clerk_user_id == clerk_user_id
    )
    if recruiter and recruiter.last_reset.date() < date.today():
        recruiter.daily_score = 0
        recruiter.last_reset = datetime.utcnow()
        await recruiter.save()
    return recruiter
```

> [!NOTE]
> This pattern saves server resources by avoiding scheduled tasks entirely. The tradeoff is a single extra date comparison on every score query — negligible at CRM scale.
