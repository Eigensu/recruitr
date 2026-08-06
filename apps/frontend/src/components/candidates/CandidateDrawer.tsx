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
} from "@tabler/icons-react";
import type { ApiCandidate, ApiCandidateMappingItem } from "@/types";
import { useApiFetch } from "@/lib/api";
import { getCandidateMappings, resolveCvRef } from "@/lib/api/candidates";
import { clientUpdateCandidate, clientConfirmResume } from "@/lib/api/candidates.client";
import { uploadResumeToCloudinary } from "@/lib/api/storage.client";
import {
  CITIES,
  EDUCATION_LEVELS,
  SOURCE_CHANNEL_OTHER,
  SOURCE_CHANNELS,
} from "@/lib/constants/candidate";
import { getAvatarPalette, getInitials } from "./CandidateCard";

interface CandidateDrawerProps {
  candidate: ApiCandidate | null;
  onClose: () => void;
  onUpdate?: (updated: ApiCandidate) => void;
  /** Approve/reject the open application. Only rendered for maintainers. */
  isMaintainer?: boolean;
  onApprove?: (id: string) => Promise<void>;
  onReject?: (id: string) => Promise<void>;
}

/** Existing records may hold values outside the canonical list (legacy imports).
 *  Keep the stored value selectable so opening and saving never erases it. */
function withExisting(options: readonly string[], current: string): string[] {
  return current && !options.includes(current) ? [...options, current] : [...options];
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
  isMaintainer,
  onApprove,
  onReject,
}: Readonly<{
  candidate: ApiCandidate;
  onClose: () => void;
  onUpdate?: (updated: ApiCandidate) => void;
  loadingMappings: boolean;
  mappings: ApiCandidateMappingItem[];
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
          <a
            href={`mailto:${candidate.email}`}
            className="flex items-center gap-2 text-xs text-text-muted hover:text-yellow transition-colors w-fit"
          >
            <IconMail className="size-3.5 shrink-0" />
            {candidate.email}
          </a>
          {candidate.phone && (
            <span className="flex items-center gap-2 text-xs text-text-muted">
              <IconPhone className="size-3.5 shrink-0" />
              {candidate.phone}
            </span>
          )}
          {cvRef &&
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
            ))}
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
  showReviewHint,
  onEdit,
}: Readonly<{
  candidate: ApiCandidate;
  loadingMappings: boolean;
  mappings: ApiCandidateMappingItem[];
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

      {/* Previous role / notice / education / source */}
      {(candidate.previous_role ||
        candidate.notice_period ||
        candidate.education_level ||
        candidate.source) && (
        <>
          <section className="flex flex-wrap gap-4">
            {candidate.previous_role && (
              <div className="flex items-center gap-2 text-sm text-text-muted">
                <IconBriefcase className="size-3.5 shrink-0 opacity-60" />
                <span>Prev: {candidate.previous_role}</span>
              </div>
            )}
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
      {candidate.tags.length > 0 && (
        <>
          <section>
            <h3 className="text-[10px] font-bold uppercase tracking-widest text-text-muted mb-3">
              Tags
            </h3>
            <div className="flex flex-wrap gap-2">
              {candidate.tags.map((tag) => (
                <span
                  key={tag}
                  className="rounded-full px-3 py-1 text-[11px] font-semibold"
                  style={{
                    background: "rgba(96,165,250,0.1)",
                    color: "#60a5fa",
                    border: "1px solid rgba(96,165,250,0.25)",
                  }}
                >
                  {tag}
                </span>
              ))}
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
    </div>
  );
}

/* ── Edit mode ─────────────────────────────────────────────────────────────── */

const inputCls = "w-full rounded-lg px-3 py-2 text-sm outline-none";
const inputStyle = {
  background: "var(--color-canvas-val)",
  color: "var(--color-text-primary)",
  border: "1px solid var(--color-border-val)",
};
const labelStyle = { color: "var(--color-text-secondary)" };

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
    previous_role: candidate.previous_role ?? "",
    city: candidate.city ?? "",
    area: candidate.area ?? "",
    gender: candidate.gender ?? "",
    age: candidate.age == null ? "" : String(candidate.age),
    education_level: candidate.education_level ?? "",
    expected_salary: candidate.expected_salary == null ? "" : String(candidate.expected_salary),
    notice_period: candidate.notice_period ?? "",
    // Lowercased: the public form used to store "External", which matched
    // neither radio and left the source unset for every applicant.
    source: candidate.source?.toLowerCase() ?? "internal",
    source_channel: candidate.source_channel ?? "",
    source_channel_other: "",
    cv_link: candidate.cv_link ?? "",
    tagInput: "",
    tags: [...candidate.tags],
    notes: candidate.notes ?? "",
  });
  const [resumeFile, setResumeFile] = useState<File | null>(null);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  function addTag() {
    const raw = form.tagInput.trim().toLowerCase();
    if (!raw || form.tags.includes(raw)) return;
    setForm((f) => ({ ...f, tags: [...f.tags, raw], tagInput: "" }));
  }

  function removeTag(tag: string) {
    setForm((f) => ({ ...f, tags: f.tags.filter((t) => t !== tag) }));
  }

  // Channels only classify external candidates; "Other" carries the typed value.
  function resolvedChannel(): string {
    if (form.source !== "external") return "";
    return form.source_channel === SOURCE_CHANNEL_OTHER
      ? form.source_channel_other.trim()
      : form.source_channel;
  }

  async function handleSave(e: React.FormEvent) {
    e.preventDefault();
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
        previous_role: form.previous_role.trim() || undefined,
        city: form.city.trim() || undefined,
        area: form.area.trim() || undefined,
        gender: form.gender.trim() || undefined,
        age: form.age ? Number(form.age) : undefined,
        education_level: form.education_level || undefined,
        expected_salary: form.expected_salary ? Number(form.expected_salary) : undefined,
        notice_period: form.notice_period.trim() || undefined,
        source: form.source.trim() || undefined,
        source_channel: resolvedChannel() || undefined,
        cv_link: form.cv_link.trim() || undefined,
        tags: form.tags,
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

  return (
    // Two fields per row so the whole profile fits in far less scrolling —
    // wide inputs (source, tags, notes, files) still span both columns.
    <form
      onSubmit={handleSave}
      className="flex-1 overflow-y-auto dashboard-scrollbar p-6 grid grid-cols-2 content-start gap-x-3 gap-y-3.5 bg-(--color-canvas)"
    >
      {error && (
        <p
          className="col-span-2 rounded-lg px-3 py-2 text-sm"
          style={{ background: "rgba(255,90,95,0.12)", color: "#FF5A5F" }}
        >
          {error}
        </p>
      )}

      <div>
        <label className="mb-1 block text-xs font-medium" style={labelStyle}>
          Full Name
        </label>
        <input
          className={inputCls}
          style={inputStyle}
          value={form.full_name}
          onChange={(e) => setForm((f) => ({ ...f, full_name: e.target.value }))}
        />
      </div>

      <div>
        <label className="mb-1 block text-xs font-medium" style={labelStyle}>
          Phone
        </label>
        <input
          type="tel"
          className={inputCls}
          style={inputStyle}
          value={form.phone}
          onChange={(e) => setForm((f) => ({ ...f, phone: e.target.value }))}
        />
      </div>

      <div className="col-span-2">
        <label className="mb-1 block text-xs font-medium" style={labelStyle}>
          Source
        </label>
        <div className="flex gap-4">
          {(["internal", "external"] as const).map((s) => (
            <label key={s} className="flex cursor-pointer items-center gap-2">
              <input
                type="radio"
                name="source"
                value={s}
                checked={form.source === s}
                onChange={() => setForm((f) => ({ ...f, source: s }))}
              />
              <span
                className="text-sm font-medium"
                style={{ color: s === "internal" ? "#3DDC97" : "#FF5A5F" }}
              >
                ● {s === "internal" ? "Internal" : "External"}
              </span>
            </label>
          ))}
        </div>
      </div>

      {/* Full width: appearing mid-grid would otherwise shift every later
          field into the opposite column. */}
      {form.source === "external" && (
        <div className="col-span-2">
          <label className="mb-1 block text-xs font-medium" style={labelStyle}>
            Source Channel
          </label>
          <select
            className={inputCls}
            style={inputStyle}
            value={form.source_channel}
            onChange={(e) => setForm((f) => ({ ...f, source_channel: e.target.value }))}
          >
            <option value="">Select...</option>
            {withExisting(SOURCE_CHANNELS, form.source_channel).map((c) => (
              <option key={c} value={c}>
                {c}
              </option>
            ))}
          </select>
          {form.source_channel === SOURCE_CHANNEL_OTHER && (
            <input
              className={`${inputCls} mt-2`}
              style={inputStyle}
              placeholder="Where did they come from?"
              value={form.source_channel_other}
              onChange={(e) => setForm((f) => ({ ...f, source_channel_other: e.target.value }))}
            />
          )}
        </div>
      )}

      <div>
        <label className="mb-1 block text-xs font-medium" style={labelStyle}>
          Previous Company
        </label>
        <input
          className={inputCls}
          style={inputStyle}
          value={form.previous_company}
          onChange={(e) => setForm((f) => ({ ...f, previous_company: e.target.value }))}
        />
      </div>

      <div>
        <label className="mb-1 block text-xs font-medium" style={labelStyle}>
          Experience (years)
        </label>
        <input
          type="number"
          min="0"
          step="0.5"
          className={inputCls}
          style={inputStyle}
          value={form.experience_years}
          onChange={(e) => setForm((f) => ({ ...f, experience_years: e.target.value }))}
        />
      </div>

      <div>
        <label className="mb-1 block text-xs font-medium" style={labelStyle}>
          Current Role
        </label>
        <input
          className={inputCls}
          style={inputStyle}
          placeholder="e.g. Senior Engineer"
          value={form.current_role}
          onChange={(e) => setForm((f) => ({ ...f, current_role: e.target.value }))}
        />
      </div>

      <div>
        <label className="mb-1 block text-xs font-medium" style={labelStyle}>
          Previous Role
        </label>
        <input
          className={inputCls}
          style={inputStyle}
          placeholder="e.g. Software Engineer"
          value={form.previous_role}
          onChange={(e) => setForm((f) => ({ ...f, previous_role: e.target.value }))}
        />
      </div>

      <div>
        <label className="mb-1 block text-xs font-medium" style={labelStyle}>
          City
        </label>
        <select
          className={inputCls}
          style={inputStyle}
          value={form.city}
          onChange={(e) => setForm((f) => ({ ...f, city: e.target.value }))}
        >
          <option value="">Select...</option>
          {withExisting(CITIES, form.city).map((c) => (
            <option key={c} value={c}>
              {c}
            </option>
          ))}
        </select>
      </div>

      <div>
        <label className="mb-1 block text-xs font-medium" style={labelStyle}>
          Area
        </label>
        <input
          className={inputCls}
          style={inputStyle}
          placeholder="e.g. Andheri"
          value={form.area}
          onChange={(e) => setForm((f) => ({ ...f, area: e.target.value }))}
        />
      </div>

      <div>
        <label className="mb-1 block text-xs font-medium" style={labelStyle}>
          Gender
        </label>
        <select
          className={inputCls}
          style={inputStyle}
          value={form.gender}
          onChange={(e) => setForm((f) => ({ ...f, gender: e.target.value }))}
        >
          <option value="">Select...</option>
          <option value="male">Male</option>
          <option value="female">Female</option>
          <option value="other">Other</option>
        </select>
      </div>

      <div>
        <label className="mb-1 block text-xs font-medium" style={labelStyle}>
          Age
        </label>
        <input
          type="number"
          className={inputCls}
          style={inputStyle}
          placeholder="e.g. 25"
          value={form.age}
          onChange={(e) => setForm((f) => ({ ...f, age: e.target.value }))}
        />
      </div>

      <div>
        <label className="mb-1 block text-xs font-medium" style={labelStyle}>
          Highest Education
        </label>
        <select
          className={inputCls}
          style={inputStyle}
          value={form.education_level}
          onChange={(e) => setForm((f) => ({ ...f, education_level: e.target.value }))}
        >
          <option value="">Select...</option>
          {withExisting(
            EDUCATION_LEVELS.map((l) => l.value),
            form.education_level,
          ).map((value) => (
            <option key={value} value={value}>
              {EDUCATION_LEVELS.find((l) => l.value === value)?.label ?? value}
            </option>
          ))}
        </select>
      </div>

      <div>
        <label className="mb-1 block text-xs font-medium" style={labelStyle}>
          Expected Salary
        </label>
        <input
          type="number"
          min="0"
          className={inputCls}
          style={inputStyle}
          placeholder="e.g. 85000"
          value={form.expected_salary}
          onChange={(e) => setForm((f) => ({ ...f, expected_salary: e.target.value }))}
        />
      </div>

      <div>
        <label className="mb-1 block text-xs font-medium" style={labelStyle}>
          Notice Period
        </label>
        <input
          className={inputCls}
          style={inputStyle}
          placeholder="e.g. 30 days"
          value={form.notice_period}
          onChange={(e) => setForm((f) => ({ ...f, notice_period: e.target.value }))}
        />
      </div>

      <div className="col-span-2">
        <label className="mb-1 block text-xs font-medium" style={labelStyle}>
          CV Link{form.source === "external" ? " *" : ""}
        </label>
        <input
          type="url"
          className={inputCls}
          style={inputStyle}
          placeholder="https://…"
          value={form.cv_link}
          onChange={(e) => setForm((f) => ({ ...f, cv_link: e.target.value }))}
        />
      </div>

      <div className="col-span-2">
        <label className="mb-1 block text-xs font-medium" style={labelStyle}>
          Resume
        </label>
        {candidate.resume_url && !resumeFile && (
          <a
            href={candidate.resume_url}
            target="_blank"
            rel="noreferrer noopener"
            className="mb-2 flex items-center gap-2 text-xs hover:text-yellow transition-colors w-fit"
            style={{ color: "var(--color-text-secondary)" }}
          >
            <IconFileText className="size-3.5 shrink-0" />
            View current resume
          </a>
        )}
        <input
          type="file"
          accept=".pdf,.docx,.doc,application/pdf,application/vnd.openxmlformats-officedocument.wordprocessingml.document,application/msword"
          className="block w-full text-sm"
          style={{ color: "var(--color-text-secondary)" }}
          onChange={(e) => setResumeFile(e.target.files?.[0] ?? null)}
        />
        {resumeFile && (
          <p className="mt-1 text-xs" style={{ color: "var(--color-text-secondary)" }}>
            {resumeFile.name}
          </p>
        )}
      </div>

      <div className="col-span-2">
        <div className="mb-1 flex items-center gap-2">
          <label className="block text-xs font-medium" style={labelStyle}>
            Manual Tags
          </label>
          <span
            className="rounded px-1.5 py-0.5 text-[9px] font-semibold uppercase tracking-wide"
            style={{ background: "rgba(251,146,60,0.15)", color: "#fb923c" }}
          >
            recruiter
          </span>
        </div>
        <div className="flex gap-2">
          <input
            className={inputCls}
            style={inputStyle}
            placeholder="e.g. senior, python"
            value={form.tagInput}
            onChange={(e) => setForm((f) => ({ ...f, tagInput: e.target.value }))}
            onKeyDown={(e) => {
              if (e.key === "Enter" || e.key === ",") {
                e.preventDefault();
                addTag();
              }
            }}
          />
          <button
            type="button"
            onClick={addTag}
            className="shrink-0 rounded-lg px-3 py-1.5 text-sm font-medium"
            style={inputStyle}
          >
            Add
          </button>
        </div>
        {form.tags.length > 0 && (
          <div className="mt-2 flex flex-wrap gap-1">
            {form.tags.map((tag) => (
              <span
                key={tag}
                className="inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-xs"
                style={{
                  background: "rgba(96,165,250,0.1)",
                  color: "#60a5fa",
                  border: "1px solid rgba(96,165,250,0.25)",
                }}
              >
                {tag}
                <button
                  type="button"
                  onClick={() => removeTag(tag)}
                  className="opacity-60 hover:opacity-100"
                >
                  ×
                </button>
              </span>
            ))}
          </div>
        )}
      </div>

      <div className="col-span-2">
        <label className="mb-1 block text-xs font-medium" style={labelStyle}>
          Notes
        </label>
        <textarea
          rows={4}
          className={inputCls}
          style={{ ...inputStyle, resize: "vertical" }}
          placeholder="Any notes about this candidate…"
          value={form.notes}
          onChange={(e) => setForm((f) => ({ ...f, notes: e.target.value }))}
        />
      </div>

      <div className="col-span-2 flex gap-3 pt-2 pb-4">
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
