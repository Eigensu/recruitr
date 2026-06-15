import { cookies } from "next/headers";
import type { ApiCandidate, CandidateFilters, PaginatedResponse } from "@/types";
import { buildCandidateQuery } from "./candidates";

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

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
