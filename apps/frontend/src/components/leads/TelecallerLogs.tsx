"use client";

import { useEffect, useState } from "react";
import { IconLoader2 } from "@tabler/icons-react";
import { cn } from "@/lib/utils";
import { apiErrorMessage, useApiFetch } from "@/lib/api";
import { istDayEnd, istDayStart, istTimestamp } from "@/lib/ist";
import { useToast } from "@/components/ui/Toast";
import {
  fetchCallLog,
  fetchNoteLog,
  type IntakeCall,
  type IntakeNote,
  type IntakeNoteStage,
} from "@/lib/api/intake";

interface Filters {
  /** IST dates, YYYY-MM-DD, inclusive. */
  start: string;
  end: string;
  telecallerId: string;
}

type Loaded<T> = { key: string; rows: T[] };

/**
 * The newest 200 rows for a filter. The result carries the filter it answers, so
 * a slow response for a filter the user has already left is shown as "loading"
 * for the current one rather than as its rows — and no state is set in the effect
 * body, only from the promise callbacks.
 */
function useLog<T>(key: string, load: () => Promise<T[]>): { rows: T[]; loading: boolean } {
  const toast = useToast();
  const [loaded, setLoaded] = useState<Loaded<T> | null>(null);

  useEffect(() => {
    let cancelled = false;
    load()
      .then((rows) => {
        if (!cancelled) setLoaded({ key, rows });
      })
      .catch((err: unknown) => {
        if (cancelled) return;
        toast(apiErrorMessage(err, "Could not load the log."), "error");
        setLoaded({ key, rows: [] });
      });
    return () => {
      cancelled = true;
    };
    // `load` is rebuilt every render; `key` says when its inputs changed.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [key, toast]);

  return { rows: loaded?.key === key ? loaded.rows : [], loading: loaded?.key !== key };
}

function Frame({
  loading,
  empty,
  children,
}: Readonly<{ loading: boolean; empty: boolean; children: React.ReactNode }>) {
  if (loading) {
    return (
      <div className="flex h-32 items-center justify-center">
        <IconLoader2 className="size-5 animate-spin text-text-muted" />
      </div>
    );
  }
  if (empty) {
    return (
      <p className="rounded-xl border border-dashed border-border py-10 text-center text-sm text-text-secondary">
        Nothing logged in this period.
      </p>
    );
  }
  return (
    <div className="overflow-x-auto rounded-xl border border-border bg-surface">{children}</div>
  );
}

const CALL_LABEL = (call: IntakeCall): { text: string; tone: string } => {
  if (call.decision === "accept")
    return { text: "Accepted", tone: "border-emerald-500/20 bg-emerald-500/10 text-emerald-500" };
  if (call.decision === "reject")
    return { text: "Rejected", tone: "border-red-500/20 bg-red-500/10 text-red-400" };
  if (call.outcome === "connected")
    return { text: "Answered", tone: "border-sky-500/20 bg-sky-500/10 text-sky-500" };
  return { text: "No answer", tone: "border-border bg-surface-panel text-text-muted" };
};

/** Every call in the period, with the time and what came of it: the telecaller activity log. */
export function CallLog({ filters }: Readonly<{ filters: Filters }>) {
  const apiFetch = useApiFetch();
  const key = `${filters.start}|${filters.end}|${filters.telecallerId}`;
  const { rows, loading } = useLog<IntakeCall>(key, () =>
    fetchCallLog(apiFetch, {
      telecaller_id: filters.telecallerId || undefined,
      start_date: istDayStart(filters.start),
      end_date: istDayEnd(filters.end),
      limit: 200,
    }),
  );

  return (
    <Frame loading={loading} empty={rows.length === 0}>
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b border-border text-left text-xs uppercase tracking-wide text-text-muted">
            <th className="px-3 py-2 font-semibold">When (IST)</th>
            <th className="px-3 py-2 font-semibold">Telecaller</th>
            <th className="px-3 py-2 font-semibold">Lead</th>
            <th className="px-3 py-2 font-semibold">Call</th>
            <th className="px-3 py-2 font-semibold">Result</th>
            <th className="px-3 py-2 font-semibold">Note</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((call) => {
            const label = CALL_LABEL(call);
            return (
              <tr key={call.id} className="border-b border-border/60 align-top">
                <td className="whitespace-nowrap px-3 py-2 text-text-secondary">
                  {istTimestamp(call.at)}
                </td>
                <td className="px-3 py-2 text-text-primary">{call.telecaller_name ?? "—"}</td>
                <td className="px-3 py-2 text-text-primary">{call.lead_name ?? "—"}</td>
                <td className="px-3 py-2 text-text-secondary">#{call.attempt}</td>
                <td className="px-3 py-2">
                  <span
                    className={cn(
                      "rounded-full border px-2 py-0.5 text-[11px] font-semibold",
                      label.tone,
                    )}
                  >
                    {label.text}
                  </span>
                </td>
                <td className="max-w-md px-3 py-2 text-text-secondary">{call.note ?? ""}</td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </Frame>
  );
}

const STAGE_LABEL: Record<IntakeNoteStage, string> = {
  telecaller: "Telecaller",
  review: "Review",
  recruiter: "Recruiter",
};

/** Every screening note in the period, by anyone, with their stage: the notes access log. */
export function NoteLog({ filters }: Readonly<{ filters: Filters }>) {
  const apiFetch = useApiFetch();
  const key = `${filters.start}|${filters.end}|${filters.telecallerId}`;
  const { rows, loading } = useLog<IntakeNote>(key, () =>
    fetchNoteLog(apiFetch, {
      author_id: filters.telecallerId || undefined,
      start_date: istDayStart(filters.start),
      end_date: istDayEnd(filters.end),
      limit: 200,
    }),
  );

  return (
    <Frame loading={loading} empty={rows.length === 0}>
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b border-border text-left text-xs uppercase tracking-wide text-text-muted">
            <th className="px-3 py-2 font-semibold">When (IST)</th>
            <th className="px-3 py-2 font-semibold">Author</th>
            <th className="px-3 py-2 font-semibold">Stage</th>
            <th className="px-3 py-2 font-semibold">Candidate</th>
            <th className="px-3 py-2 font-semibold">Note</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((note) => (
            <tr key={note.id} className="border-b border-border/60 align-top">
              <td className="whitespace-nowrap px-3 py-2 text-text-secondary">
                {istTimestamp(note.created_at)}
              </td>
              <td className="px-3 py-2 text-text-primary">{note.author_name ?? "—"}</td>
              <td className="px-3 py-2 text-text-secondary">{STAGE_LABEL[note.stage]}</td>
              <td className="px-3 py-2 text-text-primary">{note.candidate_name ?? "—"}</td>
              <td className="max-w-xl whitespace-pre-wrap break-words px-3 py-2 text-text-secondary">
                {note.body}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </Frame>
  );
}
