import { PIPELINE_STAGE_LABELS } from "@/lib/dashboard-constants";
import type {
  ClientActivityRow,
  DashboardActivityItem,
  DashboardAnalyticsWidget,
  DashboardDemoData,
  DashboardKpi,
  PipelineStage,
  PipelineStageMetric,
  RecruiterDashboardStat,
} from "@/types/dashboard";

const invalidSheetValues = new Set(["#REF!", "#N/A", "N/A", ""]);

const safeNumber = (value: unknown, fallback: number) => {
  if (value == null || invalidSheetValues.has(String(value).trim())) return fallback;

  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : fallback;
};

const pipelineStageOrder: PipelineStage[] = [
  "sent_to_client",
  "interview_scheduled",
  "result_awaited",
  "selected",
  "rejected",
  "hold",
  "offer_sent",
  "offer_accepted",
  "joined",
  "candidate_dropped",
];

const clientNames = [
  "ABNAH",
  "Abhinav Immigration",
  "Adarsh Sweets",
  "Agarwal Biryani",
  "All in",
  "Aria Communication",
  "Atmosphere",
  "August Cafe",
  "Aures Hospitality",
  "BB",
  "BTC",
  "Baesic Fit",
  "Bare",
  "Blondie",
  "Circa 11",
  "CocoCart",
  "DU Hospitality",
  "Diva",
  "Donmai",
  "Doppler",
  "Dough and Joe",
  "EDD",
  "FHPL",
  "Flavour Pots",
  "Food Square",
  "Foodmatters",
  "Ghost Kitchens",
  "Gupta Brands",
  "Huddle and Score",
  "Hummingtree",
  "Hunger Inc",
  "Idoru",
  "Ikai",
  "Izumi",
  "Izumi - GOA",
  "Kaia",
  "Kohinoor Group",
  "La Loca Maria",
  "Le 15",
  "Malsons",
  "Mia Cucina",
  "Milagro (SLH)",
  "Monarch",
  "NOTO",
  "Neighbourhood",
  "Nidhi and Mihir PR",
  "Nova",
  "Ohris Hospitality",
  "Olive",
  "PSL",
  "Pebble-Street",
  "Quetz",
  "Red Turtle",
  "Ritika & Co.",
  "Scarlett House",
  "Shalimar",
  "Shalimar Hotel",
  "Silver Train",
  "Sivako",
  "Slink and Bardot",
  "Speciality",
  "Splendour",
  "TAB",
  "TAT",
  "The Hummingtree",
  "The Kin Hotel",
  "The Nest",
  "The Ranch",
  "Tropicool",
  "True Palate",
  "UGIPL",
  "Zima",
];

const clients: ClientActivityRow[] = clientNames.map((clientName, index) => {
  const openPositions = safeNumber("#N/A", (index % 4) + 1);
  const totalSeats = safeNumber("#N/A", openPositions + (index % 3) + 1);
  const filled = safeNumber("#N/A", index % 3);
  const remaining = Math.max(totalSeats - filled, 0);

  return {
    clientName,
    clientId: `CL-${String(index + 1).padStart(3, "0")}`,
    openPositions,
    totalSeats,
    filled,
    remaining,
    inPipeline: index % 9 === 0 ? 0 : (index % 7) + 2,
    joined: index % 6 === 0 ? 1 : 0,
  };
});

const sumClientField = (
  field: keyof Pick<
    ClientActivityRow,
    "openPositions" | "totalSeats" | "filled" | "remaining" | "inPipeline" | "joined"
  >,
) => clients.reduce((sum, client) => sum + client[field], 0);

const dashboardTotals = {
  openPositions: sumClientField("openPositions"),
  totalSeats: sumClientField("totalSeats"),
  seatsFilled: sumClientField("filled"),
  remaining: sumClientField("remaining"),
  inPipeline: sumClientField("inPipeline"),
  joined: sumClientField("joined"),
};

const distributeTotal = (total: number, weights: number[]) => {
  const weightTotal = weights.reduce((sum, weight) => sum + weight, 0);
  const counts = weights.map((weight) => Math.floor((total * weight) / weightTotal));
  let remainder = total - counts.reduce((sum, count) => sum + count, 0);

  for (let index = 0; remainder > 0; index = (index + 1) % counts.length) {
    counts[index] += 1;
    remainder -= 1;
  }

  return counts;
};

const pipelineWeights = [28, 14, 12, 9, 7, 6, 8, 4, 3];
const nonJoinedPipelineTotal = Math.max(dashboardTotals.inPipeline - dashboardTotals.joined, 0);
const nonJoinedPipelineCounts = distributeTotal(nonJoinedPipelineTotal, pipelineWeights);
const pipelineCounts = pipelineStageOrder.map((stage) =>
  stage === "joined" ? dashboardTotals.joined : (nonJoinedPipelineCounts.shift() ?? 0),
);

const adjustedPipelineTotal = pipelineCounts.reduce((sum, count) => sum + count, 0);

const pipelineStages: PipelineStageMetric[] = pipelineStageOrder.map((stage, index) => {
  const count = stage === "joined" ? dashboardTotals.joined : pipelineCounts[index];

  return {
    stage,
    label: PIPELINE_STAGE_LABELS[stage],
    count,
    percent: adjustedPipelineTotal === 0 ? 0 : Math.round((count / adjustedPipelineTotal) * 100),
  };
});

const recruiterNames = ["Edwin", "Manokamna", "Hardik", "Mohit", "Aakash"];
const recruiterFocus = [
  "Client sends",
  "Interview scheduling",
  "Offer follow-ups",
  "Shortlisting",
  "Client feedback",
];

const recruiters: RecruiterDashboardStat[] = recruiterNames.map((name, index) => {
  const assignedClients = clients.filter(
    (_, clientIndex) => clientIndex % recruiterNames.length === index,
  );

  return {
    name,
    openSeats: assignedClients.reduce((sum, client) => sum + client.remaining, 0),
    inPipeline: assignedClients.reduce((sum, client) => sum + client.inPipeline, 0),
    joined: assignedClients.reduce((sum, client) => sum + client.joined, 0),
    focus: recruiterFocus[index],
  };
});

const sentToClientCount =
  pipelineStages.find((stage) => stage.stage === "sent_to_client")?.count ?? 0;
const offersAcceptedCount =
  pipelineStages.find((stage) => stage.stage === "offer_accepted")?.count ?? 0;
const droppedCount =
  pipelineStages.find((stage) => stage.stage === "candidate_dropped")?.count ?? 0;

const liveOverview: DashboardKpi[] = [
  {
    id: "open_positions",
    label: "Open Positions",
    value: dashboardTotals.openPositions,
    helper: "Active hiring mandates",
    tone: "yellow",
    trend: `${clients.length} clients synced`,
  },
  {
    id: "total_seats_open",
    label: "Total Seats Open",
    value: dashboardTotals.totalSeats,
    helper: "Approved headcount",
    tone: "navy",
    trend: `${dashboardTotals.remaining} remaining`,
  },
  {
    id: "seats_filled",
    label: "Seats Filled",
    value: dashboardTotals.seatsFilled,
    helper: "Closed requirements",
    tone: "green",
    trend: "From client rows",
  },
  {
    id: "total_pipeline",
    label: "Total In Pipeline",
    value: dashboardTotals.inPipeline,
    helper: "Candidates being moved",
    tone: "neutral",
    trend: "Across all clients",
  },
  {
    id: "sent_to_client",
    label: "Sent to Client",
    value: sentToClientCount,
    helper: "Profiles shared",
    tone: "yellow",
    trend: "Pipeline-derived",
  },
  {
    id: "offers_accepted",
    label: "Offers Accepted",
    value: offersAcceptedCount,
    helper: "Accepted offers",
    tone: "green",
    trend: "Ready for joining",
  },
  {
    id: "candidate_dropped",
    label: "Candidate Dropped",
    value: droppedCount,
    helper: "Drop-offs this cycle",
    tone: "red",
    trend: "Needs follow-up",
  },
  {
    id: "joined",
    label: "Joined",
    value: dashboardTotals.joined,
    helper: "Confirmed joins",
    tone: "green",
    trend: "From client rows",
  },
];

const activity: DashboardActivityItem[] = [
  {
    id: "act-1",
    title: `${sentToClientCount} profiles sent to client`,
    detail: "Sent to Client is currently the busiest pipeline stage.",
    timestamp: "Updated 4 min ago",
    tone: "yellow",
  },
  {
    id: "act-2",
    title: `${offersAcceptedCount} offers accepted`,
    detail: `${dashboardTotals.joined} joined candidates are reflected in client activity.`,
    timestamp: "Updated 18 min ago",
    tone: "green",
  },
  {
    id: "act-3",
    title: `${droppedCount} drop-offs need action`,
    detail: "Dropped candidates should be reviewed with the assigned recruiter.",
    timestamp: "Updated 34 min ago",
    tone: "red",
  },
  {
    id: "act-4",
    title: `${clients.length} client rows synced`,
    detail: "Dashboard totals now roll up from the client activity table.",
    timestamp: "Updated 1 hr ago",
    tone: "neutral",
  },
];

const formatPercent = (value: number) => `${Math.round(value)}%`;

const analytics: DashboardAnalyticsWidget[] = [
  {
    id: "fill_rate",
    label: "Fill Rate",
    value: formatPercent(
      dashboardTotals.totalSeats
        ? (dashboardTotals.seatsFilled / dashboardTotals.totalSeats) * 100
        : 0,
    ),
    helper: `${dashboardTotals.seatsFilled} of ${dashboardTotals.totalSeats} seats filled`,
    tone: "green",
  },
  {
    id: "pipeline_depth",
    label: "Pipeline Depth",
    value: dashboardTotals.openPositions
      ? (dashboardTotals.inPipeline / dashboardTotals.openPositions).toFixed(1)
      : "0.0",
    helper: "Candidates per open position",
    tone: "yellow",
  },
  {
    id: "join_conversion",
    label: "Join Conversion",
    value: formatPercent(
      dashboardTotals.inPipeline ? (dashboardTotals.joined / dashboardTotals.inPipeline) * 100 : 0,
    ),
    helper: `${dashboardTotals.joined} joined from ${dashboardTotals.inPipeline} in pipeline`,
    tone: "navy",
  },
  {
    id: "seat_gap",
    label: "Seat Gap",
    value: dashboardTotals.remaining.toLocaleString("en-IN"),
    helper: "Open seats still to close",
    tone: "neutral",
  },
];

const dashboardDemoData: DashboardDemoData = {
  kpis: liveOverview,
  pipelineStages,
  recruiters,
  clients,
  activity,
  totals: dashboardTotals,
  analytics,
};

export async function getDashboardDemoData() {
  return structuredClone(dashboardDemoData);
}

export async function getDashboardOverview() {
  return structuredClone({
    kpis: dashboardDemoData.kpis,
    activity: dashboardDemoData.activity,
    totals: dashboardDemoData.totals,
    analytics: dashboardDemoData.analytics,
  });
}

export async function getPipelineDashboardData() {
  return structuredClone(dashboardDemoData.pipelineStages);
}

export async function getRecruiterDashboardData() {
  return structuredClone(dashboardDemoData.recruiters);
}

export async function getClientActivityData() {
  return structuredClone(dashboardDemoData.clients);
}

export async function getDashboardAnalyticsData() {
  return structuredClone({
    totals: dashboardDemoData.totals,
    analytics: dashboardDemoData.analytics,
  });
}
