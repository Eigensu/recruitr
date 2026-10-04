"use client";

import { useEffect, useState } from "react";
import { motion } from "motion/react";
import { z } from "zod";
import { IconLoader2, IconX } from "@tabler/icons-react";
import { apiErrorMessage, useApiFetch } from "@/lib/api";
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
  StructuredCandidateTags,
  TextField,
  resolveCurrentRole,
} from "@/components/candidates/CandidateFormFields";
import {
  fetchIntakeRoleCatalog,
  fetchLeadCandidate,
  type IntakeCandidateDetails,
  type IntakeLead,
} from "@/lib/api/intake";

/**
 * The details a telecaller collects on the call, filled in before accepting.
 *
 * The same required fields as adding a candidate by hand, minus brand
 * experience — the recruiter's to fill, since they are the one placing the
 * person with a brand — and with the CV link optional, because a lead from an
 * ad usually has no CV to link. The backend enforces the same rules
 * (`IntakeCandidateDetails`); this copy exists so a missing field is caught
 * before the round trip, on a handset, next to the field itself.
 */
// Number("  ") is 0, so a whitespace-only field would pass as a real zero.
const blankToUndefined = (v: unknown) => {
  const s = typeof v === "string" ? v.trim() : v;
  return s === "" || s === undefined ? undefined : Number(s);
};

const numberFrom = (message: string) =>
  z.preprocess(blankToUndefined, z.number({ message }).min(0, "Must be 0 or more"));

const schema = z.object({
  full_name: z.string().min(1, "Name is required"),
  email: z.union([z.literal(""), z.string().email("Valid email required")]).optional(),
  phone: z.string().min(1, "Phone is required"),
  communication: z.string().min(1, "Communication is required"),
  education: z.string().min(1, "Education is required"),
  department: z.string().min(1, "Department is required"),
  specialization: z.string().min(1, "Specialization is required"),
  establishment_tag: z.string().optional(),
  current_role: z.string().min(1, "Current Role is required"),
  experience_years: numberFrom("Experience Years is required"),
  city: z.string().min(1, "City is required"),
  area: z.string().optional(),
  gender: z.enum(["male", "female", "other"], { message: "Gender is required" }),
  age: z.preprocess(
    blankToUndefined,
    z.number().int("Age must be a whole number").min(1, "Must be 1 or more").optional(),
  ),
  expected_salary: numberFrom("Expected Salary is required"),
  salary: numberFrom("Current Salary is required"),
  notice_period: z.string().min(1, "Notice Period is required"),
  cv_link: z
    .union([z.literal(""), z.string().regex(/^https?:\/\//i, "Must be an http(s) link")])
    .optional(),
});

type FormState = {
  full_name: string;
  email: string;
  phone: string;
  communication: string;
  education: string;
  department: string;
  specialization: string;
  establishment_tag: string;
  current_role: string;
  current_role_other: string;
  experience_years: string;
  city: string;
  area: string;
  gender: string;
  age: string;
  expected_salary: string;
  salary: string;
  notice_period: string;
  cv_link: string;
  notes: string;
};

const str = (v: string | number | null | undefined): string =>
  v === null || v === undefined ? "" : String(v);

/** Only what the form must not contain drops out of an optional field. */
const orUndefined = (v: string | undefined) => (v ? v : undefined);

export default function AcceptLeadDialog({
  lead,
  initialNotes = "",
  onClose,
  onSubmit,
}: {
  readonly lead: IntakeLead;
  /** Anything already typed into the card's note box. */
  readonly initialNotes?: string;
  readonly onClose: () => void;
  /** Resolves when the accept went through; rejects to keep the form open. */
  readonly onSubmit: (details: IntakeCandidateDetails, notes: string) => Promise<void>;
}) {
  const apiFetch = useApiFetch();
  const [form, setForm] = useState<FormState | null>(null);
  const [roleCatalog, setRoleCatalog] = useState<Record<string, string[]>>({});
  const [catalogFailed, setCatalogFailed] = useState(false);
  const [hasResume, setHasResume] = useState(false);
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);

  useEffect(() => {
    let cancelled = false;
    Promise.all([
      fetchLeadCandidate(apiFetch, lead.id),
      fetchIntakeRoleCatalog(apiFetch).catch(() => null),
    ])
      .then(([draft, catalog]) => {
        if (cancelled) return;
        setRoleCatalog(catalog ?? {});
        setCatalogFailed(catalog === null);
        setHasResume(draft.has_resume);
        setForm({
          full_name: str(draft.full_name),
          email: str(draft.email),
          phone: str(draft.phone),
          communication: str(draft.communication),
          education: str(draft.education),
          department: str(draft.department),
          specialization: str(draft.specialization),
          establishment_tag: str(draft.establishment_tag),
          current_role: str(draft.current_role),
          current_role_other: "",
          // Zero is what the model defaults to, not something anyone said —
          // leave it blank so the telecaller has to ask.
          experience_years: draft.experience_years ? String(draft.experience_years) : "",
          city: str(draft.city),
          area: str(draft.area),
          gender: str(draft.gender),
          age: str(draft.age),
          expected_salary: str(draft.expected_salary),
          salary: str(draft.salary),
          notice_period: str(draft.notice_period),
          cv_link: str(draft.cv_link),
          notes: initialNotes,
        });
      })
      .catch((err: unknown) => {
        if (!cancelled) setErrors({ _root: apiErrorMessage(err, "Could not load their details.") });
      });
    return () => {
      cancelled = true;
    };
    // initialNotes seeds the form once; it is not something to refetch on.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [apiFetch, lead.id]);

  function update(changes: Partial<FormState>) {
    setForm((f) => (f ? { ...f, ...changes } : f));
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!form) return;
    const parsed = schema.safeParse({
      ...form,
      current_role: resolveCurrentRole(form.current_role, form.current_role_other),
    });
    if (!parsed.success) {
      const fieldErrors: Record<string, string> = {
        _root: "Some details are missing — see the highlighted fields.",
      };
      for (const issue of parsed.error.issues) {
        if (issue.path[0]) fieldErrors[issue.path[0] as string] = issue.message;
      }
      setErrors(fieldErrors);
      return;
    }

    const data = parsed.data;
    setSaving(true);
    setErrors({});
    try {
      await onSubmit(
        {
          ...data,
          email: orUndefined(data.email),
          establishment_tag: orUndefined(data.establishment_tag),
          area: orUndefined(data.area),
          cv_link: orUndefined(data.cv_link),
        },
        form.notes,
      );
    } catch (err) {
      setErrors({ _root: apiErrorMessage(err, "That did not go through.") });
      setSaving(false);
    }
  }

  const full = "sm:col-span-2";

  return (
    <div className="fixed inset-0 z-50 flex items-end justify-center bg-black/60 sm:items-center sm:p-4">
      <button
        type="button"
        aria-label="Close"
        tabIndex={-1}
        onClick={onClose}
        className="absolute inset-0 cursor-default"
      />
      <motion.div
        initial={{ opacity: 0, y: 12 }}
        animate={{ opacity: 1, y: 0 }}
        role="dialog"
        aria-modal="true"
        aria-label={`Accept ${lead.full_name}`}
        className="relative flex max-h-[92vh] w-full max-w-2xl flex-col rounded-t-xl border border-border bg-surface shadow-2xl sm:rounded-xl"
      >
        <header className="flex items-start justify-between gap-3 border-b border-border p-4">
          <div>
            <h2 className="font-heading text-lg font-bold text-text-primary">
              Accept {lead.full_name}
            </h2>
            <p className="mt-0.5 text-sm text-text-secondary">
              Fill in what you learned on the call. An admin then assigns them to a team.
            </p>
          </div>
          <button
            type="button"
            onClick={onClose}
            aria-label="Close"
            className="rounded-lg p-1 text-text-muted hover:text-text-primary"
          >
            <IconX className="size-4" />
          </button>
        </header>

        {form === null ? (
          <div className="flex h-48 items-center justify-center">
            {errors._root ? (
              <p className="px-4 text-center text-sm text-red-400">{errors._root}</p>
            ) : (
              <IconLoader2 className="size-5 animate-spin text-text-muted" />
            )}
          </div>
        ) : (
          <form onSubmit={handleSubmit} className="flex min-h-0 flex-1 flex-col" noValidate>
            <div className="grid min-h-0 flex-1 grid-cols-1 gap-x-4 gap-y-3.5 overflow-y-auto p-4 sm:grid-cols-2">
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
                value={form.full_name}
                onChange={(full_name) => update({ full_name })}
                error={errors.full_name}
              />
              <TextField
                label="Phone *"
                type="tel"
                value={form.phone}
                onChange={(phone) => update({ phone })}
                error={errors.phone}
              />
              <TextField
                label="Email"
                type="email"
                value={form.email}
                onChange={(email) => update({ email })}
                error={errors.email}
              />
              <GenderField
                value={form.gender}
                onChange={(gender) => update({ gender })}
                error={errors.gender}
              />

              <StructuredCandidateTags
                hideBrandExperience
                form={form}
                errors={errors}
                onChange={(updates) =>
                  update({
                    ...updates,
                    // Role options are scoped to department, so a role picked
                    // under the old department can be invalid for the new one.
                    ...(updates.department !== undefined && updates.department !== form.department
                      ? { current_role: "", current_role_other: "" }
                      : {}),
                  })
                }
              />

              <CurrentRoleField
                roleCatalog={roleCatalog}
                department={form.department}
                value={form.current_role}
                other={form.current_role_other}
                onChange={(current_role) => update({ current_role })}
                onOther={(current_role_other) => update({ current_role_other })}
                error={errors.current_role}
              />
              {catalogFailed && (
                <p className="text-xs text-orange-400 sm:col-span-2">
                  Could not load the role list. Close and reopen this form to retry, or pick Other.
                </p>
              )}
              <ExperienceYearsField
                value={form.experience_years}
                onChange={(experience_years) => update({ experience_years })}
                error={errors.experience_years}
              />
              <CityField
                value={form.city}
                onChange={(city) => update({ city })}
                error={errors.city}
              />
              <AreaField
                required={false}
                value={form.area}
                onChange={(area) => update({ area })}
                error={errors.area}
              />
              <AgeField
                required={false}
                value={form.age}
                onChange={(age) => update({ age })}
                error={errors.age}
              />
              <NoticePeriodField
                value={form.notice_period}
                onChange={(notice_period) => update({ notice_period })}
                error={errors.notice_period}
              />
              <CurrentSalaryField
                value={form.salary}
                onChange={(salary) => update({ salary })}
                error={errors.salary}
              />
              <ExpectedSalaryField
                value={form.expected_salary}
                onChange={(expected_salary) => update({ expected_salary })}
                error={errors.expected_salary}
              />
              <CvLinkField
                className={full}
                value={form.cv_link}
                onChange={(cv_link) => update({ cv_link })}
                error={errors.cv_link}
              />
              {hasResume && (
                <p className={`-mt-2 text-xs text-text-muted ${full}`}>
                  They uploaded a resume with their application — it is already on file.
                </p>
              )}
              <NotesField
                className={full}
                value={form.notes}
                onChange={(notes) => update({ notes })}
              />
            </div>

            <footer className="flex gap-3 border-t border-border p-4">
              <button
                type="button"
                onClick={onClose}
                className="rounded-lg border border-border px-4 py-2 text-sm text-text-secondary hover:bg-surface-panel"
              >
                Cancel
              </button>
              <button
                type="submit"
                disabled={saving}
                className="flex-1 rounded-lg bg-emerald-600 px-3 py-2 text-sm font-semibold text-white hover:bg-emerald-500 disabled:opacity-60"
              >
                {saving ? <IconLoader2 className="mx-auto size-4 animate-spin" /> : "Accept"}
              </button>
            </footer>
          </form>
        )}
      </motion.div>
    </div>
  );
}
