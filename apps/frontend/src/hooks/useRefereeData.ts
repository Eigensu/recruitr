"use client";

import { useEffect, useState } from "react";
import { getRefereeSummary, getRefereeReferrals, getRefereePayments } from "@/lib/api/referee";
import type { RefereeSummary, RefereeReferral, RefereePayment } from "@/types";

export interface RefereeDataState {
  summary: RefereeSummary | null;
  referrals: RefereeReferral[];
  payments: RefereePayment[];
  isLoading: boolean;
  error: Error | null;
}

export function useRefereeData() {
  const [data, setData] = useState<RefereeDataState>({
    summary: null,
    referrals: [],
    payments: [],
    isLoading: true,
    error: null,
  });

  useEffect(() => {
    let cancelled = false;

    async function fetchData(isInitial = false) {
      if (!cancelled && isInitial) {
        setData((prev) => ({ ...prev, isLoading: true }));
      }
      try {
        const [summary, referrals, payments] = await Promise.all([
          getRefereeSummary(),
          getRefereeReferrals(),
          getRefereePayments(),
        ]);
        if (!cancelled) {
          setData({ summary, referrals, payments, isLoading: false, error: null });
        }
      } catch (err) {
        if (!cancelled) {
          setData((prev) => ({ ...prev, isLoading: false, error: err as Error }));
        }
      }
    }

    fetchData(true);

    // Poll every 15 minutes (900000 ms)
    const interval = setInterval(() => fetchData(false), 900000);

    return () => {
      cancelled = true;
      clearInterval(interval);
    };
  }, []);

  return data;
}
