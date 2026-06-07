import type { KanbanStage, PipelineBoardData } from "@/types";

type ApiFetch = <T>(path: string, options?: RequestInit) => Promise<T>;

export interface StageMoveResponse {
  mapping_id: string;
  candidate_id: string;
  position_id: string;
  old_stage: KanbanStage;
  new_stage: KanbanStage;
  decision: string;
  recruiter_score_delta: number;
  activity_id: string | null;
}

export function getPipelineBoard(apiFetch: ApiFetch): Promise<PipelineBoardData> {
  return apiFetch("/api/v1/pipeline/board");
}

export function moveMappingStage(
  apiFetch: ApiFetch,
  mappingId: string,
  newStage: KanbanStage,
): Promise<StageMoveResponse> {
  return apiFetch(`/api/v1/pipeline/mappings/${mappingId}/move`, {
    method: "POST",
    body: JSON.stringify({ new_stage: newStage }),
  });
}
