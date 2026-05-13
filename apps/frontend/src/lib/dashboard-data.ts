import { PIPELINE_STAGE_LABELS } from "@/lib/dashboard-constants";
import {
  getDashboardActivities,
  getDashboardClients,
  getDashboardOverview as getApiDashboardOverview,
  getDashboardPipeline,
} from "@/lib/api/dashboard";
import { getCandidateMappingsForDashboard } from "@/lib/api/candidates";
import { getEmployeesForDashboard } from "@/lib/api/employees";
import type {
  ClientActivityRow,
  DashboardActivityItem,
  DashboardAnalyticsWidget,
  DashboardDemoData,
  DashboardKpi,
  DashboardTone,
  DashboardTotals,
  PipelineStage,
  PipelineStageMetric,
  RecruiterDashboardStat,
} from "@/types/dashboard";

const PIPELINE_STAGE_ORDER: PipelineStage[] = [
  "added",
  "shortlisted",
  "sent_to_client",
  "rejected",
  "hold",
  "offer_sent",
  "offer_accepted",
  "joined",
  "dropped",
];

const DEFAULT_TOTALS: DashboardTotals = {
  openPositions: 0,
  totalSeats: 0,
  seatsFilled: 0,
  remaining: 0,
  inPipeline: 0,
  joined: 0,
};

const EMPTY_DATA: DashboardDemoData = {
  kpis: [],
  pipelineStages: [],
  recruiters: [],
  clients: [],
  activity: [],
  totals: DEFAULT_TOTALS,
  analytics: [],
};

/** How long a bundled demo-dashboard response may be reused (process-scoped). */
const DEMO_DASHBOARD_CACHE_TTL_MS = 60_000;

function cloneDashboardDemoData(data: DashboardDemoData): DashboardDemoData {
  return {
    ...data,
    kpis: data.kpis.map((k) => ({ ...k })),
    pipelineStages: data.pipelineStages.map((s) => ({ ...s })),
    recruiters: data.recruiters.map((r) => ({ ...r })),
    clients: data.clients.map((c) => ({ ...c })),
    activity: data.activity.map((a) => ({ ...a })),
    analytics: data.analytics.map((w) => ({ ...w })),
    totals: { ...data.totals },
  };
}

function percentString(value: number) {
  return `${Math.round(value)}%`;
}

function safeRatio(numerator: number, denominator: number) {
  if (denominator <= 0) return 0;
  return numerator / denominator;
}

function formatTimeAgo(isoDate: string) {
  const createdAt = new Date(isoDate).getTime();
  const now = Date.now();

  if (!Number.isFinite(createdAt)) {
    return "Updated recently";
  }

  const diffMinutes = Math.max(Math.floor((now - createdAt) / (1000 * 60)), 0);

  if (diffMinutes < 1) return "Updated just now";
  if (diffMinutes < 60) return `Updated ${diffMinutes} min ago`;

  const diffHours = Math.floor(diffMinutes / 60);
  if (diffHours < 24) return `Updated ${diffHours} hr ago`;

  const diffDays = Math.floor(diffHours / 24);
  return `Updated ${diffDays} day${diffDays > 1 ? "s" : ""} ago`;
}

function toneFromActivity(activityType: string): DashboardTone {
  switch (activityType) {
    case "joined":
    case "offer_accepted":
      return "green";
    case "rejected":
      return "red";
    case "offer_sent":
      return "yellow";
    default:
      return "neutral";
  }
}

function buildKpis(totals: DashboardTotals, pipelineStages: PipelineStageMetric[]): DashboardKpi[] {
  const sentToClient = pipelineStages.find((stage) => stage.stage === "sent_to_client")?.count ?? 0;
  const offersAccepted =
    pipelineStages.find((stage) => stage.stage === "offer_accepted")?.count ?? 0;
  const dropped = pipelineStages.find((stage) => stage.stage === "dropped")?.count ?? 0;

  return [
    {
      id: "open_positions",
      label: "Open Positions",
      value: totals.openPositions,
      helper: "Active hiring mandates",
      tone: "yellow",
      trend: `${totals.openPositions} currently open`,
    },
    {
      id: "total_seats_open",
      label: "Total Seats Open",
      value: totals.totalSeats,
      helper: "Approved headcount",
      tone: "navy",
      trend: `${totals.remaining} remaining`,
    },
    {
      id: "seats_filled",
      label: "Seats Filled",
      value: totals.seatsFilled,
      helper: "Closed requirements",
      tone: "green",
      trend: `${totals.seatsFilled} filled so far`,
    },
    {
      id: "total_pipeline",
      label: "Total In Pipeline",
      value: totals.inPipeline,
      helper: "Candidates being moved",
      tone: "neutral",
      trend: "Across all clients",
    },
    {
      id: "sent_to_client",
      label: "Sent to Client",
      value: sentToClient,
      helper: "Profiles shared",
      tone: "yellow",
      trend: "From stage activity",
    },
    {
      id: "offers_accepted",
      label: "Offers Accepted",
      value: offersAccepted,
      helper: "Accepted offers",
      tone: "green",
      trend: "Near joining stage",
    },
    {
      id: "candidate_dropped",
      label: "Candidate Dropped",
      value: dropped,
      helper: "Drop-offs this cycle",
      tone: "red",
      trend: "Needs follow-up",
    },
    {
      id: "joined",
      label: "Joined",
      value: totals.joined,
      helper: "Confirmed joins",
      tone: "green",
      trend: "Successfully onboarded",
    },
  ];
}

function buildAnalytics(totals: DashboardTotals): DashboardAnalyticsWidget[] {
  const fillRate = safeRatio(totals.seatsFilled, totals.totalSeats) * 100;
  const pipelineDepth = safeRatio(totals.inPipeline, totals.openPositions);
  const joinConversion = safeRatio(totals.joined, totals.inPipeline) * 100;

  return [
    {
      id: "fill_rate",
      label: "Fill Rate",
      value: percentString(fillRate),
      helper: `${totals.seatsFilled} of ${totals.totalSeats} seats filled`,
      tone: "green",
    },
    {
      id: "pipeline_depth",
      label: "Pipeline Depth",
      value: pipelineDepth.toFixed(1),
      helper: "Candidates per open position",
      tone: "yellow",
    },
    {
      id: "join_conversion",
      label: "Join Conversion",
      value: percentString(joinConversion),
      helper: `${totals.joined} joined from ${totals.inPipeline} in pipeline`,
      tone: "navy",
    },
    {
      id: "seat_gap",
      label: "Seat Gap",
      value: totals.remaining.toLocaleString("en-IN"),
      helper: "Open seats still to close",
      tone: "neutral",
    },
  ];
}

function buildPipelineStages(
  apiStages: Array<{ stage: string; label: string; count: number; percent: number }>,
): PipelineStageMetric[] {
  const stageMap = new Map(apiStages.map((stage) => [stage.stage, stage]));

  return PIPELINE_STAGE_ORDER.map((stage) => {
    const source = stageMap.get(stage);
    return {
      stage,
      label: source?.label ?? PIPELINE_STAGE_LABELS[stage],
      count: source?.count ?? 0,
      percent: source?.percent ?? 0,
    };
  });
}

function buildRecruiters(
  employees: Array<{ id: string; name: string }>,
  mappings: Array<{ employee_id: string; job_opening_id: string; pipeline_stage: string }>,
  clients: ClientActivityRow[],
): RecruiterDashboardStat[] {
  const clientsById = new Map(clients.map((client) => [client.clientId, client]));
  const stageCountByEmployee = new Map<string, Map<string, number>>();

  for (const mapping of mappings) {
    const byStage = stageCountByEmployee.get(mapping.employee_id) ?? new Map<string, number>();
    byStage.set(mapping.pipeline_stage, (byStage.get(mapping.pipeline_stage) ?? 0) + 1);
    stageCountByEmployee.set(mapping.employee_id, byStage);
  }

  return employees.map((employee) => {
    const employeeMappings = mappings.filter((mapping) => mapping.employee_id === employee.id);
    const inPipeline = employeeMappings.filter((mapping) => {
      return !["joined", "rejected", "dropped", "hold"].includes(mapping.pipeline_stage);
    }).length;
    const joined = employeeMappings.filter((mapping) => mapping.pipeline_stage === "joined").length;

    const touchedClientIds = new Set(employeeMappings.map((mapping) => mapping.job_opening_id));
    const openSeats = Array.from(touchedClientIds).reduce((sum, clientId) => {
      return sum + (clientsById.get(clientId)?.remaining ?? 0);
    }, 0);

    const dominantStage = Array.from(stageCountByEmployee.get(employee.id)?.entries() ?? []).sort(
      (a, b) => b[1] - a[1],
    )[0]?.[0];

    return {
      name: employee.name,
      openSeats,
      inPipeline,
      joined,
      focus: dominantStage
        ? PIPELINE_STAGE_LABELS[dominantStage as PipelineStage]
        : "Pipeline follow-ups",
    };
  });
}

function buildActivity(
  activities: Array<{ id: string; activity_type: string; description: string; created_at: string }>,
): DashboardActivityItem[] {
  return activities.slice(0, 6).map((activity) => ({
    id: activity.id,
    title: activity.description,
    detail: `Activity type: ${activity.activity_type.replace("_", " ")}`,
    timestamp: formatTimeAgo(activity.created_at),
    tone: toneFromActivity(activity.activity_type),
  }));
}

/** Process-scoped cache with TTL; concurrent callers share one in-flight fetch. */
type DashboardDemoCacheEntry = { data: DashboardDemoData; expiresAt: number };

let dashboardDemoCacheEntry: DashboardDemoCacheEntry | null = null;
let dashboardDemoDataPromise: Promise<DashboardDemoData> | null = null;

async function fetchDashboardDemoDataOnce(): Promise<DashboardDemoData> {
  const [
    overviewResult,
    pipelineResult,
    clientsResult,
    employeesResult,
    mappingsResult,
    activitiesResult,
  ] = await Promise.allSettled([
    getApiDashboardOverview(),
    getDashboardPipeline(),
    getDashboardClients({ page: 1, limit: 100 }),
    getEmployeesForDashboard(100),
    getCandidateMappingsForDashboard(),
    getDashboardActivities({ page: 1, limit: 60 }),
  ]);

  if (overviewResult.status === "rejected") {
    console.error("Dashboard overview fetch failed:", overviewResult.reason);
  }
  if (pipelineResult.status === "rejected") {
    console.error("Dashboard pipeline fetch failed:", pipelineResult.reason);
  }
  if (clientsResult.status === "rejected") {
    console.error("Dashboard clients fetch failed:", clientsResult.reason);
  }
  if (employeesResult.status === "rejected") {
    console.error("Dashboard employees fetch failed:", employeesResult.reason);
  }
  if (mappingsResult.status === "rejected") {
    console.error("Dashboard mappings fetch failed:", mappingsResult.reason);
  }
  if (activitiesResult.status === "rejected") {
    console.error("Dashboard activities fetch failed:", activitiesResult.reason);
  }

  const overview = overviewResult.status === "fulfilled" ? overviewResult.value : null;
  const pipeline = pipelineResult.status === "fulfilled" ? pipelineResult.value : null;
  const clientsResponse = clientsResult.status === "fulfilled" ? clientsResult.value : null;
  const employees = employeesResult.status === "fulfilled" ? employeesResult.value : [];
  const mappings = mappingsResult.status === "fulfilled" ? mappingsResult.value : [];
  const activitiesResponse =
    activitiesResult.status === "fulfilled" ? activitiesResult.value : null;
  const activities = activitiesResponse?.items ?? [];

  const totals: DashboardTotals = overview
    ? {
        openPositions: overview.summary.open_positions,
        totalSeats: overview.summary.total_seats_open,
        seatsFilled: overview.summary.seats_filled,
        remaining: Math.max(overview.summary.total_seats_open - overview.summary.seats_filled, 0),
        inPipeline: overview.summary.candidates_in_pipeline,
        joined: overview.summary.joined_candidates,
      }
    : DEFAULT_TOTALS;

  const pipelineStages = buildPipelineStages(pipeline?.stages ?? []);

  const clients: ClientActivityRow[] = (clientsResponse?.items ?? []).map((item) => ({
    clientName: item.client_name,
    clientId: item.id,
    openPositions: item.status === "open" ? 1 : 0,
    totalSeats: item.total_seats,
    filled: item.filled_seats,
    remaining: item.remaining_seats,
    inPipeline: item.pipeline_candidates,
    joined: item.joined_candidates,
  }));

  const recruiters = buildRecruiters(employees, mappings, clients);

  return {
    ...EMPTY_DATA,
    kpis: buildKpis(totals, pipelineStages),
    pipelineStages,
    recruiters,
    clients,
    activity: buildActivity(activities),
    totals,
    analytics: buildAnalytics(totals),
  };
}

async function loadDashboardDemoData(): Promise<DashboardDemoData> {
  const now = Date.now();
  if (dashboardDemoCacheEntry !== null && now < dashboardDemoCacheEntry.expiresAt) {
    return cloneDashboardDemoData(dashboardDemoCacheEntry.data);
  }

  dashboardDemoDataPromise ??= fetchDashboardDemoDataOnce();

  try {
    const data = await dashboardDemoDataPromise;
    dashboardDemoCacheEntry = {
      data,
      expiresAt: Date.now() + DEMO_DASHBOARD_CACHE_TTL_MS,
    };
    return cloneDashboardDemoData(data);
  } finally {
    dashboardDemoDataPromise = null;
  }
}

export async function getDashboardDemoData() {
  return loadDashboardDemoData();
}

export async function getDashboardOverview() {
  const data = await loadDashboardDemoData();
  return {
    kpis: data.kpis,
    activity: data.activity,
    totals: data.totals,
    analytics: data.analytics,
  };
}

export async function getPipelineDashboardData() {
  const data = await loadDashboardDemoData();
  return data.pipelineStages;
}

export async function getRecruiterDashboardData() {
  const data = await loadDashboardDemoData();
  return data.recruiters;
}

export async function getClientActivityData() {
  const data = await loadDashboardDemoData();
  return data.clients;
}

export async function getDashboardAnalyticsData() {
  const data = await loadDashboardDemoData();
  return {
    totals: data.totals,
    analytics: data.analytics,
  };
}
