"use client";

/**
 * Shared controls for the two candidate forms — Add Candidate, and the edit
 * mode inside CandidateDrawer.
 *
 * They collect the same profile, and every field used to exist twice: same
 * markup, same option lists, same tag handling. That is how the backend's two
 * copies of the candidate field list drifted apart and started dropping
 * previous_role and friends, so the fix is one copy of each control.
 *
 * Each field renders a single grid cell, leaving the layout (which pairs go on
 * a row, what spans full width) to the form that hosts it.
 */

import React from "react";
import {
  CITIES,
  EDUCATION_LEVELS,
  SOURCE_CHANNEL_OTHER,
  SOURCE_CHANNELS,
  COMMUNICATION_OPTIONS,
  STRUCTURED_EDUCATION_OPTIONS,
  BRAND_EXPERIENCE_OPTIONS,
  DEPARTMENT_OPTIONS,
  SPECIALIZATION_OPTIONS,
  GENDER_OPTIONS,
  CANDIDATE_SOURCES,
} from "@/lib/constants/candidate";

export const inputCls = "w-full rounded-lg px-3 py-2 text-sm outline-none";
export const inputStyle = {
  background: "var(--color-canvas-val)",
  color: "var(--color-text-primary)",
  border: "1px solid var(--color-border-val)",
};
export const labelStyle = { color: "var(--color-text-secondary)" };

/** Height of a text input, so a non-input control can sit level with one. */
const CONTROL_HEIGHT = "h-[38px]";

export type CandidateSource = "internal" | "external";

/** Existing records may hold values outside the canonical list (legacy imports).
 *  Keep the stored value selectable so opening and saving never erases it. */
export function withExisting(options: readonly string[], current: string): string[] {
  return current && !options.includes(current) ? [...options, current] : [...options];
}

/** Channels only classify external candidates; "Other" carries the typed value. */
export function resolveSourceChannel(source: string, channel: string, other: string): string {
  if (source !== "external") return "";
  return channel === SOURCE_CHANNEL_OTHER ? other.trim() : channel;
}

/* ── Building blocks ───────────────────────────────────────────────────────── */

function FieldError({ message }: Readonly<{ message?: string }>) {
  if (!message) return null;
  return (
    <p className="mt-0.5 text-xs" style={{ color: "#FF5A5F" }}>
      {message}
    </p>
  );
}

/** Label + control + optional error, as one grid cell. */
export function Field({
  label,
  error,
  className,
  labelSuffix,
  children,
}: Readonly<{
  label: string;
  error?: string;
  className?: string;
  /** Rendered beside the label — e.g. the "recruiter" badge on tags. */
  labelSuffix?: React.ReactNode;
  children: React.ReactNode;
}>) {
  return (
    <div className={className}>
      {labelSuffix ? (
        <div className="mb-1 flex items-center gap-2">
          <label className="block text-xs font-medium" style={labelStyle}>
            {label}
          </label>
          {labelSuffix}
        </div>
      ) : (
        <label className="mb-1 block text-xs font-medium" style={labelStyle}>
          {label}
        </label>
      )}
      {children}
      <FieldError message={error} />
    </div>
  );
}

/** Text-like input carrying the shared styling. */
export function TextField({
  label,
  value,
  onChange,
  error,
  className,
  ...input
}: Readonly<
  {
    label: string;
    value: string;
    onChange: (value: string) => void;
    error?: string;
    className?: string;
  } & Omit<React.InputHTMLAttributes<HTMLInputElement>, "value" | "onChange" | "className">
>) {
  return (
    <Field label={label} error={error} className={className}>
      <input
        {...input}
        className={inputCls}
        style={inputStyle}
        value={value}
        onChange={(e) => onChange(e.target.value)}
      />
    </Field>
  );
}

/** Select over a fixed option list, keeping any legacy stored value selectable. */
export function SelectField({
  label,
  value,
  onChange,
  options,
  error,
  className,
  placeholder = "Select...",
}: Readonly<{
  label: string;
  value: string;
  onChange: (value: string) => void;
  /** Plain strings, or {value,label} when the two differ. */
  options: readonly (string | { value: string; label: string })[];
  error?: string;
  className?: string;
  placeholder?: string;
}>) {
  const items = options.map((o) => (typeof o === "string" ? { value: o, label: o } : o));
  const known = items.map((i) => i.value);
  return (
    <Field label={label} error={error} className={className}>
      <select
        className={inputCls}
        style={inputStyle}
        value={value}
        onChange={(e) => onChange(e.target.value)}
      >
        <option value="">{placeholder}</option>
        {withExisting(known, value).map((v) => (
          <option key={v} value={v}>
            {items.find((i) => i.value === v)?.label ?? v}
          </option>
        ))}
      </select>
    </Field>
  );
}

/* ── Candidate-specific fields ─────────────────────────────────────────────── */

/** internal | external. Drives resume-upload and CV-link behaviour downstream. */
export function SourceField({
  value,
  onChange,
  required,
  className,
}: Readonly<{
  value: string;
  onChange: (value: CandidateSource) => void;
  required?: boolean;
  className?: string;
}>) {
  return (
    <Field label={`Source${required ? " *" : ""}`} className={className}>
      <div className={`grid grid-cols-2 gap-3 ${CONTROL_HEIGHT}`}>
        {CANDIDATE_SOURCES.map((s) => {
          const isSelected = value === s;
          return (
            <label
              key={s}
              className={`flex h-full cursor-pointer items-center justify-center rounded-lg border text-sm font-medium transition-all ${
                isSelected
                  ? "border-yellow ring-1 ring-yellow"
                  : "border-border hover:border-yellow/50"
              }`}
              style={{
                background: isSelected ? "var(--color-surface-2-val)" : "var(--color-canvas-val)",
                color: isSelected
                  ? "var(--color-text-primary-val)"
                  : "var(--color-text-secondary-val)",
              }}
            >
              <input
                type="radio"
                name="source"
                value={s}
                checked={isSelected}
                onChange={() => onChange(s as CandidateSource)}
                className="sr-only"
              />
              {s === "internal" ? "Internal" : "External"}
            </label>
          );
        })}
      </div>
    </Field>
  );
}

/** Where an external candidate came from; "Other" reveals a free-text box. */
export function SourceChannelField({
  channel,
  other,
  onChannel,
  onOther,
  className,
}: Readonly<{
  channel: string;
  other: string;
  onChannel: (value: string) => void;
  onOther: (value: string) => void;
  className?: string;
}>) {
  return (
    <div className={className}>
      <SelectField
        label="Source Channel"
        value={channel}
        onChange={onChannel}
        options={SOURCE_CHANNELS}
      />
      {channel === SOURCE_CHANNEL_OTHER && (
        <input
          className={`${inputCls} mt-2`}
          style={inputStyle}
          placeholder="Where did they come from?"
          value={other}
          onChange={(e) => onOther(e.target.value)}
        />
      )}
    </div>
  );
}

export function CityField(props: Readonly<{ value: string; onChange: (v: string) => void }>) {
  return <SelectField label="City" options={CITIES} {...props} />;
}

export function AreaField(props: Readonly<{ value: string; onChange: (v: string) => void }>) {
  return <TextField label="Area" placeholder="e.g. Andheri" {...props} />;
}

export function GenderField(props: Readonly<{ value: string; onChange: (v: string) => void }>) {
  return <SelectField label="Gender" options={GENDER_OPTIONS} {...props} />;
}

export function AgeField(
  props: Readonly<{ value: string; onChange: (v: string) => void; error?: string }>,
) {
  return <TextField label="Age" type="number" min="0" placeholder="e.g. 25" {...props} />;
}

export function EducationField(props: Readonly<{ value: string; onChange: (v: string) => void }>) {
  return <SelectField label="Highest Education" options={EDUCATION_LEVELS} {...props} />;
}

export function ExpectedSalaryField(
  props: Readonly<{ value: string; onChange: (v: string) => void; error?: string }>,
) {
  return (
    <TextField label="Expected Salary" type="number" min="0" placeholder="e.g. 85000" {...props} />
  );
}

export function CurrentSalaryField(
  props: Readonly<{ value: string; onChange: (v: string) => void; error?: string }>,
) {
  return (
    <TextField label="Current Salary" type="number" min="0" placeholder="e.g. 60000" {...props} />
  );
}

export function ExperienceYearsField(
  props: Readonly<{ value: string; onChange: (v: string) => void; error?: string }>,
) {
  return (
    <TextField
      label="Experience (years)"
      type="number"
      min="0"
      step="0.5"
      placeholder="e.g. 3"
      {...props}
    />
  );
}

export function NoticePeriodField(
  props: Readonly<{ value: string; onChange: (v: string) => void }>,
) {
  return <TextField label="Notice Period" placeholder="e.g. 30 days" {...props} />;
}

export function CurrentRoleField(
  props: Readonly<{ value: string; onChange: (v: string) => void }>,
) {
  return <TextField label="Current Role" placeholder="e.g. Senior Engineer" {...props} />;
}

export function CvLinkField({
  value,
  onChange,
  required,
  error,
  className,
}: Readonly<{
  value: string;
  onChange: (v: string) => void;
  required?: boolean;
  error?: string;
  className?: string;
}>) {
  return (
    <TextField
      label={`CV Link${required ? " *" : ""}`}
      type="url"
      placeholder="https://…"
      value={value}
      onChange={onChange}
      error={error}
      className={className}
    />
  );
}

/** Resume picker. `children` slots in a link to whatever is already on file. */
export function ResumeField({
  file,
  onFile,
  className,
  children,
}: Readonly<{
  file: File | null;
  onFile: (file: File | null) => void;
  className?: string;
  children?: React.ReactNode;
}>) {
  return (
    <Field label="Resume" className={className}>
      {children}
      <input
        type="file"
        accept=".pdf,.docx,.doc,application/pdf,application/vnd.openxmlformats-officedocument.wordprocessingml.document,application/msword"
        className="block w-full text-sm"
        style={{ color: "var(--color-text-secondary)" }}
        onChange={(e) => onFile(e.target.files?.[0] ?? null)}
      />
      {file && (
        <p className="mt-1 text-xs" style={{ color: "var(--color-text-secondary)" }}>
          {file.name}
        </p>
      )}
    </Field>
  );
}

export function NotesField({
  value,
  onChange,
  rows = 3,
  className,
}: Readonly<{
  value: string;
  onChange: (v: string) => void;
  rows?: number;
  className?: string;
}>) {
  return (
    <Field label="Notes" className={className}>
      <textarea
        rows={rows}
        className={inputCls}
        style={{ ...inputStyle, resize: "vertical" }}
        placeholder="Any notes about this candidate…"
        value={value}
        onChange={(e) => onChange(e.target.value)}
      />
    </Field>
  );
}

/** Free-text recruiter tags: type-to-add (Enter or comma), click × to remove. */
export function TagsField({
  tags,
  input,
  onInput,
  onAdd,
  onRemove,
  className,
}: Readonly<{
  tags: string[];
  input: string;
  onInput: (value: string) => void;
  onAdd: () => void;
  onRemove: (tag: string) => void;
  className?: string;
}>) {
  return (
    <Field
      label="Manual Tags"
      className={className}
      labelSuffix={
        <span
          className="rounded px-1.5 py-0.5 text-[9px] font-semibold uppercase tracking-wide"
          style={{ background: "rgba(251,146,60,0.15)", color: "#fb923c" }}
        >
          recruiter
        </span>
      }
    >
      <div className="flex gap-2">
        <input
          className={inputCls}
          style={inputStyle}
          placeholder="e.g. senior, python"
          value={input}
          onChange={(e) => onInput(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter" || e.key === ",") {
              e.preventDefault();
              onAdd();
            }
          }}
        />
        <button
          type="button"
          onClick={onAdd}
          className="shrink-0 rounded-lg px-3 py-1.5 text-sm font-medium"
          style={inputStyle}
        >
          Add
        </button>
      </div>
      {tags.length > 0 && (
        <div className="mt-2 flex flex-wrap gap-1">
          {tags.map((tag) => (
            <TagChip key={tag} tag={tag} onRemove={() => onRemove(tag)} />
          ))}
        </div>
      )}
    </Field>
  );
}

const TAG_CHIP_STYLE = {
  background: "rgba(96,165,250,0.1)",
  color: "#60a5fa",
  border: "1px solid rgba(96,165,250,0.25)",
};

/** One tag. Read-only without `onRemove` — that is the drawer's view mode. */
export function TagChip({ tag, onRemove }: Readonly<{ tag: string; onRemove?: () => void }>) {
  return (
    <span
      className="inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-xs"
      style={TAG_CHIP_STYLE}
    >
      {tag}
      {onRemove && (
        <button type="button" onClick={onRemove} className="opacity-60 hover:opacity-100">
          ×
        </button>
      )}
    </span>
  );
}

export function CommunicationField(
  props: Readonly<{ value: string; onChange: (v: string) => void }>,
) {
  return <SelectField label="Communication" options={COMMUNICATION_OPTIONS} {...props} />;
}

export function StructuredEducationField(
  props: Readonly<{ value: string; onChange: (v: string) => void }>,
) {
  return <SelectField label="Education" options={STRUCTURED_EDUCATION_OPTIONS} {...props} />;
}

export function BrandExperienceField(
  props: Readonly<{ value: string; onChange: (v: string) => void }>,
) {
  return <SelectField label="Brand Experience" options={BRAND_EXPERIENCE_OPTIONS} {...props} />;
}

export function DepartmentField(props: Readonly<{ value: string; onChange: (v: string) => void }>) {
  return <SelectField label="Department" options={DEPARTMENT_OPTIONS} {...props} />;
}

export function SpecializationField({
  department,
  value,
  onChange,
  className,
}: Readonly<{
  department: string;
  value: string;
  onChange: (v: string) => void;
  className?: string;
}>) {
  if (!department) return null;
  const options = SPECIALIZATION_OPTIONS[department] || [];
  return (
    <SelectField
      label="Specialization *"
      options={options}
      value={value}
      onChange={onChange}
      className={className}
    />
  );
}

export function StructuredCandidateTags({
  form,
  onChange,
}: Readonly<{
  form: {
    communication?: string;
    education?: string;
    brand_experience?: string;
    department?: string;
    specialization?: string;
  };
  onChange: (updates: Partial<typeof form>) => void;
}>) {
  return (
    <>
      <CommunicationField
        value={form.communication || ""}
        onChange={(v) => onChange({ communication: v })}
      />
      <StructuredEducationField
        value={form.education || ""}
        onChange={(v) => onChange({ education: v })}
      />
      <BrandExperienceField
        value={form.brand_experience || ""}
        onChange={(v) => onChange({ brand_experience: v })}
      />
      <DepartmentField
        value={form.department || ""}
        onChange={(dept) => onChange({ department: dept, specialization: "" })}
      />
      <SpecializationField
        department={form.department || ""}
        value={form.specialization || ""}
        onChange={(v) => onChange({ specialization: v })}
      />
    </>
  );
}
