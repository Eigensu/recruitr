"use client";

import { useEffect, useState } from "react";
import { IconChevronLeft, IconChevronRight, IconDownload, IconLoader2 } from "@tabler/icons-react";
import { cn } from "@/lib/utils";
import { apiErrorMessage, useApiFetch } from "@/lib/api";
import { mondayOf, shiftDate, shortDate, todayIst } from "@/lib/ist";
import { useToast } from "@/components/ui/Toast";
import TelecallerReportTable from "@/components/leads/TelecallerReportTable";
import TelecallerTargets from "@/components/leads/TelecallerTargets";
import { CallLog, NoteLog } from "@/components/leads/TelecallerLogs";
import {
  fetchTelecallerReport,
  fetchTelecallerTargets,
  type TelecallerPeriod,
  type TelecallerReport,
  type TelecallerTarget,
} from "@/lib/api/intake";

type Tab = "report" | "targets" | "calls" | "notes";

const TABS: { key: Tab; label: string }[] = [
  { key: "report", label: "Report" },
  { key: "targets", label: "Targets" },
  { key: "calls", label: "Call log" },
  { key: "notes", label: "Notes log" },
];

const PERIODS: { value: TelecallerPeriod; label: string }[] = [
  { value: "day", label: "Day" },
  { value: "week", label: "Week" },
  { value: "range", label: "Custom range" },
];

// The server refuses anything longer; checking here says why before a round trip.
const MAX_RANGE_DAYS = 92;

const field =
  "rounded-lg border border-border bg-canvas px-3 py-1.5 text-sm text-text-primary focus:outline-none focus-visible:ring-2 focus-visible:ring-yellow";

/** A CSV cell. A leading = + - @ is made literal, so a spreadsheet never runs it as a formula. */
function csvCell(value: string | number | null): string {
  if (value === null) return "";
  const text = String(value);
  const safe = /^[=+\-@]/.test(text) && Number.isNaN(Number(text)) ? `'${text}` : text;
  return /[",\n]/.test(safe) ? `"${safe.replaceAll('"', '""')}"` : safe;
}

function download(filename: string, lines: (string | number | null)[][]) {
  const csv = lines.map((line) => line.map(csvCell).join(",")).join("\n");
  const url = URL.createObjectURL(new Blob([csv], { type: "text/csv;charset=utf-8" }));
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  link.click();
  URL.revokeObjectURL(url);
}

function percent(rate: number | null): string {
  return rate === null ? "" : `${Math.round(rate * 100)}%`;
}

function downloadSummary(report: TelecallerReport) {
  download(`telecallers_${report.start_date}_to_${report.end_date}.csv`, [
    [
      "Telecaller",
      "Calls",
      "Answered",
      "No answer",
      "Forwarded",
      "Rejected",
      "Dead",
      "Bad lead rate",
      "Notes",
      "Calls target",
      "Of target",
    ],
    ...report.rows.map((r) => [
      r.telecaller_name,
      r.calls,
      r.connected,
      r.unanswered,
      r.forwarded,
      r.rejected,
      r.dead,
      percent(r.bad_lead_rate),
      r.notes_written,
      r.target_calls,
      percent(r.target_pct),
    ]),
  ]);
}

function downloadDaily(report: TelecallerReport) {
  download(`telecallers_daily_${report.start_date}_to_${report.end_date}.csv`, [
    ["Telecaller", "Date", "Calls", "Answered", "No answer", "Forwarded", "Rejected", "Dead"],
    ...report.rows.flatMap((r) =>
      r.days.map((d) => [
        r.telecaller_name,
        d.date,
        d.calls,
        d.connected,
        d.unanswered,
        d.forwarded,
        d.rejected,
        d.dead,
      ]),
    ),
  ]);
}

/** The period as the controls describe it: the dates, or why it cannot be asked for. */
function resolvePeriod(
  period: TelecallerPeriod,
  anchor: string,
  start: string,
  end: string,
): { first: string; last: string; error: string | null } {
  if (period === "day") return { first: anchor, last: anchor, error: null };
  if (period === "week") {
    const monday = mondayOf(anchor);
    return { first: monday, last: shiftDate(monday, 6), error: null };
  }
  if (!start || !end) return { first: start, last: end, error: "Pick a start and an end date." };
  if (end < start) return { first: start, last: end, error: "The end is before the start." };
  const days = (Date.parse(end) - Date.parse(start)) / 86_400_000 + 1;
  if (days > MAX_RANGE_DAYS) {
    return { first: start, last: end, error: `A range can be at most ${MAX_RANGE_DAYS} days.` };
  }
  return { first: start, last: end, error: null };
}

/**
 * Telecaller metrics for admins and maintainers: the report for a day, a week or
 * a range (one telecaller or all), the daily and weekly calls targets, and the
 * call and note logs behind the numbers. Days are IST, the same as the server's.
 */
export default function TelecallerMetrics() {
  const apiFetch = useApiFetch();
  const toast = useToast();
  const [tab, setTab] = useState<Tab>("report");
  const [period, setPeriod] = useState<TelecallerPeriod>("day");
  const [anchor, setAnchor] = useState(() => todayIst());
  const [rangeStart, setRangeStart] = useState(() => shiftDate(todayIst(), -6));
  const [rangeEnd, setRangeEnd] = useState(() => todayIst());
  const [telecallerId, setTelecallerId] = useState("");
  const [targets, setTargets] = useState<TelecallerTarget[]>([]);
  const [loaded, setLoaded] = useState<{ key: string; report: TelecallerReport } | null>(null);

  const today = todayIst();
  const { first, last, error: rangeError } = resolvePeriod(period, anchor, rangeStart, rangeEnd);
  // Everything the request depends on; the response carries it, so a slow answer
  // for something already left behind is never shown as the current one.
  const key = `${period}|${first}|${last}|${telecallerId}`;
  const report = loaded?.key === key ? loaded.report : null;
  const loading = !rangeError && report === null;

  useEffect(() => {
    let cancelled = false;
    fetchTelecallerTargets(apiFetch)
      .then((rows) => {
        if (!cancelled) setTargets(rows);
      })
      .catch((err: unknown) => {
        if (!cancelled) toast(apiErrorMessage(err, "Could not load the telecallers."), "error");
      });
    return () => {
      cancelled = true;
    };
  }, [apiFetch, toast]);

  useEffect(() => {
    if (rangeError) return undefined;
    let cancelled = false;
    fetchTelecallerReport(apiFetch, {
      period,
      ...(period === "range" ? { start: first, end: last } : { date: first }),
      telecaller_id: telecallerId || undefined,
    })
      .then((data) => {
        if (!cancelled) setLoaded({ key, report: data });
      })
      .catch((err: unknown) => {
        if (!cancelled) toast(apiErrorMessage(err, "Could not load the report."), "error");
      });
    return () => {
      cancelled = true;
    };
    // `key` already encodes period, dates and telecaller.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [apiFetch, key, rangeError, toast]);

  const step = period === "week" ? 7 : 1;
  const canStep = period !== "range";
  const atPresent = last >= today;

  function handleSaved(saved: TelecallerTarget) {
    setTargets((prev) => prev.map((t) => (t.telecaller_id === saved.telecaller_id ? saved : t)));
    // The saved target changes the progress bars, so the report is asked for again.
    setLoaded(null);
  }

  const periodLabel =
    first === last ? shortDate(first) : `${shortDate(first)} – ${shortDate(last)}`;

  return (
    <div>
      <div className="mb-4 flex gap-1 border-b border-border">
        {TABS.map((t) => (
          <button
            key={t.key}
            type="button"
            onClick={() => setTab(t.key)}
            className={cn(
              "px-4 py-2 text-sm font-medium transition-colors",
              tab === t.key
                ? "border-b-2 border-yellow text-text-primary"
                : "border-b-2 border-transparent text-text-secondary hover:text-text-primary",
            )}
          >
            {t.label}
          </button>
        ))}
      </div>

      {tab !== "targets" && (
        <div className="mb-4 flex flex-wrap items-center gap-3">
          <div className="flex gap-1 rounded-lg border border-border p-1">
            {PERIODS.map((p) => (
              <button
                key={p.value}
                type="button"
                onClick={() => setPeriod(p.value)}
                className={cn(
                  "rounded-md px-2.5 py-1.5 text-xs font-medium transition-colors",
                  period === p.value
                    ? "bg-yellow/15 text-navy dark:text-yellow"
                    : "text-text-secondary hover:text-text-primary",
                )}
              >
                {p.label}
              </button>
            ))}
          </div>

          {canStep ? (
            <div className="flex items-center gap-1">
              <button
                type="button"
                aria-label={period === "week" ? "Previous week" : "Previous day"}
                onClick={() => setAnchor((a) => shiftDate(a, -step))}
                className="rounded-lg border border-border p-1.5 text-text-secondary hover:text-text-primary"
              >
                <IconChevronLeft className="size-4" />
              </button>
              <input
                type="date"
                value={anchor}
                max={today}
                onChange={(e) => e.target.value && setAnchor(e.target.value)}
                aria-label="Date"
                className={field}
              />
              <button
                type="button"
                aria-label={period === "week" ? "Next week" : "Next day"}
                disabled={atPresent}
                onClick={() => setAnchor((a) => shiftDate(a, step))}
                className="rounded-lg border border-border p-1.5 text-text-secondary hover:text-text-primary disabled:opacity-40"
              >
                <IconChevronRight className="size-4" />
              </button>
            </div>
          ) : (
            <div className="flex items-center gap-2">
              <input
                type="date"
                value={rangeStart}
                max={today}
                onChange={(e) => setRangeStart(e.target.value)}
                aria-label="Start date"
                className={field}
              />
              <span className="text-text-muted">to</span>
              <input
                type="date"
                value={rangeEnd}
                max={today}
                onChange={(e) => setRangeEnd(e.target.value)}
                aria-label="End date"
                className={field}
              />
            </div>
          )}

          <select
            value={telecallerId}
            onChange={(e) => setTelecallerId(e.target.value)}
            aria-label="Telecaller"
            className={field}
          >
            <option value="">All telecallers</option>
            {targets.map((t) => (
              <option key={t.telecaller_id} value={t.telecaller_id}>
                {t.telecaller_name}
              </option>
            ))}
          </select>

          <span className="text-sm text-text-secondary">{periodLabel}</span>

          {tab === "report" && report && (
            <div className="ml-auto flex gap-2">
              <button
                type="button"
                onClick={() => downloadSummary(report)}
                className="inline-flex items-center gap-1.5 rounded-lg border border-border px-3 py-1.5 text-xs font-medium text-text-secondary transition-colors hover:text-text-primary"
              >
                <IconDownload className="size-3.5" />
                Summary CSV
              </button>
              {first !== last && (
                <button
                  type="button"
                  onClick={() => downloadDaily(report)}
                  className="inline-flex items-center gap-1.5 rounded-lg border border-border px-3 py-1.5 text-xs font-medium text-text-secondary transition-colors hover:text-text-primary"
                >
                  <IconDownload className="size-3.5" />
                  Daily CSV
                </button>
              )}
            </div>
          )}
        </div>
      )}

      {tab !== "targets" && rangeError && (
        <p role="alert" className="mb-4 text-sm text-red-400">
          {rangeError}
        </p>
      )}

      {tab === "report" && !rangeError && (
        <>
          {loading && (
            <div className="flex h-40 items-center justify-center">
              <IconLoader2 className="size-6 animate-spin text-text-muted" />
            </div>
          )}
          {report && <TelecallerReportTable report={report} />}
        </>
      )}

      {tab === "targets" && <TelecallerTargets targets={targets} onSaved={handleSaved} />}

      {tab === "calls" && !rangeError && (
        <CallLog filters={{ start: first, end: last, telecallerId }} />
      )}
      {tab === "notes" && !rangeError && (
        <NoteLog filters={{ start: first, end: last, telecallerId }} />
      )}
    </div>
  );
}
