import type { RefereeSummary, RefereeReferral, RefereePayment } from "@/types";

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

async function clientFetch<T>(path: string): Promise<T> {
  const res = await fetch(`${API_URL}${path}`, {
    method: "GET",
    headers: { Accept: "application/json" },
    credentials: "include",
  });
  if (!res.ok) throw new Error(`Referee API failed (${res.status}) on ${path}`);
  return res.json();
}

export async function getRefereeSummary(): Promise<RefereeSummary> {
  return clientFetch<RefereeSummary>("/api/v1/referee-dashboard/summary");
}

export async function getRefereeReferrals(): Promise<RefereeReferral[]> {
  return clientFetch<RefereeReferral[]>("/api/v1/referee-dashboard/referrals");
}

export async function getRefereePayments(): Promise<RefereePayment[]> {
  return clientFetch<RefereePayment[]>("/api/v1/referee-dashboard/payments");
}

/** The only two moves the portal offers; the backend enforces the same pair. */
export type RefereeStageMove = "interview" | "selected" | "rejected";

async function readError(res: Response, fallback: string): Promise<string> {
  try {
    const body = await res.json();
    if (typeof body?.detail === "string") return body.detail;
  } catch {
    // Non-JSON error body — fall through to the generic message.
  }
  return fallback;
}

export async function moveOwnReferral(
  mappingId: string,
  newStage: RefereeStageMove,
): Promise<void> {
  const res = await fetch(`${API_URL}/api/v1/referee-dashboard/referrals/${mappingId}/move`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    credentials: "include",
    body: JSON.stringify({ new_stage: newStage }),
  });
  if (!res.ok) throw new Error(await readError(res, "Could not update this referral."));
}

export async function uploadOwnReferralOffer(mappingId: string, file: File): Promise<void> {
  const formData = new FormData();
  formData.append("file", file);

  const res = await fetch(
    `${API_URL}/api/v1/referee-dashboard/referrals/${mappingId}/offer-letter`,
    { method: "PUT", credentials: "include", body: formData },
  );
  if (!res.ok) throw new Error(await readError(res, "Could not upload the offer letter."));
}
