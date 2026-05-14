import { cookies } from "next/headers";
import { z } from "zod";
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

const leaderboardRecruiterSchema = z
  .object({
    id: z.string(),
    name: z.string(),
    email: z.string(),
    initials: z.string(),
    rank: z.number(),
    xp: z.number(),
    level: z.number(),
    totalMappings: z.number(),
    offersReceived: z.number(),
    joined: z.number(),
    rejected: z.number(),
    monthlyGrowth: z.number(),
    successRate: z.number(),
    badge: z.string(),
    badges: z.array(z.string()),
    monthlyData: z.array(z.number()),
    avatarColor: z.string(),
  })
  .passthrough();

const leaderboardOverviewSchema = z.object({
  kpis: z.array(
    z
      .object({
        id: z.string(),
        label: z.string(),
        value: z.number(),
        suffix: z.string().nullable().optional(),
        helper: z.string(),
        tone: z.enum(["yellow", "green", "red", "navy", "neutral"]),
      })
      .passthrough(),
  ),
  top_recruiter: leaderboardRecruiterSchema.nullable(),
});

const leaderboardPageSchema = <T extends z.ZodTypeAny>(itemSchema: T) =>
  z.object({
    items: z.array(itemSchema),
    meta: z.object({
      page: z.number(),
      limit: z.number(),
      total: z.number(),
      pages: z.number(),
      has_next: z.boolean(),
      has_prev: z.boolean(),
    }),
  });

const leaderboardMonthlyGrowthSchema = z.object({
  labels: z.array(z.string()),
  series: z.array(
    z
      .object({
        employee_id: z.string(),
        name: z.string(),
        monthlyData: z.array(z.number()),
      })
      .passthrough(),
  ),
});

const leaderboardCompanyProgressSchema = z.object({
  items: z.array(
    z
      .object({
        company: z.string(),
        role: z.string(),
        totalSeats: z.number(),
        filled: z.number(),
        recruiterCount: z.number(),
      })
      .passthrough(),
  ),
});

const leaderboardActivitySchema = leaderboardPageSchema(
  z
    .object({
      id: z.string(),
      recruiter: z.string(),
      initials: z.string(),
      action: z.string(),
      target: z.string(),
      timestamp: z.string(),
      tone: z.enum(["yellow", "green", "red", "neutral"]),
      avatarColor: z.string(),
      activity_type: z.string(),
    })
    .passthrough(),
);

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

  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), 5000);

  try {
    const res = await fetch(`${API_URL}${path}`, {
      headers: { Accept: "application/json", ...(cookieHeader ? { Cookie: cookieHeader } : {}) },
      cache: "no-store",
      signal: controller.signal,
    });

    if (!res.ok) {
      throw new Error(`Leaderboard API failed (${res.status}) on ${path}`);
    }

    const data = await res.json();
    if (path.includes("/overview")) {
      return leaderboardOverviewSchema.parse(data) as T;
    }
    if (path.includes("/rankings")) {
      return leaderboardPageSchema(leaderboardRecruiterSchema).parse(data) as T;
    }
    if (path.includes("/monthly-growth")) {
      return leaderboardMonthlyGrowthSchema.parse(data) as T;
    }
    if (path.includes("/company-progress")) {
      return leaderboardCompanyProgressSchema.parse(data) as T;
    }
    if (path.includes("/activity")) {
      return leaderboardActivitySchema.parse(data) as T;
    }
    return data as T;
  } catch (error) {
    if (error instanceof Error && error.name === "AbortError") {
      throw new Error(`Leaderboard API timed out on ${path}`);
    }
    throw error;
  } finally {
    clearTimeout(timeoutId);
  }
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
