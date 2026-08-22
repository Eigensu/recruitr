"use client";

import {
  IconFileCv,
  IconClock,
  IconCheck,
  IconCircleCheck,
  IconCalendar,
  IconInfoCircle,
} from "@tabler/icons-react";
import { useRefereeData } from "@/hooks/useRefereeData";
import { useCurrentUser } from "@/hooks/useCurrentUser";
import { ThemeToggle } from "@/components/ui/ThemeToggle";
import DashboardKpiCard from "@/components/dashboard/molecules/DashboardKpiCard";

/** Timeline dot: filled for the stage in progress, ticked for stages behind it.
 *
 * A stage still ahead draws as a hollow ring, never as a filled disc: the row
 * behind it is painted with --color-surface-2-val, so a `bg-surface-2` dot was
 * exactly the same colour as its own background in both themes. It vanished,
 * and because the dot sits above the connector line it punched a gap in the
 * track wherever it sat — the stepper read as floating, disconnected dashes.
 */
function stageDotCls(isCurrent: boolean, isReached: boolean): string {
  if (isCurrent) return "bg-yellow text-navy ring-4 ring-yellow/20";
  if (isReached) return "bg-yellow text-navy";
  return "border-2 border-text-muted bg-surface-2 text-transparent";
}

function stageLabelCls(isCurrent: boolean, isReached: boolean): string {
  // Brand yellow reads fine on the dark theme's navy surfaces but is close to
  // unreadable as small text on the light theme's near-white cards — darken it
  // for light mode and keep the bright brand color for dark mode.
  if (isCurrent) return "text-amber-800 dark:text-yellow";
  if (isReached) return "text-text-primary";
  return "text-text-muted";
}

/** How a referral that has stopped moving is labelled, keyed on PipelineStage.
 *
 * A rejected or withdrawn referral rewinds to CV Reviewed, and one on hold
 * freezes at the step it reached, so in every closed-out case the stepper alone
 * shows a dead referral as merely sitting partway along. Without this badge that
 * reads as "still in progress".
 */
const CLOSED_STAGE_LABELS: Record<string, string> = {
  rejected: "Not proceeding",
  candidate_dropped: "Candidate withdrew",
  on_hold: "On hold",
};

interface EarningsStateProps {
  paymentStatus: string;
  kanbanStage: string;
  amount?: number | null;
}

/**
 * What the referee is owed for one referral.
 *
 * A joined candidate shows as Pending rather than as an amount: the incentive
 * is only priced once the 7-day eligibility window closes, and quoting a figure
 * before then would promise money that can still fall away.
 */
function EarningsState({ paymentStatus, kanbanStage, amount }: EarningsStateProps) {
  // The API sends the PaymentStatus enum's own casing ("Paid"/"Owed"); compare
  // case-insensitively so a spelling change server-side cannot silently drop
  // this back to the "—" fallback.
  const status = paymentStatus?.toLowerCase();

  if (status === "paid") {
    return (
      <>
        <div className="text-xl font-bold text-text-primary">
          ₹{amount?.toLocaleString("en-IN")}
        </div>
        <div className="mt-1 flex items-center gap-1 rounded-full bg-emerald-500/10 px-2 py-0.5 text-xs font-medium text-emerald-400">
          <IconCircleCheck className="size-3" /> Paid
        </div>
      </>
    );
  }

  if (status === "owed") {
    return (
      <>
        <div className="text-xl font-bold text-amber-800 dark:text-yellow">
          ₹{amount?.toLocaleString("en-IN")}
        </div>
        <div className="mt-1 flex items-center gap-1 rounded-full bg-yellow/10 px-2 py-0.5 text-xs font-medium text-amber-800 dark:text-yellow">
          <IconClock className="size-3" /> Owed
        </div>
      </>
    );
  }

  if (kanbanStage === "Joined") {
    return (
      <>
        <div className="text-sm font-medium text-text-secondary">Pending</div>
        <div className="mt-1 text-[10px] text-text-muted text-right">Eligible after 7 days</div>
      </>
    );
  }

  return <div className="text-sm font-medium text-text-muted">—</div>;
}

export default function RefereePortal() {
  const { summary, referrals, payments, isLoading, error } = useRefereeData();
  const { user } = useCurrentUser();

  // One step per forward PipelineStage, mirroring map_stage_to_referee on the
  // backend. Keep the two in step: a label absent there can never light up here.
  const refereeStages = ["CV Received", "CV Reviewed", "Interview Round(s)", "Selected", "Joined"];

  return (
    <div
      className="min-h-full px-4 py-5 sm:px-6 lg:px-8"
      style={{ background: "var(--color-canvas)", color: "var(--color-text-primary)" }}
    >
      <div className="mx-auto flex w-full max-w-400 flex-col gap-5">
        {/* HEADER */}
        <header className="pb-4" style={{ borderBottom: "1px solid var(--color-border-val)" }}>
          <div className="flex items-start justify-between gap-4">
            <div>
              <p
                className="text-xs font-bold uppercase tracking-normal"
                style={{ color: "var(--color-text-secondary)" }}
              >
                Referee Portal
              </p>
              <h1
                className="mt-2 font-heading text-4xl leading-tight sm:text-5xl"
                style={{ color: "var(--color-text-primary)" }}
              >
                Welcome, {user?.full_name ?? "back"}
              </h1>
            </div>
            <div className="mt-1 shrink-0">
              <ThemeToggle />
            </div>
          </div>
        </header>

        {isLoading && (
          <div className="space-y-8 animate-pulse">
            <div className="grid gap-4 sm:grid-cols-3">
              <div className="h-32 rounded-2xl bg-surface-2" />
              <div className="h-32 rounded-2xl bg-surface-2" />
              <div className="h-32 rounded-2xl bg-surface-2" />
            </div>
            <div className="h-64 rounded-2xl bg-surface-2" />
            <div className="h-48 rounded-2xl bg-surface-2" />
          </div>
        )}

        {!isLoading && error && (
          <div className="rounded-2xl border border-red-500/20 bg-red-500/10 p-6 text-center text-red-600 dark:text-red-400">
            <p>Unable to load dashboard data. Please try again later.</p>
          </div>
        )}

        {!isLoading && !error && (
          <>
            {/* SUMMARY TILES */}
            <div className="grid gap-4 sm:grid-cols-3 sm:h-[180px]">
              <DashboardKpiCard
                index={0}
                metric={{
                  id: "referee_cvs_shared",
                  label: "CVs Shared",
                  value: summary?.cvs_shared ?? 0,
                  helper: "Total profiles submitted",
                  tone: "green",
                  trend: "Total",
                }}
              />
              <DashboardKpiCard
                index={1}
                metric={{
                  id: "referee_cvs_actioned",
                  label: "CVs Actioned",
                  value: summary?.cvs_actioned ?? 0,
                  helper: "Actioned by Binge team",
                  tone: "neutral",
                  trend: "Actioned",
                }}
              />
              <DashboardKpiCard
                index={2}
                metric={{
                  id: "referee_earnings",
                  label: "Earnings Accrued",
                  value: summary?.accrued_earnings ?? 0,
                  helper: "Eligible total to be paid",
                  tone: "yellow",
                  trend: "Eligible",
                  prefix: "₹",
                }}
              />
            </div>

            {/* CANDIDATE JOURNEY */}
            <div className="mt-2 flex flex-col gap-4">
              <div className="flex flex-wrap items-end justify-between gap-3">
                <div>
                  <h2
                    className="font-heading text-2xl"
                    style={{ color: "var(--color-text-primary)" }}
                  >
                    Candidate Journey
                  </h2>
                  <p className="mt-1 text-sm" style={{ color: "var(--color-text-secondary)" }}>
                    Track every referral through the Binge hiring process.
                  </p>
                </div>
                <div
                  className="flex items-center gap-1.5 text-xs text-text-secondary"
                  style={{ color: "var(--color-text-secondary)" }}
                >
                  <IconInfoCircle className="size-4" />
                  <span>Earnings eligible 7 days after joining</span>
                </div>
              </div>

              {/* The 300px floor is there to hold the empty state open; with
                  referrals on screen it just left a slab of dead space under
                  the last card. */}
              <div
                className={`rounded-lg bg-surface-panel shadow-md shadow-black/30 p-5 theme-transition flex flex-col ${
                  referrals.length === 0 ? "min-h-[300px]" : ""
                }`}
              >
                {referrals.length === 0 ? (
                  <div
                    className="flex flex-1 flex-col items-center justify-center gap-2 py-10 text-center"
                    style={{ opacity: 0.5 }}
                  >
                    <IconFileCv className="size-8" style={{ opacity: 0.4 }} />
                    <p className="max-w-60 text-sm">
                      Candidates you refer to Binge will appear here.
                    </p>
                  </div>
                ) : (
                  <div className="space-y-3">
                    {referrals.map((candidate) => {
                      // Determine current index in the 7-stage array
                      const currentIndex = refereeStages.indexOf(candidate.kanban_stage);
                      const closedLabel = candidate.pipeline_stage
                        ? CLOSED_STAGE_LABELS[candidate.pipeline_stage]
                        : undefined;

                      return (
                        <div
                          key={candidate.id}
                          className="rounded-lg border p-4 transition-colors hover:border-yellow theme-transition"
                          style={{
                            borderColor: "var(--color-border-val)",
                            background: "var(--color-surface-2-val)",
                          }}
                        >
                          <div className="flex flex-col gap-5 sm:flex-row sm:items-start sm:justify-between">
                            {/* Candidate Info */}
                            <div className="space-y-1 sm:w-1/3">
                              <div className="flex flex-wrap items-center gap-2">
                                <h4 className="font-medium text-text-primary">
                                  {candidate.candidate_name}
                                </h4>
                                {closedLabel && (
                                  <span className="rounded-full bg-red-500/10 px-2 py-0.5 text-[10px] font-semibold text-red-600 dark:text-red-400">
                                    {closedLabel}
                                  </span>
                                )}
                              </div>
                              <div className="flex flex-wrap items-center gap-2 text-sm text-text-secondary">
                                <span>Role</span>
                                {/* Without the fallback this read as a bare
                                    "Role" with nothing after it whenever the
                                    referral carries no role_level. */}
                                {candidate.role_level ? (
                                  <span className="rounded-full bg-navy/10 dark:bg-white/10 px-2.5 py-0.5 text-xs font-medium text-text-primary">
                                    {candidate.role_level}
                                  </span>
                                ) : (
                                  <span className="text-xs italic text-text-muted">
                                    not set yet
                                  </span>
                                )}
                              </div>
                              <div className="text-xs text-text-muted mt-2">
                                Submitted{" "}
                                {new Date(candidate.submission_date).toLocaleDateString("en-GB")}
                              </div>
                            </div>

                            {/* Status Timeline */}
                            {/* py-2: the current-stage dot's ring-4 glow bleeds
                                4px past its box via box-shadow, and setting
                                overflow-x here implicitly forces overflow-y to
                                clip too — without padding that glow got cut
                                off at the top/bottom edges. */}
                            <div className="flex-1 overflow-x-auto scrollbar-none py-2">
                              {/* items-start, not items-center: the two-line
                                  labels ("CV Reviewed", "Interview Round(s)")
                                  make their columns taller, and centring then
                                  lifted those dots above the one-line ones so
                                  the track stair-stepped across the row. */}
                              <div className="min-w-[500px] flex items-start justify-between">
                                {refereeStages.map((stage, i) => {
                                  const isReached = currentIndex >= i;
                                  const isCurrent = currentIndex === i;
                                  const isJoined = stage === "Joined";

                                  return (
                                    <div
                                      key={stage}
                                      className="relative flex flex-col items-center flex-1"
                                    >
                                      {i !== 0 && (
                                        <div
                                          className={`absolute top-2.5 -left-1/2 w-full h-0.5 ${isReached ? "bg-yellow" : "bg-text-muted/40"}`}
                                        />
                                      )}

                                      <div
                                        className={`relative z-10 flex size-5 items-center justify-center rounded-full text-[10px] ${stageDotCls(
                                          isCurrent,
                                          isReached,
                                        )}`}
                                      >
                                        {isReached && <IconCheck stroke={3} className="size-3" />}
                                      </div>

                                      <div
                                        className={`mt-2 min-h-[24px] max-w-[76px] px-1 text-center text-[10px] font-medium leading-tight ${stageLabelCls(
                                          isCurrent,
                                          isReached,
                                        )}`}
                                      >
                                        {stage}
                                      </div>

                                      {isJoined && candidate.joining_date && isCurrent && (
                                        <div className="mt-1 text-[9px] text-amber-800/80 dark:text-yellow/70">
                                          {new Date(candidate.joining_date).toLocaleDateString(
                                            "en-GB",
                                          )}
                                        </div>
                                      )}
                                    </div>
                                  );
                                })}
                              </div>
                            </div>

                            {/* Earnings State */}
                            <div className="flex shrink-0 flex-col items-end sm:w-48">
                              <EarningsState
                                paymentStatus={candidate.payment_status}
                                kanbanStage={candidate.kanban_stage}
                                amount={candidate.incentive_amount}
                              />
                            </div>
                          </div>
                        </div>
                      );
                    })}
                  </div>
                )}
              </div>
            </div>

            {/* PAYMENT HISTORY & SCHEDULE */}
            <div className="mt-2 grid gap-6 lg:grid-cols-3">
              <div className="lg:col-span-2 flex flex-col gap-4">
                <div>
                  <h2
                    className="font-heading text-2xl"
                    style={{ color: "var(--color-text-primary)" }}
                  >
                    Payment History
                  </h2>
                </div>

                <div className="rounded-lg bg-surface-panel shadow-md shadow-black/30 overflow-hidden theme-transition flex-1">
                  {payments.length === 0 ? (
                    <div
                      className="flex flex-1 flex-col items-center justify-center gap-2 py-16 text-center"
                      style={{ opacity: 0.5 }}
                    >
                      <p className="max-w-60 text-sm">No payments processed yet.</p>
                    </div>
                  ) : (
                    <div className="overflow-x-auto">
                      <table className="w-full text-left text-sm text-text-secondary">
                        <thead
                          className="bg-surface-2 text-xs font-semibold uppercase tracking-normal theme-transition"
                          style={{ color: "var(--color-text-secondary)" }}
                        >
                          <tr>
                            <th
                              className="px-5 py-3 border-b"
                              style={{ borderColor: "var(--color-border-val)" }}
                            >
                              Month
                            </th>
                            <th
                              className="px-5 py-3 border-b"
                              style={{ borderColor: "var(--color-border-val)" }}
                            >
                              Amount
                            </th>
                            <th
                              className="px-5 py-3 border-b"
                              style={{ borderColor: "var(--color-border-val)" }}
                            >
                              Paid On
                            </th>
                            <th
                              className="px-5 py-3 border-b"
                              style={{ borderColor: "var(--color-border-val)" }}
                            >
                              Reference
                            </th>
                          </tr>
                        </thead>
                        <tbody className="divide-y divide-border">
                          {payments.map((p) => (
                            <tr key={p.batch_id} className="hover:bg-surface-2 transition-colors">
                              <td className="px-5 py-4 font-medium text-text-primary">
                                {p.cycle_month}
                              </td>
                              <td className="px-5 py-4 text-emerald-400 font-medium">
                                ₹{p.total_amount.toLocaleString("en-IN")}
                              </td>
                              <td className="px-5 py-4">
                                {new Date(p.paid_on).toLocaleDateString("en-GB")}
                              </td>
                              <td className="px-5 py-4 font-mono text-xs text-text-muted">
                                {p.payment_reference || "—"}
                              </td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  )}
                </div>
              </div>

              <div className="flex flex-col gap-4">
                <div>
                  <h2
                    className="font-heading text-2xl"
                    style={{ color: "var(--color-text-primary)" }}
                  >
                    Schedule
                  </h2>
                </div>
                <div className="rounded-lg bg-surface-panel shadow-md shadow-black/30 p-5 theme-transition">
                  <div
                    className="flex size-10 items-center justify-center rounded-lg mb-4"
                    style={{ background: "rgba(243,255,84,0.15)", color: "#f3ff54" }}
                  >
                    <IconCalendar className="size-5" />
                  </div>
                  <div
                    className="space-y-2 text-sm"
                    style={{ color: "var(--color-text-secondary)" }}
                  >
                    <p>
                      Referral payments are processed monthly on the{" "}
                      <strong
                        className="font-medium"
                        style={{ color: "var(--color-text-primary)" }}
                      >
                        7th
                      </strong>{" "}
                      for eligible unpaid earnings.
                    </p>
                    <p className="text-xs" style={{ opacity: 0.7 }}>
                      If the 7th falls on a weekend or bank holiday, payment is processed on the
                      next working day.
                    </p>
                  </div>
                </div>
              </div>
            </div>
          </>
        )}

        {/* Footer spacing */}
        <div className="h-8" />
      </div>
    </div>
  );
}
