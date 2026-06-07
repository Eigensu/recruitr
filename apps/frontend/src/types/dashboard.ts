export type DashboardTone = "yellow" | "navy" | "green" | "red" | "neutral";

export type PipelineStage =
  | "sourced"
  | "sent_to_client"
  | "interview"
  | "decision_pending"
  | "offer"
  | "offer_accepted"
  | "position_close"
  | "rejected"
  | "on_hold";

export interface DashboardKpi {
  id: string;
  label: string;
  value: number;
  helper: string;
  tone: DashboardTone;
  trend: string;
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
}

export interface DashboardAnalyticsWidget {
  id: string;
  label: string;
  value: string;
  helper: string;
  tone: DashboardTone;
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
