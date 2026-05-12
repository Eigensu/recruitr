import type { DashboardTone, PipelineStage } from "@/types/dashboard";

export const DASHBOARD_COLORS = {
  navy: "#002348",
  navyDark: "#001A36",
  yellow: "#F3FF54",
  charcoal: "#262626",
  light: "#F9F7F8",
  white: "#FFFFFF",
  success: "#3DDC97",
  danger: "#FF5A5F",
  warning: "#F7C948",
};

export const DASHBOARD_CARD_CLASS =
  "rounded-lg border border-white/10 bg-white/[0.045] shadow-sm shadow-black/20 backdrop-blur";

export const DASHBOARD_PANEL_CLASS =
  "rounded-lg border border-white/10 bg-white/[0.035] shadow-sm shadow-black/20";

export const DASHBOARD_TABLE_HEADER_CLASS =
  "text-xs font-semibold uppercase tracking-normal text-white/45";

export const PIPELINE_STAGE_LABELS: Record<PipelineStage, string> = {
  added: "Added",
  shortlisted: "Shortlisted",
  sent_to_client: "Sent to Client",
  rejected: "Rejected",
  hold: "Hold",
  offer_sent: "Offer Sent",
  offer_accepted: "Offer Accepted",
  joined: "Joined",
  dropped: "Candidate Dropped",
};

export const TONE_CLASSES: Record<
  DashboardTone,
  {
    card: string;
    text: string;
    muted: string;
    accent: string;
    chip: string;
  }
> = {
  yellow: {
    card: "border-yellow/70 bg-yellow text-navy shadow-yellow/10",
    text: "text-navy",
    muted: "text-navy/70",
    accent: "bg-navy",
    chip: "bg-navy text-yellow",
  },
  navy: {
    card: "border-yellow/20 bg-navy text-white",
    text: "text-white",
    muted: "text-white/60",
    accent: "bg-yellow",
    chip: "bg-yellow/15 text-yellow",
  },
  green: {
    card: "border-emerald-300/20 bg-emerald-400/10 text-white",
    text: "text-white",
    muted: "text-emerald-100/70",
    accent: "bg-emerald-300",
    chip: "bg-emerald-300/15 text-emerald-200",
  },
  red: {
    card: "border-red-300/20 bg-red-400/10 text-white",
    text: "text-white",
    muted: "text-red-100/70",
    accent: "bg-red-300",
    chip: "bg-red-300/15 text-red-200",
  },
  neutral: {
    card: "border-white/10 bg-white/[0.045] text-white",
    text: "text-white",
    muted: "text-white/55",
    accent: "bg-white",
    chip: "bg-white/10 text-white/75",
  },
};
