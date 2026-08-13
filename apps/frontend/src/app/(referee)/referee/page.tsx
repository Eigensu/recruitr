"use client";

import {
  IconFileCv,
  IconBriefcase,
  IconWallet,
  IconClock,
  IconCheck,
  IconCircleCheck,
  IconCalendar,
  IconInfoCircle,
} from "@tabler/icons-react";
import { useRefereeData } from "@/hooks/useRefereeData";

export default function RefereePortal() {
  const { summary, referrals, payments, isLoading, error } = useRefereeData();

  // Define the exact 7 stages according to spec
  const refereeStages = [
    "CV Received",
    "CV Reviewed",
    "Screening Call",
    "Interview Round(s)",
    "Offer Extended",
    "Offer Accepted",
    "Joined",
  ];

  return (
    <div className="flex h-full flex-col">
      {/* SCROLLABLE MAIN CONTENT */}
      <div className="flex-1 overflow-y-auto p-4 sm:p-6 lg:p-8">
        <div className="mx-auto max-w-6xl space-y-8">
          {/* INTRO */}
          <div className="space-y-1">
            <h2 className="text-2xl font-heading font-bold text-text-primary">Welcome back</h2>
            <p className="text-sm text-text-secondary">
              Track your submitted candidates, hiring progress, and referral earnings here.
            </p>
          </div>

          {isLoading ? (
            <div className="space-y-8 animate-pulse">
              <div className="grid gap-4 sm:grid-cols-3">
                <div className="h-32 rounded-2xl bg-surface-2" />
                <div className="h-32 rounded-2xl bg-surface-2" />
                <div className="h-32 rounded-2xl bg-surface-2" />
              </div>
              <div className="h-64 rounded-2xl bg-surface-2" />
              <div className="h-48 rounded-2xl bg-surface-2" />
            </div>
          ) : error ? (
            <div className="rounded-2xl border border-red-500/20 bg-red-500/10 p-6 text-center text-red-600 dark:text-red-400">
              <p>Unable to load dashboard data. Please try again later.</p>
            </div>
          ) : (
            <>
              {/* SUMMARY TILES */}
              <div className="grid gap-4 sm:grid-cols-3">
                <div className="flex flex-col justify-between rounded-2xl border border-border bg-surface-card p-6 shadow-sm theme-transition">
                  <div className="flex items-center gap-3 text-text-secondary">
                    <IconFileCv className="size-5" />
                    <span className="text-sm font-medium">CVs Shared</span>
                  </div>
                  <div className="mt-4 text-4xl font-bold text-text-primary">
                    {summary?.cvs_shared ?? 0}
                  </div>
                  <div className="mt-1 text-xs text-text-muted">Total profiles submitted</div>
                </div>

                <div className="flex flex-col justify-between rounded-2xl border border-border bg-surface-card p-6 shadow-sm theme-transition">
                  <div className="flex items-center gap-3 text-text-secondary">
                    <IconBriefcase className="size-5" />
                    <span className="text-sm font-medium">CVs Actioned</span>
                  </div>
                  <div className="mt-4 text-4xl font-bold text-text-primary">
                    {summary?.cvs_actioned ?? 0}
                  </div>
                  <div className="mt-1 text-xs text-text-muted">Actioned by Binge team</div>
                </div>

                <div className="flex flex-col justify-between rounded-2xl bg-yellow p-6 shadow-md shadow-yellow/20 relative overflow-hidden theme-transition">
                  <div className="absolute -right-4 -top-4 opacity-10">
                    <IconWallet className="size-32 text-navy" />
                  </div>
                  <div className="relative z-10 flex items-center gap-3 text-navy">
                    <IconWallet className="size-5" />
                    <span className="text-sm font-medium">Earnings Accrued</span>
                  </div>
                  <div className="relative z-10 mt-4 text-4xl font-heading font-bold text-navy">
                    ₹{summary?.accrued_earnings?.toLocaleString("en-IN") ?? 0}
                  </div>
                  <div className="relative z-10 mt-1 text-xs font-medium text-navy/70">
                    Eligible total to be paid
                  </div>
                </div>
              </div>

              {/* CANDIDATE JOURNEY */}
              <div className="space-y-4">
                <div className="flex items-center justify-between">
                  <div>
                    <h3 className="text-xl font-heading font-bold text-text-primary">
                      Candidate Journey
                    </h3>
                    <p className="text-sm text-text-secondary">
                      Track every referral through the Binge hiring process.
                    </p>
                  </div>
                  <div className="flex items-center gap-1.5 text-xs text-text-secondary">
                    <IconInfoCircle className="size-4" />
                    <span>Earnings become eligible 7 days after joining.</span>
                  </div>
                </div>

                {referrals.length === 0 ? (
                  <div className="rounded-2xl border border-dashed border-border bg-surface-2 p-12 text-center theme-transition">
                    <div className="mx-auto flex size-12 items-center justify-center rounded-full bg-surface-card text-text-secondary shadow-sm">
                      <IconFileCv className="size-6" />
                    </div>
                    <h4 className="mt-4 text-base font-medium text-text-primary">
                      No referrals yet
                    </h4>
                    <p className="mt-1 text-sm text-text-muted">
                      Candidates you refer to Binge will appear here.
                    </p>
                  </div>
                ) : (
                  <div className="space-y-3">
                    {referrals.map((candidate) => {
                      // Determine current index in the 7-stage array
                      const currentIndex = refereeStages.indexOf(candidate.kanban_stage);

                      return (
                        <div
                          key={candidate.id}
                          className="rounded-2xl border border-border bg-surface-card p-5 shadow-sm transition-colors hover:bg-surface-2 theme-transition"
                        >
                          <div className="flex flex-col gap-5 sm:flex-row sm:items-start sm:justify-between">
                            {/* Candidate Info */}
                            <div className="space-y-1 sm:w-1/3">
                              <h4 className="font-medium text-text-primary">
                                {candidate.candidate_name}
                              </h4>
                              <div className="flex flex-wrap items-center gap-2 text-sm text-text-secondary">
                                <span>Role</span>
                                {candidate.role_level && (
                                  <span className="rounded-full bg-navy/10 dark:bg-white/10 px-2.5 py-0.5 text-xs font-medium text-text-primary">
                                    {candidate.role_level}
                                  </span>
                                )}
                              </div>
                              <div className="text-xs text-text-muted mt-2">
                                Submitted{" "}
                                {new Date(candidate.submission_date).toLocaleDateString("en-GB")}
                              </div>
                            </div>

                            {/* Status Timeline */}
                            <div className="flex-1 overflow-x-auto scrollbar-none">
                              <div className="min-w-[500px] flex items-center justify-between">
                                {refereeStages.map((stage, i) => {
                                  const isPast = currentIndex >= i;
                                  const isCurrent = currentIndex === i;
                                  const isJoined = stage === "Joined";
                                  const isSkipped = stage === "Screening Call" && isPast; // Specially gray this out if skipped

                                  return (
                                    <div
                                      key={stage}
                                      className="relative flex flex-col items-center flex-1"
                                    >
                                      {/* Connector line */}
                                      {i !== 0 && (
                                        <div
                                          className={`absolute top-2.5 -left-1/2 w-full h-0.5 ${isPast && !isSkipped ? "bg-yellow" : "bg-border"}`}
                                        />
                                      )}

                                      <div
                                        className={`relative z-10 flex size-5 items-center justify-center rounded-full text-[10px]
                                        ${
                                          isCurrent
                                            ? "bg-yellow text-navy ring-4 ring-yellow/20"
                                            : isPast && !isSkipped
                                              ? "bg-yellow text-navy"
                                              : "bg-surface-2 text-transparent"
                                        }`}
                                      >
                                        {isPast && !isSkipped && (
                                          <IconCheck stroke={3} className="size-3" />
                                        )}
                                      </div>

                                      <div
                                        className={`mt-2 text-center text-[10px] font-medium max-w-[60px] leading-tight
                                        ${isCurrent ? "text-yellow" : isPast && !isSkipped ? "text-text-primary" : "text-text-muted"}`}
                                      >
                                        {stage}
                                      </div>

                                      {/* Joined date sublabel */}
                                      {isJoined && candidate.joining_date && isCurrent && (
                                        <div className="mt-1 text-[9px] text-yellow/70">
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
                              {candidate.payment_status === "paid" ? (
                                <>
                                  <div className="text-xl font-bold text-text-primary">
                                    ₹{candidate.incentive_amount?.toLocaleString("en-IN")}
                                  </div>
                                  <div className="mt-1 flex items-center gap-1 rounded-full bg-emerald-500/10 px-2 py-0.5 text-xs font-medium text-emerald-400">
                                    <IconCircleCheck className="size-3" /> Paid
                                  </div>
                                </>
                              ) : candidate.payment_status === "owed" ? (
                                <>
                                  <div className="text-xl font-bold text-yellow">
                                    ₹{candidate.incentive_amount?.toLocaleString("en-IN")}
                                  </div>
                                  <div className="mt-1 flex items-center gap-1 rounded-full bg-yellow/10 px-2 py-0.5 text-xs font-medium text-yellow">
                                    <IconClock className="size-3" /> Owed
                                  </div>
                                </>
                              ) : candidate.kanban_stage === "Joined" ? (
                                <>
                                  <div className="text-sm font-medium text-text-secondary">
                                    Pending
                                  </div>
                                  <div className="mt-1 text-[10px] text-text-muted text-right">
                                    Eligible after 7 days
                                  </div>
                                </>
                              ) : (
                                <div className="text-sm font-medium text-text-muted">—</div>
                              )}
                            </div>
                          </div>
                        </div>
                      );
                    })}
                  </div>
                )}
              </div>

              {/* PAYMENT HISTORY & SCHEDULE */}
              <div className="grid gap-6 lg:grid-cols-3">
                <div className="lg:col-span-2 space-y-4">
                  <h3 className="text-xl font-heading font-bold text-text-primary">
                    Payment History
                  </h3>

                  {payments.length === 0 ? (
                    <div className="rounded-2xl border border-dashed border-border bg-surface-2 p-8 text-center text-sm text-text-secondary theme-transition">
                      No payments processed yet.
                    </div>
                  ) : (
                    <div className="rounded-2xl border border-border bg-surface-card overflow-hidden shadow-sm theme-transition">
                      <div className="overflow-x-auto">
                        <table className="w-full text-left text-sm text-text-secondary">
                          <thead className="bg-surface-2 text-xs font-medium uppercase text-text-muted theme-transition">
                            <tr>
                              <th className="px-5 py-3">Month</th>
                              <th className="px-5 py-3">Amount</th>
                              <th className="px-5 py-3">Paid On</th>
                              <th className="px-5 py-3">Reference</th>
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
                    </div>
                  )}
                </div>

                <div className="space-y-4">
                  <h3 className="text-xl font-heading font-bold text-text-primary">
                    Payment Schedule
                  </h3>
                  <div className="rounded-2xl border border-border bg-surface-card p-5 shadow-sm space-y-4 theme-transition">
                    <div className="flex size-10 items-center justify-center rounded-full bg-surface-2 text-text-primary theme-transition">
                      <IconCalendar className="size-5" />
                    </div>
                    <div className="space-y-2 text-sm text-text-secondary">
                      <p>
                        Referral payments are processed monthly on the{" "}
                        <strong className="text-text-primary font-medium">7th</strong> for eligible
                        unpaid earnings.
                      </p>
                      <p className="text-xs">
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
    </div>
  );
}
