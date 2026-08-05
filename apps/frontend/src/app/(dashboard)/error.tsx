"use client";
import React from "react";
import { IconAlertTriangle } from "@tabler/icons-react";

// Named DashboardError, not Error: a local declaration called Error shadows the
// built-in, which makes the `Error & { digest }` annotation below read as though
// it referred to this component. Next.js only cares about the default export.
export default function DashboardError({
  error,
  reset,
}: Readonly<{
  error: Error & { digest?: string };
  reset: () => void;
}>) {
  return (
    <div className="flex h-full flex-col items-center justify-center p-6 text-center animate-in fade-in duration-300">
      <div className="rounded-full bg-red-100 p-4 dark:bg-red-900/30 mb-4">
        <IconAlertTriangle className="h-8 w-8 text-red-600 dark:text-red-400" />
      </div>
      <h2 className="text-xl font-bold text-text-primary mb-2">Something went wrong!</h2>
      <p className="text-sm text-text-secondary mb-6 max-w-md">
        {error.message || "An unexpected error occurred while loading this page."}
      </p>
      <button
        type="button"
        onClick={() => reset()}
        className="rounded-lg bg-navy px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-navy/90 dark:bg-yellow dark:text-navy dark:hover:bg-yellow/90"
      >
        Try again
      </button>
    </div>
  );
}
