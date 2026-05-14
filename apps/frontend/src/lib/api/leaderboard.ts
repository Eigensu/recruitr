import { cookies } from "next/headers";
import type {
  CompanyHiringItem,
  LeaderboardKpi,
  LeaderboardRecruiter,
  RecentActivityItem,
} from "@/lib/leaderboard-data";

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

interface ApiPage<T> {
  items: T[];
  meta: {
    page: number;
    limit: number;
    total: number;
    pages: number;
    has_next: boolean;
    has_prev: boolean;
  };
}

interface ApiOverview {
  kpis: LeaderboardKpi[];
  top_recruiter: LeaderboardRecruiter | null;
}

interface ApiMonthlyGrowth {
  labels: string[];
  series: Array<{ employee_id: string; name: string; monthlyData: number[] }>;
}

interface ApiActivityItem extends Omit<RecentActivityItem, "timestamp"> {
  timestamp: string;
}

function relativeTime(value: string) {
  const diffMs = Date.now() - new Date(value).getTime();
  const minutes = Math.max(0, Math.round(diffMs / 60000));
  if (minutes < 1) return "Just now";
  if (minutes < 60) return `${minutes} min ago`;
  const hours = Math.round(minutes / 60);
  if (hours < 24) return `${hours} hr ago`;
  return `${Math.round(hours / 24)} d ago`;
}

async function leaderboardFetch<T>(path: string): Promise<T> {
  const cookieStore = await cookies();
  const cookieHeader = cookieStore
    .getAll()
    .map((item) => `${item.name}=${item.value}`)
    .join("; ");

  const res = await fetch(`${API_URL}${path}`, {
    headers: { Accept: "application/json", ...(cookieHeader ? { Cookie: cookieHeader } : {}) },
    cache: "no-store",
  });

  if (!res.ok) {
    throw new Error(`Leaderboard API failed (${res.status}) on ${path}`);
  }
  return (await res.json()) as T;
}

export async function getLeaderboardPageData() {
  const [overview, rankings, growth, companies, activity] = await Promise.all([
    leaderboardFetch<ApiOverview>("/api/v1/leaderboard/overview"),
    leaderboardFetch<ApiPage<LeaderboardRecruiter>>("/api/v1/leaderboard/rankings?limit=50"),
    leaderboardFetch<ApiMonthlyGrowth>("/api/v1/leaderboard/monthly-growth"),
    leaderboardFetch<{ items: CompanyHiringItem[] }>("/api/v1/leaderboard/company-progress"),
    leaderboardFetch<ApiPage<ApiActivityItem>>("/api/v1/leaderboard/activity?limit=12"),
  ]);

  const growthById = new Map(growth.series.map((item) => [item.employee_id, item.monthlyData]));
  const recruiters = rankings.items.map((item) => ({
    ...item,
    monthlyData: growthById.get(item.id) ?? item.monthlyData,
  }));

  return {
    kpis: overview.kpis,
    topRecruiter: overview.top_recruiter ?? recruiters[0] ?? null,
    recruiters,
    companies: companies.items,
    activity: activity.items.map((item) => ({ ...item, timestamp: relativeTime(item.timestamp) })),
    monthLabels: growth.labels.length ? growth.labels : undefined,
  };
}
