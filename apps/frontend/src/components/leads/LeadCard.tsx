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
  IconPhoneOff,
  IconSchool,
  IconX,
} from "@tabler/icons-react";
import { apiErrorMessage, useApiFetch } from "@/lib/api";
import { useToast } from "@/components/ui/Toast";
import CvLinkButton, { needsCv } from "@/components/leads/CvLinkButton";
import LeadCvLink from "@/components/leads/LeadCvLink";
import { cn } from "@/lib/utils";
import {
  REJECT_REASON_LABELS,
  elapsedHours,
  fetchLeadCalls,
  formatHours,
  type IntakeCall,
  type IntakeLead,
  type IntakeRejectReason,
} from "@/lib/api/intake";

interface LeadCardProps {
  lead: IntakeLead;
  busy: boolean;
  /** Log a call nobody answered. Rejects if it fails, so the note box keeps what was typed. */
  onCall: (note: string) => Promise<void>;
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
function WaitingBadge({ lead }: Readonly<{ lead: IntakeLead }>) {
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

/**
 * How many calls this lead has had, out of the limit. Amber from the third, red
 * on the last one left: the next unanswered call closes the lead.
 */
function CallBadge({ lead }: Readonly<{ lead: IntakeLead }>) {
  if (lead.call_attempts === 0) return null;
  const left = lead.max_call_attempts - lead.call_attempts;
  return (
    <span
      className={cn(
        "inline-flex shrink-0 items-center gap-1 rounded-full border px-2 py-1 text-[11px] font-semibold",
        left <= 1
          ? "border-red-500/20 bg-red-500/10 text-red-400"
          : lead.call_attempts >= 3
            ? "border-amber-500/20 bg-amber-500/10 text-amber-500"
            : "border-border bg-surface-panel text-text-muted",
      )}
      title={left <= 1 ? "One more unanswered call closes this lead." : undefined}
    >
      <IconPhoneOff className="size-3" />
      Called {lead.call_attempts} of {lead.max_call_attempts}
    </span>
  );
}

/** The notes left on earlier calls to this lead, fetched when first opened. */
function CallHistory({ lead }: Readonly<{ lead: IntakeLead }>) {
  const apiFetch = useApiFetch();
  const toast = useToast();
  const [open, setOpen] = useState(false);
  const [calls, setCalls] = useState<IntakeCall[] | null>(null);
  // A call logged since the list was fetched must show up, so it is keyed on the
  // count, not just on whether the list was ever loaded.
  const [loadedFor, setLoadedFor] = useState(-1);

  async function toggle() {
    const next = !open;
    setOpen(next);
    if (next && loadedFor !== lead.call_attempts) {
      try {
        setCalls(await fetchLeadCalls(apiFetch, lead.id));
        setLoadedFor(lead.call_attempts);
      } catch (err) {
        toast(apiErrorMessage(err, "Could not load the call history."), "error");
      }
    }
  }

  if (lead.call_attempts === 0) return null;
  return (
    <div className="mt-2">
      <button
        type="button"
        onClick={toggle}
        className="text-xs font-medium text-text-muted underline-offset-2 hover:text-text-secondary hover:underline"
      >
        {open ? "Hide call history" : "Show call history"}
      </button>
      {open && (
        <ol className="mt-1.5 space-y-1.5">
          {calls === null && <li className="text-xs text-text-muted">Loading…</li>}
          {calls?.map((call) => (
            <li
              key={call.id}
              className="rounded-lg border border-border bg-canvas px-2.5 py-1.5 text-xs text-text-secondary"
            >
              <span className="font-semibold">Call {call.attempt}</span>
              <span className="text-text-muted">
                {" "}
                ·{" "}
                {new Date(call.at).toLocaleString("en-IN", {
                  day: "numeric",
                  month: "short",
                  hour: "numeric",
                  minute: "2-digit",
                })}
              </span>
              {call.note ? <p className="mt-0.5">{call.note}</p> : null}
            </li>
          ))}
        </ol>
      )}
    </div>
  );
}

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

export default function LeadCard({
  lead,
  busy,
  onCall,
  onAccept,
  onReject,
}: Readonly<LeadCardProps>) {
  const [notes, setNotes] = useState("");
  const [noAnswer, setNoAnswer] = useState(false);
  const [callNote, setCallNote] = useState("");
  const [logging, setLogging] = useState(false);
  const toast = useToast();
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
        <div className="flex shrink-0 flex-col items-end gap-1.5">
          <WaitingBadge lead={lead} />
          <CallBadge lead={lead} />
        </div>
      </header>

      {/* The number is the job. Big, and a real tel: link so one tap dials it. */}
      {lead.phone && (
        <a
          href={`tel:${lead.phone}`}
          className="mt-3 flex items-center justify-center gap-2 rounded-lg border border-navy/20 bg-yellow/10 px-4 py-3 font-heading text-lg font-bold tracking-wide text-navy transition-colors hover:bg-yellow/20 active:scale-[0.99] dark:border-yellow/20 dark:text-yellow"
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
        <LeadCvLink lead={lead} />
      </div>

      {needsCv(lead) && (
        <div className="mt-3">
          <CvLinkButton lead={lead} />
        </div>
      )}

      <CallHistory lead={lead} />

      {noAnswer && (
        <div className="mt-3 rounded-lg border border-border bg-canvas p-3">
          <p className="mb-2 text-xs font-semibold uppercase tracking-wide text-text-muted">
            Call {lead.call_attempts + 1} of {lead.max_call_attempts}: no answer
            {lead.call_attempts + 1 >= lead.max_call_attempts &&
              " — this closes the lead as unreachable"}
          </p>
          <textarea
            value={callNote}
            onChange={(e) => setCallNote(e.target.value)}
            rows={2}
            maxLength={1000}
            placeholder="Note on this attempt (optional): rang out, busy, switched off…"
            className="w-full resize-none rounded-lg border border-border bg-surface p-2.5 text-sm text-text-primary placeholder:text-text-muted focus:border-navy/40 focus:outline-none dark:focus:border-yellow/40"
          />
          <div className="mt-2 flex gap-2">
            <button
              type="button"
              onClick={() => setNoAnswer(false)}
              disabled={logging}
              className="flex-1 rounded-lg border border-border px-3 py-2 text-sm text-text-secondary hover:bg-surface-panel disabled:opacity-60"
            >
              Cancel
            </button>
            <button
              type="button"
              disabled={logging || busy}
              onClick={async () => {
                setLogging(true);
                try {
                  await onCall(callNote);
                  setCallNote("");
                  setNoAnswer(false);
                } catch (err) {
                  toast(apiErrorMessage(err, "Could not log that call."), "error");
                } finally {
                  setLogging(false);
                }
              }}
              className="flex-1 rounded-lg bg-amber-500 px-3 py-2 text-sm font-semibold text-white hover:bg-amber-400 disabled:opacity-60"
            >
              {logging ? <IconLoader2 className="mx-auto size-4 animate-spin" /> : "Log call"}
            </button>
          </div>
        </div>
      )}

      {showNotes && (
        <textarea
          value={notes}
          onChange={(e) => setNotes(e.target.value)}
          rows={2}
          maxLength={2000}
          placeholder="What did they say?"
          className="mt-3 w-full resize-none rounded-lg border border-border bg-canvas p-2.5 text-sm text-text-primary placeholder:text-text-muted focus:border-navy/40 focus:outline-none dark:focus:border-yellow/40"
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
            onClick={() => setNoAnswer((v) => !v)}
            aria-label="No answer"
            title="They didn't pick up"
            className={cn(
              "rounded-lg border p-2 transition-colors",
              noAnswer
                ? "border-amber-500/40 bg-amber-500/10 text-amber-500"
                : "border-border text-text-muted hover:text-text-secondary",
            )}
          >
            <IconPhoneOff className="size-4" />
          </button>
          <button
            type="button"
            onClick={() => setShowNotes((v) => !v)}
            aria-label="Add a note"
            className={cn(
              "rounded-lg border p-2 transition-colors",
              showNotes
                ? "border-navy/30 bg-yellow/10 text-navy dark:border-yellow/30 dark:text-yellow"
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
