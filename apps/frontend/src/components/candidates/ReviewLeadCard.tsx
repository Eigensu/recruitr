"use client";

import { useState } from "react";
import {
  IconBriefcase,
  IconCheck,
  IconClock,
  IconLoader2,
  IconMapPin,
  IconNote,
  IconPhone,
  IconSchool,
  IconUser,
  IconX,
} from "@tabler/icons-react";
import CvLinkButton, { needsCv } from "@/components/leads/CvLinkButton";
import LeadCvLink from "@/components/leads/LeadCvLink";
import LeadNotes from "@/components/leads/LeadNotes";
import { cn } from "@/lib/utils";
import {
  REJECT_REASON_LABELS,
  elapsedHours,
  formatHours,
  type IntakeLead,
  type IntakeRejectReason,
} from "@/lib/api/intake";

interface Props {
  lead: IntakeLead;
  busy: boolean;
  /** Show whose lead this is — on for maintainers, who see every recruiter's. */
  showRecruiter: boolean;
  onAccept: () => void;
  onReject: (reason: IntakeRejectReason | undefined, notes: string) => void;
  onViewProfile: () => void;
}

const REASONS = Object.keys(REJECT_REASON_LABELS) as IntakeRejectReason[];

function Meta({
  icon: Icon,
  children,
}: Readonly<{ icon: typeof IconMapPin; children: React.ReactNode }>) {
  if (!children) return null;
  return (
    <span className="inline-flex items-center gap-1.5 text-xs text-text-secondary">
      <Icon className="size-3.5 shrink-0 text-text-muted" />
      {children}
    </span>
  );
}

/**
 * One lead in the Candidates page's Review tab: a telecaller screened them, an
 * admin handed them to this recruiter's team, and now the recruiter decides.
 *
 * Accept moves them into the Candidates tab; reject archives them. The waiting
 * time is the recruiter's own clock, and `overdue` comes from the server so it
 * agrees with the SLA alerts.
 */
export default function ReviewLeadCard({
  lead,
  busy,
  showRecruiter,
  onAccept,
  onReject,
  onViewProfile,
}: Readonly<Props>) {
  const [rejecting, setRejecting] = useState(false);
  const [reason, setReason] = useState<IntakeRejectReason | undefined>();
  const [notes, setNotes] = useState("");
  const waited = elapsedHours(lead.recruiter_assigned_at);
  // One string, so Meta's emptiness check sees an empty row as empty: passed as
  // two children it got an array, which is truthy even when both are blank.
  const work = [lead.current_role, lead.experience_years > 0 && `${lead.experience_years} yrs`]
    .filter(Boolean)
    .join(" · ");

  return (
    <article className="flex flex-col rounded-xl border border-border bg-surface p-4 shadow-sm">
      <header className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <button
            type="button"
            onClick={onViewProfile}
            className="block max-w-full truncate text-left font-heading text-lg font-bold text-text-primary hover:underline"
          >
            {lead.full_name}
          </button>
          {lead.role_interest && (
            <p className="mt-0.5 truncate text-sm text-text-secondary">
              Interested in {lead.role_interest}
            </p>
          )}
        </div>
        {waited !== null && (
          <span
            className={cn(
              "inline-flex shrink-0 items-center gap-1 rounded-full border px-2 py-1 text-[11px] font-semibold",
              lead.overdue
                ? "border-red-500/20 bg-red-500/10 text-red-400"
                : "border-border bg-surface-panel text-text-muted",
            )}
          >
            <IconClock className="size-3" />
            waiting {formatHours(waited)}
          </span>
        )}
      </header>

      <div className="mt-3 flex flex-wrap gap-x-4 gap-y-1.5">
        {lead.phone && (
          <a
            href={`tel:${lead.phone}`}
            className="inline-flex items-center gap-1.5 text-xs font-semibold text-text-primary hover:underline"
          >
            <IconPhone className="size-3.5 shrink-0 text-text-muted" />
            {lead.phone}
          </a>
        )}
        <LeadCvLink lead={lead} />
        <Meta icon={IconMapPin}>{lead.city}</Meta>
        <Meta icon={IconBriefcase}>{work}</Meta>
        <Meta icon={IconSchool}>{lead.education}</Meta>
        {showRecruiter && <Meta icon={IconUser}>{lead.recruiter_name ?? "—"}</Meta>}
      </div>

      {needsCv(lead) && (
        <div className="mt-3">
          <CvLinkButton lead={lead} />
        </div>
      )}

      {lead.telecaller_notes && (
        <p className="mt-3 rounded-lg border border-border bg-canvas p-2.5 text-xs text-text-secondary">
          <IconNote className="mr-1 inline size-3.5 text-text-muted" />
          <span className="font-semibold">
            {lead.telecaller_name ? `${lead.telecaller_name}: ` : "Telecaller: "}
          </span>
          {lead.telecaller_notes}
        </p>
      )}

      <LeadNotes leadId={lead.id} />

      <div className="mt-auto">
        {rejecting ? (
          <div className="mt-3 rounded-lg border border-border bg-canvas p-3">
            <p className="mb-2 text-xs font-semibold uppercase tracking-wide text-text-muted">
              Why? (optional)
            </p>
            <div className="flex flex-wrap gap-1.5">
              {REASONS.map((value) => (
                <button
                  key={value}
                  type="button"
                  onClick={() => setReason(reason === value ? undefined : value)}
                  className={cn(
                    "rounded-full border px-2.5 py-1 text-xs transition-colors",
                    reason === value
                      ? "border-red-500/30 bg-red-500/15 text-red-400"
                      : "border-border text-text-secondary hover:border-text-muted",
                  )}
                >
                  {REJECT_REASON_LABELS[value]}
                </button>
              ))}
            </div>
            <textarea
              value={notes}
              onChange={(e) => setNotes(e.target.value)}
              rows={2}
              maxLength={2000}
              placeholder="Notes (optional)"
              className="mt-3 w-full resize-none rounded-lg border border-border bg-surface p-2.5 text-sm text-text-primary placeholder:text-text-muted focus:border-navy/40 focus:outline-none dark:focus:border-yellow/40"
            />
            <div className="mt-2 flex gap-2">
              <button
                type="button"
                onClick={() => setRejecting(false)}
                className="flex-1 rounded-lg border border-border px-3 py-2 text-sm text-text-secondary hover:bg-surface-panel"
              >
                Cancel
              </button>
              <button
                type="button"
                disabled={busy}
                onClick={() => onReject(reason, notes)}
                className="flex-1 rounded-lg bg-red-500/90 px-3 py-2 text-sm font-semibold text-white hover:bg-red-500 disabled:opacity-60"
              >
                {busy ? <IconLoader2 className="mx-auto size-4 animate-spin" /> : "Confirm reject"}
              </button>
            </div>
          </div>
        ) : (
          <div className="mt-3 flex items-center gap-2">
            <button
              type="button"
              disabled={busy}
              onClick={() => setRejecting(true)}
              className="flex-1 rounded-lg border border-border px-3 py-2 text-sm font-medium text-text-secondary hover:border-red-500/30 hover:text-red-400 disabled:opacity-60"
            >
              <IconX className="mr-1 inline size-4" />
              Reject
            </button>
            <button
              type="button"
              disabled={busy}
              onClick={onAccept}
              className="flex-1 rounded-lg bg-emerald-600 px-3 py-2 text-sm font-semibold text-white hover:bg-emerald-500 disabled:opacity-60"
            >
              {busy ? (
                <IconLoader2 className="mx-auto size-4 animate-spin" />
              ) : (
                <>
                  <IconCheck className="mr-1 inline size-4" />
                  Accept
                </>
              )}
            </button>
          </div>
        )}
      </div>
    </article>
  );
}
