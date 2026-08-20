"use client";

import { useCallback, useEffect, useRef, useState } from "react";
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

  // Guards the async setState after unmount. A ref rather than a local flag so
  // refresh(), which outlives the effect that created it, reads the same value.
  const cancelled = useRef(false);

  const fetchData = useCallback(async (isInitial = false) => {
    if (!cancelled.current && isInitial) {
      setData((prev) => ({ ...prev, isLoading: true }));
    }
    try {
      const [summary, referrals, payments] = await Promise.all([
        getRefereeSummary(),
        getRefereeReferrals(),
        getRefereePayments(),
      ]);
      if (!cancelled.current) {
        setData({ summary, referrals, payments, isLoading: false, error: null });
      }
    } catch (err) {
      if (!cancelled.current) {
        setData((prev) => ({ ...prev, isLoading: false, error: err as Error }));
      }
    }
  }, []);

  useEffect(() => {
    cancelled.current = false;
    fetchData(true);

    // Poll every 15 minutes (900000 ms)
    const interval = setInterval(() => fetchData(false), 900000);

    return () => {
      cancelled.current = true;
      clearInterval(interval);
    };
  }, [fetchData]);

  /** Re-read the dashboard after an action, without flashing the skeleton. */
  const refresh = useCallback(() => fetchData(false), [fetchData]);

  return { ...data, refresh };
}
