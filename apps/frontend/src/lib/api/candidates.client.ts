"use client";

import type {
  ApiCandidate,
  BulkUploadResult,
  CandidateFilters,
  CandidateReferrerOption,
  PaginatedResponse,
} from "@/types";

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

// Plain truthy string/enum filters — one line each would be identical but for
// the key, which is exactly what pushed this past Sonar's cognitive-complexity
// budget as a flat if-chain. Looping over the field list keeps it one branch.
const STRING_FILTER_KEYS = [
  "search",
  "source",
  "source_channel",
  "created_by",
  "referee_id",
  "city",
  "gender",
  "role",
  "salary",
  "status",
] as const satisfies readonly (keyof CandidateFilters)[];

function buildQuery(filters: Partial<CandidateFilters>): string {
  const params = new URLSearchParams();
  for (const key of STRING_FILTER_KEYS) {
    const value = filters[key];
    if (value) params.set(key, String(value));
  }
  if (filters.tags) filters.tags.forEach((t) => params.append("tags", t));
  if (filters.has_resume !== undefined) params.set("has_resume", String(filters.has_resume));
  if (filters.has_cv_link !== undefined) params.set("has_cv_link", String(filters.has_cv_link));
  if (filters.page) params.set("page", String(filters.page));
  if (filters.limit) params.set("limit", String(filters.limit));
  const qs = params.toString();
  return qs ? `?${qs}` : "";
}

export async function clientFetchCandidates(
  filters: Partial<CandidateFilters>,
): Promise<PaginatedResponse<ApiCandidate>> {
  const res = await fetch(`${API_URL}/api/v1/candidates${buildQuery(filters)}`, {
    credentials: "include",
  });
  if (!res.ok) throw new Error(`Candidates fetch failed: ${res.status}`);
  return res.json() as Promise<PaginatedResponse<ApiCandidate>>;
}

export async function clientFetchCandidateReferees(): Promise<CandidateReferrerOption[]> {
  const res = await fetch(`${API_URL}/api/v1/candidates/referees`, {
    credentials: "include",
  });
  if (!res.ok) throw new Error(`Candidate referees fetch failed: ${res.status}`);
  return res.json() as Promise<CandidateReferrerOption[]>;
}

export async function clientCreateCandidate(data: {
  full_name: string;
  email?: string;
  phone: string;
  tags?: string[];
  communication?: string;
  education?: string;
  brand_experience?: string;
  department?: string;
  specialization?: string;
  establishment_tag?: string;
  cv_link?: string;
  current_role?: string;
  experience_years?: number;
  expected_salary?: number;
  notice_period?: string;
  source?: string;
  source_channel?: string;
  city?: string;
  area?: string;
  gender?: string;
  age?: number;
  salary?: number;
  notes?: string;
}): Promise<ApiCandidate> {
  const res = await fetch(`${API_URL}/api/v1/candidates`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    credentials: "include",
    body: JSON.stringify(data),
  });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

export async function clientUpdateCandidate(
  id: string,
  data: Partial<{
    full_name: string;
    phone: string;
    previous_company: string;
    experience_years: number;
    education_level: string;
    tags: string[];
    communication: string;
    education: string;
    brand_experience: string;
    department: string;
    specialization: string;
    establishment_tag: string;
    cv_link: string;
    current_role: string;
    expected_salary: number;
    notice_period: string;
    source: string;
    source_channel: string;
    city: string;
    area: string;
    gender: string;
    age: number;
    salary: number;
    notes: string;
  }>,
): Promise<ApiCandidate> {
  const res = await fetch(`${API_URL}/api/v1/candidates/${id}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    credentials: "include",
    body: JSON.stringify(data),
  });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

export async function clientConfirmResume(
  candidateId: string,
  data: { resume_public_id: string; resume_url: string },
): Promise<ApiCandidate> {
  const res = await fetch(`${API_URL}/api/v1/candidates/${candidateId}/resume`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    credentials: "include",
    body: JSON.stringify({ candidate_id: candidateId, ...data }),
  });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

export async function clientApproveCandidate(id: string): Promise<ApiCandidate> {
  const res = await fetch(`${API_URL}/api/v1/candidates/${id}/approve`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    credentials: "include",
  });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

export async function clientRejectCandidate(id: string): Promise<ApiCandidate> {
  const res = await fetch(`${API_URL}/api/v1/candidates/${id}/reject`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    credentials: "include",
  });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

export async function clientDeleteCandidate(id: string): Promise<void> {
  const res = await fetch(`${API_URL}/api/v1/candidates/${id}`, {
    method: "DELETE",
    credentials: "include",
  });
  if (!res.ok) throw new Error(await res.text());
}

export async function clientBulkUpload(files: File[]): Promise<BulkUploadResult> {
  const formData = new FormData();
  files.forEach((f) => formData.append("files", f));
  const res = await fetch(`${API_URL}/api/v1/candidates/bulk-upload`, {
    method: "POST",
    credentials: "include",
    body: formData,
  });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

export async function clientPublicApply(formData: FormData): Promise<ApiCandidate> {
  const res = await fetch(`${API_URL}/api/v1/public/apply`, {
    method: "POST",
    body: formData,
  });
  if (!res.ok) {
    // Surface FastAPI's `detail` string rather than the raw JSON envelope,
    // which would otherwise be rendered verbatim to the applicant.
    const data = await res.json().catch(() => null);
    throw new Error(
      typeof data?.detail === "string" ? data.detail : "Could not submit your application.",
    );
  }
  return res.json();
}
