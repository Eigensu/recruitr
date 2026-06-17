import { Skeleton } from "@/components/common/skeletons/Skeleton";

export default function PositionCardSkeleton() {
  return (
    <div className="relative p-4 rounded-xl border border-border bg-surface-panel overflow-hidden">
      {/* Top row */}
      <div className="flex items-start justify-between gap-3 mb-2">
        <div className="flex-1 min-w-0 space-y-2">
          <div className="flex items-center gap-2">
            <Skeleton className="h-4 w-16 rounded-full" />
          </div>
          <Skeleton className="h-4 w-3/4" />
          <Skeleton className="h-3 w-1/2" />
        </div>
        <div className="shrink-0 flex flex-col items-center gap-1 min-w-9">
          <Skeleton className="h-6 w-8" />
          <Skeleton className="h-2 w-6" />
        </div>
      </div>

      {/* Tags row */}
      <div className="flex flex-wrap gap-1.5 mb-3 mt-4">
        <Skeleton className="h-4 w-12 rounded-full" />
        <Skeleton className="h-4 w-14 rounded-full" />
        <Skeleton className="h-4 w-16 rounded-full" />
      </div>

      {/* Pipeline fill progress */}
      <div className="mb-2.5">
        <div className="flex justify-between items-center mb-1">
          <Skeleton className="h-2 w-12" />
          <Skeleton className="h-2 w-8" />
        </div>
        <Skeleton className="h-1.5 w-full rounded-full" />
      </div>

      {/* Mapped candidate avatars */}
      <div className="flex items-center gap-2 mt-1.5 pt-1">
        <div className="flex -space-x-1.5">
          <Skeleton className="size-6 rounded-full border-2 border-surface" />
          <Skeleton className="size-6 rounded-full border-2 border-surface" />
          <Skeleton className="size-6 rounded-full border-2 border-surface" />
        </div>
        <Skeleton className="h-2 w-16" />
      </div>
    </div>
  );
}
