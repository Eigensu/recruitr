"use client";

import { useState } from "react";
import { IconChevronDown, IconChevronRight } from "@tabler/icons-react";
import { cn } from "@/lib/utils";
import { shortDate } from "@/lib/ist";
import { formatRate, type TelecallerReport, type TelecallerReportRow } from "@/lib/api/intake";

const COLUMNS: { key: keyof Omit<TelecallerReportRow, "days">; label: string; hint?: string }[] = [
  { key: "calls", label: "Calls", hint: "Every call made, answered or not" },
  { key: "connected", label: "Answered", hint: "Calls where a person picked up" },
  { key: "unanswered", label: "No answer" },
  { key: "forwarded", label: "Forwarded", hint: "Accepted and sent for review" },
  { key: "rejected", label: "Rejected", hint: "Turned away on the call" },
  { key: "dead", label: "Dead", hint: "Closed after the full set of unanswered calls" },
];

function TargetCell({ row }: Readonly<{ row: TelecallerReportRow }>) {
  if (!row.target_calls) return <span className="text-text-muted">No target</span>;
  const pct = row.target_pct ?? 0;
  return (
    <div className="min-w-28">
      <div className="flex justify-between text-xs">
        <span className="text-text-primary">
          {row.calls} / {row.target_calls}
        </span>
        <span className={cn(pct >= 1 ? "font-semibold text-emerald-500" : "text-text-muted")}>
          {formatRate(pct)}
        </span>
      </div>
      <div className="mt-1 h-1.5 overflow-hidden rounded-full bg-surface-panel">
        <div
          className={cn("h-full rounded-full", pct >= 1 ? "bg-emerald-500" : "bg-yellow")}
          style={{ width: `${Math.min(pct, 1) * 100}%` }}
        />
      </div>
    </div>
  );
}

/** One telecaller's day-by-day numbers, shown when their row is opened. */
function DayBreakdown({ row }: Readonly<{ row: TelecallerReportRow }>) {
  return (
    <table className="w-full text-xs">
      <thead>
        <tr className="text-left text-text-muted">
          <th className="py-1 pr-3 font-medium">Day</th>
          {COLUMNS.map((c) => (
            <th key={c.key} className="px-2 py-1 text-right font-medium">
              {c.label}
            </th>
          ))}
        </tr>
      </thead>
      <tbody>
        {row.days.map((day) => (
          <tr key={day.date} className="border-t border-border/60">
            <td className="py-1 pr-3 text-text-secondary">{shortDate(day.date)}</td>
            {COLUMNS.map((c) => (
              <td key={c.key} className="px-2 py-1 text-right tabular-nums text-text-primary">
                {day[c.key as keyof typeof day]}
              </td>
            ))}
          </tr>
        ))}
      </tbody>
    </table>
  );
}

/**
 * The report: one row per telecaller, with a total, and each row opens to show
 * its days. `Bad leads` is the share of what they finished with that was not
 * forwarded (rejected plus dead), so a high number is a bad batch of leads as
 * often as a harsh telecaller.
 */
export default function TelecallerReportTable({ report }: Readonly<{ report: TelecallerReport }>) {
  const [open, setOpen] = useState<ReadonlySet<string>>(new Set());
  const multiDay = report.start_date !== report.end_date;

  function toggle(id: string) {
    setOpen((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }

  if (report.rows.length === 0) {
    return (
      <p className="rounded-xl border border-dashed border-border py-12 text-center text-sm text-text-secondary">
        No telecallers yet. Add them under Settings → Telecallers.
      </p>
    );
  }

  return (
    <div className="overflow-x-auto rounded-xl border border-border bg-surface">
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b border-border text-left text-xs uppercase tracking-wide text-text-muted">
            <th className="px-3 py-2 font-semibold">Telecaller</th>
            {COLUMNS.map((c) => (
              <th key={c.key} title={c.hint} className="px-3 py-2 text-right font-semibold">
                {c.label}
              </th>
            ))}
            <th
              title="Rejected plus dead, of everything they finished with"
              className="px-3 py-2 text-right font-semibold"
            >
              Bad leads
            </th>
            <th className="px-3 py-2 text-right font-semibold">Notes</th>
            <th className="px-3 py-2 font-semibold">Calls vs target</th>
          </tr>
        </thead>
        <tbody>
          {report.rows.map((row) => {
            const expanded = open.has(row.telecaller_id);
            return (
              <RowWithDays
                key={row.telecaller_id}
                row={row}
                expanded={expanded}
                canExpand={multiDay}
                onToggle={() => toggle(row.telecaller_id)}
              />
            );
          })}
        </tbody>
        <tfoot>
          <tr className="border-t border-border bg-surface-panel font-semibold">
            <td className="px-3 py-2 text-text-primary">All telecallers</td>
            {COLUMNS.map((c) => (
              <td key={c.key} className="px-3 py-2 text-right tabular-nums">
                {report.totals[c.key as keyof typeof report.totals]}
              </td>
            ))}
            <td className="px-3 py-2 text-right tabular-nums">
              {formatRate(report.totals.bad_lead_rate)}
            </td>
            <td className="px-3 py-2 text-right tabular-nums">{report.totals.notes_written}</td>
            <td />
          </tr>
        </tfoot>
      </table>
    </div>
  );
}

function RowWithDays({
  row,
  expanded,
  canExpand,
  onToggle,
}: Readonly<{
  row: TelecallerReportRow;
  expanded: boolean;
  canExpand: boolean;
  onToggle: () => void;
}>) {
  return (
    <>
      <tr className="border-b border-border/60">
        <td className="px-3 py-2">
          <button
            type="button"
            onClick={onToggle}
            disabled={!canExpand}
            aria-expanded={canExpand ? expanded : undefined}
            className="inline-flex items-center gap-1 text-left font-medium text-text-primary disabled:cursor-default"
          >
            {canExpand &&
              (expanded ? (
                <IconChevronDown className="size-3.5 text-text-muted" />
              ) : (
                <IconChevronRight className="size-3.5 text-text-muted" />
              ))}
            {row.telecaller_name}
            {!row.active && <span className="text-xs font-normal text-text-muted">(paused)</span>}
          </button>
        </td>
        {COLUMNS.map((c) => (
          <td key={c.key} className="px-3 py-2 text-right tabular-nums text-text-primary">
            {row[c.key]}
          </td>
        ))}
        <td className="px-3 py-2 text-right tabular-nums text-text-primary">
          {formatRate(row.bad_lead_rate)}
        </td>
        <td className="px-3 py-2 text-right tabular-nums text-text-primary">{row.notes_written}</td>
        <td className="px-3 py-2">
          <TargetCell row={row} />
        </td>
      </tr>
      {expanded && (
        <tr className="border-b border-border/60 bg-canvas">
          <td colSpan={COLUMNS.length + 4} className="px-6 py-3">
            <DayBreakdown row={row} />
          </td>
        </tr>
      )}
    </>
  );
}
