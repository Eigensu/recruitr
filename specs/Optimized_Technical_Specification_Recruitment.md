# Technical Specification: Gamified Recruitment CRM (Eigensu v1.0)

## 1. System Architecture
The application is a high-performance, decoupled web ecosystem built for scalability, real-time interaction, and data consistency.

### 1.1 Frontend (Next.js 14+)
* **Framework:** Next.js with App Router for server-side rendering (SSR) and optimized routing.
* **Styling:** Tailwind CSS utilizing the **Inter** typeface for professional, geometric clarity.
* **State Management:** Zustand for lightweight global state (User Auth, Active Brand).
* **Interactions:** `@dnd-kit` for the drag-and-drop Kanban engine, ensuring 60fps interaction speed.

### 1.2 Backend (FastAPI)
* **Framework:** FastAPI (Python) for asynchronous, high-speed execution of CRM logic.
* **Authentication:** **Clerk** (Managed Auth) to handle B2B multi-tenant routing (verifying Brand vs. Recruiter organizations). FastAPI will verify the incoming Bearer JWT tokens.
* **Worker Service:** `Celery` or `FastAPI BackgroundTasks` for asynchronous processes like email triggers.

### 1.3 Database (MongoDB Replica Set)
* **Cluster:** MongoDB Atlas (Cloud) configured as a **Replica Set** to support multi-document ACID transactions, critical for gamification data integrity.

---

## 2. Infrastructure & File Handling

### 2.1 The Presigned URL Flow (Resumes)
To prevent the FastAPI backend from becoming a bottleneck during high-volume document ingestion:
1.  Next.js client requests a temporary, secure upload link from FastAPI.
2.  Next.js uploads the PDF/Word resume *directly* from the user's browser to an **AWS S3** bucket.
3.  S3 triggers an EventBridge webhook back to FastAPI to initiate the asynchronous parsing worker.

---

## 3. Detailed Data Models

### 3.1 Brands Collection
```json
{
  "_id": "ObjectId",
  "clerk_org_id": "string",
  "name": "string",
  "domain": "string (unique)",
  "branding": {
    "logo_url": "string"
  },
  "created_at": "datetime"
}
```

### 3.2 Positions Collection
```json
{
  "_id": "ObjectId",
  "brand_id": "ObjectId",
  "title": "string",
  "requirements": ["keyword1", "keyword2"],
  "status": "string (open | filled | archived)",
  "matched_candidates": [
    {
      "candidate_id": "ObjectId",
      "status": "string (pending | accepted | rejected)",
      "feedback": "string"
    }
  ]
}
```

### 3.3 Candidates & Gamification
* **Candidates:** Stores personal data, `resume_s3_key`, and an array of `extracted_skills`.
* **Recruiters (Gamification):**
    * `clerk_user_id`: string
    * `daily_score`: integer (Reset every 24h)
    * `badges`: Array of strings (e.g., `["speed_demon", "quality_sourcer"]`)

---

## 4. Core Logic Engines

### 4.1 Keyword Matching Engine (Database Layer)
To ensure performance at scale, the match calculation ($Score = \frac{|Keywords_{Candidate} \cap Keywords_{Job}|}{|Keywords_{Job}|}$) must be executed at the database layer, not in Python memory.

* **Implementation:** Use a **MongoDB Aggregation Pipeline** utilizing the `$setIntersection` operator. The pipeline will filter candidates, calculate the intersection score, sort descending, and return only the "Top 10" to FastAPI.

### 4.2 Gamification & Drag-and-Drop (Transactional)
When a recruiter matches a candidate, the system must update both the Position and the Recruiter simultaneously.
* **Implementation:** The FastAPI `/match` endpoint must wrap the database updates in a `ClientSession.start_transaction()` block. If the server crashes after updating the Position but before updating the Recruiter's score, the transaction rolls back, preventing data corruption.

---

## 5. API Endpoints (FastAPI)

| Endpoint | Method | Purpose |
| :--- | :--- | :--- |
| `/api/v1/auth/verify` | GET | Validates Clerk JWT tokens |
| `/api/v1/positions` | POST | Brand creates a new job opening |
| `/api/v1/storage/presign`| GET | Generates AWS S3 upload URL |
| `/api/v1/pipeline/match` | PATCH | Moves a candidate to a job (Executes DB Transaction) |
| `/api/v1/gamify/leaderboard` | GET | Fetches recruiter rankings by daily/weekly points |

---

## 6. Deployment Pipeline
* **Development:** Built using **Cursor** and **GitHub Copilot** to maintain high coding standards.
* **CI/CD:** GitHub Actions triggers.
* **Infrastructure:** * Frontend: Vercel.
    * API: Railway (using Gunicorn with Uvicorn workers).
    * Storage: AWS S3.
