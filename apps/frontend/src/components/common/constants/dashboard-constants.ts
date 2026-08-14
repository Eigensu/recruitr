import type { DashboardTone, PipelineStage } from "@/types/dashboard";
import {
  IconBriefcase,
  IconChartDots3,
  IconCheck,
  IconCircleX,
  IconClockHour4,
  IconPercentage,
  IconRoute,
  IconSend,
  IconTargetArrow,
  IconUsers,
  IconFileCv,
  IconWallet,
} from "@tabler/icons-react";

export const KPI_ICON_MAP = {
  open_positions: IconBriefcase,
  total_seats_open: IconUsers,
  seats_filled: IconCheck,
  total_pipeline: IconUsers,
  sent_to_client: IconSend,
  offers_accepted: IconCheck,
  candidate_dropped: IconCircleX,
  joined: IconCheck,
  // Client dashboard hero metrics
  open_roles: IconBriefcase,
  in_process: IconUsers,
  avg_days_to_shortlist: IconClockHour4,
  // Referee dashboard hero metrics
  referee_cvs_shared: IconFileCv,
  referee_cvs_actioned: IconBriefcase,
  referee_earnings: IconWallet,
} as const;

export const ANALYTICS_ICON_MAP = {
  fill_rate: IconPercentage,
  pipeline_depth: IconRoute,
  join_conversion: IconTargetArrow,
  seat_gap: IconChartDots3,
} as const;

export const DASHBOARD_COLORS = {
  navy: "var(--color-navy)",
  navyDark: "var(--color-navy-dark)",
  yellow: "var(--color-yellow)",
  charcoal: "var(--color-charcoal)",
  light: "var(--color-light)",
  white: "#FFFFFF",
  success: "#3DDC97",
  danger: "#FF5A5F",
  warning: "#F7C948",
};

export const CHART_COLORS = [
  "#F3FF54",
  "#3DDC97",
  "#60A5FA",
  "#F7C948",
  "#FF8A8A",
  "#C084FC",
  "#FB923C",
  "#2DD4BF",
  "#FFFFFF",
  "#94A3B8",
];

export const DASHBOARD_CARD_CLASS =
  "rounded-lg bg-surface-card shadow-md shadow-black/30 backdrop-blur";

export const DASHBOARD_PANEL_CLASS = "rounded-lg bg-surface-panel shadow-md shadow-black/30";

export const DASHBOARD_WIDGET_CLASS = "rounded-lg bg-surface-panel p-4 shadow-sm shadow-black/20";

export const DASHBOARD_TABLE_HEADER_CLASS =
  "text-xs font-semibold uppercase tracking-normal text-[color:var(--color-text-secondary)]";

export const PIPELINE_STAGE_LABELS: Record<PipelineStage, string> = {
  sourced: "Added",
  sent_to_client: "Sent to Client",
  interview: "Interview",
  decision_pending: "Result Awaited",
  offer: "Offer Sent",
  offer_accepted: "Offer Accepted",
  position_close: "Joined",
  rejected: "Rejected",
  on_hold: "On Hold",
};

export const TONE_STYLES: Record<
  DashboardTone,
  {
    cardBg: string;
    cardText: string;
    mutedOpacity: number;
    chipBg: string;
    chipText: string;
    shadow: string;
  }
> = {
  yellow: {
    cardBg: "#f3ff54",
    cardText: "#002348",
    mutedOpacity: 0.65,
    chipBg: "#002348",
    chipText: "#f3ff54",
    shadow: "0 10px 24px rgba(243, 255, 84, 0.2)",
  },
  navy: {
    cardBg: "#002348",
    cardText: "#ffffff",
    mutedOpacity: 0.6,
    chipBg: "rgba(243,255,84,0.15)",
    chipText: "#f3ff54",
    shadow: "0 10px 24px rgba(0, 0, 0, 0.3)",
  },
  green: {
    cardBg: "var(--color-card-positive)",
    cardText: "var(--color-card-positive-text)",
    mutedOpacity: 0.7,
    chipBg: "var(--color-card-positive-badge)",
    chipText: "var(--color-card-positive-text)",
    shadow: "0 10px 24px rgba(0, 0, 0, 0.2)",
  },
  red: {
    cardBg: "var(--color-card-negative)",
    cardText: "var(--color-card-negative-text)",
    mutedOpacity: 0.7,
    chipBg: "var(--color-card-negative-badge)",
    chipText: "var(--color-card-negative-text)",
    shadow: "0 10px 24px rgba(0, 0, 0, 0.2)",
  },
  neutral: {
    cardBg: "var(--color-surface-val)",
    cardText: "var(--color-text-primary)",
    mutedOpacity: 0.55,
    chipBg: "rgba(255,255,255,0.1)",
    chipText: "var(--color-text-primary)",
    shadow: "0 10px 24px rgba(0, 0, 0, 0.3)",
  },
};
