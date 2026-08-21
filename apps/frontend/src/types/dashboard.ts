export type DashboardTone = "yellow" | "navy" | "green" | "red" | "neutral";

export type PipelineStage =
  | "sourced"
  | "sent_to_client"
  | "interview"
  | "selected"
  | "joined"
  | "rejected"
  | "candidate_dropped"
  | "on_hold";

export interface DashboardKpi {
  id: string;
  label: string;
  value: number;
  helper: string;
  tone: DashboardTone;
  trend: string;
  /** Unit shown after the animated number, e.g. "days". */
  suffix?: string;
  /** Symbol shown before the animated number, e.g. "₹". */
  prefix?: string;
}

export interface PipelineStageMetric {
  stage: PipelineStage;
  label: string;
  count: number;
  percent: number;
}

export interface RecruiterDashboardStat {
  name: string;
  openSeats: number;
  inPipeline: number;
  joined: number;
  focus: string;
}

export interface ClientActivityRow {
  clientName: string;
  clientId: string;
  openPositions: number;
  totalSeats: number;
  filled: number;
  remaining: number;
  inPipeline: number;
  joined: number;
}

export interface DashboardActivityItem {
  id: string;
  title: string;
  detail: string;
  timestamp: string;
  tone: DashboardTone;
}

export interface DashboardTotals {
  openPositions: number;
  totalSeats: number;
  seatsFilled: number;
  remaining: number;
  inPipeline: number;
  joined: number;
  actionNeeded: number;
  avgDaysToShortlist: number;
}

export interface AnalyticsBreakdownRow {
  label: string;
  value: string;
}

export interface DashboardAnalyticsWidget {
  id: string;
  label: string;
  value: string;
  helper: string;
  tone: DashboardTone;
  /** Per-row detail behind the headline number; renders under the helper. */
  breakdown?: AnalyticsBreakdownRow[];
}

export interface StageTimingMetric {
  stage: PipelineStage;
  label: string;
  avgDays: number;
  count: number;
}

export interface StageTimingSummary {
  stages: StageTimingMetric[];
  avgDaysInStage: number;
  avgDaysToAction: number;
  actionMoves: number;
  candidatesWaiting: number;
  stalledCount: number;
  stalledAfterDays: number;
}

export interface DashboardDemoData {
  kpis: DashboardKpi[];
  pipelineStages: PipelineStageMetric[];
  recruiters: RecruiterDashboardStat[];
  clients: ClientActivityRow[];
  activity: DashboardActivityItem[];
  totals: DashboardTotals;
  analytics: DashboardAnalyticsWidget[];
}

export type ClientProfileStatus = "active" | "on_hold" | "closed";

export interface ClientProfileRow {
  client_name: string;
  total_open_positions: number;
  total_candidates: number;
  active_recruiters: number;
  last_activity: string | null; // ISO datetime string
  status: ClientProfileStatus;
}
