"use client";

import { cn } from "@/lib/utils";
import { formatHours, formatRate, type IntakePersonStats } from "@/lib/api/intake";

/**
 * Per-person time-to-action, for either leg.
 *
 * Median leads the table and the average follows it, in that order on purpose:
 * one lead left over a weekend moves an average past the limit on its own, and
 * reading the mean first is how a team that is actually fine gets called slow.
 */
export default function LegStatsTable({
  title,
  rows,
  emptyMessage,
  showDecisions = false,
}: {
  readonly title: string;
  readonly rows: IntakePersonStats[];
  readonly emptyMessage: string;
  readonly showDecisions?: boolean;
}) {
  return (
    <section className="rounded-xl border border-border bg-surface p-4">
      <h2 className="mb-3 font-heading text-base font-bold text-text-primary">{title}</h2>
      <div className="overflow-x-auto">
        <table className="w-full min-w-[640px] text-left text-sm">
          <thead className="text-text-secondary">
            <tr>
              <th className="border-b border-border p-2 font-semibold">Person</th>
              <th className="border-b border-border p-2 text-right font-semibold">Assigned</th>
              <th className="border-b border-border p-2 text-right font-semibold">Waiting</th>
              <th className="border-b border-border p-2 text-right font-semibold">Overdue</th>
              <th className="border-b border-border p-2 text-right font-semibold">Median</th>
              <th className="border-b border-border p-2 text-right font-semibold">Average</th>
              <th className="border-b border-border p-2 text-right font-semibold">p90</th>
              <th className="border-b border-border p-2 text-right font-semibold">Within SLA</th>
              {showDecisions && (
                <th className="border-b border-border p-2 text-right font-semibold">Accepted</th>
              )}
            </tr>
          </thead>
          <tbody className="divide-y divide-border">
            {rows.length === 0 ? (
              <tr>
                <td colSpan={showDecisions ? 9 : 8} className="p-6 text-center text-text-muted">
                  {emptyMessage}
                </td>
              </tr>
            ) : (
              rows.map((row) => (
                <tr key={row.employee_id ?? row.name} className="transition-colors hover:bg-canvas">
                  <td className="p-2">
                    <span className="font-medium text-text-primary">{row.name}</span>
                  </td>
                  <td className="p-2 text-right text-text-secondary">{row.assigned}</td>
                  <td className="p-2 text-right text-text-secondary">{row.pending}</td>
                  <td
                    className={cn(
                      "p-2 text-right",
                      row.overdue > 0 ? "font-semibold text-red-400" : "text-text-secondary",
                    )}
                  >
                    {row.overdue}
                  </td>
                  <td className="p-2 text-right text-text-primary">
                    {formatHours(row.median_hours)}
                  </td>
                  <td className="p-2 text-right text-text-secondary">
                    {formatHours(row.avg_hours)}
                  </td>
                  <td className="p-2 text-right text-text-secondary">
                    {formatHours(row.p90_hours)}
                  </td>
                  <td className="p-2 text-right text-text-secondary">
                    {formatRate(row.sla_compliance)}
                  </td>
                  {showDecisions && (
                    <td className="p-2 text-right text-text-secondary">
                      {formatRate(row.accept_rate)}
                    </td>
                  )}
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>
    </section>
  );
}
