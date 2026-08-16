/**
 * Shared TypeScript interfaces for the Eigensu CRM.
 * These mirror the FastAPI Pydantic response schemas.
 */

// ── Auth ──────────────────────────────────────────────────────────────────────

export type UserRole = "employee" | "maintainer" | "admin" | "client" | "referee";

export interface UserInfo {
  user_id: string;
  email: string;
  full_name: string | null;
  role: UserRole;
  employee_id: string | null;
  brand_id: string | null;
  brand_name?: string | null;
  brand_domain?: string | null;
  notification_preferences?: Record<string, boolean>;
  /** Set only for the client role — the employer company this login is scoped to. */
  client_id?: string | null;
  client_name?: string | null;
  /** Set only for the referee role. */
  connect_code?: string | null;
}

// ── Referee Portal ─────────────────────────────────────────────────────────────

export interface RefereeSummary {
  cvs_shared: number;
  cvs_actioned: number;
  accrued_earnings: number;
}

export interface RefereeReferral {
  id: string;
  candidate_name: string;
  role_level: string | null;
  submission_date: string;
  kanban_stage: string;
  joining_date: string | null;
  joining_plus7_eligible: boolean;
  incentive_status: string;
  incentive_amount: number | null;
  payment_status: string;
  payment_date: string | null;
}

export interface RefereePayment {
  batch_id: string;
  cycle_month: string;
  total_amount: number;
  paid_on: string;
  payment_reference: string | null;
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

export type CandidateStatus = "PENDING" | "APPROVED" | "REJECTED";
export type LegacyCandidateStatus = "pending" | "accepted" | "rejected";
export type PositionStatus = "open" | "filled" | "archived";

export interface MatchedCandidate {
  candidate_id: string;
  status: LegacyCandidateStatus;
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
  train_line: string | null;
  seniority: string;
  status: string; // "open" | "on_hold" | "closed"
  total_seats: number;
  filled_seats: number;
  remaining_seats: number;
  mapped_count: number;
  mapped_preview: ApiMappedPreview[];
  assigned_employee_id: string | null;
  assigned_employee_name: string | null;
  requirements: string[];
  date_opened: string;
  target_close: string | null;
  notes: string | null;
}

/** Ranked candidate from GET /positions/{id}/top-candidates. match_score is 0..1. */
export interface ApiTopCandidate {
  id: string;
  full_name: string;
  email: string | null;
  phone: string | null;
  previous_company: string | null;
  experience_years: number;
  education_level: string | null;
  skills: string[];
  tags: string[];
  preferred_train_line: string | null;
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

export type CandidateSource = "internal" | "external";

/** Legacy type used by old /api/v1/candidates (old module). Phase C will remove it. */
export interface Candidate {
  id: string;
  name: string;
  email: string;
  phone: string | null;
  resume_url: string | null;
  extracted_skills: string[];
  // Candidate management additions
  tags: string[];
  source: CandidateSource;
  cv_link: string | null;
}

export interface CandidateFilters {
  search?: string;
  source?: CandidateSource;
  /** External channel the candidate came from (LinkedIn, Naukri, …). */
  source_channel?: string;
  /** Employee id of the recruiter who added them, or "unassigned". */
  created_by?: string;
  tags?: string[];
  has_resume?: boolean;
  has_cv_link?: boolean;
  city?: string;
  gender?: string;
  role?: string;
  salary?: string;
  status?: string;
  page: number;
  limit: number;
}

export interface BulkUploadFailure {
  filename: string;
  reason: string;
}

export interface BulkUploadResult {
  created: number;
  updated: number;
  failed: BulkUploadFailure[];
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
  email: string | null;
  phone: string | null;
  previous_company: string | null;
  experience_years: number;
  education_level: string | null;
  city: string | null;
  area: string | null;
  gender: string | null;
  age: number | null;
  skills: string[];
  tags: string[];
  communication: string | null;
  education: string | null;
  brand_experience: string | null;
  department: string | null;
  specialization: string | null;
  preferred_train_line: string | null;
  cv_link: string | null;
  resume_url: string | null;
  current_stage: PipelineStage;
  mappings_count: number;
  current_role: string | null;
  expected_salary: number | null;
  notice_period: string | null;
  source: string | null;
  /** Which external channel the candidate came from (LinkedIn, Naukri, …). */
  source_channel: string | null;
  salary: number | null;
  notes: string | null;
  status: CandidateStatus;
  /** Employee id of the recruiter who added them. Null for public applications. */
  created_by_id: string | null;
  created_by_name: string | null;
  /**
   * The CV belongs to another recruiter, so `cv_link` and `resume_url` came back
   * null for that reason rather than because there is no CV on file.
   */
  cv_locked: boolean;
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

/** A recruiter as offered in a filter dropdown. */
export interface RecruiterOption {
  id: string;
  name: string;
}

export type CandidateEventType =
  | "created"
  | "applied"
  | "approved"
  | "declined"
  | "mapped"
  | "stage_moved"
  | "unmapped";

/** One entry in a candidate's permanent history — GET /candidates/{id}/history */
export interface ApiCandidateHistoryEvent {
  id: string | null;
  at: string;
  event_type: CandidateEventType;
  employee_id: string | null;
  employee_name: string | null;
  position_id: string | null;
  position_code: string | null;
  position_role: string | null;
  client_name: string | null;
  from_stage: PipelineStage | null;
  to_stage: PipelineStage | null;
  note: string | null;
}

/** A company this candidate was actually placed with. */
export interface ApiCandidatePlacement {
  position_id: string | null;
  position_code: string | null;
  role: string | null;
  client_name: string | null;
  stage: PipelineStage;
  at: string;
  employee_name: string | null;
  /** False once they have moved on from that stage — it still happened. */
  is_current: boolean;
}

export interface ApiCandidateHistory {
  events: ApiCandidateHistoryEvent[];
  placements: ApiCandidatePlacement[];
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
  target_status: LegacyCandidateStatus;
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

// ── Kanban (legacy — kept for backward compat with old components) ────────────

export interface KanbanColumn {
  id: LegacyCandidateStatus;
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
  status: LegacyCandidateStatus;
}

// ── Pipeline Kanban (Phase D — real API types) ────────────────────────────────

export type KanbanStage =
  | "sourced"
  | "sent_to_client"
  | "interview"
  | "decision_pending"
  | "offer"
  | "offer_accepted"
  | "position_close"
  | "rejected";

export interface PipelineCard {
  mapping_id: string;
  candidate_id: string;
  candidate_name: string;
  candidate_email: string;
  position_id: string;
  position_code: string;
  position_role: string;
  position_client: string;
  employee_id: string | null;
  stage: KanbanStage;
  match_score: number | null;
  decision: string;
  mapped_at: string;
}

export interface PipelineColumn {
  stage: KanbanStage;
  label: string;
  count: number;
  mappings: PipelineCard[];
}

export interface PipelineBoardData {
  stages: PipelineColumn[];
}

/** Minimal agency identity exposed on unauthenticated surfaces (public form). */
export interface PublicBrand {
  id: string;
  name: string;
  logo_url: string | null;
}
