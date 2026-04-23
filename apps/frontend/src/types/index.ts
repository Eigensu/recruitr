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

// ── Candidates ───────────────────────────────────────────────────────────────

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
