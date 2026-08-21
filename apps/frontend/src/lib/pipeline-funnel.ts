import type { PipelineStage, PipelineStageMetric } from "@/types/dashboard";

/**
 * Shared by the server-rendered dashboard payload and the client-side refetch
 * the funnel's recruiter filter fires, so both render the same rows. Keep it
 * free of server-only imports (`next/headers` via lib/api/*).
 */

/**
 * The funnel's two groups, splitting on the same line the backend does:
 * TERMINAL_STAGES close a mapping's lifecycle, everything else is still live.
 * Every stage appears in one of them, so the percentages add up to the whole
 * pipeline instead of to whatever subset happened to be on screen.
 */
export const FUNNEL_GROUPS: ReadonlyArray<{ id: string; label: string; stages: PipelineStage[] }> =
  [
    {
      id: "open",
      label: "Still open",
      stages: ["sourced", "sent_to_client", "interview", "selected", "on_hold"],
    },
    { id: "closed", label: "Closed", stages: ["joined", "rejected", "candidate_dropped"] },
  ];

/** Stages the funnel renders, top to bottom. */
export const PIPELINE_FUNNEL_ORDER: PipelineStage[] = FUNNEL_GROUPS.flatMap(
  (group) => group.stages,
);

/**
 * Owned here rather than taken from the API, whose labels come out of a
 * `.title()` call — "Sent To Client", "Candidate Dropped". Sentence case, and
 * short enough to sit beside a count in a narrow panel.
 */
export const PIPELINE_FUNNEL_LABELS: Record<PipelineStage, string> = {
  sourced: "Sourced",
  sent_to_client: "Sent to client",
  interview: "Interview",
  selected: "Selected",
  joined: "Joined",
  rejected: "Rejected",
  candidate_dropped: "Dropped",
  on_hold: "On hold",
};

/**
 * Colour carries the outcome, not the row number: warming yellows as a
 * candidate advances, green for a hire, red and orange for the two ways out,
 * grey for paused. Pinned per stage so a bar keeps its colour when refiltered.
 */
export const PIPELINE_STAGE_COLORS: Record<PipelineStage, string> = {
  sourced: "rgba(243, 255, 84, 0.38)",
  sent_to_client: "rgba(243, 255, 84, 0.62)",
  interview: "rgba(243, 255, 84, 0.82)",
  selected: "#F3FF54",
  joined: "#3DDC97",
  rejected: "#FF8A8A",
  candidate_dropped: "#FB923C",
  on_hold: "#94A3B8",
};

export interface ApiPipelineStage {
  stage: string;
  label: string;
  count: number;
  percent: number;
}

export interface RecruiterOption {
  id: string;
  name: string;
}

export function buildPipelineStages(apiStages: ApiPipelineStage[]): PipelineStageMetric[] {
  const stageMap = new Map(apiStages.map((stage) => [stage.stage, stage]));

  return PIPELINE_FUNNEL_ORDER.map((stage) => {
    const source = stageMap.get(stage);
    return {
      stage,
      label: PIPELINE_FUNNEL_LABELS[stage],
      count: source?.count ?? 0,
      percent: source?.percent ?? 0,
    };
  });
}

/** Whole percents at a glance; anything present but tiny stays visible as <1%. */
export function formatPipelinePercent(percent: number): string {
  if (percent <= 0) return "0%";
  if (percent < 1) return "<1%";
  return `${Math.round(percent)}%`;
}
