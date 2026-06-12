import { cookies } from "next/headers";
import type {
  ApiCandidate,
  ApiCandidateMappingItem,
  Candidate,
  CandidateFilters,
  PaginatedResponse,
  PipelineStage,
} from "@/types";

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

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

async function serverFetch<T>(path: string): Promise<T> {
  const cookieStore = await cookies();
  const cookieHeader = cookieStore
    .getAll()
    .map((c) => `${c.name}=${c.value}`)
    .join("; ");

  const res = await fetch(`${API_URL}${path}`, {
    headers: {
      Accept: "application/json",
      ...(cookieHeader ? { Cookie: cookieHeader } : {}),
    },
    cache: "no-store",
  });

  if (!res.ok) throw new Error(`Candidates API ${res.status}: ${path}`);
  return res.json() as Promise<T>;
}

function toCandidate(a: ApiCandidate): Candidate {
  return {
    id: a.id,
    name: a.full_name,
    email: a.email,
    phone: a.phone,
    resume_url: a.resume_url,
    extracted_skills: a.skills ?? [],
    tags: a.recruiter_tags ?? [],
    source: "external",
    cv_link: null,
  };
}

/** Server-side initial load (used by the candidates page server component). */
export async function getCandidates(filters: Partial<CandidateFilters> = {}): Promise<Candidate[]> {
  const data = await serverFetch<PaginatedResponse<ApiCandidate>>(
    `/api/v1/candidates${buildCandidateQuery(filters)}`,
  );
  return (data.items ?? []).map(toCandidate);
}

export function getCandidateTags() {
  return serverFetch<string[]>("/api/v1/candidates/tags");
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
