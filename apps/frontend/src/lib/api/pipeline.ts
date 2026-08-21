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

export async function setMappingInterviewDate(
  mappingId: string,
  interviewDate: string,
): Promise<void> {
  const res = await fetch(`${API_URL}/api/v1/pipeline/mappings/${mappingId}/interview-date`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    credentials: "include",
    body: JSON.stringify({ interview_date: interviewDate }),
  });
  if (!res.ok) throw new Error(await res.text());
}

export async function uploadMappingOffer(mappingId: string, file: File): Promise<void> {
  const formData = new FormData();
  formData.append("file", file);

  const res = await fetch(`${API_URL}/api/v1/pipeline/mappings/${mappingId}/offer-letter`, {
    method: "PUT",
    credentials: "include",
    body: formData,
  });
  // The endpoint rejects a non-PDF (400) and an oversize file (413) with a
  // readable `detail`; res.text() would put the raw JSON in front of the user.
  if (!res.ok) {
    let detail = "Could not upload the offer letter.";
    try {
      const body = await res.json();
      if (typeof body?.detail === "string") detail = body.detail;
    } catch {
      // Non-JSON error body — keep the generic message.
    }
    throw new Error(detail);
  }
}

export async function setMappingJoiningDate(
  mappingId: string,
  joiningDate: string,
  salaryOffered: number,
): Promise<void> {
  const res = await fetch(`${API_URL}/api/v1/pipeline/mappings/${mappingId}/joining-date`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    credentials: "include",
    body: JSON.stringify({ joining_date: joiningDate, salary_offered: salaryOffered }),
  });
  if (!res.ok) throw new Error(await res.text());
}

export async function setMappingDropped(mappingId: string, droppedNotes: string): Promise<void> {
  const res = await fetch(`${API_URL}/api/v1/pipeline/mappings/${mappingId}/dropped`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    credentials: "include",
    body: JSON.stringify({ dropped_notes: droppedNotes }),
  });
  if (!res.ok) throw new Error(await res.text());
}
