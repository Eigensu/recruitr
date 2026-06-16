"use client";

import { useState } from "react";
import { z } from "zod";
import { clientConfirmResume, clientCreateCandidate } from "@/lib/api/candidates.client";
import { uploadResumeToCloudinary } from "@/lib/api/storage.client";
import type { ApiCandidate } from "@/types";

const schema = z.object({
  name: z.string().min(1, "Name is required"),
  email: z.string().email("Valid email required"),
  phone: z.string().optional(),
  source: z.enum(["internal", "external"]),
  tags: z.array(z.string()),
  cv_link: z.string().url("Must be a valid URL").optional().or(z.literal("")),
  current_role: z.string().optional(),
  salary: z.preprocess(
    (v) => (v === "" || v === undefined ? undefined : Number(v)),
    z.number().positive("Must be a positive number").optional(),
  ),
  notes: z.string().optional(),
});

interface Props {
  onSuccess: (candidate: ApiCandidate) => void;
  onCancel: () => void;
}

const inputCls = "w-full rounded-lg px-3 py-2 text-sm outline-none";
const inputStyle = {
  background: "var(--color-canvas-val)",
  color: "var(--color-text-primary)",
  border: "1px solid var(--color-border-val)",
};
const labelStyle = { color: "var(--color-text-secondary)" };

export default function AddCandidateForm({ onSuccess, onCancel }: Props) {
  const [form, setForm] = useState({
    name: "",
    email: "",
    phone: "",
    source: "internal" as "internal" | "external",
    tagInput: "",
    tags: [] as string[],
    cv_link: "",
    current_role: "",
    salary: "",
    notes: "",
  });
  const [resumeFile, setResumeFile] = useState<File | null>(null);
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [loading, setLoading] = useState(false);

  function addTag() {
    const raw = form.tagInput.trim().toLowerCase();
    if (!raw || form.tags.includes(raw)) return;
    setForm((f) => ({ ...f, tags: [...f.tags, raw], tagInput: "" }));
  }

  function removeTag(tag: string) {
    setForm((f) => ({ ...f, tags: f.tags.filter((t) => t !== tag) }));
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    const parsed = schema.safeParse({
      name: form.name,
      email: form.email,
      phone: form.phone || undefined,
      source: form.source,
      tags: form.tags,
      cv_link: form.cv_link || undefined,
      current_role: form.current_role || undefined,
      salary: form.salary || undefined,
      notes: form.notes || undefined,
    });

    if (!parsed.success) {
      const fieldErrors: Record<string, string> = {};
      parsed.error.issues.forEach((err) => {
        if (err.path[0]) fieldErrors[err.path[0] as string] = err.message;
      });
      setErrors(fieldErrors);
      return;
    }

    setLoading(true);
    setErrors({});
    try {
      let candidate = await clientCreateCandidate({
        full_name: parsed.data.name,
        email: parsed.data.email,
        phone: parsed.data.phone,
        recruiter_tags: parsed.data.tags,
        cv_link: parsed.data.cv_link,
        current_role: parsed.data.current_role,
        salary: parsed.data.salary,
        notes: parsed.data.notes,
      });

      if (parsed.data.source === "internal" && resumeFile) {
        const uploaded = await uploadResumeToCloudinary(resumeFile);
        candidate = await clientConfirmResume(candidate.id, uploaded);
      }

      onSuccess(candidate);
    } catch (err: unknown) {
      setErrors({ _root: err instanceof Error ? err.message : "Failed to create candidate" });
    } finally {
      setLoading(false);
    }
  }

  return (
    <form onSubmit={handleSubmit} className="flex flex-col gap-4 p-4">
      <h2 className="text-lg font-semibold" style={{ color: "var(--color-text-primary)" }}>
        Add Candidate
      </h2>

      {errors._root && (
        <p
          className="rounded-lg px-3 py-2 text-sm"
          style={{ background: "rgba(255,90,95,0.12)", color: "#FF5A5F" }}
        >
          {errors._root}
        </p>
      )}

      <div>
        <label className="mb-1 block text-xs font-medium" style={labelStyle}>
          Name *
        </label>
        <input
          className={inputCls}
          style={inputStyle}
          value={form.name}
          onChange={(e) => setForm((f) => ({ ...f, name: e.target.value }))}
        />
        {errors.name && (
          <p className="mt-0.5 text-xs" style={{ color: "#FF5A5F" }}>
            {errors.name}
          </p>
        )}
      </div>

      <div>
        <label className="mb-1 block text-xs font-medium" style={labelStyle}>
          Email *
        </label>
        <input
          type="email"
          className={inputCls}
          style={inputStyle}
          value={form.email}
          onChange={(e) => setForm((f) => ({ ...f, email: e.target.value }))}
        />
        {errors.email && (
          <p className="mt-0.5 text-xs" style={{ color: "#FF5A5F" }}>
            {errors.email}
          </p>
        )}
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
          Source *
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
        {errors.salary && (
          <p className="mt-0.5 text-xs" style={{ color: "#FF5A5F" }}>
            {errors.salary}
          </p>
        )}
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
        {form.tags.length > 0 && (
          <div className="mt-2 flex flex-wrap gap-1">
            {form.tags.map((tag) => (
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
      </div>

      {form.source === "internal" && (
        <div>
          <label className="mb-1 block text-xs font-medium" style={labelStyle}>
            Resume PDF
          </label>
          <input
            type="file"
            accept=".pdf,application/pdf"
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
      )}

      <div>
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
        {errors.cv_link && (
          <p className="mt-0.5 text-xs" style={{ color: "#FF5A5F" }}>
            {errors.cv_link}
          </p>
        )}
      </div>

      <div>
        <label className="mb-1 block text-xs font-medium" style={labelStyle}>
          Notes
        </label>
        <textarea
          rows={3}
          className={inputCls}
          style={{ ...inputStyle, resize: "vertical" }}
          placeholder="Any notes about this candidate…"
          value={form.notes}
          onChange={(e) => setForm((f) => ({ ...f, notes: e.target.value }))}
        />
      </div>

      <div className="flex gap-3 pt-2">
        <button
          type="submit"
          disabled={loading}
          className="flex-1 rounded-lg py-2 text-sm font-semibold disabled:opacity-50"
          style={{ background: "var(--color-yellow)", color: "#002348" }}
        >
          {loading ? "Saving…" : "Add Candidate"}
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
