import { LeaderboardTableSkeleton, KpiCardSkeleton } from "@/components/leaderboard";
import { PanelSkeleton } from "@/components/dashboard/atoms/PanelSkeleton";

export default function LeaderboardLoading() {
  return (
    <div className="min-h-full bg-black px-4 py-5 text-white sm:px-6 lg:px-8">
      <div className="mx-auto flex w-full max-w-400 flex-col gap-5">
        {/* Header skeleton */}
        <div className="border-b border-white/10 pb-4 space-y-2">
          <div className="h-3 w-40 rounded bg-white/10 animate-pulse" />
          <div className="h-10 w-72 rounded bg-white/10 animate-pulse" />
        </div>

        {/* Hero skeleton */}
        <PanelSkeleton rows={3} />

        {/* KPI skeletons */}
        <div className="grid grid-cols-2 gap-4 sm:grid-cols-4 xl:grid-cols-8">
          {Array.from({ length: 8 }, (_, i) => (
            <KpiCardSkeleton key={i} />
          ))}
        </div>

        {/* Chart skeletons */}
        <div className="grid grid-cols-1 gap-5 xl:grid-cols-2">
          <PanelSkeleton rows={5} />
          <PanelSkeleton rows={5} />
        </div>

        {/* Table skeleton */}
        <LeaderboardTableSkeleton />

        {/* Bottom row skeletons */}
        <div className="grid grid-cols-1 gap-5 xl:grid-cols-2">
          <PanelSkeleton rows={4} />
          <PanelSkeleton rows={6} />
        </div>
      </div>
    </div>
  );
}
