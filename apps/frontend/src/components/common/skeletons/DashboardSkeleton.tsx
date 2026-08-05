import React from "react";
import { Skeleton } from "./Skeleton";

// Fixed identities for the placeholders. Keying by map index ties each element
// to a position rather than to a thing.
const KPI_SKELETON_KEYS = ["kpi-a", "kpi-b", "kpi-c", "kpi-d"];

export default function DashboardSkeleton() {
  return (
    <div className="p-6 md:p-10 max-w-7xl mx-auto w-full animate-in fade-in duration-300">
      <div className="mb-8">
        <Skeleton className="h-10 w-48 mb-2" />
        <Skeleton className="h-5 w-64" />
      </div>

      {/* KPI Cards Skeleton */}
      <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-4 gap-6 mb-8">
        {KPI_SKELETON_KEYS.map((key) => (
          <Skeleton key={key} className="h-32 w-full rounded-2xl" />
        ))}
      </div>

      {/* Main Charts Skeleton */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <div className="lg:col-span-2">
          <Skeleton className="h-96 w-full rounded-2xl" />
        </div>
        <div>
          <Skeleton className="h-96 w-full rounded-2xl" />
        </div>
      </div>
    </div>
  );
}
