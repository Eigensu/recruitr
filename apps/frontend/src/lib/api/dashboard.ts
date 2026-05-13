import { cookies } from "next/headers";

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

type QueryValue = string | number | boolean | null | undefined;

export interface ApiPaginationMeta {
  page: number;
  limit: number;
  total: number;
  pages: number;
  has_next: boolean;
  has_prev: boolean;
}

export interface ApiPaginatedResponse<T> {
  items: T[];
  meta: ApiPaginationMeta;
}

export interface ApiDashboardOverviewResponse {
  summary: {
    open_positions: number;
    total_seats_open: number;
    seats_filled: number;
    candidates_in_pipeline: number;
    offers_accepted: number;
    joined_candidates: number;
  };
  pipeline: Array<{
    stage: string;
    label: string;
    count: number;
    percent: number;
  }>;
  generated_at: string;
}

export interface ApiDashboardPipelineResponse {
  stages: Array<{
    stage: string;
    label: string;
    count: number;
    percent: number;
  }>;
  total_candidates: number;
  generated_at: string;
}

export interface ApiDashboardEmployeeItem {
  id: string;
  name: string;
  email: string;
  mappings: {
    offers_received: number;
    joined_candidates: number;
    rejected_candidates: number;
  };
  total_mappings: number;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

export interface ApiDashboardClientItem {
  id: string;
  client_name: string;
  role: string;
  total_seats: number;
  filled_seats: number;
  remaining_seats: number;
  status: string;
  candidate_count: number;
  pipeline_candidates: number;
  offers_accepted: number;
  joined_candidates: number;
  created_at: string;
  updated_at: string;
  is_active: boolean;
}

export interface ApiDashboardMappingItem {
  id: string;
  employee_id: string;
  candidate_id: string;
  job_opening_id: string;
  pipeline_stage: string;
  mapped_at: string;
  updated_at: string;
}

export interface ApiDashboardActivityItem {
  id: string;
  employee_id: string | null;
  activity_type: "mapped" | "offer_sent" | "offer_accepted" | "joined" | "rejected";
  target_entity_type: "candidate" | "job_opening" | "client";
  target_entity_id: string;
  description: string;
  created_at: string;
}

function withQuery(path: string, query?: Record<string, QueryValue>) {
  if (!query) return path;

  const params = new URLSearchParams();
  for (const [key, value] of Object.entries(query)) {
    if (value === null || value === undefined || value === "") continue;
    params.set(key, String(value));
  }

  const queryString = params.toString();
  return queryString ? `${path}?${queryString}` : path;
}

async function dashboardFetch<T>(path: string, query?: Record<string, QueryValue>): Promise<T> {
  const cookieStore = await cookies();
  const cookieHeader = cookieStore
    .getAll()
    .map((item) => `${item.name}=${item.value}`)
    .join("; ");

  const res = await fetch(`${API_URL}${withQuery(path, query)}`, {
    method: "GET",
    headers: {
      Accept: "application/json",
      ...(cookieHeader ? { Cookie: cookieHeader } : {}),
    },
    cache: "no-store",
  });

  if (!res.ok) {
    throw new Error(`Dashboard API failed (${res.status}) on ${path}`);
  }

  return (await res.json()) as T;
}

async function fetchAllPages<T>(
  path: string,
  baseQuery: Record<string, QueryValue> = {},
  limit = 100,
  maxPages = 50,
  maxItems = 5000,
): Promise<T[]> {
  const items: T[] = [];
  let page = 1;

  while (page <= maxPages && items.length < maxItems) {
    const response = await dashboardFetch<ApiPaginatedResponse<T>>(path, {
      ...baseQuery,
      page,
      limit,
    });

    if (response.items.length === 0) {
      break;
    }

    const remaining = maxItems - items.length;
    items.push(...response.items.slice(0, remaining));

    if (!response.meta.has_next || page >= response.meta.pages || items.length >= maxItems) {
      break;
    }

    page += 1;
  }

  return items;
}

export function getDashboardOverview() {
  return dashboardFetch<ApiDashboardOverviewResponse>("/api/v1/dashboard/overview");
}

export function getDashboardPipeline() {
  return dashboardFetch<ApiDashboardPipelineResponse>("/api/v1/dashboard/pipeline");
}

export function getDashboardEmployees(query: Record<string, QueryValue> = {}) {
  return dashboardFetch<ApiPaginatedResponse<ApiDashboardEmployeeItem>>(
    "/api/v1/dashboard/employees",
    query,
  );
}

export function getDashboardClients(query: Record<string, QueryValue> = {}) {
  return dashboardFetch<ApiPaginatedResponse<ApiDashboardClientItem>>(
    "/api/v1/dashboard/clients",
    query,
  );
}

export function getDashboardMappings(query: Record<string, QueryValue> = {}) {
  return dashboardFetch<ApiPaginatedResponse<ApiDashboardMappingItem>>(
    "/api/v1/dashboard/mappings",
    query,
  );
}

export function getDashboardActivities(query: Record<string, QueryValue> = {}) {
  return dashboardFetch<ApiPaginatedResponse<ApiDashboardActivityItem>>(
    "/api/v1/dashboard/activity",
    query,
  );
}

export function getAllDashboardMappings(maxMappings = 500) {
  const limit = Math.min(100, Math.max(maxMappings, 1));
  return fetchAllPages<ApiDashboardMappingItem>(
    "/api/v1/dashboard/mappings",
    {},
    limit,
    50,
    maxMappings,
  );
}

export function getAllDashboardActivities(limit = 60) {
  return fetchAllPages<ApiDashboardActivityItem>("/api/v1/dashboard/activity", {}, limit);
}
