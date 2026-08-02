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
      <div className="flex min-h-screen items-center justify-center bg-gray-50 p-4">
        <div className="w-full max-w-md rounded-2xl bg-white p-8 text-center shadow-xl border border-gray-100">
          <div className="mx-auto mb-4 flex h-16 w-16 items-center justify-center rounded-full bg-green-100">
            <svg
              className="h-8 w-8 text-green-600"
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
          <h2 className="text-2xl font-bold text-gray-900 mb-2">Application Submitted!</h2>
          <p className="text-gray-600">
            Thank you for applying. We have received your application and will be in touch soon.
          </p>
        </div>
      </div>
    );
  }

  const inputCls =
    "w-full rounded-xl border border-gray-200 bg-gray-50 px-4 py-3 text-sm text-gray-900 focus:border-blue-500 focus:bg-white focus:outline-none focus:ring-1 focus:ring-blue-500 transition-colors";
  const labelCls = "mb-1.5 block text-sm font-medium text-gray-700";

  return (
    <div className="min-h-screen bg-gray-50 font-sans text-gray-900 selection:bg-blue-100 relative">
      {/* Top right logo */}
      <div className="absolute top-6 right-6 lg:top-8 lg:right-8 flex items-center gap-2">
        <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-blue-600 text-white font-bold">
          R
        </div>
        <span className="text-xl font-bold tracking-tight text-gray-900">Recruitr</span>
      </div>

      <div className="flex min-h-screen items-center justify-center p-4 py-16">
        <div className="w-full max-w-2xl rounded-2xl bg-white p-8 shadow-xl shadow-gray-200/50 border border-gray-100 lg:p-12">
          <div className="mb-8 text-center">
            <h1 className="text-3xl font-bold tracking-tight text-gray-900 sm:text-4xl">
              Submit your application
            </h1>
            <p className="mt-3 text-gray-500">
              Join our talent network. It only takes a few minutes.
            </p>
          </div>

          {error && (
            <div className="mb-6 rounded-xl bg-red-50 p-4 border border-red-100">
              <p className="text-sm text-red-600">{error}</p>
            </div>
          )}

          <form onSubmit={handleSubmit} className="space-y-6">
            <div className="grid grid-cols-1 gap-6 sm:grid-cols-2">
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

            <div className="grid grid-cols-1 gap-6 sm:grid-cols-2">
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

            <div className="grid grid-cols-1 gap-6 sm:grid-cols-2">
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
              <div className="mt-1 flex justify-center rounded-xl border-2 border-dashed border-gray-300 px-6 py-8 transition-colors hover:border-blue-400">
                <div className="text-center">
                  <svg
                    className="mx-auto h-10 w-10 text-gray-300"
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
                  <div className="mt-4 flex text-sm leading-6 text-gray-600 justify-center">
                    <label
                      htmlFor="file-upload"
                      className="relative cursor-pointer rounded-md bg-white font-semibold text-blue-600 focus-within:outline-none focus-within:ring-2 focus-within:ring-blue-600 focus-within:ring-offset-2 hover:text-blue-500"
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
                  <p className="text-xs leading-5 text-gray-500 mt-1">
                    {resume ? resume.name : "PDF, DOCX up to 10MB"}
                  </p>
                </div>
              </div>
            </div>

            <div className="pt-4">
              <button
                type="submit"
                disabled={loading}
                className="w-full rounded-xl bg-blue-600 px-4 py-4 text-sm font-semibold text-white shadow-sm hover:bg-blue-500 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-blue-600 disabled:opacity-50 transition-all"
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
        <div className="min-h-screen bg-gray-50 flex items-center justify-center">Loading...</div>
      }
    >
      <PublicApplicationFormContent />
    </Suspense>
  );
}
