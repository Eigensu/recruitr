import type { CandidateCard, CandidateSource, LegacyCandidateStatus } from "@/types";
import type { KanbanFilters } from "@/stores/usePipelineStore";

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

type FilteredCard = CandidateCard & { status: LegacyCandidateStatus };

export interface SuggestedCandidate {
  id: string;
  name: string;
  email: string;
  resume_url: string | null;
  extracted_skills: string[];
  tags: string[];
  source: CandidateSource;
  cv_link: string | null;
  match_score: number;
}

/** Keyword-scored suggestions for a position (reuses the match engine). */
export async function fetchSuggestions(
  positionId: string,
  limit = 10,
): Promise<SuggestedCandidate[]> {
  const res = await fetch(
    `${API_URL}/api/v1/pipeline/top-candidates?position_id=${positionId}&limit=${limit}`,
    { credentials: "include" },
  );
  if (!res.ok) throw new Error(`Suggestions fetch failed: ${res.status}`);
  return res.json();
}

/** Assign a candidate to a position's pipeline (lands in Pending). */
export async function assignCandidate(positionId: string, candidateId: string): Promise<void> {
  const res = await fetch(`${API_URL}/api/v1/pipeline/match`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    credentials: "include",
    body: JSON.stringify({
      position_id: positionId,
      candidate_id: candidateId,
      target_status: "pending",
    }),
  });
  if (!res.ok) throw new Error(await res.text());
}

export async function fetchFilteredPipeline(
  positionId: string,
  filters: KanbanFilters,
): Promise<Record<LegacyCandidateStatus, CandidateCard[]>> {
  const params = new URLSearchParams({ position_id: positionId });
  if (filters.recruiter_id) params.set("recruiter_id", filters.recruiter_id);
  if (filters.client_id) params.set("client_id", filters.client_id);
  if (filters.stage) params.set("stage", filters.stage);
  if (filters.mapped_after) params.set("mapped_after", filters.mapped_after);
  if (filters.mapped_before) params.set("mapped_before", filters.mapped_before);
  if (filters.tags) filters.tags.forEach((t) => params.append("tags", t));

  const res = await fetch(`${API_URL}/api/v1/pipeline/filtered?${params.toString()}`, {
    credentials: "include",
  });
  if (!res.ok) throw new Error(`Pipeline filtered fetch failed: ${res.status}`);
  const cards: FilteredCard[] = await res.json();

  return {
    pending: cards.filter((c) => c.status === "pending"),
    accepted: cards.filter((c) => c.status === "accepted"),
    rejected: cards.filter((c) => c.status === "rejected"),
  };
}
