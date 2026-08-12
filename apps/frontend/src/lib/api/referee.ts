import { dashboardFetch } from "./dashboard";
import type { RefereeSummary, RefereeReferral, RefereePayment } from "@/types";

export async function getRefereeSummary(): Promise<RefereeSummary> {
  return dashboardFetch<RefereeSummary>("/api/v1/referee-dashboard/summary");
}

export async function getRefereeReferrals(): Promise<RefereeReferral[]> {
  return dashboardFetch<RefereeReferral[]>("/api/v1/referee-dashboard/referrals");
}

export async function getRefereePayments(): Promise<RefereePayment[]> {
  return dashboardFetch<RefereePayment[]>("/api/v1/referee-dashboard/payments");
}
