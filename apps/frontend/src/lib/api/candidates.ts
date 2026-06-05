/**
 * Client-side API helpers for the candidates resource.
 *
 * All functions accept the `apiFetch` returned by `useApiFetch()` so they
 * can be called from any client component.
 */

import type {
  ApiCandidate,
  ApiCandidateMappingItem,
  PaginatedResponse,
  PipelineStage,
} from "@/types";

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
