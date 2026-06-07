/**
 * Shared TypeScript interfaces for the Eigensu CRM.
 * These mirror the FastAPI Pydantic response schemas.
 */

// ── Auth ──────────────────────────────────────────────────────────────────────

export interface UserInfo {
  user_id: string;
  org_id: string | null;
  org_role: string | null;
}

// ── Brands ───────────────────────────────────────────────────────────────────

export interface Brand {
  id: string;
  owner_id: string;
  name: string;
  domain: string;
  branding: {
    logo_public_id: string | null;
    logo_url: string | null;
  };
  created_at: string;
}

// ── Positions ────────────────────────────────────────────────────────────────

export type CandidateStatus = "pending" | "accepted" | "rejected";
export type PositionStatus = "open" | "filled" | "archived";

export interface MatchedCandidate {
  candidate_id: string;
  status: CandidateStatus;
  feedback: string | null;
}

export interface Position {
  id: string;
  brand_id: string;
  title: string;
  requirements: string[];
  status: PositionStatus;
  matched_candidates: MatchedCandidate[];
}

// ── Positions (Recruitment API — mirrors PositionListItem schema) ─────────────

export interface ApiMappedPreview {
  id: string;
  full_name: string;
}

export interface ApiPosition {
  id: string;
  code: string;
  client_id: string;
  client_name: string;
  role: string;
  department: string | null;
  city: string | null;
  seniority: string;
  status: string; // "open" | "on_hold" | "closed"
  total_seats: number;
  filled_seats: number;
  remaining_seats: number;
  mapped_count: number;
  mapped_preview: ApiMappedPreview[];
  assigned_employee_id: string | null;
  assigned_employee_name: string | null;
  date_opened: string;
  target_close: string | null;
  notes: string | null;
}

/** Ranked candidate from GET /positions/{id}/top-candidates. match_score is 0..1. */
export interface ApiTopCandidate {
  id: string;
  full_name: string;
  email: string;
  phone: string | null;
  previous_company: string | null;
  experience_years: number;
  skills: string[];
  resume_url: string | null;
  match_score: number | null; // 0..1, null when position has no requirements
  is_mapped: boolean;
}

export interface ApiClientOption {
  id: string;
  code: string;
  name: string;
}

export interface ApiPositionFilters {
  clients: ApiClientOption[];
  statuses: string[];
}

// ── Candidates ───────────────────────────────────────────────────────────────

/** Legacy type used by old /api/v1/candidates (old module). Phase C will remove it. */
export interface Candidate {
  id: string;
  name: string;
  email: string;
  phone: string | null;
  resume_url: string | null;
  extracted_skills: string[];
}

export interface CandidateMatchScore extends Candidate {
  match_score: number;
}

// ── Recruitment API types (Phase B+) ─────────────────────────────────────────

export type PipelineStage =
  | "sourced"
  | "sent_to_client"
  | "interview"
  | "decision_pending"
  | "offer"
  | "offer_accepted"
  | "position_close"
  | "rejected"
  | "on_hold";

/** Canonical candidate returned by GET /api/v1/candidates */
export interface ApiCandidate {
  id: string;
  full_name: string;
  email: string;
  phone: string | null;
  previous_company: string | null;
  experience_years: number;
  skills: string[];
  resume_url: string | null;
  current_stage: PipelineStage;
  mappings_count: number;
  created_at: string;
}

/** One position mapping returned by GET /api/v1/candidates/{id}/mappings */
export interface ApiCandidateMappingItem {
  mapping_id: string;
  position_id: string;
  position_code: string;
  role: string;
  client_name: string;
  city: string | null;
  stage: PipelineStage;
  match_score: number | null;
  mapped_at: string;
}

/** Shared pagination meta (mirrors ApiPaginationMeta in lib/api/dashboard.ts) */
export interface PaginationMeta {
  page: number;
  limit: number;
  total: number;
  pages: number;
  has_next: boolean;
  has_prev: boolean;
}

export interface PaginatedResponse<T> {
  items: T[];
  meta: PaginationMeta;
}

// ── Gamification ─────────────────────────────────────────────────────────────

export interface LeaderboardEntry {
  user_id: string;
  daily_score: number;
  weekly_score: number;
  badges: string[];
  rank: number;
}

export interface RecruiterStats {
  user_id: string;
  daily_score: number;
  weekly_score: number;
  badges: string[];
}

// ── Pipeline ─────────────────────────────────────────────────────────────────

export interface MatchRequest {
  position_id: string;
  candidate_id: string;
  target_status: CandidateStatus;
}

export interface MatchResponse {
  position_id: string;
  candidate_id: string;
  status: string;
  recruiter_daily_score: number;
}

// ── Storage ───────────────────────────────────────────────────────────────────

export interface CloudinarySignature {
  signature: string;
  timestamp: number;
  cloud_name: string;
  api_key: string;
  upload_preset: string;
  folder: string;
}

// ── Kanban ───────────────────────────────────────────────────────────────────

export interface KanbanColumn {
  id: CandidateStatus;
  title: string;
  cards: CandidateCard[];
}

export interface CandidateCard {
  id: string; // candidate_id — used as dnd-kit item id
  name: string;
  email: string;
  extracted_skills: string[];
  resume_url: string | null;
  match_score?: number;
  status: CandidateStatus;
}
