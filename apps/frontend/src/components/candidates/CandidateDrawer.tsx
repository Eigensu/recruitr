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
  IconSparkles,
  IconTag,
  IconCurrencyDollar,
  IconNotes,
  IconPencil,
  IconCheck,
} from "@tabler/icons-react";
import type { ApiCandidate, ApiCandidateMappingItem } from "@/types";
import { useApiFetch } from "@/lib/api";
import { getCandidateMappings, resolveCvRef } from "@/lib/api/candidates";
import { clientUpdateCandidate } from "@/lib/api/candidates.client";
import { getAvatarPalette, getInitials } from "./CandidateCard";

interface CandidateDrawerProps {
  candidate: ApiCandidate | null;
  onClose: () => void;
  onUpdate?: (updated: ApiCandidate) => void;
}

export default function CandidateDrawer({
  candidate,
  onClose,
  onUpdate,
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
}: Readonly<{
  candidate: ApiCandidate;
  onClose: () => void;
  onUpdate?: (updated: ApiCandidate) => void;
  loadingMappings: boolean;
  mappings: ApiCandidateMappingItem[];
}>) {
  const [isEditing, setIsEditing] = useState(false);

  const palette = getAvatarPalette(candidate.full_name);
  const initials = getInitials(candidate.full_name);
  const cvRef = resolveCvRef(candidate.cv_link, candidate.resume_url);

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

        <h2
          id="candidateDrawerTitle"
          className="font-heading font-bold text-text-primary text-2xl leading-tight"
        >
          {candidate.full_name}
        </h2>
        <p className="text-sm text-text-muted mt-1 flex items-center gap-1.5">
          <IconBriefcase className="size-3.5 shrink-0" />
          {candidate.previous_company ?? "Independent"} · {candidate.experience_years} yrs exp
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
        <ViewBody candidate={candidate} loadingMappings={loadingMappings} mappings={mappings} />
      )}
    </>
  );
}

/* ── View mode ─────────────────────────────────────────────────────────────── */

function ViewBody({
  candidate,
  loadingMappings,
  mappings,
}: Readonly<{
  candidate: ApiCandidate;
  loadingMappings: boolean;
  mappings: ApiCandidateMappingItem[];
}>) {
  return (
    <div className="flex-1 overflow-y-auto dashboard-scrollbar p-6 space-y-6 bg-(--color-canvas)">
      {/* Current role / salary */}
      {(candidate.current_role != null || candidate.salary != null) && (
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
                <span>{candidate.salary.toLocaleString()}</span>
              </div>
            )}
          </section>
          <div className="h-px bg-border/50" />
        </>
      )}

      {/* Skills */}
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

      {/* Tags */}
      {(candidate.ai_tags.length > 0 || candidate.recruiter_tags.length > 0) && (
        <>
          <section>
            <h3 className="text-[10px] font-bold uppercase tracking-widest text-text-muted mb-3">
              Tags
            </h3>
            {candidate.ai_tags.length > 0 && (
              <div className="mb-3">
                <div className="flex items-center gap-1.5 mb-2">
                  <IconSparkles className="size-3 opacity-60" style={{ color: "#60a5fa" }} />
                  <span
                    className="text-[9px] font-bold uppercase tracking-widest"
                    style={{ color: "#60a5fa" }}
                  >
                    Auto · Parsed
                  </span>
                </div>
                <div className="flex flex-wrap gap-1.5">
                  {candidate.ai_tags.map((tag) => (
                    <span
                      key={tag}
                      className="text-[10px] font-medium px-2.5 py-0.5 rounded-full"
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
              </div>
            )}
            {candidate.recruiter_tags.length > 0 && (
              <div>
                <div className="flex items-center gap-1.5 mb-2">
                  <IconTag className="size-3 opacity-60" style={{ color: "#fb923c" }} />
                  <span
                    className="text-[9px] font-bold uppercase tracking-widest"
                    style={{ color: "#fb923c" }}
                  >
                    Manual · Recruiter
                  </span>
                </div>
                <div className="flex flex-wrap gap-1.5">
                  {candidate.recruiter_tags.map((tag) => (
                    <span
                      key={tag}
                      className="text-[10px] font-medium px-2.5 py-0.5 rounded-full"
                      style={{
                        background: "rgba(251,146,60,0.1)",
                        color: "#fb923c",
                        border: "1px solid rgba(251,146,60,0.25)",
                      }}
                    >
                      {tag}
                    </span>
                  ))}
                </div>
              </div>
            )}
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
    salary: candidate.salary == null ? "" : String(candidate.salary),
    cv_link: candidate.cv_link ?? "",
    tagInput: "",
    recruiter_tags: [...candidate.recruiter_tags],
    notes: candidate.notes ?? "",
  });
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  function addTag() {
    const raw = form.tagInput.trim().toLowerCase();
    if (!raw || form.recruiter_tags.includes(raw)) return;
    setForm((f) => ({ ...f, recruiter_tags: [...f.recruiter_tags, raw], tagInput: "" }));
  }

  function removeTag(tag: string) {
    setForm((f) => ({ ...f, recruiter_tags: f.recruiter_tags.filter((t) => t !== tag) }));
  }

  async function handleSave(e: React.FormEvent) {
    e.preventDefault();
    setSaving(true);
    setError(null);
    try {
      const payload: Parameters<typeof clientUpdateCandidate>[1] = {
        full_name: form.full_name.trim() || undefined,
        phone: form.phone.trim() || undefined,
        previous_company: form.previous_company.trim() || undefined,
        experience_years: form.experience_years ? Number(form.experience_years) : undefined,
        current_role: form.current_role.trim() || undefined,
        salary: form.salary ? Number(form.salary) : undefined,
        cv_link: form.cv_link.trim() || undefined,
        recruiter_tags: form.recruiter_tags,
        notes: form.notes.trim() || undefined,
      };
      const updated = await clientUpdateCandidate(candidate.id, payload);
      onSaved(updated);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Failed to save");
    } finally {
      setSaving(false);
    }
  }

  return (
    <form
      onSubmit={handleSave}
      className="flex-1 overflow-y-auto dashboard-scrollbar p-6 space-y-4 bg-(--color-canvas)"
    >
      {error && (
        <p
          className="rounded-lg px-3 py-2 text-sm"
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
          Salary
        </label>
        <input
          type="number"
          min="0"
          className={inputCls}
          style={inputStyle}
          placeholder="e.g. 85000"
          value={form.salary}
          onChange={(e) => setForm((f) => ({ ...f, salary: e.target.value }))}
        />
      </div>

      <div>
        <label className="mb-1 block text-xs font-medium" style={labelStyle}>
          CV Link
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

      <div>
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
        {form.recruiter_tags.length > 0 && (
          <div className="mt-2 flex flex-wrap gap-1">
            {form.recruiter_tags.map((tag) => (
              <span
                key={tag}
                className="inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-xs"
                style={{
                  background: "rgba(251,146,60,0.1)",
                  color: "#fb923c",
                  border: "1px solid rgba(251,146,60,0.25)",
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

        {/* Auto tags — read-only display */}
        {candidate.ai_tags.length > 0 && (
          <div className="mt-3">
            <div className="flex items-center gap-1.5 mb-1.5">
              <IconSparkles className="size-3 opacity-50" style={{ color: "#60a5fa" }} />
              <span
                className="text-[9px] font-bold uppercase tracking-widest opacity-60"
                style={{ color: "#60a5fa" }}
              >
                Auto · Parsed (read-only)
              </span>
            </div>
            <div className="flex flex-wrap gap-1">
              {candidate.ai_tags.map((tag) => (
                <span
                  key={tag}
                  className="text-[10px] px-2 py-0.5 rounded-full opacity-60"
                  style={{
                    background: "rgba(96,165,250,0.08)",
                    color: "#60a5fa",
                    border: "1px solid rgba(96,165,250,0.18)",
                  }}
                >
                  {tag}
                </span>
              ))}
            </div>
          </div>
        )}
      </div>

      <div>
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

      <div className="flex gap-3 pt-2 pb-4">
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
