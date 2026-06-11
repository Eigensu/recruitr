"use client";

import type { BulkUploadResult, Candidate, CandidateFilters, CandidateSource } from "@/types";

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

function buildQuery(filters: Partial<CandidateFilters>): string {
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

export async function clientFetchCandidates(
  filters: Partial<CandidateFilters>,
): Promise<Candidate[]> {
  const res = await fetch(`${API_URL}/api/v1/candidates${buildQuery(filters)}`, {
    credentials: "include",
  });
  if (!res.ok) throw new Error(`Candidates fetch failed: ${res.status}`);
  return res.json();
}

export async function clientCreateCandidate(data: {
  name: string;
  email: string;
  phone?: string;
  source: CandidateSource;
  tags?: string[];
  cv_link?: string;
}): Promise<Candidate> {
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
    name: string;
    phone: string;
    cv_link: string;
    source: CandidateSource;
    tags: string[];
  }>,
): Promise<Candidate> {
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
): Promise<Candidate> {
  const res = await fetch(`${API_URL}/api/v1/candidates/${candidateId}/resume`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    credentials: "include",
    body: JSON.stringify({ candidate_id: candidateId, ...data }),
  });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
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
