import { PIPELINE_STAGE_LABELS } from "@/components/common/constants/dashboard-constants";
import type { PipelineStage, PipelineStageMetric } from "@/types/dashboard";

/**
 * Shared by the server-rendered dashboard payload and the client-side refetch
 * the funnel's recruiter filter fires, so both render the same rows. Keep it
 * free of server-only imports (`next/headers` via lib/api/*).
 */

/** Stages the dashboard funnel renders, top to bottom. */
export const PIPELINE_FUNNEL_ORDER: PipelineStage[] = [
  "sourced",
  "sent_to_client",
  "interview",
  "rejected",
  "candidate_dropped",
  "on_hold",
];

/**
 * CHART_COLORS entries pinned per stage rather than taken by row index, so a
 * bar keeps its colour when the funnel is refiltered and the two drop-off
 * stages read as drop-offs.
 */
export const PIPELINE_STAGE_COLORS: Record<PipelineStage, string> = {
  sourced: "#60A5FA",
  sent_to_client: "#F3FF54",
  interview: "#C084FC",
  selected: "#2DD4BF",
  joined: "#3DDC97",
  rejected: "#FF8A8A",
  candidate_dropped: "#FB923C",
  on_hold: "#94A3B8",
};

/** Shorter than the API's "Candidate Dropped", which the bar label truncates. */
const FUNNEL_LABEL_OVERRIDES: Partial<Record<PipelineStage, string>> = {
  candidate_dropped: "Dropped",
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
      label: FUNNEL_LABEL_OVERRIDES[stage] ?? source?.label ?? PIPELINE_STAGE_LABELS[stage],
      count: source?.count ?? 0,
      percent: source?.percent ?? 0,
    };
  });
}
