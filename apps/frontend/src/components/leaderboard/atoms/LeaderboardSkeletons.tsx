/** Skeleton block for leaderboard — re-exports the shared one for local use. */
export { SkeletonBlock } from "@/components/dashboard/atoms/SkeletonBlock";

export function LeaderboardRowSkeleton() {
  return (
    <div className="flex items-center gap-4 px-5 py-3">
      <div className="w-8 h-4 rounded bg-(--color-surface-2-val) animate-pulse shrink-0" />
      <div className="flex items-center gap-3 flex-1">
        <div className="size-9 rounded-full bg-(--color-surface-2-val) animate-pulse shrink-0" />
        <div className="h-4 w-28 rounded bg-(--color-surface-2-val) animate-pulse" />
      </div>
      <div className="h-4 w-10 rounded bg-(--color-surface-2-val) animate-pulse hidden sm:block" />
      <div className="h-4 w-10 rounded bg-(--color-surface-2-val) animate-pulse hidden md:block" />
      <div className="h-4 w-10 rounded bg-(--color-surface-2-val) animate-pulse hidden lg:block" />
      <div className="h-4 w-14 rounded bg-(--color-surface-2-val) animate-pulse hidden xl:block" />
      <div className="h-5 w-20 rounded-full bg-(--color-surface-2-val) animate-pulse" />
    </div>
  );
}

export function LeaderboardTableSkeleton() {
  return (
    <div className="rounded-lg bg-(--color-surface-val) shadow-md overflow-hidden">
      <div className="px-5 py-4 flex items-center justify-between">
        <div className="h-5 w-40 rounded bg-(--color-surface-2-val) animate-pulse" />
        <div className="h-4 w-24 rounded bg-(--color-surface-2-val) animate-pulse" />
      </div>
      {Array.from({ length: 6 }, (_, i) => (
        <LeaderboardRowSkeleton key={i} />
      ))}
    </div>
  );
}

export function KpiCardSkeleton() {
  return (
    <div className="rounded-lg bg-(--color-surface-val) shadow-md p-4 animate-pulse">
      <div className="flex items-start justify-between gap-3">
        <div>
          <div className="h-3 w-24 rounded bg-(--color-surface-2-val) mb-2" />
          <div className="h-7 w-16 rounded bg-(--color-surface-2-val)" />
        </div>
        <div className="size-9 rounded-lg bg-(--color-surface-2-val) shrink-0" />
      </div>
      <div className="mt-3 h-3 w-32 rounded bg-(--color-surface-2-val)" />
    </div>
  );
}
