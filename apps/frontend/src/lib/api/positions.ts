import type { ApiPosition, ApiTopCandidate, ApiPositionFilters, PaginatedResponse } from "@/types";

type ApiFetch = <T>(path: string, options?: RequestInit) => Promise<T>;

export interface PositionCreatePayload {
  client_id: string;
  role: string;
  department?: string;
  city?: string;
  seniority?: string;
  requirements?: string[];
  total_seats?: number;
  notes?: string;
}

export interface PositionListParams {
  search?: string;
  client_id?: string;
  status?: string;
  page?: number;
  limit?: number;
}

function buildQuery(params: PositionListParams): string {
  const q = new URLSearchParams();
  if (params.search) q.set("search", params.search);
  if (params.client_id) q.set("client_id", params.client_id);
  if (params.status) q.set("status", params.status);
  if (params.page) q.set("page", String(params.page));
  if (params.limit) q.set("limit", String(params.limit));
  const s = q.toString();
  return s ? `?${s}` : "";
}

export function listPositions(
  apiFetch: ApiFetch,
  params: PositionListParams = {},
): Promise<PaginatedResponse<ApiPosition>> {
  return apiFetch(`/api/v1/positions${buildQuery(params)}`);
}

export function getPositionFilters(apiFetch: ApiFetch): Promise<ApiPositionFilters> {
  return apiFetch("/api/v1/positions/filters");
}

export function getTopCandidates(
  apiFetch: ApiFetch,
  positionId: string,
  limit = 10,
): Promise<ApiTopCandidate[]> {
  return apiFetch(`/api/v1/positions/${positionId}/top-candidates?limit=${limit}`);
}

export function mapCandidateToPosition(
  apiFetch: ApiFetch,
  positionId: string,
  candidateId: string,
): Promise<unknown> {
  return apiFetch(`/api/v1/positions/${positionId}/candidates`, {
    method: "POST",
    body: JSON.stringify({ candidate_id: candidateId }),
  });
}

export function createPosition(
  apiFetch: ApiFetch,
  payload: PositionCreatePayload,
): Promise<ApiPosition> {
  return apiFetch("/api/v1/positions", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function unmapCandidateFromPosition(
  apiFetch: ApiFetch,
  positionId: string,
  candidateId: string,
): Promise<void> {
  return apiFetch(`/api/v1/positions/${positionId}/candidates/${candidateId}`, {
    method: "DELETE",
  });
}
