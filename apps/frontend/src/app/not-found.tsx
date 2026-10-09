"use client";

import Link from "next/link";
import DashboardSidebar from "@/components/sidebar/DashboardSidebar";
import { ToastProvider } from "@/components/ui/Toast";
import { useCurrentUser } from "@/hooks/useCurrentUser";
import "./(dashboard)/dashboard.css";

export default function NotFound() {
  const { user } = useCurrentUser();

  return (
    <ToastProvider>
      <div className="flex h-dvh overflow-hidden bg-shell md:p-3 md:gap-3 text-text-primary">
        <DashboardSidebar user={user} />

        <main className="flex-1 overflow-hidden bg-canvas md:rounded-xl md:shadow-2xl flex flex-col">
          {/* Inner scroll container — matches dashboard structure */}
          <div className="flex-1 overflow-y-auto scrollbar-none pb-[calc(4rem+env(safe-area-inset-bottom,0px))] md:pb-0">
            {/* 404 Content */}
            <div className="flex min-h-full flex-col items-center justify-center p-6 text-center">
              <div className="mb-4 font-heading text-[100px] font-bold leading-none tracking-tight text-navy dark:text-yellow sm:text-[140px]">
                404
              </div>
              <h1 className="mb-3 font-heading text-2xl font-bold tracking-tight sm:text-4xl">
                Page Not Found
              </h1>
              <p className="mb-8 max-w-md text-sm text-text-secondary sm:text-base">
                The page you&apos;re looking for doesn&apos;t exist or may have been moved.
              </p>
              <Link
                href="/"
                className="rounded-xl bg-navy px-8 py-3.5 font-subtitle text-sm font-bold tracking-wide text-white transition-all hover:-translate-y-0.5 hover:bg-navy-dark hover:shadow-lg active:translate-y-0 dark:bg-yellow dark:text-navy"
              >
                Back to Home
              </Link>
            </div>
          </div>
        </main>
      </div>
    </ToastProvider>
  );
}
