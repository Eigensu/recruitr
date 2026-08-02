"use client";

import { Suspense, useState } from "react";
import { useSearchParams } from "next/navigation";
import { clientPublicApply } from "@/lib/api/candidates.client";

function PublicApplicationFormContent() {
  const searchParams = useSearchParams();
  const brandId = searchParams.get("brandId");

  const [loading, setLoading] = useState(false);
  const [success, setSuccess] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const [form, setForm] = useState({
    fullName: "",
    email: "",
    phone: "",
    city: "",
    currentRole: "",
    educationLevel: "",
  });
  const [resume, setResume] = useState<File | null>(null);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!form.fullName || !form.email) {
      setError("Name and Email are required");
      return;
    }

    setLoading(true);
    setError(null);

    const formData = new FormData();
    if (brandId) formData.append("brand_id", brandId);
    formData.append("full_name", form.fullName);
    formData.append("email", form.email);
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
        err instanceof Error ? err.message : "Something went wrong. Please try again.";
      setError(errorMessage);
    } finally {
      setLoading(false);
    }
  };

  if (success) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-shell p-4 font-sans text-text-primary theme-transition">
        <div className="w-full max-w-md rounded-2xl bg-surface-panel p-8 text-center shadow-xl border border-border">
          <div className="mx-auto mb-6 flex h-16 w-16 items-center justify-center rounded-full bg-emerald-500/10">
            <svg
              className="h-8 w-8 text-emerald-500"
              fill="none"
              stroke="currentColor"
              viewBox="0 0 24 24"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M5 13l4 4L19 7"
              />
            </svg>
          </div>
          <h2 className="text-2xl font-heading font-bold text-text-primary mb-3">
            Application Submitted!
          </h2>
          <p className="text-text-secondary text-sm">
            Thank you for applying. We have received your application and will be in touch soon.
          </p>
        </div>
      </div>
    );
  }

  const inputCls =
    "w-full rounded-xl border border-border bg-canvas px-4 py-3 sm:py-3.5 text-sm text-text-primary placeholder:text-text-muted/60 focus:border-yellow focus:outline-none focus:ring-1 focus:ring-yellow transition-colors";
  const labelCls = "mb-1.5 block text-sm font-medium text-text-primary";

  return (
    <div className="min-h-screen bg-shell font-sans text-text-primary selection:bg-yellow selection:text-navy relative theme-transition">
      {/* Top right logo */}
      <div className="absolute top-6 right-6 lg:top-8 lg:right-8 flex items-center gap-2">
        <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-yellow text-navy font-heading font-bold text-lg">
          R
        </div>
        <span className="text-xl font-heading font-bold tracking-tight text-text-primary">
          Recruitr
        </span>
      </div>

      <div className="flex min-h-screen items-center justify-center p-4 py-20 sm:p-6 lg:p-8">
        <div className="w-full max-w-2xl rounded-3xl bg-surface-panel p-6 sm:p-10 lg:p-12 shadow-2xl shadow-black/10 border border-border">
          <div className="mb-8 text-center">
            <h1 className="font-heading text-3xl font-bold tracking-tight text-text-primary sm:text-4xl">
              Submit your application
            </h1>
            <p className="mt-3 text-text-secondary text-sm sm:text-base">
              Join our talent network. It only takes a few minutes.
            </p>
          </div>

          {error && (
            <div className="mb-6 rounded-xl bg-red-500/10 p-4 border border-red-500/20">
              <p className="text-sm text-red-500 font-medium">{error}</p>
            </div>
          )}

          <form onSubmit={handleSubmit} className="space-y-5 sm:space-y-6">
            <div className="grid grid-cols-1 gap-5 sm:gap-6 sm:grid-cols-2">
              <div>
                <label htmlFor="fullName" className={labelCls}>
                  Full Name *
                </label>
                <input
                  id="fullName"
                  type="text"
                  required
                  className={inputCls}
                  placeholder="Jane Doe"
                  value={form.fullName}
                  onChange={(e) => setForm({ ...form, fullName: e.target.value })}
                />
              </div>
              <div>
                <label htmlFor="email" className={labelCls}>
                  Email Address *
                </label>
                <input
                  id="email"
                  type="email"
                  required
                  className={inputCls}
                  placeholder="jane@example.com"
                  value={form.email}
                  onChange={(e) => setForm({ ...form, email: e.target.value })}
                />
              </div>
            </div>

            <div className="grid grid-cols-1 gap-5 sm:gap-6 sm:grid-cols-2">
              <div>
                <label htmlFor="phone" className={labelCls}>
                  Phone Number
                </label>
                <input
                  id="phone"
                  type="tel"
                  className={inputCls}
                  placeholder="+1 (555) 000-0000"
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
                  type="text"
                  className={inputCls}
                  placeholder="e.g. New York, London"
                  value={form.city}
                  onChange={(e) => setForm({ ...form, city: e.target.value })}
                />
              </div>
            </div>

            <div className="grid grid-cols-1 gap-5 sm:gap-6 sm:grid-cols-2">
              <div>
                <label htmlFor="currentRole" className={labelCls}>
                  Current Role
                </label>
                <input
                  id="currentRole"
                  type="text"
                  className={inputCls}
                  placeholder="e.g. Software Engineer"
                  value={form.currentRole}
                  onChange={(e) => setForm({ ...form, currentRole: e.target.value })}
                />
              </div>
              <div>
                <label htmlFor="educationLevel" className={labelCls}>
                  Highest Education
                </label>
                <select
                  id="educationLevel"
                  className={inputCls}
                  value={form.educationLevel}
                  onChange={(e) => setForm({ ...form, educationLevel: e.target.value })}
                >
                  <option value="">Select education...</option>
                  <option value="High School">High School</option>
                  <option value="Bachelors">Bachelors (Undergraduate)</option>
                  <option value="Masters">Masters (Postgraduate)</option>
                  <option value="PhD">PhD / Doctorate</option>
                </select>
              </div>
            </div>

            <div>
              <label className={labelCls}>Resume / CV (PDF or DOCX)</label>
              <div className="mt-1.5 flex justify-center rounded-xl border-2 border-dashed border-border bg-canvas/30 px-6 py-10 sm:py-12 transition-all hover:border-yellow hover:bg-canvas/60">
                <div className="text-center">
                  <svg
                    className="mx-auto h-12 w-12 text-text-muted/60"
                    stroke="currentColor"
                    fill="none"
                    viewBox="0 0 48 48"
                    aria-hidden="true"
                  >
                    <path
                      d="M28 8H12a4 4 0 00-4 4v20m32-12v8m0 0v8a4 4 0 01-4 4H12a4 4 0 01-4-4v-4m32-4l-3.172-3.172a4 4 0 00-5.656 0L28 28M8 32l9.172-9.172a4 4 0 015.656 0L28 28m0 0l4 4m4-24h8m-4-4v8m-12 4h.02"
                      strokeWidth={2}
                      strokeLinecap="round"
                      strokeLinejoin="round"
                    />
                  </svg>
                  <div className="mt-4 flex text-sm leading-6 text-text-secondary justify-center">
                    <label
                      htmlFor="file-upload"
                      className="relative cursor-pointer rounded-md font-semibold text-yellow hover:text-yellow-dark focus-within:outline-none focus-within:ring-2 focus-within:ring-yellow focus-within:ring-offset-2 focus-within:ring-offset-surface-panel transition-colors"
                    >
                      <span>Upload a file</span>
                      <input
                        id="file-upload"
                        name="file-upload"
                        type="file"
                        className="sr-only"
                        accept=".pdf,.docx,application/pdf,application/vnd.openxmlformats-officedocument.wordprocessingml.document"
                        onChange={(e) => setResume(e.target.files?.[0] || null)}
                      />
                    </label>
                    <p className="pl-1">or drag and drop</p>
                  </div>
                  <p className="text-xs leading-5 text-text-muted mt-1.5">
                    {resume ? resume.name : "PDF, DOCX up to 10MB"}
                  </p>
                </div>
              </div>
            </div>

            <div className="pt-4 sm:pt-6">
              <button
                type="submit"
                disabled={loading}
                className="w-full rounded-xl bg-yellow px-4 py-4 text-sm sm:text-base font-bold text-navy shadow-sm hover:brightness-105 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-yellow disabled:opacity-50 transition-all"
              >
                {loading ? "Submitting..." : "Submit Application"}
              </button>
            </div>
          </form>
        </div>
      </div>
    </div>
  );
}

export default function PublicApplicationForm() {
  return (
    <Suspense
      fallback={
        <div className="min-h-screen bg-shell flex items-center justify-center font-sans text-text-secondary text-sm">
          Loading...
        </div>
      }
    >
      <PublicApplicationFormContent />
    </Suspense>
  );
}
