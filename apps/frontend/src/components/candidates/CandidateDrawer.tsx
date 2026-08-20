import React, { useEffect, useState } from "react";
import { AnimatePresence, motion } from "motion/react";
import {
  IconX,
  IconMail,
  IconPhone,
  IconExternalLink,
  IconCircleCheck,
  IconBriefcase,
  IconFileText,
  IconLink,
  IconCurrencyDollar,
  IconNotes,
  IconPencil,
  IconCheck,
  IconClockHour4,
  IconSchool,
  IconLock,
  IconUserCheck,
  IconBuildingStore,
  IconHistory,
} from "@tabler/icons-react";
import type {
  ApiCandidate,
  ApiCandidateHistory,
  ApiCandidateHistoryEvent,
  ApiCandidateMappingItem,
  ApiCandidatePlacement,
} from "@/types";
import { useApiFetch } from "@/lib/api";
import { getCandidateHistory, getCandidateMappings, resolveCvRef } from "@/lib/api/candidates";
import { clientUpdateCandidate, clientConfirmResume } from "@/lib/api/candidates.client";
import { uploadResumeToCloudinary } from "@/lib/api/storage.client";
import { getAvatarPalette, getInitials } from "./CandidateCard";
import {
  AgeField,
  AreaField,
  CityField,
  CurrentRoleField,
  CurrentSalaryField,
  CvLinkField,
  EducationField,
  ExpectedSalaryField,
  ExperienceYearsField,
  GenderField,
  NoticePeriodField,
  NotesField,
  ResumeField,
  SourceChannelField,
  SourceField,
  StructuredCandidateTags,
  TagChip,
  TextField,
  inputStyle,
  resolveSourceChannel,
} from "./CandidateFormFields";

interface CandidateDrawerProps {
  candidate: ApiCandidate | null;
  onClose: () => void;
  onUpdate?: (updated: ApiCandidate) => void;
  /** Approve/reject the open application. Only rendered for maintainers. */
  isMaintainer?: boolean;
  onApprove?: (id: string) => Promise<void>;
  onReject?: (id: string) => Promise<void>;
}

export default function CandidateDrawer({
  candidate,
  onClose,
  onUpdate,
  isMaintainer,
  onApprove,
  onReject,
}: Readonly<CandidateDrawerProps>) {
  const apiFetch = useApiFetch();
  const [mappings, setMappings] = useState<ApiCandidateMappingItem[]>([]);
  const [loadingMappings, setLoadingMappings] = useState(false);
  // Tagged with the candidate it was fetched for: `candidate` changes on
  // every switch (a new object each time), but this state only updates once
  // the fetch resolves. Rendering it unconditionally between those two
  // moments would show the previous candidate's history under the new one's
  // name — the effect below has not yet even set loadingHistory back to true.
  const [history, setHistory] = useState<{ candidateId: string; data: ApiCandidateHistory } | null>(
    null,
  );
  const [loadingHistory, setLoadingHistory] = useState(false);

  useEffect(() => {
    if (!candidate) return;
    let cancelled = false;
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setLoadingMappings(true);
    getCandidateMappings(apiFetch, candidate.id)
      .then((data) => {
        if (!cancelled) setMappings(data);
      })
      .catch(() => {
        if (!cancelled) setMappings([]);
      })
      .finally(() => {
        if (!cancelled) setLoadingMappings(false);
      });
    return () => {
      cancelled = true;
    };
  }, [apiFetch, candidate]);

  useEffect(() => {
    if (!candidate) return;
    let cancelled = false;
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setLoadingHistory(true);
    getCandidateHistory(apiFetch, candidate.id)
      .then((data) => {
        if (!cancelled) setHistory({ candidateId: candidate.id, data });
      })
      .catch(() => {
        if (!cancelled) setHistory(null);
      })
      .finally(() => {
        if (!cancelled) setLoadingHistory(false);
      });
    return () => {
      cancelled = true;
    };
  }, [apiFetch, candidate]);

  return (
    <AnimatePresence>
      {candidate && (
        <>
          {/* Backdrop */}
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            onClick={onClose}
            className="fixed inset-0 bg-black/60 backdrop-blur-sm z-40"
          />

          {/* Slide-over panel */}
          <motion.div
            role="dialog"
            aria-modal="true"
            aria-labelledby="candidateDrawerTitle"
            initial={{ x: "100%" }}
            animate={{ x: 0 }}
            exit={{ x: "100%" }}
            transition={{ type: "spring", damping: 28, stiffness: 250 }}
            className="fixed right-0 top-0 bottom-0 w-full sm:w-120 bg-(--color-surface) border-l border-border shadow-2xl z-50 flex flex-col"
          >
            <DrawerInner
              candidate={candidate}
              onClose={onClose}
              onUpdate={onUpdate}
              loadingMappings={loadingMappings}
              mappings={mappings}
              history={history?.candidateId === candidate.id ? history.data : null}
              loadingHistory={loadingHistory}
              isMaintainer={isMaintainer}
              onApprove={onApprove}
              onReject={onReject}
            />
          </motion.div>
        </>
      )}
    </AnimatePresence>
  );
}

function DrawerInner({
  candidate,
  onClose,
  onUpdate,
  loadingMappings,
  mappings,
  history,
  loadingHistory,
  isMaintainer,
  onApprove,
  onReject,
}: Readonly<{
  candidate: ApiCandidate;
  onClose: () => void;
  onUpdate?: (updated: ApiCandidate) => void;
  loadingMappings: boolean;
  mappings: ApiCandidateMappingItem[];
  history: ApiCandidateHistory | null;
  loadingHistory: boolean;
  isMaintainer?: boolean;
  onApprove?: (id: string) => Promise<void>;
  onReject?: (id: string) => Promise<void>;
}>) {
  const [isEditing, setIsEditing] = useState(false);

  const palette = getAvatarPalette(candidate.full_name);
  const initials = getInitials(candidate.full_name);
  const cvRef = resolveCvRef(candidate.cv_link, candidate.resume_url);
  const isPending = candidate.status === "PENDING";
  const canDecide = isPending && !!isMaintainer && !!(onApprove || onReject);

  function handleSaved(updated: ApiCandidate) {
    setIsEditing(false);
    onUpdate?.(updated);
  }

  return (
    <>
      {/* Header */}
      <div className="p-6 border-b border-border">
        <div className="flex items-start justify-between mb-4">
          <div
            className="size-14 rounded-2xl flex items-center justify-center font-heading font-bold text-xl"
            style={{
              backgroundColor: palette.bg,
              color: palette.text,
              border: `1px solid ${palette.border}`,
            }}
          >
            {initials}
          </div>
          <div className="flex items-center gap-2">
            <button
              type="button"
              onClick={() => setIsEditing((v) => !v)}
              aria-label={isEditing ? "Cancel edit" : "Edit candidate"}
              className="p-2 rounded-xl border border-border text-text-muted hover:text-text-primary hover:border-white/20 transition-all"
              style={
                isEditing
                  ? { borderColor: "var(--color-yellow)", color: "var(--color-yellow)" }
                  : {}
              }
            >
              {isEditing ? <IconCheck className="size-4" /> : <IconPencil className="size-4" />}
            </button>
            <button
              type="button"
              onClick={onClose}
              aria-label="Close candidate details"
              className="p-2 rounded-xl border border-border text-text-muted hover:text-text-primary hover:border-white/20 transition-all"
            >
              <IconX className="size-4" />
            </button>
          </div>
        </div>

        {isPending && (
          <span className="mb-2 inline-flex items-center gap-1.5 rounded-full border border-yellow/25 bg-yellow/10 px-2.5 py-1 text-[10px] font-bold uppercase tracking-wide text-yellow">
            <IconClockHour4 className="size-3" />
            Pending application
          </span>
        )}

        <h2
          id="candidateDrawerTitle"
          className="font-heading font-bold text-text-primary text-2xl leading-tight"
        >
          {candidate.full_name}
        </h2>
        <p className="text-sm text-text-muted mt-1 flex items-center gap-1.5">
          <IconBriefcase className="size-3.5 shrink-0" />
          {candidate.previous_company ? `${candidate.previous_company} · ` : ""}
          {candidate.experience_years} yrs exp
        </p>

        {/* Contact */}
        <div className="mt-4 flex flex-col gap-2">
          {candidate.phone && (
            <span className="flex items-center gap-2 text-xs text-text-muted">
              <IconPhone className="size-3.5 shrink-0" />
              {candidate.phone}
            </span>
          )}
          {candidate.email && (
            <a
              href={`mailto:${candidate.email}`}
              className="flex items-center gap-2 text-xs text-text-muted hover:text-yellow transition-colors w-fit"
            >
              <IconMail className="size-3.5 shrink-0" />
              {candidate.email}
            </a>
          )}
          {candidate.cv_locked ? (
            <span className="flex items-center gap-2 text-xs opacity-50 cursor-default w-fit">
              <IconLock className="size-3.5 shrink-0" />
              {candidate.created_by_name
                ? `CV held by ${candidate.created_by_name}`
                : "CV held by another recruiter"}
            </span>
          ) : (
            cvRef &&
            (cvRef.href ? (
              <a
                href={cvRef.href}
                target="_blank"
                rel="noreferrer noopener"
                className="flex items-center gap-2 text-xs text-text-muted hover:text-yellow transition-colors w-fit"
              >
                {candidate.cv_link ? (
                  <IconLink className="size-3.5 shrink-0" />
                ) : (
                  <IconFileText className="size-3.5 shrink-0" />
                )}
                {cvRef.label}
              </a>
            ) : (
              <span
                className="flex items-center gap-2 text-xs opacity-40 cursor-default w-fit"
                title="CV on file — not yet uploaded"
              >
                <IconFileText className="size-3.5 shrink-0" />
                {cvRef.label} (on file)
              </span>
            ))
          )}
          {candidate.created_by_name && (
            <span className="flex items-center gap-2 text-xs text-text-muted">
              <IconUserCheck className="size-3.5 shrink-0" />
              Added by {candidate.created_by_name}
            </span>
          )}
        </div>
      </div>

      {/* Body */}
      {isEditing ? (
        <EditForm
          candidate={candidate}
          onSaved={handleSaved}
          onCancel={() => setIsEditing(false)}
        />
      ) : (
        <ViewBody
          candidate={candidate}
          loadingMappings={loadingMappings}
          mappings={mappings}
          history={history}
          loadingHistory={loadingHistory}
          showReviewHint={canDecide}
          onEdit={() => setIsEditing(true)}
        />
      )}

      {/* Decision bar — outside the scroll area so it stays reachable.
          Hidden while editing: approving half-typed edits would discard them. */}
      {canDecide && !isEditing && (
        <DecisionBar candidateId={candidate.id} onApprove={onApprove} onReject={onReject} />
      )}
    </>
  );
}

/* ── Pending decision bar ──────────────────────────────────────────────────── */

function DecisionBar({
  candidateId,
  onApprove,
  onReject,
}: Readonly<{
  candidateId: string;
  onApprove?: (id: string) => Promise<void>;
  onReject?: (id: string) => Promise<void>;
}>) {
  const [acting, setActing] = useState<"approve" | "reject" | null>(null);

  // Closing the drawer is the caller's job: it knows whether the decision
  // actually landed, so a failed approve leaves the panel open on the details.
  async function run(kind: "approve" | "reject", fn: (id: string) => Promise<void>) {
    setActing(kind);
    try {
      await fn(candidateId);
    } finally {
      setActing(null);
    }
  }

  return (
    <div className="shrink-0 border-t border-border bg-(--color-surface) p-4 flex items-center gap-3">
      {onReject && (
        <button
          type="button"
          disabled={acting !== null}
          onClick={() => run("reject", onReject)}
          className="rounded-lg border border-red-500/25 bg-red-500/10 px-4 py-2 text-sm font-semibold text-red-500 transition-colors hover:bg-red-500/20 disabled:opacity-50"
        >
          {acting === "reject" ? "Rejecting…" : "Reject"}
        </button>
      )}
      {onApprove && (
        <button
          type="button"
          disabled={acting !== null}
          onClick={() => run("approve", onApprove)}
          className="flex-1 rounded-lg py-2 text-sm font-bold disabled:opacity-50"
          style={{ background: "var(--color-yellow)", color: "#002348" }}
        >
          {acting === "approve" ? "Approving…" : "Approve candidate"}
        </button>
      )}
    </div>
  );
}

/* ── View mode ─────────────────────────────────────────────────────────────── */

function ViewBody({
  candidate,
  loadingMappings,
  mappings,
  history,
  loadingHistory,
  showReviewHint,
  onEdit,
}: Readonly<{
  candidate: ApiCandidate;
  loadingMappings: boolean;
  mappings: ApiCandidateMappingItem[];
  history: ApiCandidateHistory | null;
  loadingHistory: boolean;
  showReviewHint?: boolean;
  onEdit: () => void;
}>) {
  return (
    <div className="flex-1 overflow-y-auto dashboard-scrollbar p-6 space-y-6 bg-(--color-canvas)">
      {showReviewHint && (
        <section className="rounded-xl border border-yellow/20 bg-yellow/5 p-4">
          <p className="text-xs leading-relaxed text-text-secondary">
            This candidate applied through your public form, so only what they filled in is here.
            Review it and{" "}
            <button
              type="button"
              onClick={onEdit}
              className="font-semibold text-yellow underline underline-offset-2 hover:opacity-80"
            >
              add any missing details
            </button>{" "}
            before approving.
          </p>
        </section>
      )}

      {/* Role & compensation */}
      {(candidate.current_role ||
        candidate.salary != null ||
        candidate.expected_salary != null) && (
        <>
          <section className="flex flex-wrap gap-4">
            {candidate.current_role && (
              <div className="flex items-center gap-2 text-sm text-text-muted">
                <IconBriefcase className="size-3.5 shrink-0 opacity-60" />
                <span>{candidate.current_role}</span>
              </div>
            )}
            {candidate.salary != null && (
              <div className="flex items-center gap-2 text-sm text-text-muted">
                <IconCurrencyDollar className="size-3.5 shrink-0 opacity-60" />
                <span>Current: {candidate.salary.toLocaleString()}</span>
              </div>
            )}
            {candidate.expected_salary != null && (
              <div className="flex items-center gap-2 text-sm text-text-muted">
                <IconCurrencyDollar className="size-3.5 shrink-0 opacity-60" />
                <span>Expected: {candidate.expected_salary.toLocaleString()}</span>
              </div>
            )}
          </section>
          <div className="h-px bg-border/50" />
        </>
      )}

      {/* Notice / education / source */}
      {(candidate.notice_period || candidate.education_level || candidate.source) && (
        <>
          <section className="flex flex-wrap gap-4">
            {candidate.notice_period && (
              <div className="flex items-center gap-2 text-sm text-text-muted">
                <span>Notice: {candidate.notice_period}</span>
              </div>
            )}
            {candidate.education_level && (
              <div className="flex items-center gap-2 text-sm text-text-muted">
                <IconSchool className="size-3.5 shrink-0 opacity-60" />
                <span>{candidate.education_level}</span>
              </div>
            )}
            {candidate.source && (
              <div className="flex items-center gap-2 text-sm text-text-muted capitalize">
                <span>
                  Source: {candidate.source}
                  {/* Not capitalized — channel names carry their own casing (LinkedIn). */}
                  {candidate.source_channel && (
                    <span className="normal-case"> · {candidate.source_channel}</span>
                  )}
                </span>
              </div>
            )}
          </section>
          <div className="h-px bg-border/50" />
        </>
      )}

      {/* Demographics */}
      {(candidate.city || candidate.area || candidate.gender || candidate.age) && (
        <>
          <section className="flex flex-wrap gap-4">
            {(candidate.city || candidate.area) && (
              <div className="flex items-center gap-2 text-sm text-text-muted capitalize">
                <span>{[candidate.city, candidate.area].filter(Boolean).join(" • ")}</span>
              </div>
            )}
            {(candidate.gender || candidate.age) && (
              <div className="flex items-center gap-2 text-sm text-text-muted capitalize">
                <span>
                  {[candidate.gender, candidate.age ? `${candidate.age} yrs` : null]
                    .filter(Boolean)
                    .join(" • ")}
                </span>
              </div>
            )}
          </section>
          <div className="h-px bg-border/50" />
        </>
      )}

      {/* Skills — parsed from the CV, so empty until one is uploaded */}
      {candidate.skills.length > 0 && (
        <>
          <section>
            <h3 className="text-[10px] font-bold uppercase tracking-widest text-text-muted mb-3">
              Skills &amp; Expertise
            </h3>
            <div className="flex flex-wrap gap-2">
              {candidate.skills.map((skill) => (
                <span
                  key={skill}
                  className="skill-tag text-[11px] font-semibold px-3 py-1 rounded-full"
                >
                  {skill}
                </span>
              ))}
            </div>
          </section>
          <div className="h-px bg-border/50" />
        </>
      )}

      {/* Tags */}
      {(candidate.communication ||
        candidate.education ||
        candidate.brand_experience ||
        candidate.department ||
        candidate.specialization) && (
        <>
          <section>
            <h3 className="text-[10px] font-bold uppercase tracking-widest text-text-muted mb-3">
              Tags
            </h3>
            <div className="flex flex-wrap gap-2">
              {candidate.communication && <TagChip tag={`Comm: ${candidate.communication}`} />}
              {candidate.education && <TagChip tag={`Edu: ${candidate.education}`} />}
              {candidate.brand_experience && <TagChip tag={`Exp: ${candidate.brand_experience}`} />}
              {candidate.department && <TagChip tag={`Dept: ${candidate.department}`} />}
              {candidate.specialization && <TagChip tag={`Spec: ${candidate.specialization}`} />}
            </div>
          </section>
          <div className="h-px bg-border/50" />
        </>
      )}

      {/* Notes */}
      {candidate.notes && (
        <>
          <section>
            <div className="flex items-center gap-1.5 mb-2">
              <IconNotes className="size-3.5 opacity-60 text-text-muted" />
              <h3 className="text-[10px] font-bold uppercase tracking-widest text-text-muted">
                Notes
              </h3>
            </div>
            <p className="text-[12px] text-text-muted leading-relaxed whitespace-pre-wrap">
              {candidate.notes}
            </p>
          </section>
          <div className="h-px bg-border/50" />
        </>
      )}

      {/* Placements — where this person actually landed. Kept above the live
          mappings: it is the part of the profile that outlives the board. */}
      {(history?.placements.length ?? 0) > 0 && (
        <>
          <section>
            <div className="flex items-center gap-1.5 mb-3">
              <IconBuildingStore className="size-3.5 opacity-60 text-text-muted" />
              <h3 className="text-[10px] font-bold uppercase tracking-widest text-text-muted">
                Placements
              </h3>
            </div>
            <div className="space-y-2">
              {history?.placements.map((p) => (
                <PlacementRow key={`${p.position_id}-${p.stage}-${p.at}`} placement={p} />
              ))}
            </div>
          </section>
          <div className="h-px bg-border/50" />
        </>
      )}

      {/* Mapped positions */}
      <section>
        <div className="flex items-center justify-between mb-3">
          <h3 className="text-[10px] font-bold uppercase tracking-widest text-text-muted">
            Mapped Positions
          </h3>
          <span className="text-[10px] font-bold px-2 py-0.5 rounded-full bg-surface-panel border border-border text-text-secondary">
            {loadingMappings ? "…" : mappings.length}
          </span>
        </div>
        <MappingsList loadingMappings={loadingMappings} mappings={mappings} />
      </section>

      <div className="h-px bg-border/50" />

      {/* Full history */}
      <section>
        <div className="flex items-center gap-1.5 mb-3">
          <IconHistory className="size-3.5 opacity-60 text-text-muted" />
          <h3 className="text-[10px] font-bold uppercase tracking-widest text-text-muted">
            History
          </h3>
        </div>
        <HistoryTimeline loading={loadingHistory} events={history?.events ?? []} />
      </section>
    </div>
  );
}

/* ── History ───────────────────────────────────────────────────────────────── */

const STAGE_LABELS: Record<string, string> = {
  sourced: "Sourced",
  sent_to_client: "Sent to client",
  interview: "Interview",
  position_close: "Joined",
  rejected: "Rejected",
  on_hold: "On hold",
};

function stageLabel(stage: string | null): string {
  if (!stage) return "";
  return STAGE_LABELS[stage] ?? stage.replaceAll("_", " ");
}

function formatDate(iso: string): string {
  return new Date(iso).toLocaleDateString(undefined, {
    day: "numeric",
    month: "short",
    year: "numeric",
  });
}

function PlacementRow({ placement }: Readonly<{ placement: ApiCandidatePlacement }>) {
  const joined = placement.stage === "joined";
  return (
    <div className="flex items-start justify-between gap-2 rounded-xl border border-border bg-surface-panel p-3">
      <div className="min-w-0">
        <p className="font-heading font-bold text-text-primary text-sm leading-snug truncate">
          {placement.client_name ?? "Unknown company"}
        </p>
        <p className="text-[11px] text-text-muted mt-0.5 truncate">
          {[placement.role, placement.position_code].filter(Boolean).join(" · ")}
        </p>
        <p className="text-[10px] text-text-muted mt-1">
          {formatDate(placement.at)}
          {placement.employee_name ? ` · ${placement.employee_name}` : ""}
          {placement.is_current ? "" : " · since moved on"}
        </p>
      </div>
      <span
        className="shrink-0 rounded-lg border px-2 py-1 text-[9px] font-bold uppercase"
        style={
          joined
            ? {
                background: "rgba(52,211,153,0.1)",
                color: "#34d399",
                borderColor: "rgba(52,211,153,0.2)",
              }
            : {
                background: "rgba(243,255,84,0.1)",
                color: "var(--color-yellow)",
                borderColor: "rgba(243,255,84,0.2)",
              }
        }
      >
        {joined ? "Joined" : "Selected"}
      </span>
    </div>
  );
}

function eventSummary(event: ApiCandidateHistoryEvent): string {
  const at = event.client_name ? ` at ${event.client_name}` : "";
  switch (event.event_type) {
    case "applied":
      return "Applied through the public form";
    case "created":
      return "Added to the talent pool";
    case "approved":
      return "Application approved";
    case "declined":
      return "Application declined";
    case "mapped":
      return `Put forward for ${event.position_role ?? "a position"}${at}`;
    case "unmapped":
      return `Withdrawn from ${event.position_role ?? "a position"}${at}`;
    case "stage_moved":
      return event.from_stage
        ? `${stageLabel(event.from_stage)} → ${stageLabel(event.to_stage)}${at}`
        : `${stageLabel(event.to_stage)}${at}`;
    default:
      return event.event_type;
  }
}

function HistoryTimeline({
  loading,
  events,
}: Readonly<{ loading: boolean; events: ApiCandidateHistoryEvent[] }>) {
  if (loading) {
    return (
      <div className="h-16 rounded-xl border border-dashed border-border flex items-center justify-center">
        <div className="size-4 border-2 border-border border-t-text-muted rounded-full animate-spin" />
      </div>
    );
  }
  if (events.length === 0) {
    return (
      <p className="rounded-xl border border-dashed border-border bg-surface-panel p-4 text-center text-xs text-text-muted">
        Nothing recorded yet.
      </p>
    );
  }
  // Newest first: the last thing that happened is the thing being looked for.
  const ordered = [...events].reverse();
  return (
    <ol className="relative space-y-3 border-l border-border/60 pl-4">
      {ordered.map((event, i) => (
        <li key={event.id ?? `${event.at}-${i}`} className="relative">
          <span
            className="absolute -left-[21px] top-1.5 size-1.5 rounded-full"
            style={{ background: i === 0 ? "var(--color-yellow)" : "var(--color-border-val)" }}
          />
          <p className="text-xs text-text-primary leading-snug">{eventSummary(event)}</p>
          <p className="text-[10px] text-text-muted mt-0.5">
            {formatDate(event.at)}
            {event.employee_name ? ` · ${event.employee_name}` : ""}
            {event.position_code ? ` · ${event.position_code}` : ""}
          </p>
        </li>
      ))}
    </ol>
  );
}

/* ── Edit mode ─────────────────────────────────────────────────────────────── */

function EditForm({
  candidate,
  onSaved,
  onCancel,
}: Readonly<{
  candidate: ApiCandidate;
  onSaved: (updated: ApiCandidate) => void;
  onCancel: () => void;
}>) {
  const [form, setForm] = useState({
    full_name: candidate.full_name,
    phone: candidate.phone ?? "",
    previous_company: candidate.previous_company ?? "",
    experience_years: String(candidate.experience_years),
    current_role: candidate.current_role ?? "",
    city: candidate.city ?? "",
    area: candidate.area ?? "",
    gender: candidate.gender ?? "",
    age: candidate.age == null ? "" : String(candidate.age),
    education_level: candidate.education_level ?? "",
    expected_salary: candidate.expected_salary == null ? "" : String(candidate.expected_salary),
    salary: candidate.salary == null ? "" : String(candidate.salary),
    notice_period: candidate.notice_period ?? "",
    // Lowercased: the public form used to store "External", which matched
    // neither radio and left the source unset for every applicant.
    source: candidate.source?.toLowerCase() ?? "internal",
    source_channel: candidate.source_channel ?? "",
    source_channel_other: "",
    cv_link: candidate.cv_link ?? "",
    communication: candidate.communication ?? "",
    education: candidate.education ?? "",
    brand_experience: candidate.brand_experience ?? "",
    department: candidate.department ?? "",
    specialization: candidate.specialization ?? "",
    notes: candidate.notes ?? "",
  });
  const [resumeFile, setResumeFile] = useState<File | null>(null);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  function resolvedChannel(): string {
    return resolveSourceChannel(form.source, form.source_channel, form.source_channel_other);
  }

  async function handleSave(e: React.FormEvent) {
    e.preventDefault();
    if (form.department && !form.specialization) {
      setError("Specialization is required when a department is selected");
      return;
    }
    setSaving(true);
    setError(null);
    try {
      if (resumeFile) {
        const uploaded = await uploadResumeToCloudinary(resumeFile);
        await clientConfirmResume(candidate.id, uploaded);
      }
      const payload: Parameters<typeof clientUpdateCandidate>[1] = {
        full_name: form.full_name.trim() || undefined,
        phone: form.phone.trim() || undefined,
        previous_company: form.previous_company.trim() || undefined,
        experience_years: form.experience_years ? Number(form.experience_years) : undefined,
        current_role: form.current_role.trim() || undefined,
        city: form.city.trim() || undefined,
        area: form.area.trim() || undefined,
        gender: form.gender.trim() || undefined,
        age: form.age ? Number(form.age) : undefined,
        education_level: form.education_level || undefined,
        expected_salary: form.expected_salary ? Number(form.expected_salary) : undefined,
        salary: form.salary ? Number(form.salary) : undefined,
        notice_period: form.notice_period.trim() || undefined,
        source: form.source.trim() || undefined,
        source_channel: resolvedChannel() || undefined,
        cv_link: form.cv_link.trim() || undefined,
        communication: form.communication || undefined,
        education: form.education || undefined,
        brand_experience: form.brand_experience || undefined,
        department: form.department || undefined,
        specialization: form.specialization || undefined,
        notes: form.notes.trim() || undefined,
      };
      // The upload happens once, above, before the PATCH: confirming a resume
      // kicks off background parsing that writes to the same document, so the
      // recruiter's edits have to land last. A second upload used to run here
      // for internal candidates, duplicating the Cloudinary asset and racing
      // its own parse against the values just saved.
      const updated = await clientUpdateCandidate(candidate.id, payload);
      onSaved(updated);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Failed to save");
    } finally {
      setSaving(false);
    }
  }

  // Two fields per row from the sm breakpoint so the whole profile fits in far
  // less scrolling; single column below it, where the drawer is full-width and
  // half-width controls would be unusable. Wide inputs span both columns, as do
  // the conditional fields, which would otherwise shift every later field into
  // the opposite column when they appear.
  const full = "sm:col-span-2";

  return (
    <form
      onSubmit={handleSave}
      className="flex-1 overflow-y-auto dashboard-scrollbar grid grid-cols-1 content-start gap-x-3 gap-y-3.5 bg-(--color-canvas) p-6 sm:grid-cols-2"
    >
      {error && (
        <p
          className={`rounded-lg px-3 py-2 text-sm ${full}`}
          style={{ background: "rgba(255,90,95,0.12)", color: "#FF5A5F" }}
        >
          {error}
        </p>
      )}

      <TextField
        label="Full Name"
        value={form.full_name}
        onChange={(full_name) => setForm((f) => ({ ...f, full_name }))}
      />
      <TextField
        label="Phone"
        type="tel"
        value={form.phone}
        onChange={(phone) => setForm((f) => ({ ...f, phone }))}
      />

      <SourceField
        className={full}
        value={form.source}
        onChange={(source) => setForm((f) => ({ ...f, source }))}
      />

      {form.source === "external" && (
        <SourceChannelField
          className={full}
          channel={form.source_channel}
          other={form.source_channel_other}
          onChannel={(source_channel) => setForm((f) => ({ ...f, source_channel }))}
          onOther={(source_channel_other) => setForm((f) => ({ ...f, source_channel_other }))}
        />
      )}

      <TextField
        label="Previous Company"
        value={form.previous_company}
        onChange={(previous_company) => setForm((f) => ({ ...f, previous_company }))}
      />
      <ExperienceYearsField
        value={form.experience_years}
        onChange={(experience_years) => setForm((f) => ({ ...f, experience_years }))}
      />

      <CurrentRoleField
        value={form.current_role}
        onChange={(current_role) => setForm((f) => ({ ...f, current_role }))}
      />

      <CityField value={form.city} onChange={(city) => setForm((f) => ({ ...f, city }))} />
      <AreaField value={form.area} onChange={(area) => setForm((f) => ({ ...f, area }))} />

      <GenderField value={form.gender} onChange={(gender) => setForm((f) => ({ ...f, gender }))} />
      <AgeField value={form.age} onChange={(age) => setForm((f) => ({ ...f, age }))} />

      <EducationField
        value={form.education_level}
        onChange={(education_level) => setForm((f) => ({ ...f, education_level }))}
      />
      <ExpectedSalaryField
        value={form.expected_salary}
        onChange={(expected_salary) => setForm((f) => ({ ...f, expected_salary }))}
      />
      <CurrentSalaryField
        value={form.salary}
        onChange={(salary) => setForm((f) => ({ ...f, salary }))}
      />
      <NoticePeriodField
        value={form.notice_period}
        onChange={(notice_period) => setForm((f) => ({ ...f, notice_period }))}
      />

      {/* The CV belongs to whoever sourced this candidate. Editing the rest of
          the profile is still fair game, but the two CV controls are not shown
          at all: an empty CV link field reads as "no CV", and uploading a
          replacement resume would overwrite work that is not this recruiter's. */}
      {candidate.cv_locked ? (
        <p
          className={`flex items-center gap-2 rounded-lg px-3 py-2 text-xs ${full}`}
          style={{ ...inputStyle, opacity: 0.7 }}
        >
          <IconLock className="size-3.5 shrink-0" />
          {candidate.created_by_name
            ? `CV held by ${candidate.created_by_name} — only they can change it`
            : "CV held by another recruiter"}
        </p>
      ) : (
        <>
          <CvLinkField
            className={full}
            required={form.source === "external"}
            value={form.cv_link}
            onChange={(cv_link) => setForm((f) => ({ ...f, cv_link }))}
          />

          <ResumeField className={full} file={resumeFile} onFile={setResumeFile}>
            {candidate.resume_url && !resumeFile && (
              <a
                href={candidate.resume_url}
                target="_blank"
                rel="noreferrer noopener"
                className="mb-2 flex w-fit items-center gap-2 text-xs transition-colors hover:text-yellow"
                style={{ color: "var(--color-text-secondary)" }}
              >
                <IconFileText className="size-3.5 shrink-0" />
                View current resume
              </a>
            )}
          </ResumeField>
        </>
      )}

      <StructuredCandidateTags
        form={form}
        onChange={(updates) => setForm((f) => ({ ...f, ...updates }))}
      />

      <NotesField
        className={full}
        rows={4}
        value={form.notes}
        onChange={(notes) => setForm((f) => ({ ...f, notes }))}
      />

      <div className={`flex gap-3 pt-2 pb-4 ${full}`}>
        <button
          type="submit"
          disabled={saving}
          className="flex-1 rounded-lg py-2 text-sm font-semibold disabled:opacity-50"
          style={{ background: "var(--color-yellow)", color: "#002348" }}
        >
          {saving ? "Saving…" : "Save Changes"}
        </button>
        <button
          type="button"
          onClick={onCancel}
          className="rounded-lg px-4 py-2 text-sm"
          style={inputStyle}
        >
          Cancel
        </button>
      </div>
    </form>
  );
}

/* ── Shared sub-components ─────────────────────────────────────────────────── */

function MappingsList({
  loadingMappings,
  mappings,
}: Readonly<{ loadingMappings: boolean; mappings: ApiCandidateMappingItem[] }>) {
  if (loadingMappings) {
    return (
      <div className="h-16 rounded-xl border border-dashed border-border flex items-center justify-center">
        <div className="size-4 border-2 border-border border-t-text-muted rounded-full animate-spin" />
      </div>
    );
  }
  if (mappings.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center p-8 rounded-xl border border-dashed border-border bg-surface-panel gap-2">
        <IconBriefcase className="size-5 text-text-muted opacity-30" />
        <p className="text-xs text-text-muted text-center">Not mapped to any open positions</p>
      </div>
    );
  }
  return (
    <div className="space-y-3">
      {mappings.map((m) => (
        <MappingCard key={m.mapping_id} mapping={m} />
      ))}
    </div>
  );
}

function MappingCard({ mapping }: Readonly<{ mapping: ApiCandidateMappingItem }>) {
  const stageLabel = mapping.stage.replaceAll("_", " ");
  return (
    <div className="p-4 rounded-xl border border-border bg-surface-panel">
      <div className="flex items-start justify-between gap-2 mb-2">
        <div className="min-w-0">
          <span className="text-[10px] font-mono font-bold px-1.5 py-0.5 rounded bg-teal-500/10 text-teal-400 border border-teal-500/20 inline-block mb-1.5">
            {mapping.position_code}
          </span>
          <h4 className="font-heading font-bold text-text-primary text-sm leading-snug">
            {mapping.role}
          </h4>
          <p className="text-[11px] text-text-muted mt-0.5">
            {mapping.client_name}
            {mapping.city ? ` · ${mapping.city}` : ""}
          </p>
        </div>
        <span className="flex items-center gap-1 px-2 py-1 rounded-lg bg-emerald-500/10 text-emerald-400 border border-emerald-500/20 text-[9px] font-bold uppercase shrink-0">
          <IconCircleCheck className="size-3" />
          {stageLabel}
        </span>
      </div>

      {mapping.match_score !== null && (
        <div className="flex items-center gap-2 mt-2">
          <div className="flex-1 h-1 rounded-full bg-border overflow-hidden">
            <div
              className="h-full rounded-full bg-yellow"
              style={{ width: `${Math.round(mapping.match_score * 100)}%` }}
            />
          </div>
          <span className="text-[10px] font-bold text-yellow shrink-0">
            {Math.round(mapping.match_score * 100)}%
          </span>
        </div>
      )}

      <div className="mt-3 pt-3 border-t border-border/40">
        <a
          href={`/positions/${mapping.position_id}/pipeline`}
          className="text-[11px] font-semibold text-text-muted hover:text-yellow transition-colors flex items-center gap-1"
        >
          View Pipeline <IconExternalLink className="size-3" />
        </a>
      </div>
    </div>
  );
}
