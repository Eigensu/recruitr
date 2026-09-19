"use client";

import { useCallback, useEffect, useState } from "react";
import { AnimatePresence } from "motion/react";
import { IconLoader2, IconPhoneCall, IconRefresh } from "@tabler/icons-react";
import { useApiFetch, apiErrorMessage } from "@/lib/api";
import { useToast } from "@/components/ui/Toast";
import LeadCard from "@/components/leads/LeadCard";
import {
  acceptLead,
  fetchMyLeads,
  rejectLead,
  type IntakeLead,
  type IntakeRejectReason,
} from "@/lib/api/intake";

/**
 * A telecaller's own queue: the people to ring, oldest assignment first.
 *
 * Oldest first is the server's ordering and is deliberately not re-sorted here
 * — the oldest lead is the closest to breaching, so working the list top to
 * bottom is the same thing as working it in the order that keeps people inside
 * the day.
 */
export default function TelecallerQueue() {
  const apiFetch = useApiFetch();
  const toast = useToast();
  const [leads, setLeads] = useState<IntakeLead[]>([]);
  const [loading, setLoading] = useState(true);
  const [busyId, setBusyId] = useState<string | null>(null);

  // State is only ever set from a promise callback, never synchronously in the
  // effect body — the same shape useCurrentUser uses, and what keeps React from
  // cascading a second render before the first has painted.
  const load = useCallback(
    (): Promise<void> =>
      fetchMyLeads(apiFetch)
        .then(setLeads)
        .catch((err: unknown) => {
          toast(apiErrorMessage(err, "Could not load your queue."), "error");
        }),
    [apiFetch, toast],
  );

  useEffect(() => {
    let cancelled = false;
    load().finally(() => {
      if (!cancelled) setLoading(false);
    });
    return () => {
      cancelled = true;
    };
  }, [load]);

  /**
   * Both decisions share this: the card leaves the list as soon as the server
   * confirms. No optimistic removal — a failed accept that had already vanished
   * from the screen would look like a call that was logged when it was not.
   */
  async function decide(lead: IntakeLead, action: () => Promise<IntakeLead>, done: string) {
    setBusyId(lead.id);
    try {
      await action();
      setLeads((prev) => prev.filter((row) => row.id !== lead.id));
      toast(done, "success");
    } catch (err) {
      toast(apiErrorMessage(err, "That did not go through."), "error");
    } finally {
      setBusyId(null);
    }
  }

  if (loading) {
    return (
      <div className="flex h-64 items-center justify-center">
        <IconLoader2 className="size-6 animate-spin text-text-muted" />
      </div>
    );
  }

  return (
    <main className="mx-auto w-full max-w-2xl p-4 duration-300 animate-in fade-in sm:p-6 lg:p-8">
      <header className="mb-6 flex items-start justify-between gap-3">
        <div>
          <h1 className="font-heading text-2xl font-bold tracking-tight text-text-primary">
            Your queue
          </h1>
          <p className="mt-1 text-sm text-text-secondary">
            {leads.length === 0
              ? "Nothing waiting."
              : `${leads.length} ${leads.length === 1 ? "person" : "people"} to call, longest wait first.`}
          </p>
        </div>
        <button
          type="button"
          onClick={() => load()}
          aria-label="Refresh"
          className="rounded-lg border border-border p-2 text-text-muted transition-colors hover:text-text-primary"
        >
          <IconRefresh className="size-4" />
        </button>
      </header>

      {leads.length === 0 ? (
        <div className="flex flex-col items-center justify-center gap-3 rounded-xl border border-dashed border-border py-16 text-center">
          <IconPhoneCall className="size-8 text-text-secondary" />
          <p className="text-sm text-text-secondary">
            You are all caught up. New leads arrive automatically.
          </p>
        </div>
      ) : (
        <div className="flex flex-col gap-3">
          <AnimatePresence mode="popLayout">
            {leads.map((lead) => (
              <LeadCard
                key={lead.id}
                lead={lead}
                busy={busyId === lead.id}
                onAccept={(notes) =>
                  decide(
                    lead,
                    () => acceptLead(apiFetch, lead.id, notes),
                    `${lead.full_name} passed to a recruiter.`,
                  )
                }
                onReject={(reason: IntakeRejectReason | undefined, notes) =>
                  decide(
                    lead,
                    () => rejectLead(apiFetch, lead.id, reason, notes),
                    `${lead.full_name} rejected.`,
                  )
                }
              />
            ))}
          </AnimatePresence>
        </div>
      )}
    </main>
  );
}
