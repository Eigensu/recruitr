import { LeaderboardTableSkeleton, KpiCardSkeleton } from "@/components/leaderboard";
import { PanelSkeleton } from "@/components/dashboard/atoms/PanelSkeleton";

export default function LeaderboardLoading() {
  return (
    <div
      className="min-h-full px-4 py-5 sm:px-6 lg:px-8 animate-in fade-in duration-300"
      style={{ background: "var(--color-canvas)", color: "var(--color-text-primary)" }}
    >
      <div className="mx-auto flex w-full max-w-400 flex-col gap-5">
        {/* Header skeleton */}
        <div
          className="pb-4 flex items-start justify-between gap-4"
          style={{ borderBottom: "1px solid var(--color-border-val)" }}
        >
          <div>
            <div className="h-4 w-48 rounded bg-surface-2 animate-pulse mb-3" />
            <div className="h-10 w-72 sm:h-12 sm:w-96 rounded bg-surface-2 animate-pulse" />
          </div>
          <div className="mt-1 shrink-0 h-10 w-10 rounded-full bg-surface-2 animate-pulse" />
        </div>

        {/* Hero skeleton */}
        <div className="h-64 rounded-xl bg-surface-2 animate-pulse" />

        {/* KPI skeletons */}
        <div className="grid grid-cols-2 gap-4 sm:grid-cols-4 xl:grid-cols-8">
          {Array.from({ length: 8 }, (_, i) => (
            <div key={i} className="h-28 rounded-xl bg-surface-2 animate-pulse" />
          ))}
        </div>

        {/* Chart skeletons */}
        <div className="grid grid-cols-1 gap-5 xl:grid-cols-2">
          <div className="h-[400px] rounded-xl bg-surface-2 animate-pulse" />
          <div className="h-[400px] rounded-xl bg-surface-2 animate-pulse" />
        </div>

        {/* Table skeleton */}
        <LeaderboardTableSkeleton />

        {/* Bottom row skeletons 1 */}
        <div className="grid grid-cols-1 gap-5 xl:grid-cols-[1fr_360px]">
          <div className="h-[400px] rounded-xl bg-surface-2 animate-pulse" />
          <div className="h-[400px] rounded-xl bg-surface-2 animate-pulse" />
        </div>

        {/* Bottom row skeletons 2 */}
        <div className="grid grid-cols-1 gap-5 xl:grid-cols-[360px_1fr]">
          <div className="h-[400px] rounded-xl bg-surface-2 animate-pulse" />
          <div className="h-[400px] rounded-xl bg-surface-2 animate-pulse" />
        </div>
      </div>
    </div>
  );
}
