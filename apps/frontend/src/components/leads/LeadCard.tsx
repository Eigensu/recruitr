"use client";

import { useState } from "react";
import { motion } from "motion/react";
import {
  IconBriefcase,
  IconCheck,
  IconClock,
  IconLoader2,
  IconMapPin,
  IconNote,
  IconPhone,
  IconSchool,
  IconX,
} from "@tabler/icons-react";
import { cn } from "@/lib/utils";
import {
  REJECT_REASON_LABELS,
  elapsedHours,
  formatHours,
  type IntakeLead,
  type IntakeRejectReason,
} from "@/lib/api/intake";

interface LeadCardProps {
  lead: IntakeLead;
  busy: boolean;
  onAccept: (notes: string) => void;
  onReject: (reason: IntakeRejectReason | undefined, notes: string) => void;
}

const REASONS = Object.keys(REJECT_REASON_LABELS) as IntakeRejectReason[];

/**
 * How long this person has been waiting, red once they are overdue.
 *
 * `overdue` comes from the server rather than being recomputed here against a
 * copy of the SLA limit: the limit is configuration, and a stale copy in the
 * browser would quietly disagree with the alerts and the reports.
 */
function WaitingBadge({ lead }: { lead: IntakeLead }) {
  const waited = elapsedHours(lead.telecaller_assigned_at);
  if (waited === null) return null;
  return (
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
  );
}

function Meta({ icon: Icon, children }: { icon: typeof IconMapPin; children: React.ReactNode }) {
  if (!children) return null;
  return (
    <span className="inline-flex items-center gap-1.5 text-xs text-text-secondary">
      <Icon className="size-3.5 shrink-0 text-text-muted" />
      {children}
    </span>
  );
}

export default function LeadCard({ lead, busy, onAccept, onReject }: LeadCardProps) {
  const [notes, setNotes] = useState("");
  const [showNotes, setShowNotes] = useState(false);
  const [rejecting, setRejecting] = useState(false);
  const [reason, setReason] = useState<IntakeRejectReason | undefined>();

  return (
    <motion.article
      layout
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0, scale: 0.97 }}
      transition={{ duration: 0.2 }}
      className="rounded-xl border border-border bg-surface p-4 shadow-sm"
    >
      <header className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <h2 className="truncate font-heading text-lg font-bold text-text-primary">
            {lead.full_name}
          </h2>
          {lead.role_interest && (
            <p className="mt-0.5 truncate text-sm text-text-secondary">
              Interested in {lead.role_interest}
            </p>
          )}
        </div>
        <WaitingBadge lead={lead} />
      </header>

      {/* The number is the job. Big, and a real tel: link so one tap dials it. */}
      {lead.phone && (
        <a
          href={`tel:${lead.phone}`}
          className="mt-3 flex items-center justify-center gap-2 rounded-lg border border-yellow/20 bg-yellow/10 px-4 py-3 font-heading text-lg font-bold tracking-wide text-yellow transition-colors hover:bg-yellow/20 active:scale-[0.99]"
        >
          <IconPhone className="size-5" />
          {lead.phone}
        </a>
      )}

      <div className="mt-3 flex flex-wrap gap-x-4 gap-y-1.5">
        <Meta icon={IconMapPin}>{lead.city}</Meta>
        <Meta icon={IconBriefcase}>
          {lead.current_role}
          {lead.experience_years > 0 && ` · ${lead.experience_years} yrs`}
        </Meta>
        <Meta icon={IconSchool}>{lead.education}</Meta>
      </div>

      {showNotes && (
        <textarea
          value={notes}
          onChange={(e) => setNotes(e.target.value)}
          rows={2}
          maxLength={2000}
          placeholder="What did they say?"
          className="mt-3 w-full resize-none rounded-lg border border-border bg-canvas p-2.5 text-sm text-text-primary placeholder:text-text-muted focus:border-yellow/40 focus:outline-none"
        />
      )}

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
          <div className="mt-3 flex gap-2">
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
            onClick={() => setShowNotes((v) => !v)}
            aria-label="Add a note"
            className={cn(
              "rounded-lg border p-2 transition-colors",
              showNotes
                ? "border-yellow/30 bg-yellow/10 text-yellow"
                : "border-border text-text-muted hover:text-text-secondary",
            )}
          >
            <IconNote className="size-4" />
          </button>
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
            onClick={() => onAccept(notes)}
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
    </motion.article>
  );
}
