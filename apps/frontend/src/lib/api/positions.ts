import type { ApiPosition, ApiTopCandidate, ApiPositionFilters, PaginatedResponse } from "@/types";

type ApiFetch = <T>(path: string, options?: RequestInit) => Promise<T>;

export interface PositionCreatePayload {
  client_id: string;
  role: string;
  department?: string;
  salary?: string;
  mumbai_area?: string;
  city?: string;
  seniority?: string;
  requirements?: string[];
  total_seats?: number;
  notes?: string;
}

export interface PositionUpdatePayload {
  role?: string;
  department?: string;
  salary?: string;
  mumbai_area?: string;
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
  return apiFetch(`/api/v1/positions/${positionId}/map-candidate`, {
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
  return apiFetch(`/api/v1/positions/${positionId}/unmap-candidate?candidate_id=${candidateId}`, {
    method: "POST",
  });
}

export function deletePosition(apiFetch: ApiFetch, positionId: string): Promise<void> {
  return apiFetch(`/api/v1/positions/${positionId}`, { method: "DELETE" });
}

export function reopenPosition(apiFetch: ApiFetch, positionId: string): Promise<ApiPosition> {
  return apiFetch(`/api/v1/positions/${positionId}/reopen`, { method: "POST" });
}

export function updatePosition(
  apiFetch: ApiFetch,
  positionId: string,
  payload: PositionUpdatePayload,
): Promise<ApiPosition> {
  return apiFetch(`/api/v1/positions/${positionId}`, {
    method: "PATCH",
    body: JSON.stringify(payload),
  });
}

export const updatePositionApproval =
  (apiFetch: ApiFetch) =>
  async (positionId: string, approvalStatus: string): Promise<ApiPosition> => {
    return apiFetch<ApiPosition>(`/api/v1/positions/${positionId}/approval`, {
      method: "PUT",
      body: JSON.stringify({ approval_status: approvalStatus }),
    });
  };
