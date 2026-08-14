"use client";

import { useState } from "react";
import Image from "next/image";
import { useSearchParams } from "next/navigation";
import { z } from "zod";
import { IconAlertCircle, IconCheck, IconChevronDown } from "@tabler/icons-react";
import { clientPublicApply } from "@/lib/api/candidates.client";
import ResumeDropzone from "@/components/public/ResumeDropzone";
import { ThemeToggle } from "@/components/ui/ThemeToggle";
import {
  CITIES,
  EDUCATION_LEVELS,
  SOURCE_CHANNEL_OTHER,
  SOURCE_CHANNELS,
} from "@/lib/constants/candidate";
import type { PublicBrand } from "@/types";

// The API stores email as a plain string with no format check, so a typo here
// is stored silently and the applicant simply never hears back. Validate it.
const schema = z
  .object({
    fullName: z.string().trim().min(1, "Enter your name."),
    email: z.string().trim().email("Enter a valid email address."),
    phone: z.string().trim().min(6, "Enter a phone number we can reach you on."),
    sourceChannel: z.string(),
    sourceChannelOther: z.string().trim(),
  })
  // "Other" is only meaningful with the free-text value that explains it.
  .refine((v) => v.sourceChannel !== SOURCE_CHANNEL_OTHER || v.sourceChannelOther.length > 0, {
    path: ["sourceChannelOther"],
    message: "Tell us where you heard about us.",
  });

interface ApplicationFormProps {
  /** Resolved agency — drives both the submitted brand_id and the page chrome. */
  brand?: PublicBrand | null;
  /** Bare agency id, for links that carry one without a resolvable domain.
   *  Used only when `brand` is absent, and renders no agency branding. */
  brandId?: string | null;
  /** Whether this form is rendered inside the dashboard app. Strips the page shell. */
  isEmbedded?: boolean;
  /** Pre-fill the connect code, bypassing the URL search params. */
  initialConnectCode?: string | null;
  /** Pre-fill the source channel. */
  initialSourceChannel?: string | null;
}

const inputCls =
  "w-full rounded-lg border border-border bg-transparent px-3.5 py-2.5 text-sm text-text-primary placeholder:text-text-secondary focus:border-yellow focus:outline-none focus:ring-1 focus:ring-yellow transition-colors";
const inputErrorCls = inputCls.replace("border-border", "border-red-500/60");
const labelCls = "mb-1.5 block text-xs font-medium text-text-secondary";
// bg-surface rather than bg-canvas: canvas is the page grey in light mode, and
// the dropdown reads as a panel floating above the form in both themes.
const optionCls = "bg-surface text-text-primary";

function FieldError({ id, message }: Readonly<{ id: string; message?: string }>) {
  if (!message) return null;
  return (
    <p id={id} className="mt-1.5 text-xs font-medium text-red-500">
      {message}
    </p>
  );
}

/** Native select styled to match the text inputs, with a token-coloured chevron. */
function Select({
  id,
  label,
  value,
  onChange,
  options,
  placeholder,
  required,
}: Readonly<{
  id: string;
  label: string;
  value: string;
  onChange: (value: string) => void;
  options: readonly (string | { value: string; label: string })[];
  placeholder: string;
  required?: boolean;
}>) {
  const items = options.map((o) => (typeof o === "string" ? { value: o, label: o } : o));
  return (
    <div>
      <label htmlFor={id} className={labelCls}>
        {label} {required && <span className="text-yellow">*</span>}
      </label>
      <div className="relative">
        <select
          id={id}
          name={id}
          className={`${inputCls} appearance-none pr-10`}
          value={value}
          onChange={(e) => onChange(e.target.value)}
        >
          {/* Options carry their own colours on top of the root `color-scheme`.
              Chrome on Windows/Linux draws the dropdown from the element rather
              than the colour scheme, and would otherwise inherit the near-white
              `text-text-primary` onto its default white popup. */}
          <option className={optionCls} value="">
            {placeholder}
          </option>
          {items.map((item) => (
            <option className={optionCls} key={item.value} value={item.value}>
              {item.label}
            </option>
          ))}
        </select>
        <IconChevronDown className="pointer-events-none absolute right-3 top-1/2 size-4 -translate-y-1/2 text-text-secondary" />
      </div>
    </div>
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
        <h2 className="text-[11px] font-semibold uppercase tracking-wider text-text-primary">
          {title}
        </h2>
        <p className="mt-1 text-xs text-text-secondary">{hint}</p>
      </div>
      {children}
    </section>
  );
}

export default function ApplicationForm({ brand, brandId, isEmbedded, initialConnectCode, initialSourceChannel }: Readonly<ApplicationFormProps>) {
  const [loading, setLoading] = useState(false);
  const [success, setSuccess] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [fieldErrors, setFieldErrors] = useState<Record<string, string>>({});

  const searchParams = useSearchParams();
  const queryConnectCode = searchParams?.get("connectCode") ?? "";
  
  const startingConnectCode = initialConnectCode ?? queryConnectCode;
  const startingSourceChannel = initialSourceChannel ?? (startingConnectCode ? "Connected by a Binge Partner" : "");

  const [form, setForm] = useState({
    fullName: "",
    email: "",
    phone: "",
    city: "",
    currentRole: "",
    educationLevel: "",
    sourceChannel: startingSourceChannel,
    sourceChannelOther: "",
    connectCode: startingConnectCode,
  });
  const [resume, setResume] = useState<File | null>(null);

  // Null lets the API infer the agency when the deployment has exactly one.
  const targetBrandId = brand?.id ?? brandId ?? null;

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();

    const parsed = schema.safeParse({
      fullName: form.fullName,
      email: form.email,
      phone: form.phone,
      sourceChannel: form.sourceChannel,
      sourceChannelOther: form.sourceChannelOther,
    });
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
    formData.append("phone", parsed.data.phone);
    if (form.city) formData.append("city", form.city);
    if (form.currentRole) formData.append("current_role", form.currentRole);
    if (form.educationLevel) formData.append("education_level", form.educationLevel);
    // "Other" carries no information on its own — send what they typed instead.
    const channel =
      form.sourceChannel === SOURCE_CHANNEL_OTHER
        ? parsed.data.sourceChannelOther
        : form.sourceChannel;
    if (channel) formData.append("source_channel", channel);
    if (form.connectCode) formData.append("connect_code", form.connectCode);
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
    // min-w-0 so a long agency name truncates instead of pushing the theme
    // toggle off the right edge of a phone screen.
    <div className="flex min-w-0 items-center gap-2.5">
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
      <span className="truncate font-heading text-lg font-bold tracking-tight text-text-primary">
        {brand?.name ?? "Binge"}
      </span>
    </div>
  );

  if (success) {
    if (isEmbedded) {
      return (
        <div className="w-full max-w-2xl mx-auto rounded-2xl border border-border bg-surface p-8 text-center text-text-primary shadow-sm mt-8">
          <div className="mx-auto mb-5 flex size-12 items-center justify-center rounded-full bg-green-500/10 text-green-600">
            <IconCheck className="size-6" />
          </div>
          <h1 className="font-heading text-2xl font-bold tracking-tight text-text-primary">
            Application received
          </h1>
          <p className="mt-3 text-sm text-text-secondary">
            Your candidate has been successfully submitted to {brand?.name ?? "the hiring team"}.
          </p>
        </div>
      );
    }
    return (
      <main className="relative flex min-h-dvh items-center justify-center bg-shell p-4 font-sans theme-transition">
        {/* This screen has no header, and it is where an applicant may sit for a
            while reading the confirmation — so the toggle follows them here. */}
        <div className="absolute right-4 top-4 sm:right-6 sm:top-6">
          <ThemeToggle size="lg" />
        </div>
        <div className="w-full max-w-md rounded-2xl border border-border bg-surface-panel p-8 text-center text-text-primary">
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
  const formContent = (
    <div className={`flex justify-center ${isEmbedded ? "" : "px-4 pb-16 sm:px-6"}`}>
      <div className={`w-full ${isEmbedded ? "" : "max-w-2xl"}`}>
        <div className="mb-7">
            <h1 className="font-heading text-3xl font-bold tracking-tight text-text-primary sm:text-4xl">
              Find Your Next Job
            </h1>
            <p className="mt-2.5 text-sm text-text-secondary sm:text-base">
              One application. Multiple job opportunities.
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
            className="flex flex-col gap-6 rounded-2xl border border-border bg-surface-panel text-text-primary p-5 sm:p-8"
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
                    Phone <span className="text-yellow">*</span>
                  </label>
                  <input
                    id="phone"
                    name="phone"
                    type="tel"
                    autoComplete="tel"
                    required
                    aria-invalid={!!fieldErrors.phone}
                    aria-describedby={fieldErrors.phone ? "phone-error" : undefined}
                    className={fieldErrors.phone ? inputErrorCls : inputCls}
                    placeholder="+91 98765 43210"
                    value={form.phone}
                    onChange={(e) => setForm({ ...form, phone: e.target.value })}
                  />
                  <FieldError id="phone-error" message={fieldErrors.phone} />
                </div>
                <Select
                  id="city"
                  label="City"
                  value={form.city}
                  onChange={(city) => setForm({ ...form, city })}
                  options={CITIES}
                  placeholder="Select your city..."
                />
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
                <Select
                  id="educationLevel"
                  label="Highest education"
                  value={form.educationLevel}
                  onChange={(educationLevel) => setForm({ ...form, educationLevel })}
                  options={EDUCATION_LEVELS}
                  placeholder="Select..."
                />
              </div>
            </Section>

            <Section title="How you heard about us" hint="Just so we can say thanks to whoever pointed you our way.">
              <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
                <Select
                  id="sourceChannel"
                  label="Where you heard about us"
                  value={form.sourceChannel}
                  onChange={(sourceChannel) => {
                    const isConnectCodeOption = sourceChannel === "Referred by a Friend" || sourceChannel === "Connected by a Binge Partner";
                    setForm({ 
                      ...form, 
                      sourceChannel,
                      connectCode: isConnectCodeOption ? form.connectCode : ""
                    });
                  }}
                  options={SOURCE_CHANNELS}
                  placeholder="Select..."
                />
                {form.sourceChannel === SOURCE_CHANNEL_OTHER && (
                  <div>
                    <label htmlFor="sourceChannelOther" className={labelCls}>
                      Tell us where <span className="text-yellow">*</span>
                    </label>
                    <input
                      id="sourceChannelOther"
                      name="sourceChannelOther"
                      aria-invalid={!!fieldErrors.sourceChannelOther}
                      aria-describedby={
                        fieldErrors.sourceChannelOther ? "sourceChannelOther-error" : undefined
                      }
                      className={fieldErrors.sourceChannelOther ? inputErrorCls : inputCls}
                      placeholder="e.g. College placement cell"
                      value={form.sourceChannelOther}
                      onChange={(e) => setForm({ ...form, sourceChannelOther: e.target.value })}
                    />
                    <FieldError
                      id="sourceChannelOther-error"
                      message={fieldErrors.sourceChannelOther}
                    />
                  </div>
                )}
                {(form.sourceChannel === "Referred by a Friend" || form.sourceChannel === "Connected by a Binge Partner") && (
                  <div>
                    <label htmlFor="connectCode" className={labelCls}>
                      Connect Code
                    </label>
                    <input
                      id="connectCode"
                      name="connectCode"
                      className={inputCls}
                      placeholder="e.g. ABC1234"
                      value={form.connectCode}
                      onChange={(e) => setForm({ ...form, connectCode: e.target.value })}
                    />
                    <p className="mt-1.5 text-xs text-text-secondary">
                      Have a Connect Code? Enter it here (optional).
                    </p>
                  </div>
                )}
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
  );

  if (isEmbedded) {
    return formContent;
  }

  return (
    <main className="min-h-dvh bg-shell font-sans text-text-primary theme-transition">
      <header className="flex items-center justify-between gap-3 px-5 py-5 sm:px-8">
        {masthead}
        <ThemeToggle size="lg" />
      </header>
      {formContent}
    </main>
  );
}
