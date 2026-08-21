"use client";

import type { ApiPipelineStage } from "@/lib/pipeline-funnel";

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export interface ClientDashboardPipelineResponse {
  stages: ApiPipelineStage[];
  total_candidates: number;
}

/** Browser-side twin of getDashboardPipeline, for filters that refetch in place. */
export async function clientFetchDashboardPipeline(
  employeeId?: string,
  signal?: AbortSignal,
): Promise<ClientDashboardPipelineResponse> {
  const qs = employeeId ? `?employee_id=${encodeURIComponent(employeeId)}` : "";
  const res = await fetch(`${API_URL}/api/v1/dashboard/pipeline${qs}`, {
    credentials: "include",
    signal,
  });
  if (!res.ok) throw new Error(`Dashboard pipeline fetch failed: ${res.status}`);
  return res.json() as Promise<ClientDashboardPipelineResponse>;
}
