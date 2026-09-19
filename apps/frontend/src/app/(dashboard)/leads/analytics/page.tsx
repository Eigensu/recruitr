"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import {
  IconAlertTriangle,
  IconArrowLeft,
  IconLoader2,
  IconPlugConnected,
  IconPlugConnectedX,
} from "@tabler/icons-react";
import { cn } from "@/lib/utils";
import { apiErrorMessage, useApiFetch } from "@/lib/api";
import { useCurrentUser } from "@/hooks/useCurrentUser";
import { useToast } from "@/components/ui/Toast";
import LegStatsTable from "@/components/leads/LegStatsTable";
import IntakeFunnelBar from "@/components/leads/IntakeFunnelBar";
import {
  REJECT_REASON_LABELS,
  fetchCampaigns,
  fetchOverview,
  fetchRecruiterStats,
  fetchTelecallerStats,
  formatHours,
  formatRate,
  type IntakeCampaignGroup,
  type IntakeCampaignRow,
  type IntakeLegStats,
  type IntakeOverview,
  type IntakePersonStats,
  type IntakeRejectReason,
} from "@/lib/api/intake";

const RANGES = [
  { label: "7 days", days: 7 },
  { label: "30 days", days: 30 },
  { label: "90 days", days: 90 },
  { label: "All time", days: 0 },
];

const GROUPS: { value: IntakeCampaignGroup; label: string }[] = [
  { value: "campaign", label: "Campaign" },
  { value: "ad", label: "Ad" },
  { value: "form", label: "Form" },
  { value: "channel", label: "Channel" },
];

function Stat({
  label,
  value,
  hint,
  tone,
}: {
  label: string;
  value: string;
  hint?: string;
  tone?: "alert";
}) {
  return (
    <div
      className={cn(
        "rounded-xl border p-4",
        tone === "alert" && value !== "0"
          ? "border-red-500/25 bg-red-500/5"
          : "border-border bg-surface",
      )}
    >
      <p className="text-xs font-semibold uppercase tracking-wide text-text-muted">{label}</p>
      <p
        className={cn(
          "mt-2 font-heading text-3xl leading-none",
          tone === "alert" && value !== "0" ? "text-red-400" : "text-text-primary",
        )}
      >
        {value}
      </p>
      {hint && <p className="mt-2 text-xs text-text-secondary">{hint}</p>}
    </div>
  );
}

/** The headline row for one leg: the three numbers that describe its speed. */
function LegSummary({ title, stats }: { title: string; stats: IntakeLegStats }) {
  return (
    <section className="rounded-xl border border-border bg-surface p-4">
      <header className="mb-3 flex items-baseline justify-between gap-2">
        <h2 className="font-heading text-base font-bold text-text-primary">{title}</h2>
        <span className="text-xs text-text-muted">{stats.sla_hours}h limit</span>
      </header>
      <dl className="grid grid-cols-3 gap-3">
        {[
          ["Median", formatHours(stats.median_hours)],
          ["Average", formatHours(stats.avg_hours)],
          ["p90", formatHours(stats.p90_hours)],
        ].map(([label, value]) => (
          <div key={label}>
            <dt className="text-xs text-text-muted">{label}</dt>
            <dd className="mt-1 font-heading text-xl text-text-primary">{value}</dd>
          </div>
        ))}
      </dl>
      <p className="mt-3 border-t border-border pt-3 text-xs text-text-secondary">
        {stats.actioned} actioned · {formatRate(stats.sla_compliance)} within the limit ·{" "}
        <span className={cn(stats.overdue > 0 && "font-semibold text-red-400")}>
          {stats.overdue} overdue
        </span>
      </p>
    </section>
  );
}

export default function LeadAnalyticsPage() {
  const apiFetch = useApiFetch();
  const router = useRouter();
  const toast = useToast();
  const { isMaintainer, isLoading: authLoading } = useCurrentUser();

  const [days, setDays] = useState(30);
  const [groupBy, setGroupBy] = useState<IntakeCampaignGroup>("campaign");
  const [overview, setOverview] = useState<IntakeOverview | null>(null);
  const [telecallers, setTelecallers] = useState<IntakePersonStats[]>([]);
  const [recruiters, setRecruiters] = useState<IntakePersonStats[]>([]);
  const [campaigns, setCampaigns] = useState<IntakeCampaignRow[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!authLoading && !isMaintainer) router.replace("/");
  }, [authLoading, isMaintainer, router]);

  // `loading` is raised in the range/grouping handlers, never synchronously in
  // the effect: setState in an effect body cascades a render, which is what
  // react-hooks/set-state-in-effect forbids.
  const load = useCallback((): Promise<void> => {
    const window = days
      ? { start_date: new Date(Date.now() - days * 86_400_000).toISOString() }
      : {};
    return Promise.all([
      fetchOverview(apiFetch, window),
      fetchTelecallerStats(apiFetch, window),
      fetchRecruiterStats(apiFetch, window),
      fetchCampaigns(apiFetch, groupBy, window),
    ])
      .then(([o, t, r, c]) => {
        setOverview(o);
        setTelecallers(t);
        setRecruiters(r);
        setCampaigns(c.rows);
      })
      .catch((err: unknown) => {
        toast(apiErrorMessage(err, "Could not load the intake report."), "error");
      });
  }, [apiFetch, days, groupBy, toast]);

  useEffect(() => {
    if (authLoading || !isMaintainer) return undefined;
    let cancelled = false;
    load().finally(() => {
      if (!cancelled) setLoading(false);
    });
    return () => {
      cancelled = true;
    };
  }, [authLoading, isMaintainer, load]);

  if (authLoading || !isMaintainer) {
    return (
      <div className="flex h-64 items-center justify-center">
        <IconLoader2 className="size-6 animate-spin text-text-muted" />
      </div>
    );
  }

  const funnel = overview?.funnel;
  const source = overview?.source;

  return (
    <main className="mx-auto w-full max-w-7xl p-4 duration-300 animate-in fade-in sm:p-6 lg:p-8">
      <header className="mb-6 flex flex-wrap items-start justify-between gap-3">
        <div>
          <Link
            href="/leads"
            className="mb-2 inline-flex items-center gap-1 text-xs text-text-muted transition-colors hover:text-text-primary"
          >
            <IconArrowLeft className="size-3.5" />
            All leads
          </Link>
          <h1 className="font-heading text-2xl font-bold tracking-tight text-text-primary">
            Lead intake
          </h1>
          <p className="mt-1 text-sm text-text-secondary">
            Leads that arrived {days ? `in the last ${days} days` : "since the beginning"}, followed
            wherever they got to.
          </p>
        </div>
        <div className="flex gap-1 rounded-lg border border-border p-1">
          {RANGES.map((range) => (
            <button
              key={range.days}
              type="button"
              onClick={() => {
                setLoading(true);
                setDays(range.days);
              }}
              className={cn(
                "rounded-md px-2.5 py-1.5 text-xs font-medium transition-colors",
                days === range.days
                  ? "bg-yellow/15 text-yellow"
                  : "text-text-secondary hover:text-text-primary",
              )}
            >
              {range.label}
            </button>
          ))}
        </div>
      </header>

      {/* The sheet connection. A silent failure here looks exactly like "no
          leads today", so it is stated rather than left to be inferred. */}
      {source && (
        <div
          className={cn(
            "mb-6 flex flex-wrap items-center gap-2 rounded-xl border px-4 py-3 text-sm",
            source.last_error || !source.enabled
              ? "border-red-500/25 bg-red-500/5 text-red-400"
              : "border-border bg-surface text-text-secondary",
          )}
        >
          {source.last_error || !source.enabled ? (
            <IconPlugConnectedX className="size-4 shrink-0" />
          ) : (
            <IconPlugConnected className="size-4 shrink-0 text-emerald-400" />
          )}
          <span>
            {!source.configured
              ? "No sheet connected yet."
              : !source.enabled
                ? "Lead intake is switched off."
                : source.last_error
                  ? `Last sync failed: ${source.last_error}`
                  : source.last_success_at
                    ? `Last synced ${new Date(source.last_success_at).toLocaleString()}`
                    : "Connected, waiting for the first sync."}
          </span>
          {source.consecutive_failures > 1 && (
            <span className="font-semibold">({source.consecutive_failures} in a row)</span>
          )}
        </div>
      )}

      {loading && !overview ? (
        <div className="flex h-64 items-center justify-center">
          <IconLoader2 className="size-6 animate-spin text-text-muted" />
        </div>
      ) : (
        <div className="flex flex-col gap-6">
          {funnel && (
            <>
              <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
                <Stat label="Leads in" value={String(funnel.ingested)} />
                <Stat
                  label="Awaiting a call"
                  value={String(funnel.pending_telecaller)}
                  hint={
                    overview?.telecaller.oldest_pending_hours
                      ? `oldest ${formatHours(overview.telecaller.oldest_pending_hours)}`
                      : undefined
                  }
                />
                <Stat
                  label="Overdue"
                  value={String(
                    (overview?.telecaller.overdue ?? 0) + (overview?.recruiter.overdue ?? 0),
                  )}
                  tone="alert"
                  hint="past the limit, both legs"
                />
                <Stat
                  label="In nobody's queue"
                  value={String(funnel.unassigned)}
                  tone="alert"
                  hint="no clock running"
                />
              </div>

              <IntakeFunnelBar funnel={funnel} />
            </>
          )}

          <div className="grid gap-4 lg:grid-cols-2">
            {overview && <LegSummary title="Telecaller response" stats={overview.telecaller} />}
            {overview && <LegSummary title="Recruiter response" stats={overview.recruiter} />}
          </div>

          <LegStatsTable
            title="By telecaller"
            rows={telecallers}
            emptyMessage="No leads have been assigned to a telecaller yet."
            showDecisions
          />
          <LegStatsTable
            title="By recruiter"
            rows={recruiters}
            emptyMessage="No accepted leads have reached a recruiter yet."
          />

          {/* Why leads are turned away. wrong_number dominating is a problem
              with the ad form, not with the person making the calls. */}
          {overview && overview.reject_reasons.length > 0 && (
            <section className="rounded-xl border border-border bg-surface p-4">
              <h2 className="mb-3 font-heading text-base font-bold text-text-primary">
                Why leads were rejected
              </h2>
              <ul className="flex flex-wrap gap-2">
                {overview.reject_reasons.map((row) => (
                  <li
                    key={row.reason}
                    className="inline-flex items-center gap-2 rounded-full border border-border px-3 py-1.5 text-sm"
                  >
                    <span className="text-text-secondary">
                      {REJECT_REASON_LABELS[row.reason as IntakeRejectReason] ?? "Unspecified"}
                    </span>
                    <span className="font-heading text-text-primary">{row.count}</span>
                  </li>
                ))}
              </ul>
            </section>
          )}

          <section className="rounded-xl border border-border bg-surface p-4">
            <header className="mb-3 flex flex-wrap items-center justify-between gap-2">
              <h2 className="font-heading text-base font-bold text-text-primary">
                What the spend produced
              </h2>
              <div className="flex gap-1 rounded-lg border border-border p-1">
                {GROUPS.map((group) => (
                  <button
                    key={group.value}
                    type="button"
                    onClick={() => {
                      setLoading(true);
                      setGroupBy(group.value);
                    }}
                    className={cn(
                      "rounded-md px-2.5 py-1 text-xs font-medium transition-colors",
                      groupBy === group.value
                        ? "bg-yellow/15 text-yellow"
                        : "text-text-secondary hover:text-text-primary",
                    )}
                  >
                    {group.label}
                  </button>
                ))}
              </div>
            </header>
            <div className="overflow-x-auto">
              <table className="w-full min-w-[520px] text-left text-sm">
                <thead className="text-text-secondary">
                  <tr>
                    <th className="border-b border-border p-2 font-semibold">Name</th>
                    <th className="border-b border-border p-2 text-right font-semibold">Leads</th>
                    <th className="border-b border-border p-2 text-right font-semibold">
                      Accepted
                    </th>
                    <th className="border-b border-border p-2 text-right font-semibold">
                      Accept rate
                    </th>
                    <th className="border-b border-border p-2 text-right font-semibold">
                      Reached a recruiter
                    </th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-border">
                  {campaigns.length === 0 ? (
                    <tr>
                      <td colSpan={5} className="p-6 text-center text-text-muted">
                        Nothing to report for this window.
                      </td>
                    </tr>
                  ) : (
                    campaigns.map((row) => (
                      <tr key={row.label} className="transition-colors hover:bg-canvas">
                        <td className="max-w-[260px] truncate p-2 text-text-primary">
                          {row.label}
                        </td>
                        <td className="p-2 text-right text-text-secondary">{row.leads}</td>
                        <td className="p-2 text-right text-text-secondary">{row.accepted}</td>
                        <td className="p-2 text-right text-text-secondary">
                          {formatRate(row.accept_rate)}
                        </td>
                        <td className="p-2 text-right text-text-secondary">
                          {formatRate(row.actioned_rate)}
                        </td>
                      </tr>
                    ))
                  )}
                </tbody>
              </table>
            </div>
          </section>

          {funnel && funnel.duplicate > 0 && (
            <p className="flex items-center gap-2 text-xs text-text-muted">
              <IconAlertTriangle className="size-3.5" />
              {funnel.duplicate} of these leads were people already in the system — the same person
              filling in the form twice. They are linked, not re-reviewed.
            </p>
          )}
        </div>
      )}
    </main>
  );
}
