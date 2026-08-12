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
