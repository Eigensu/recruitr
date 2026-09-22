"use client";

import type {
  ApiCandidate,
  BulkUploadResult,
  CandidateFilters,
  CandidateReferrerOption,
  PaginatedResponse,
} from "@/types";
import { buildCandidateQuery } from "./candidates";

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export async function clientFetchCandidates(
  filters: Partial<CandidateFilters>,
): Promise<PaginatedResponse<ApiCandidate>> {
  const res = await fetch(`${API_URL}/api/v1/candidates${buildCandidateQuery(filters)}`, {
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
