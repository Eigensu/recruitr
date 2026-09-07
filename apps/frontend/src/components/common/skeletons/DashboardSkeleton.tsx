import React from "react";
import { Skeleton } from "./Skeleton";

const KPI_SKELETON_KEYS = ["kpi-a", "kpi-b", "kpi-c", "kpi-d"];

export default function DashboardSkeleton() {
  return (
    <div
      className="min-h-full px-4 py-5 sm:px-6 lg:px-8 animate-in fade-in duration-300"
      style={{ background: "var(--color-canvas)", color: "var(--color-text-primary)" }}
    >
      <div className="mx-auto flex w-full max-w-400 flex-col gap-5">
        <header className="pb-4" style={{ borderBottom: "1px solid var(--color-border-val)" }}>
          <div className="flex items-start justify-between gap-4">
            <div>
              <Skeleton className="h-4 w-32 mb-3" />
              <Skeleton className="h-10 w-72 sm:h-12 sm:w-96" />
            </div>
            <div className="mt-1 flex shrink-0 items-center gap-2">
              <Skeleton className="h-10 w-10 rounded-full" />
            </div>
          </div>
        </header>

        <div className="grid grid-cols-1 items-stretch gap-6 xl:grid-cols-[minmax(300px,0.9fr)_minmax(0,1.9fr)]">
          {/* Pipeline Pie Section Placeholder */}
          <Skeleton className="h-[360px] w-full rounded-xl" />

          {/* Live Overview Section Placeholder */}
          <section className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-2 xl:grid-rows-2 xl:auto-rows-fr h-full">
            {KPI_SKELETON_KEYS.map((key) => (
              <Skeleton key={key} className="h-[120px] w-full rounded-xl" />
            ))}
          </section>
        </div>

        <div className="grid grid-cols-1 items-stretch gap-6 xl:grid-cols-[minmax(320px,0.8fr)_minmax(0,1.2fr)]">
          {/* Analytics Section Placeholder */}
          <Skeleton className="h-[360px] w-full rounded-xl" />
          {/* Recruiter Line Section Placeholder */}
          <Skeleton className="h-[360px] w-full rounded-xl" />
        </div>

        {/* Table placeholers */}
        <Skeleton className="h-[400px] w-full rounded-xl" />
      </div>
    </div>
  );
}
