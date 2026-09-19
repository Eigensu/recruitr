"use client";

import { cn } from "@/lib/utils";
import type { IntakeFunnel } from "@/lib/api/intake";

/**
 * Where every lead ended up, as one proportional bar.
 *
 * A bar rather than a funnel chart because these are not stages in sequence —
 * a rejected lead and an actioned one are both finished, they just finished
 * differently. The segments sum to the total, which is the only claim the
 * picture makes.
 */
const SEGMENTS: {
  key: keyof Omit<IntakeFunnel, "ingested">;
  label: string;
  bar: string;
  dot: string;
}[] = [
  {
    key: "pending_telecaller",
    label: "Awaiting a call",
    bar: "bg-yellow/70",
    dot: "bg-yellow/70",
  },
  {
    key: "pending_recruiter",
    label: "With a recruiter",
    bar: "bg-blue-500/70",
    dot: "bg-blue-500/70",
  },
  { key: "actioned", label: "Put forward", bar: "bg-emerald-500/70", dot: "bg-emerald-500/70" },
  { key: "rejected", label: "Rejected", bar: "bg-red-500/60", dot: "bg-red-500/60" },
  { key: "unassigned", label: "Unassigned", bar: "bg-orange-500/60", dot: "bg-orange-500/60" },
  { key: "duplicate", label: "Duplicate", bar: "bg-text-muted/40", dot: "bg-text-muted/40" },
];

export default function IntakeFunnelBar({ funnel }: { readonly funnel: IntakeFunnel }) {
  const total = funnel.ingested;
  if (total === 0) {
    return (
      <section className="rounded-xl border border-dashed border-border p-8 text-center text-sm text-text-muted">
        No leads arrived in this window.
      </section>
    );
  }

  return (
    <section className="rounded-xl border border-border bg-surface p-4">
      <h2 className="mb-3 font-heading text-base font-bold text-text-primary">
        Where {total} {total === 1 ? "lead" : "leads"} ended up
      </h2>
      <div className="flex h-3 w-full overflow-hidden rounded-full bg-canvas">
        {SEGMENTS.map((segment) => {
          const value = funnel[segment.key];
          if (!value) return null;
          return (
            <div
              key={segment.key}
              className={cn("h-full", segment.bar)}
              style={{ width: `${(value / total) * 100}%` }}
              title={`${segment.label}: ${value}`}
            />
          );
        })}
      </div>
      <ul className="mt-3 flex flex-wrap gap-x-5 gap-y-2">
        {SEGMENTS.map((segment) => {
          const value = funnel[segment.key];
          if (!value) return null;
          return (
            <li key={segment.key} className="flex items-center gap-2 text-xs">
              <span className={cn("size-2 rounded-full", segment.dot)} />
              <span className="text-text-secondary">{segment.label}</span>
              <span className="font-heading text-text-primary">{value}</span>
              <span className="text-text-muted">({Math.round((value / total) * 100)}%)</span>
            </li>
          );
        })}
      </ul>
    </section>
  );
}
