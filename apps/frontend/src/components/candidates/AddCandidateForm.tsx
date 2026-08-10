"use client";

import { useState } from "react";
import { z } from "zod";
import { clientConfirmResume, clientCreateCandidate } from "@/lib/api/candidates.client";
import { uploadResumeToCloudinary } from "@/lib/api/storage.client";
import type { ApiCandidate } from "@/types";
import {
  AgeField,
  AreaField,
  CityField,
  CurrentRoleField,
  CurrentSalaryField,
  CvLinkField,
  ExpectedSalaryField,
  ExperienceYearsField,
  GenderField,
  NoticePeriodField,
  NotesField,
  ResumeField,
  SourceChannelField,
  SourceField,
  StructuredCandidateTags,
  TextField,
  inputStyle,
  resolveSourceChannel,
} from "./CandidateFormFields";

const schema = z
  .object({
    name: z.string().min(1, "Name is required"),
    email: z.string().email("Valid email required").min(1, "Email is required"),
    phone: z.string().min(1, "Phone is required"),
    source: z.enum(["internal", "external"]),
    source_channel: z.string().optional(),
    communication: z.string().min(1, "Communication is required"),
    education: z.string().min(1, "Education is required"),
    brand_experience: z.string().min(1, "Brand Experience is required"),
    department: z.string().min(1, "Department is required"),
    specialization: z.string().optional(),
    cv_link: z.string().optional(),
    current_role: z.string().min(1, "Current Role is required"),
    experience_years: z.preprocess(
      (v) => (v === "" || v === undefined ? undefined : Number(v)),
      z.number({ message: "Experience Years is required" }).min(0, "Must be 0 or more"),
    ),
    city: z.string().min(1, "City is required"),
    area: z.string().min(1, "Area is required"),
    gender: z.enum(["male", "female", "other"], { message: "Gender is required" }),
    age: z.preprocess(
      (v) => (v === "" || v === undefined ? undefined : Number(v)),
      z.number({ message: "Age is required" }).positive("Must be a positive number"),
    ),
    expected_salary: z.preprocess(
      (v) => (v === "" || v === undefined ? undefined : Number(v)),
      z.number({ message: "Expected Salary is required" }).positive("Must be a positive number"),
    ),
    salary: z.preprocess(
      (v) => (v === "" || v === undefined ? undefined : Number(v)),
      z.number({ message: "Current Salary is required" }).positive("Must be a positive number"),
    ),
    notice_period: z.string().min(1, "Notice Period is required"),
    notes: z.string().optional(),
  })
  .superRefine((data, ctx) => {
    if (data.department && !data.specialization) {
      ctx.addIssue({
        code: z.ZodIssueCode.custom,
        path: ["specialization"],
        message: "Specialization is required when a department is selected",
      });
    }
    if (data.source === "external" && !data.source_channel) {
      ctx.addIssue({
        code: z.ZodIssueCode.custom,
        path: ["source_channel"],
        message: "Source Channel is required for external source",
      });
    }
    if (data.source === "external" && (!data.cv_link || data.cv_link.trim() === "")) {
      ctx.addIssue({
        code: z.ZodIssueCode.custom,
        path: ["cv_link"],
        message: "CV Link is required for external source",
      });
    } else if (data.source === "external" && data.cv_link) {
      const isUrl = z.string().url().safeParse(data.cv_link);
      if (!isUrl.success) {
        ctx.addIssue({
          code: z.ZodIssueCode.custom,
          path: ["cv_link"],
          message: "Must be a valid URL",
        });
      }
    }
  });

interface Props {
  onSuccess: (candidate: ApiCandidate) => void;
  onCancel: () => void;
}

export default function AddCandidateForm({ onSuccess, onCancel }: Props) {
  const [form, setForm] = useState({
    name: "",
    email: "",
    phone: "",
    source: "internal" as "internal" | "external",
    source_channel: "",
    source_channel_other: "",
    communication: "",
    education: "",
    brand_experience: "",
    department: "",
    specialization: "",
    cv_link: "",
    current_role: "",
    experience_years: "",
    city: "",
    area: "",
    gender: "" as "male" | "female" | "other" | "",
    age: "",
    expected_salary: "",
    salary: "",
    notice_period: "",
    notes: "",
  });
  const [resumeFile, setResumeFile] = useState<File | null>(null);
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [loading, setLoading] = useState(false);

  function resolvedChannel(): string {
    return resolveSourceChannel(form.source, form.source_channel, form.source_channel_other);
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    const parsed = schema.safeParse({
      name: form.name,
      email: form.email || undefined,
      phone: form.phone,
      source: form.source,
      source_channel: resolvedChannel() || undefined,
      communication: form.communication || undefined,
      education: form.education || undefined,
      brand_experience: form.brand_experience || undefined,
      department: form.department || undefined,
      specialization: form.specialization || undefined,
      cv_link: form.cv_link || undefined,
      current_role: form.current_role || undefined,
      experience_years: form.experience_years || undefined,
      city: form.city || undefined,
      area: form.area || undefined,
      gender: form.gender || undefined,
      age: form.age || undefined,
      expected_salary: form.expected_salary || undefined,
      salary: form.salary || undefined,
      notice_period: form.notice_period || undefined,
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

    if (parsed.data.source === "internal" && !resumeFile) {
      setErrors({ _root: "Please select a CV file to upload" });
      return;
    }
    setLoading(true);
    setErrors({});
    try {
      let candidate = await clientCreateCandidate({
        full_name: parsed.data.name,
        email: parsed.data.email || undefined,
        phone: parsed.data.phone,
        communication: parsed.data.communication,
        education: parsed.data.education,
        brand_experience: parsed.data.brand_experience,
        department: parsed.data.department,
        specialization: parsed.data.specialization,
        cv_link: parsed.data.cv_link,
        current_role: parsed.data.current_role,
        experience_years: parsed.data.experience_years,
        city: parsed.data.city,
        area: parsed.data.area,
        gender: parsed.data.gender,
        age: parsed.data.age,
        expected_salary: parsed.data.expected_salary,
        salary: parsed.data.salary,
        notice_period: parsed.data.notice_period,
        source: parsed.data.source,
        source_channel: parsed.data.source_channel,
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

  const full = "sm:col-span-2";

  return (
    <form onSubmit={handleSubmit} className="grid grid-cols-1 gap-x-4 gap-y-3.5 p-4 sm:grid-cols-2">
      <h2
        className={`text-lg font-semibold ${full}`}
        style={{ color: "var(--color-text-primary)" }}
      >
        Add Candidate
      </h2>

      {errors._root && (
        <p
          className={`rounded-lg px-3 py-2 text-sm ${full}`}
          style={{ background: "rgba(255,90,95,0.12)", color: "#FF5A5F" }}
        >
          {errors._root}
        </p>
      )}

      <TextField
        label="Name *"
        value={form.name}
        onChange={(name) => setForm((f) => ({ ...f, name }))}
        error={errors.name}
      />
      <TextField
        label="Email *"
        type="email"
        value={form.email}
        onChange={(email) => setForm((f) => ({ ...f, email }))}
        error={errors.email}
      />
      <TextField
        label="Phone *"
        type="tel"
        value={form.phone}
        onChange={(phone) => setForm((f) => ({ ...f, phone }))}
        error={errors.phone}
      />
      <SourceField
        required
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

      <CurrentRoleField
        value={form.current_role}
        onChange={(current_role) => setForm((f) => ({ ...f, current_role }))}
      />
      <ExperienceYearsField
        value={form.experience_years}
        onChange={(experience_years) => setForm((f) => ({ ...f, experience_years }))}
        error={errors.experience_years}
      />
      <CityField value={form.city} onChange={(city) => setForm((f) => ({ ...f, city }))} />
      <AreaField value={form.area} onChange={(area) => setForm((f) => ({ ...f, area }))} />
      <GenderField
        value={form.gender}
        onChange={(v) => setForm((f) => ({ ...f, gender: v as typeof f.gender }))}
      />
      <AgeField
        value={form.age}
        onChange={(age) => setForm((f) => ({ ...f, age }))}
        error={errors.age}
      />
      <ExpectedSalaryField
        value={form.expected_salary}
        onChange={(expected_salary) => setForm((f) => ({ ...f, expected_salary }))}
        error={errors.expected_salary}
      />
      <CurrentSalaryField
        value={form.salary}
        onChange={(salary) => setForm((f) => ({ ...f, salary }))}
        error={errors.salary}
      />
      <NoticePeriodField
        value={form.notice_period}
        onChange={(notice_period) => setForm((f) => ({ ...f, notice_period }))}
      />

      <StructuredCandidateTags
        form={form}
        onChange={(updates) => setForm((f) => ({ ...f, ...updates }))}
      />

      {form.source === "internal" && <ResumeField file={resumeFile} onFile={setResumeFile} />}
      <CvLinkField
        required={form.source === "external"}
        value={form.cv_link}
        onChange={(cv_link) => setForm((f) => ({ ...f, cv_link }))}
        error={errors.cv_link}
      />

      <NotesField
        className={full}
        value={form.notes}
        onChange={(notes) => setForm((f) => ({ ...f, notes }))}
      />

      <div className={`flex gap-3 pt-2 ${full}`}>
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
