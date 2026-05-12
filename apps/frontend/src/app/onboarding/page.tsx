"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import Image from "next/image";

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export default function OnboardingPage() {
  const router = useRouter();
  const [agencyName, setAgencyName] = useState("");
  const [domain, setDomain] = useState("");
  const [error, setError] = useState("");
  const [isLoading, setIsLoading] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    setIsLoading(true);
    try {
      const res = await fetch(`${API_URL}/api/v1/brands`, {
        method: "POST",
        credentials: "include",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ name: agencyName, domain }),
      });
      if (!res.ok) {
        const text = await res.text();
        let data;
        try {
          data = JSON.parse(text);
        } catch (e) {
          console.error("Failed to parse error response:", text);
          throw new Error("Failed to create workspace: Invalid server response.");
        }
        throw new Error(data?.detail ?? "Failed to create workspace.");
      }
      router.push("/");
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Something went wrong.");
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <main className="flex min-h-dvh flex-col items-center justify-center bg-white px-6">
      <div className="mb-8 flex flex-col items-center gap-3">
        <div className="size-12 overflow-hidden rounded-xl shadow">
          <Image
            src="/logo-yellow.jpeg"
            alt="Binge"
            width={48}
            height={48}
            className="size-full object-cover"
          />
        </div>
        <h1 className="font-heading text-2xl font-bold tracking-tight text-navy">
          Set up your workspace
        </h1>
        <p className="text-sm text-muted text-center max-w-xs">
          You&apos;re almost there. Tell us about your recruitment agency.
        </p>
      </div>

      <form
        onSubmit={handleSubmit}
        className="w-full max-w-sm flex flex-col gap-4"
        id="onboarding-form"
      >
        {error && (
          <div
            className="rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-600"
            role="alert"
          >
            {error}
          </div>
        )}

        <div>
          <label
            className="mb-1.5 block text-[13px] font-semibold tracking-wide text-charcoal"
            htmlFor="ob-name"
          >
            Agency Name
          </label>
          <input
            id="ob-name"
            type="text"
            placeholder="e.g. Binge Consulting"
            required
            value={agencyName}
            onChange={(e) => setAgencyName(e.target.value)}
            className="block w-full rounded-[10px] border-[1.5px] border-gray-200 bg-white px-4 py-3 text-sm text-charcoal outline-none transition-all placeholder:text-gray-400 focus:border-navy focus:ring-2 focus:ring-navy/10"
          />
        </div>

        <div>
          <label
            className="mb-1.5 block text-[13px] font-semibold tracking-wide text-charcoal"
            htmlFor="ob-domain"
          >
            Agency Domain
          </label>
          <input
            id="ob-domain"
            type="text"
            placeholder="e.g. bingeconsulting.com"
            required
            value={domain}
            onChange={(e) => setDomain(e.target.value)}
            className="block w-full rounded-[10px] border-[1.5px] border-gray-200 bg-white px-4 py-3 text-sm text-charcoal outline-none transition-all placeholder:text-gray-400 focus:border-navy focus:ring-2 focus:ring-navy/10"
          />
        </div>

        <button
          type="submit"
          disabled={isLoading}
          className="mt-2 w-full cursor-pointer rounded-[10px] bg-navy px-6 py-3.5 text-sm font-bold tracking-wide text-white transition-all hover:-translate-y-0.5 hover:bg-navy-dark hover:shadow-lg disabled:cursor-not-allowed disabled:opacity-70"
          id="ob-sub"
        >
          {isLoading ? "Creating workspace…" : "Create Workspace →"}
        </button>
      </form>
    </main>
  );
}
