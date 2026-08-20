"use client";

import { IconUsersGroup } from "@tabler/icons-react";

interface SourcingMetric {
  source_type: string | null;
  source_channel: string | null;
  candidate_count: number;
  pipeline_candidates: number;
  offers_accepted: number;
  joined_candidates: number;
}

interface SourcingAnalyticsTableProps {
  metrics: SourcingMetric[];
}

export default function SourcingAnalyticsTable({ metrics }: SourcingAnalyticsTableProps) {
  return (
    <section aria-label="Sourcing Team Analytics" className="flex flex-col h-full">
      <header className="mb-4 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <div className="flex size-8 items-center justify-center rounded-lg bg-navy/5 text-navy dark:bg-yellow/10 dark:text-yellow">
            <IconUsersGroup size={18} />
          </div>
          <h2 className="font-heading text-lg font-bold text-text-primary">Sourcing Analytics</h2>
        </div>
      </header>

      <div className="flex-1 rounded-xl border border-border bg-surface p-1 shadow-sm overflow-hidden">
        <div className="h-full overflow-auto">
          <table className="w-full min-w-[600px] text-left text-sm">
            <thead className="sticky top-0 z-10 bg-surface text-text-secondary">
              <tr>
                <th className="border-b border-border p-3 font-semibold">Source Type</th>
                <th className="border-b border-border p-3 font-semibold">Channel</th>
                <th className="border-b border-border p-3 text-right font-semibold">
                  Total Candidates
                </th>
                <th className="border-b border-border p-3 text-right font-semibold">In Pipeline</th>
                <th className="border-b border-border p-3 text-right font-semibold">Offers</th>
                <th className="border-b border-border p-3 text-right font-semibold">Joined</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border">
              {metrics.length === 0 ? (
                <tr>
                  <td colSpan={6} className="p-8 text-center text-text-muted">
                    No sourcing data available yet.
                  </td>
                </tr>
              ) : (
                metrics.map((row, idx) => (
                  <tr key={idx} className="transition-colors hover:bg-canvas">
                    <td className="p-3">
                      <span className="font-medium text-text-primary capitalize">
                        {row.source_type || "Unknown"}
                      </span>
                    </td>
                    <td className="p-3 text-text-secondary capitalize">
                      {row.source_channel || "—"}
                    </td>
                    <td className="p-3 text-right font-medium">{row.candidate_count}</td>
                    <td className="p-3 text-right text-text-secondary">
                      {row.pipeline_candidates}
                    </td>
                    <td className="p-3 text-right text-green-600 font-medium">
                      {row.offers_accepted}
                    </td>
                    <td className="p-3 text-right text-navy dark:text-yellow font-bold">
                      {row.joined_candidates}
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>
    </section>
  );
}
