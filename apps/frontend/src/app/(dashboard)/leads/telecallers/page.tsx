"use client";

import { useEffect } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { IconArrowLeft, IconLoader2 } from "@tabler/icons-react";
import { useCurrentUser } from "@/hooks/useCurrentUser";
import TelecallerMetrics from "@/components/leads/TelecallerMetrics";

/**
 * Telecaller metrics: admins and maintainers only. The same gate as the intake
 * analytics page; the endpoints behind it refuse everyone else anyway, so this
 * only saves a recruiter the sight of a screen that would be empty with errors.
 */
export default function TelecallerMetricsPage() {
  const router = useRouter();
  const { isMaintainer, isLoading } = useCurrentUser();

  useEffect(() => {
    if (!isLoading && !isMaintainer) router.replace("/");
  }, [isLoading, isMaintainer, router]);

  if (isLoading || !isMaintainer) {
    return (
      <div className="flex h-64 items-center justify-center">
        <IconLoader2 className="size-6 animate-spin text-text-muted" />
      </div>
    );
  }

  return (
    <div className="mx-auto w-full max-w-7xl p-4 duration-300 animate-in fade-in sm:p-6 lg:p-8">
      <header className="mb-6">
        <Link
          href="/leads"
          className="mb-2 inline-flex items-center gap-1 text-xs text-text-muted transition-colors hover:text-text-primary"
        >
          <IconArrowLeft className="size-3.5" />
          All leads
        </Link>
        <h1 className="font-heading text-2xl font-bold tracking-tight text-text-primary">
          Telecaller metrics
        </h1>
        <p className="mt-1 text-sm text-text-secondary">
          Calls made, what came of them, and progress against each telecaller&apos;s targets. Days
          are India time.
        </p>
      </header>
      <TelecallerMetrics />
    </div>
  );
}
