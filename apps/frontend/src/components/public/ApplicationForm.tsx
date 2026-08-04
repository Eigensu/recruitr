"use client";

import { useState } from "react";
import Image from "next/image";
import { z } from "zod";
import { IconAlertCircle, IconCheck, IconChevronDown } from "@tabler/icons-react";
import { clientPublicApply } from "@/lib/api/candidates.client";
import ResumeDropzone from "@/components/public/ResumeDropzone";
import type { PublicBrand } from "@/types";

// The API stores email as a plain string with no format check, so a typo here
// is stored silently and the applicant simply never hears back. Validate it.
const schema = z.object({
  fullName: z.string().trim().min(1, "Enter your name."),
  email: z.string().trim().email("Enter a valid email address."),
});

interface ApplicationFormProps {
  /** Resolved agency — drives both the submitted brand_id and the page chrome. */
  brand?: PublicBrand | null;
  /** Bare agency id, for links that carry one without a resolvable domain.
   *  Used only when `brand` is absent, and renders no agency branding. */
  brandId?: string | null;
}

const inputCls =
  "w-full rounded-lg border border-border bg-canvas px-3.5 py-2.5 text-sm text-text-primary placeholder:text-text-muted focus:border-yellow focus:outline-none focus:ring-1 focus:ring-yellow transition-colors";
const inputErrorCls = inputCls.replace("border-border", "border-red-500/60");
const labelCls = "mb-1.5 block text-xs font-medium text-text-secondary";

function FieldError({ id, message }: Readonly<{ id: string; message?: string }>) {
  if (!message) return null;
  return (
    <p id={id} className="mt-1.5 text-xs font-medium text-red-500">
      {message}
    </p>
  );
}

/** Section wrapper — mirrors the grouped panels used across the dashboard. */
function Section({
  title,
  hint,
  children,
}: Readonly<{ title: string; hint: string; children: React.ReactNode }>) {
  return (
    <section className="border-t border-border pt-6 first:border-t-0 first:pt-0">
      <div className="mb-4">
        <h2 className="text-[11px] font-semibold uppercase tracking-wider text-text-muted">
          {title}
        </h2>
        <p className="mt-1 text-xs text-text-muted/80">{hint}</p>
      </div>
      {children}
    </section>
  );
}

export default function ApplicationForm({ brand, brandId }: Readonly<ApplicationFormProps>) {
  const [loading, setLoading] = useState(false);
  const [success, setSuccess] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [fieldErrors, setFieldErrors] = useState<Record<string, string>>({});

  const [form, setForm] = useState({
    fullName: "",
    email: "",
    phone: "",
    city: "",
    currentRole: "",
    educationLevel: "",
  });
  const [resume, setResume] = useState<File | null>(null);

  // Null lets the API infer the agency when the deployment has exactly one.
  const targetBrandId = brand?.id ?? brandId ?? null;
  const agency = brand?.name ?? "our talent network";

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();

    const parsed = schema.safeParse({ fullName: form.fullName, email: form.email });
    if (!parsed.success) {
      const next: Record<string, string> = {};
      parsed.error.issues.forEach((issue) => {
        if (issue.path[0]) next[issue.path[0] as string] = issue.message;
      });
      setFieldErrors(next);
      setError(null);
      return;
    }

    setLoading(true);
    setError(null);
    setFieldErrors({});

    const formData = new FormData();
    if (targetBrandId) formData.append("brand_id", targetBrandId);
    formData.append("full_name", parsed.data.fullName);
    formData.append("email", parsed.data.email);
    if (form.phone) formData.append("phone", form.phone);
    if (form.city) formData.append("city", form.city);
    if (form.currentRole) formData.append("current_role", form.currentRole);
    if (form.educationLevel) formData.append("education_level", form.educationLevel);
    if (resume) formData.append("resume", resume);

    try {
      await clientPublicApply(formData);
      setSuccess(true);
    } catch (err: unknown) {
      const errorMessage =
        err instanceof Error ? err.message : "Something went wrong. Try again.";
      setError(errorMessage);
    } finally {
      setLoading(false);
    }
  };

  const masthead = (
    <div className="flex items-center gap-2.5">
      {brand?.logo_url ? (
        <Image
          src={brand.logo_url}
          alt=""
          width={32}
          height={32}
          className="size-8 rounded-lg object-cover"
          unoptimized
        />
      ) : (
        <Image
          src="/logo-yellow.jpeg"
          alt=""
          width={32}
          height={32}
          className="size-8 rounded-lg object-cover"
        />
      )}
      <span className="font-heading text-lg font-bold tracking-tight text-text-primary">
        {brand?.name ?? "Binge"}
      </span>
    </div>
  );

  if (success) {
    return (
      <main className="flex min-h-dvh items-center justify-center bg-shell p-4 font-sans theme-transition">
        <div className="w-full max-w-md rounded-2xl border border-border bg-surface-panel p-8 text-center">
          <div className="mx-auto mb-5 flex size-12 items-center justify-center rounded-full bg-yellow/10 text-yellow">
            <IconCheck className="size-6" />
          </div>
          <h1 className="font-heading text-2xl font-bold tracking-tight text-text-primary">
            Application received
          </h1>
          <p className="mt-3 text-sm text-text-secondary">
            {brand?.name ?? "The team"} has your details
            {resume ? " and your CV" : ""}. You&apos;ll hear back by email if there&apos;s a match.
          </p>
        </div>
      </main>
    );
  }

  return (
    <main className="min-h-dvh bg-shell font-sans text-text-primary theme-transition">
      <header className="flex items-center justify-between px-5 py-5 sm:px-8">
        {masthead}
      </header>

      <div className="flex justify-center px-4 pb-16 sm:px-6">
        <div className="w-full max-w-2xl">
          <div className="mb-7">
            <h1 className="font-heading text-3xl font-bold tracking-tight text-text-primary sm:text-4xl">
              Join {agency}
            </h1>
            <p className="mt-2.5 text-sm text-text-secondary sm:text-base">
              Share your details and CV. Takes about two minutes — every field but your name and
              email is optional.
            </p>
          </div>

          {error && (
            <div
              role="alert"
              className="mb-6 flex items-start gap-2.5 rounded-xl border border-red-500/20 bg-red-500/10 p-3.5"
            >
              <IconAlertCircle className="mt-px size-4 shrink-0 text-red-500" />
              <p className="text-sm font-medium text-red-500">{error}</p>
            </div>
          )}

          <form
            onSubmit={handleSubmit}
            noValidate
            className="flex flex-col gap-6 rounded-2xl border border-border bg-surface-panel p-5 sm:p-8"
          >
            <Section title="About you" hint="How the team will reach you.">
              <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
                <div>
                  <label htmlFor="fullName" className={labelCls}>
                    Full name <span className="text-yellow">*</span>
                  </label>
                  <input
                    id="fullName"
                    name="fullName"
                    autoComplete="name"
                    required
                    aria-invalid={!!fieldErrors.fullName}
                    aria-describedby={fieldErrors.fullName ? "fullName-error" : undefined}
                    className={fieldErrors.fullName ? inputErrorCls : inputCls}
                    placeholder="Jane Doe"
                    value={form.fullName}
                    onChange={(e) => setForm({ ...form, fullName: e.target.value })}
                  />
                  <FieldError id="fullName-error" message={fieldErrors.fullName} />
                </div>
                <div>
                  <label htmlFor="email" className={labelCls}>
                    Email <span className="text-yellow">*</span>
                  </label>
                  <input
                    id="email"
                    name="email"
                    type="email"
                    autoComplete="email"
                    required
                    aria-invalid={!!fieldErrors.email}
                    aria-describedby={fieldErrors.email ? "email-error" : undefined}
                    className={fieldErrors.email ? inputErrorCls : inputCls}
                    placeholder="jane@example.com"
                    value={form.email}
                    onChange={(e) => setForm({ ...form, email: e.target.value })}
                  />
                  <FieldError id="email-error" message={fieldErrors.email} />
                </div>
                <div>
                  <label htmlFor="phone" className={labelCls}>
                    Phone
                  </label>
                  <input
                    id="phone"
                    name="phone"
                    type="tel"
                    autoComplete="tel"
                    className={inputCls}
                    placeholder="+91 98765 43210"
                    value={form.phone}
                    onChange={(e) => setForm({ ...form, phone: e.target.value })}
                  />
                </div>
                <div>
                  <label htmlFor="city" className={labelCls}>
                    City
                  </label>
                  <input
                    id="city"
                    name="city"
                    autoComplete="address-level2"
                    className={inputCls}
                    placeholder="Mumbai"
                    value={form.city}
                    onChange={(e) => setForm({ ...form, city: e.target.value })}
                  />
                </div>
              </div>
            </Section>

            <Section title="Your background" hint="Helps match you to the right roles.">
              <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
                <div>
                  <label htmlFor="currentRole" className={labelCls}>
                    Current role
                  </label>
                  <input
                    id="currentRole"
                    name="currentRole"
                    autoComplete="organization-title"
                    className={inputCls}
                    placeholder="Software Engineer"
                    value={form.currentRole}
                    onChange={(e) => setForm({ ...form, currentRole: e.target.value })}
                  />
                </div>
                <div>
                  <label htmlFor="educationLevel" className={labelCls}>
                    Highest education
                  </label>
                  <div className="relative">
                    <select
                      id="educationLevel"
                      className={`${inputCls} appearance-none pr-10`}
                      value={form.educationLevel}
                      onChange={(e) => setForm({ ...form, educationLevel: e.target.value })}
                    >
                      <option value="">Select...</option>
                      <option value="High School">High School</option>
                      <option value="Bachelors">Bachelors (Undergraduate)</option>
                      <option value="Masters">Masters (Postgraduate)</option>
                      <option value="PhD">PhD / Doctorate</option>
                    </select>
                    <IconChevronDown className="pointer-events-none absolute right-3 top-1/2 size-4 -translate-y-1/2 text-text-muted" />
                  </div>
                </div>
              </div>
            </Section>

            <Section title="Your CV" hint="Optional, but it gets you matched faster.">
              <ResumeDropzone file={resume} onChange={setResume} disabled={loading} />
            </Section>

            <button
              type="submit"
              disabled={loading}
              className="mt-1 w-full rounded-lg bg-yellow px-4 py-3 text-sm font-bold text-navy transition-all hover:brightness-105 disabled:opacity-50"
            >
              {loading ? "Sending…" : "Send application"}
            </button>
          </form>

          <p className="mt-4 text-center text-xs text-text-muted">
            Your details are shared only with {brand?.name ?? "the hiring team"}.
          </p>
        </div>
      </div>
    </main>
  );
}
