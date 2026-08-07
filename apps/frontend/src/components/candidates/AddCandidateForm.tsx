"use client";

import { useState } from "react";
import { z } from "zod";
import { clientConfirmResume, clientCreateCandidate } from "@/lib/api/candidates.client";
import { uploadResumeToCloudinary } from "@/lib/api/storage.client";
import type { ApiCandidate } from "@/types";
import {
  AgeField,
  AreaField,
  BrandExperienceField,
  CityField,
  CommunicationField,
  CurrentRoleField,
  CvLinkField,
  DepartmentField,
  ExpectedSalaryField,
  GenderField,
  NoticePeriodField,
  NotesField,
  PreviousRoleField,
  ResumeField,
  SourceChannelField,
  SourceField,
  SpecializationField,
  StructuredEducationField,
  TextField,
  inputStyle,
  resolveSourceChannel,
} from "./CandidateFormFields";

const schema = z.object({
  name: z.string().min(1, "Name is required"),
  email: z.string().email("Valid email required"),
  phone: z.string().optional(),
  source: z.enum(["internal", "external"]),
  source_channel: z.string().optional(),
  communication: z.string().optional(),
  education: z.string().optional(),
  brand_experience: z.string().optional(),
  department: z.string().optional(),
  specialization: z.string().optional(),
  cv_link: z.string().url("Must be a valid URL").optional().or(z.literal("")),
  current_role: z.string().optional(),
  previous_role: z.string().optional(),
  city: z.string().optional(),
  area: z.string().optional(),
  gender: z.enum(["male", "female", "other"]).optional(),
  age: z.preprocess(
    (v) => (v === "" || v === undefined ? undefined : Number(v)),
    z.number().positive("Must be a positive number").optional(),
  ),
  expected_salary: z.preprocess(
    (v) => (v === "" || v === undefined ? undefined : Number(v)),
    z.number().positive("Must be a positive number").optional(),
  ),
  notice_period: z.string().optional(),
  notes: z.string().optional(),
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
    previous_role: "",
    city: "",
    area: "",
    gender: "" as "male" | "female" | "other" | "",
    age: "",
    expected_salary: "",
    notice_period: "",
    notes: "",
  });
  const [resumeFile, setResumeFile] = useState<File | null>(null);
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [loading, setLoading] = useState(false);

  function handleDepartmentChange(dept: string) {
    setForm((f) => ({ ...f, department: dept, specialization: "" }));
  }

  function resolvedChannel(): string {
    return resolveSourceChannel(form.source, form.source_channel, form.source_channel_other);
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    const parsed = schema.safeParse({
      name: form.name,
      email: form.email,
      phone: form.phone || undefined,
      source: form.source,
      source_channel: resolvedChannel() || undefined,
      communication: form.communication || undefined,
      education: form.education || undefined,
      brand_experience: form.brand_experience || undefined,
      department: form.department || undefined,
      specialization: form.specialization || undefined,
      cv_link: form.cv_link || undefined,
      current_role: form.current_role || undefined,
      previous_role: form.previous_role || undefined,
      city: form.city || undefined,
      area: form.area || undefined,
      gender: form.gender || undefined,
      age: form.age || undefined,
      expected_salary: form.expected_salary || undefined,
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

    if (parsed.data.department && !parsed.data.specialization) {
      setErrors({ specialization: "Specialization is required when a department is selected" });
      return;
    }
    setLoading(true);
    setErrors({});
    try {
      let candidate = await clientCreateCandidate({
        full_name: parsed.data.name,
        email: parsed.data.email,
        phone: parsed.data.phone,
        communication: parsed.data.communication,
        education: parsed.data.education,
        brand_experience: parsed.data.brand_experience,
        department: parsed.data.department,
        specialization: parsed.data.specialization,
        cv_link: parsed.data.cv_link,
        current_role: parsed.data.current_role,
        previous_role: parsed.data.previous_role,
        city: parsed.data.city,
        area: parsed.data.area,
        gender: parsed.data.gender,
        age: parsed.data.age,
        expected_salary: parsed.data.expected_salary,
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

  // Two fields per row: the single column ran far past the fold and pushed the
  // submit button out of sight. Short fields pair up; the wide ones — source,
  // tags, notes — span both, as do the conditional fields, which would
  // otherwise shift every later field into the opposite column when they show.
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
        label="Phone"
        type="tel"
        value={form.phone}
        onChange={(phone) => setForm((f) => ({ ...f, phone }))}
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
      <PreviousRoleField
        value={form.previous_role}
        onChange={(previous_role) => setForm((f) => ({ ...f, previous_role }))}
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
      <NoticePeriodField
        value={form.notice_period}
        onChange={(notice_period) => setForm((f) => ({ ...f, notice_period }))}
      />

      <CommunicationField
        value={form.communication}
        onChange={(communication) => setForm((f) => ({ ...f, communication }))}
      />
      <StructuredEducationField
        value={form.education}
        onChange={(education) => setForm((f) => ({ ...f, education }))}
      />
      <BrandExperienceField
        value={form.brand_experience}
        onChange={(brand_experience) => setForm((f) => ({ ...f, brand_experience }))}
      />
      <DepartmentField value={form.department} onChange={handleDepartmentChange} />
      <SpecializationField
        department={form.department}
        value={form.specialization}
        onChange={(specialization) => setForm((f) => ({ ...f, specialization }))}
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
