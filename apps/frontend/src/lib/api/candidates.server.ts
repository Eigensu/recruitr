import { cookies } from "next/headers";
import type { ApiCandidate, CandidateFilters, PaginatedResponse, RecruiterOption } from "@/types";
import { buildCandidateQuery } from "./candidates";

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

async function serverFetch<T>(path: string, init: RequestInit = {}): Promise<T> {
  const cookieStore = await cookies();
  const cookieHeader = cookieStore
    .getAll()
    .map((c) => `${c.name}=${c.value}`)
    .join("; ");

  const res = await fetch(`${API_URL}${path}`, {
    ...init,
    headers: {
      Accept: "application/json",
      ...(cookieHeader ? { Cookie: cookieHeader } : {}),
      ...init.headers,
    },
    cache: "no-store",
  });

  if (!res.ok) throw new Error(`Candidates API ${res.status}: ${path}`);
  return res.json() as Promise<T>;
}

export async function getCandidates(
  filters: Partial<CandidateFilters> = {},
): Promise<PaginatedResponse<ApiCandidate>> {
  return serverFetch<PaginatedResponse<ApiCandidate>>(
    `/api/v1/candidates${buildCandidateQuery(filters)}`,
  );
}

export function getCandidateTags() {
  return serverFetch<string[]>("/api/v1/candidates/tags");
}

export function getCandidateRoles() {
  return serverFetch<string[]>("/api/v1/candidates/roles");
}

/**
 * Recruiters in this brand, for the "added by" filter.
 *
 * Timeboxed: this feeds one non-critical filter dropdown, called from the
 * page's async component body with nothing to stream around it — a hung
 * request here would otherwise hold up the whole candidate directory render,
 * not just the dropdown.
 */
export async function getRecruiters(): Promise<RecruiterOption[]> {
  const employees = await serverFetch<{ id: string; name: string }[]>("/api/v1/teams/employees", {
    signal: AbortSignal.timeout(5000),
  });
  return employees.map((e) => ({ id: e.id, name: e.name }));
}
