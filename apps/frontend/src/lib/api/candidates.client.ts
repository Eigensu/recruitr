"use client";

import type { ApiCandidate, BulkUploadResult, CandidateFilters, PaginatedResponse } from "@/types";

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

function buildQuery(filters: Partial<CandidateFilters>): string {
  const params = new URLSearchParams();
  if (filters.search) params.set("search", filters.search);
  if (filters.source) params.set("source", filters.source);
  if (filters.tags) filters.tags.forEach((t) => params.append("tags", t));
  if (filters.has_resume !== undefined) params.set("has_resume", String(filters.has_resume));
  if (filters.has_cv_link !== undefined) params.set("has_cv_link", String(filters.has_cv_link));
  if (filters.city) params.set("city", filters.city);
  if (filters.gender) params.set("gender", filters.gender);
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

export async function clientCreateCandidate(data: {
  full_name: string;
  email: string;
  phone?: string;
  tags?: string[];
  cv_link?: string;
  current_role?: string;
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
    tags: string[];
    cv_link: string;
    current_role: string;
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
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    credentials: "include",
    body: JSON.stringify({ candidate_id: candidateId, ...data }),
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
