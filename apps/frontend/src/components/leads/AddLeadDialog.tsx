"use client";

import { useRef, useState } from "react";
import { motion } from "motion/react";
import {
  IconFileText,
  IconLoader2,
  IconPlus,
  IconSend,
  IconTrash,
  IconUpload,
  IconX,
} from "@tabler/icons-react";
import { cn } from "@/lib/utils";
import { apiErrorMessage } from "@/lib/api";
import { addLeads, parseResumes, type ManualLeadInput } from "@/lib/api/intake";
import { CITIES, DEPARTMENT_OPTIONS } from "@/lib/constants/candidate";
import {
  RESUME_BATCH_MAX_FILES,
  RESUME_LIMITS_LABEL,
  RESUME_MAX_BYTES,
} from "@/lib/constants/uploads";

const FIELD_KEYS = [
  "full_name",
  "phone",
  "email",
  "city",
  "current_role",
  "department",
  "current_company",
  "experience_years",
  "salary",
  "expected_salary",
] as const;
type FieldKey = (typeof FIELD_KEYS)[number];
type Fields = Record<FieldKey, string>;

interface Draft {
  key: string;
  file: File | null;
  fields: Fields;
  problems: Partial<Record<FieldKey, string>>;
  /** What the server said when this draft was last submitted and not added. */
  serverError?: string;
}

const EMPTY: Fields = Object.fromEntries(FIELD_KEYS.map((k) => [k, ""])) as Fields;

const INPUT =
  "w-full rounded-lg border border-border bg-transparent px-2.5 py-1.5 text-sm text-text-primary placeholder:text-text-muted focus:border-yellow focus:outline-none";
const LABEL = "mb-1 block text-[11px] font-medium text-text-secondary";

let keySeq = 0;
const nextKey = () => `draft-${++keySeq}`;

function isResumeFile(file: File): boolean {
  const name = file.name.toLowerCase();
  return name.endsWith(".pdf") || name.endsWith(".docx");
}

function validate(fields: Fields): Draft["problems"] {
  const problems: Draft["problems"] = {};
  if (!fields.full_name.trim()) problems.full_name = "Required";
  if (fields.phone.replace(/\D/g, "").length < 10) problems.phone = "10-digit number";
  if (fields.salary.trim() === "" || Number(fields.salary) < 0) problems.salary = "Required";
  if (fields.expected_salary.trim() !== "" && Number(fields.expected_salary) < 0)
    problems.expected_salary = "Must be 0 or more";
  return problems;
}

function toInput(fields: Fields, resumeIndex: number | undefined): ManualLeadInput {
  const text = (k: FieldKey) => fields[k].trim() || undefined;
  const num = (k: FieldKey) => (fields[k].trim() === "" ? undefined : Number(fields[k]));
  return {
    full_name: fields.full_name.trim(),
    phone: fields.phone.trim(),
    email: text("email"),
    city: text("city"),
    current_role: text("current_role"),
    department: text("department"),
    current_company: text("current_company"),
    experience_years: num("experience_years"),
    salary: Number(fields.salary),
    expected_salary: num("expected_salary"),
    resume_index: resumeIndex,
  };
}

/**
 * Add leads by hand, or from a stack of resumes.
 *
 * Dropping resumes reads each into a draft to check — nothing is saved or
 * uploaded until "Add". Every draft goes through the telecaller queue like any
 * other lead, and is added or refused on its own: the ones that go through
 * leave the list, the ones that don't stay with the reason.
 */
export default function AddLeadDialog({
  onClose,
  onAdded,
}: {
  readonly onClose: () => void;
  readonly onAdded: () => void;
}) {
  const inputRef = useRef<HTMLInputElement>(null);
  const [drafts, setDrafts] = useState<Draft[]>([]);
  const [rejected, setRejected] = useState<{ name: string; reason: string }[]>([]);
  const [reading, setReading] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [added, setAdded] = useState({ queued: 0, waiting: 0, duplicate: 0 });
  const [done, setDone] = useState<{ name: string; detail: string }[]>([]);

  const busy = reading || submitting;
  const room = RESUME_BATCH_MAX_FILES - drafts.length;

  async function addFiles(list: FileList | null) {
    if (!list || list.length === 0) return;
    setError(null);
    const files = Array.from(list);
    const skipped: { name: string; reason: string }[] = [];
    const usable: File[] = [];
    for (const file of files) {
      if (!isResumeFile(file)) skipped.push({ name: file.name, reason: "Not a PDF or .docx" });
      else if (file.size > RESUME_MAX_BYTES) skipped.push({ name: file.name, reason: "Over 5 MB" });
      else if (usable.length >= room)
        skipped.push({ name: file.name, reason: `Only ${RESUME_BATCH_MAX_FILES} leads at a time` });
      else usable.push(file);
    }
    setRejected((prev) => [...prev, ...skipped]);
    if (usable.length === 0) return;

    setReading(true);
    try {
      const parsed = await parseResumes(usable);
      const next: Draft[] = [];
      const unreadable: { name: string; reason: string }[] = [];
      parsed.forEach((draft, i) => {
        if (draft.error) {
          unreadable.push({ name: draft.filename, reason: draft.error });
          return;
        }
        next.push({
          key: nextKey(),
          file: usable[i],
          problems: {},
          fields: {
            ...EMPTY,
            full_name: draft.full_name ?? "",
            phone: draft.phone ?? "",
            email: draft.email ?? "",
            city: draft.city ?? "",
            current_role: draft.current_role ?? "",
            department: draft.department ?? "",
            current_company: draft.current_company ?? "",
            experience_years: draft.experience_years == null ? "" : String(draft.experience_years),
          },
        });
      });
      setRejected((prev) => [...prev, ...unreadable]);
      setDrafts((prev) => [...prev, ...next]);
    } catch (err) {
      setError(apiErrorMessage(err, "Couldn't read those resumes."));
    } finally {
      setReading(false);
      if (inputRef.current) inputRef.current.value = "";
    }
  }

  function addBlank() {
    setDrafts((prev) => [
      ...prev,
      { key: nextKey(), file: null, fields: { ...EMPTY }, problems: {} },
    ]);
  }

  function update(key: string, field: FieldKey, value: string) {
    setDrafts((prev) =>
      prev.map((d) =>
        d.key === key
          ? {
              ...d,
              fields: { ...d.fields, [field]: value },
              problems: { ...d.problems, [field]: undefined },
            }
          : d,
      ),
    );
  }

  function remove(key: string) {
    setDrafts((prev) => prev.filter((d) => d.key !== key));
  }

  async function submit() {
    setError(null);
    const checked = drafts.map((d) => ({
      ...d,
      problems: validate(d.fields),
      serverError: undefined,
    }));
    setDrafts(checked);
    if (checked.some((d) => Object.keys(d.problems).length > 0)) return;

    // Each draft names its resume by position in the files sent with it.
    const files: File[] = [];
    const inputs = checked.map((d) => {
      if (!d.file) return toInput(d.fields, undefined);
      files.push(d.file);
      return toInput(d.fields, files.length - 1);
    });

    setSubmitting(true);
    try {
      const res = await addLeads(inputs, files);
      const byIndex = new Map(res.results.map((r) => [r.index, r]));
      setDrafts(
        checked
          .map((d, i) => ({ draft: d, result: byIndex.get(i) }))
          .filter(({ result }) => result?.status === "error")
          .map(({ draft, result }) => ({ ...draft, serverError: result?.detail })),
      );
      setAdded((prev) => ({
        queued: prev.queued + res.queued,
        waiting: prev.waiting + res.waiting,
        duplicate: prev.duplicate + res.duplicate,
      }));
      // Drafts that went through leave the list, so their outcome — including
      // "the resume couldn't be attached" — is kept here instead.
      setDone((prev) => [
        ...prev,
        ...res.results
          .filter((r) => r.status !== "error")
          .map((r) => ({ name: r.full_name ?? `Lead ${r.index + 1}`, detail: r.detail })),
      ]);
      if (res.queued + res.waiting + res.duplicate > 0) onAdded();
    } catch (err) {
      setError(apiErrorMessage(err, "Couldn't add those leads. Nothing was saved."));
    } finally {
      setSubmitting(false);
    }
  }

  const addedTotal = added.queued + added.waiting + added.duplicate;

  return (
    <div className="fixed inset-0 z-50 flex items-end justify-center bg-black/60 p-4 sm:items-center">
      <button
        type="button"
        aria-label="Close"
        tabIndex={-1}
        onClick={busy ? undefined : onClose}
        className="absolute inset-0 cursor-default"
      />
      <motion.div
        initial={{ opacity: 0, y: 12 }}
        animate={{ opacity: 1, y: 0 }}
        role="dialog"
        aria-modal="true"
        aria-label="Add leads"
        className="relative flex max-h-[90vh] w-full max-w-4xl flex-col rounded-xl border border-border bg-surface p-5 shadow-2xl"
      >
        <header className="mb-4 flex items-start justify-between gap-3">
          <div>
            <h2 className="font-heading text-lg font-bold text-text-primary">Add leads</h2>
            <p className="mt-0.5 text-sm text-text-secondary">
              Drop resumes to fill the details in, or add someone by hand. Each lead goes to a
              telecaller first. Salaries are per month.
            </p>
          </div>
          <button
            type="button"
            onClick={onClose}
            disabled={busy}
            aria-label="Close"
            className="rounded-lg p-1 text-text-muted hover:text-text-primary disabled:opacity-40"
          >
            <IconX className="size-4" />
          </button>
        </header>

        {error && (
          <p
            role="alert"
            className="mb-3 rounded-lg border border-red-500/20 bg-red-500/10 px-3 py-2 text-sm text-red-400"
          >
            {error}
          </p>
        )}

        {addedTotal > 0 && (
          <p
            role="status"
            className="mb-3 rounded-lg border border-emerald-500/20 bg-emerald-500/10 px-3 py-2 text-sm text-emerald-300"
          >
            Added {added.queued + added.waiting} lead{added.queued + added.waiting === 1 ? "" : "s"}
            {added.waiting > 0 && ` (${added.waiting} waiting for an active telecaller)`}
            {added.duplicate > 0 &&
              `; ${added.duplicate} already in the pool, filed as duplicate${added.duplicate === 1 ? "" : "s"}`}
            .
          </p>
        )}
        {done.length > 0 && (
          <ul className="mb-3 max-h-24 overflow-y-auto text-xs text-text-secondary">
            {done.map((d, i) => (
              <li key={`${d.name}-${i}`}>
                <span className="text-text-primary">{d.name}</span> — {d.detail}
              </li>
            ))}
          </ul>
        )}

        <div className="min-h-0 flex-1 overflow-y-auto pr-1">
          <div className="mb-3 flex flex-wrap items-center gap-2">
            <label
              htmlFor="lead-resumes"
              className={cn(
                "inline-flex cursor-pointer items-center gap-1.5 rounded-lg border border-dashed border-border px-3 py-2 text-sm text-text-secondary hover:border-yellow/40 hover:text-text-primary",
                (busy || room <= 0) && "pointer-events-none opacity-50",
              )}
            >
              {reading ? (
                <IconLoader2 className="size-4 animate-spin" />
              ) : (
                <IconUpload className="size-4" />
              )}
              {reading ? "Reading resumes…" : "Add from resumes"}
              <input
                ref={inputRef}
                id="lead-resumes"
                type="file"
                multiple
                accept=".pdf,.docx,application/pdf,application/vnd.openxmlformats-officedocument.wordprocessingml.document"
                className="sr-only"
                onChange={(e) => addFiles(e.target.files)}
              />
            </label>
            <button
              type="button"
              onClick={addBlank}
              disabled={busy || room <= 0}
              className="inline-flex items-center gap-1.5 rounded-lg border border-border px-3 py-2 text-sm text-text-secondary hover:text-text-primary disabled:opacity-50"
            >
              <IconPlus className="size-4" />
              Add without a resume
            </button>
            <span className="text-xs text-text-muted">{RESUME_LIMITS_LABEL}</span>
          </div>

          {rejected.length > 0 && (
            <ul className="mb-3 rounded-lg border border-border px-3 py-2 text-xs text-text-muted">
              {rejected.map((r) => (
                <li key={`${r.name}-${r.reason}`}>
                  <span className="text-text-secondary">{r.name}</span> — not added: {r.reason}
                </li>
              ))}
            </ul>
          )}

          {drafts.length === 0 && !reading && (
            <p className="rounded-xl border border-dashed border-border px-6 py-10 text-center text-sm text-text-muted">
              {addedTotal > 0
                ? "All done. Add more, or close."
                : "Nothing to add yet — choose resumes or add someone by hand."}
            </p>
          )}

          <ol className="flex flex-col gap-3">
            {drafts.map((draft, n) => (
              <li
                key={draft.key}
                className={cn(
                  "rounded-xl border p-3",
                  draft.serverError ? "border-red-500/40" : "border-border",
                )}
              >
                <div className="mb-2 flex items-center justify-between gap-2">
                  <span className="flex items-center gap-1.5 text-xs text-text-muted">
                    <span className="font-semibold text-text-secondary">Lead {n + 1}</span>
                    {draft.file && (
                      <>
                        <IconFileText className="size-3.5" />
                        {draft.file.name}
                      </>
                    )}
                  </span>
                  <button
                    type="button"
                    onClick={() => remove(draft.key)}
                    disabled={busy}
                    aria-label={`Remove lead ${n + 1}`}
                    className="rounded p-1 text-text-muted hover:text-red-400 disabled:opacity-40"
                  >
                    <IconTrash className="size-3.5" />
                  </button>
                </div>
                {draft.serverError && (
                  <p className="mb-2 text-xs text-red-400">Not added: {draft.serverError}</p>
                )}
                <div className="grid grid-cols-2 gap-2 sm:grid-cols-3">
                  <Field draft={draft} k="full_name" label="Name *" onChange={update} />
                  <Field draft={draft} k="phone" label="Phone *" type="tel" onChange={update} />
                  <Field draft={draft} k="email" label="Email" type="email" onChange={update} />
                  <Field draft={draft} k="city" label="City" list="lead-cities" onChange={update} />
                  <Field draft={draft} k="current_role" label="Current role" onChange={update} />
                  <div>
                    <label className={LABEL} htmlFor={`${draft.key}-department`}>
                      Department
                    </label>
                    <select
                      id={`${draft.key}-department`}
                      value={draft.fields.department}
                      onChange={(e) => update(draft.key, "department", e.target.value)}
                      className={INPUT}
                    >
                      <option value="">—</option>
                      {DEPARTMENT_OPTIONS.map((d) => (
                        <option key={d.value} value={d.value}>
                          {d.label}
                        </option>
                      ))}
                    </select>
                  </div>
                  <Field
                    draft={draft}
                    k="current_company"
                    label="Current company"
                    onChange={update}
                  />
                  <Field
                    draft={draft}
                    k="experience_years"
                    label="Experience (years)"
                    type="number"
                    onChange={update}
                  />
                  <div className="grid grid-cols-2 gap-2">
                    <Field
                      draft={draft}
                      k="salary"
                      label="Current ₹/month *"
                      type="number"
                      onChange={update}
                    />
                    <Field
                      draft={draft}
                      k="expected_salary"
                      label="Expected ₹/month"
                      type="number"
                      onChange={update}
                    />
                  </div>
                </div>
              </li>
            ))}
          </ol>
          <datalist id="lead-cities">
            {CITIES.filter((c) => c !== "Other").map((c) => (
              <option key={c} value={c} />
            ))}
          </datalist>
        </div>

        <footer className="mt-4 flex items-center justify-end gap-3">
          <button
            type="button"
            onClick={onClose}
            disabled={busy}
            className="rounded-lg px-3 py-2 text-sm text-text-secondary hover:text-text-primary disabled:opacity-40"
          >
            {addedTotal > 0 && drafts.length === 0 ? "Done" : "Cancel"}
          </button>
          <button
            type="button"
            onClick={submit}
            disabled={busy || drafts.length === 0}
            className="inline-flex items-center gap-1.5 rounded-lg bg-yellow px-4 py-2 text-sm font-semibold text-navy disabled:opacity-50"
          >
            {submitting ? (
              <IconLoader2 className="size-4 animate-spin" />
            ) : (
              <IconSend className="size-4" />
            )}
            {drafts.length === 0
              ? "Add"
              : `Add ${drafts.length} lead${drafts.length === 1 ? "" : "s"}`}
          </button>
        </footer>
      </motion.div>
    </div>
  );
}

function Field({
  draft,
  k,
  label,
  type = "text",
  list,
  onChange,
}: Readonly<{
  draft: Draft;
  k: FieldKey;
  label: string;
  type?: string;
  list?: string;
  onChange: (key: string, field: FieldKey, value: string) => void;
}>) {
  const id = `${draft.key}-${k}`;
  const problem = draft.problems[k];
  return (
    <div>
      <label className={LABEL} htmlFor={id}>
        {label}
      </label>
      <input
        id={id}
        type={type}
        list={list}
        min={type === "number" ? 0 : undefined}
        value={draft.fields[k]}
        onChange={(e) => onChange(draft.key, k, e.target.value)}
        aria-invalid={!!problem}
        className={cn(INPUT, problem && "border-red-500/60")}
      />
      {problem && <span className="mt-0.5 block text-[11px] text-red-400">{problem}</span>}
    </div>
  );
}
