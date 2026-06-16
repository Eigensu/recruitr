import type {
  ApiCandidate,
  ApiCandidateMappingItem,
  CandidateFilters,
  PaginatedResponse,
  PipelineStage,
} from "@/types";

/**
 * Resolves a candidate's best CV reference.
 * Returns { href } when the value is a navigable absolute http/https URL,
 * or { href: null } when it's a bare filename / relative path (legacy seed data
 * before upload_cvs.py has run) — so the UI can still show a "CV on file" badge.
 * Returns null when there is no CV reference at all.
 */
function isAbsoluteUrl(url: string): boolean {
  try {
    const p = new URL(url);
    return p.protocol === "http:" || p.protocol === "https:";
  } catch {
    return false;
  }
}

/**
 * Resolves a candidate's best CV reference.
 * Returns { href } when the value is a navigable absolute http/https URL,
 * or { href: null } when it's a bare filename / relative path (legacy seed data
 * before upload_cvs.py has run) — so the UI can still show a "CV on file" badge.
 * Returns null when there is no CV reference at all.
 */
export function resolveCvRef(
  cvLink: string | null | undefined,
  resumeUrl: string | null | undefined,
): { label: string; href: string | null } | null {
  if (cvLink) {
    return { label: "CV Link", href: isAbsoluteUrl(cvLink) ? cvLink : null };
  }
  if (resumeUrl) {
    return { label: "Resume", href: isAbsoluteUrl(resumeUrl) ? resumeUrl : null };
  }
  return null;
}

export function buildCandidateQuery(filters: Partial<CandidateFilters>): string {
  const params = new URLSearchParams();
  if (filters.search) params.set("search", filters.search);
  if (filters.source) params.set("source", filters.source);
  if (filters.tags) filters.tags.forEach((t) => params.append("tags", t));
  if (filters.has_resume !== undefined) params.set("has_resume", String(filters.has_resume));
  if (filters.has_cv_link !== undefined) params.set("has_cv_link", String(filters.has_cv_link));
  if (filters.page) params.set("page", String(filters.page));
  if (filters.limit) params.set("limit", String(filters.limit));
  const qs = params.toString();
  return qs ? `?${qs}` : "";
}

type ApiFetch = <T>(path: string, options?: RequestInit) => Promise<T>;

export type ExperienceFilter = "lt2" | "2to5" | "gt5";

export interface CandidateListParams {
  search?: string;
  experience?: ExperienceFilter;
  stage?: PipelineStage;
  page?: number;
  limit?: number;
}

export interface CandidateCreatePayload {
  full_name: string;
  email: string;
  phone?: string;
  previous_company?: string;
  experience_years: number;
  skills: string[];
}

export interface CandidateUpdatePayload {
  full_name?: string;
  phone?: string;
  previous_company?: string;
  experience_years?: number;
  skills?: string[];
}

function buildQuery(params: CandidateListParams): string {
  const q = new URLSearchParams();
  if (params.search) q.set("search", params.search);
  if (params.experience) q.set("experience", params.experience);
  if (params.stage) q.set("stage", params.stage);
  if (params.page) q.set("page", String(params.page));
  if (params.limit) q.set("limit", String(params.limit));
  const s = q.toString();
  return s ? `?${s}` : "";
}

export function listCandidates(
  apiFetch: ApiFetch,
  params: CandidateListParams = {},
): Promise<PaginatedResponse<ApiCandidate>> {
  return apiFetch(`/api/v1/candidates${buildQuery(params)}`);
}

export function getCandidate(apiFetch: ApiFetch, id: string): Promise<ApiCandidate> {
  return apiFetch(`/api/v1/candidates/${id}`);
}

export function createCandidate(
  apiFetch: ApiFetch,
  data: CandidateCreatePayload,
): Promise<ApiCandidate> {
  return apiFetch("/api/v1/candidates", {
    method: "POST",
    body: JSON.stringify(data),
  });
}

export function updateCandidate(
  apiFetch: ApiFetch,
  id: string,
  data: CandidateUpdatePayload,
): Promise<ApiCandidate> {
  return apiFetch(`/api/v1/candidates/${id}`, {
    method: "PATCH",
    body: JSON.stringify(data),
  });
}

export function getCandidateMappings(
  apiFetch: ApiFetch,
  id: string,
): Promise<ApiCandidateMappingItem[]> {
  return apiFetch(`/api/v1/candidates/${id}/mappings`);
}

export interface ResumeConfirmPayload {
  resume_public_id: string;
  resume_url: string;
}

export function confirmResume(
  apiFetch: ApiFetch,
  id: string,
  data: ResumeConfirmPayload,
): Promise<ApiCandidate> {
  return apiFetch(`/api/v1/candidates/${id}/resume`, {
    method: "POST",
    body: JSON.stringify(data),
  });
}

export function deleteCandidate(apiFetch: ApiFetch, id: string): Promise<void> {
  return apiFetch(`/api/v1/candidates/${id}`, { method: "DELETE" });
}
