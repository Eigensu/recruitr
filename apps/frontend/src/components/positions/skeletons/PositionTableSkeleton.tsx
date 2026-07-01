import { Skeleton } from "@/components/common/skeletons/Skeleton";

export default function PositionTableSkeleton() {
  return (
    <div className="p-3.5 rounded-xl border border-border bg-surface-panel flex items-start gap-2.5 relative">
      {/* Rank badge */}
      <Skeleton className="absolute -left-3 top-1/2 -translate-y-1/2 size-5 rounded-full border border-border" />

      {/* Drag handle */}
      <div className="mt-0.5 p-1 shrink-0">
        <Skeleton className="size-4" />
      </div>

      <div className="flex-1 min-w-0 space-y-2">
        {/* Name + score */}
        <div className="flex items-start justify-between gap-2 mb-1.5">
          <div className="min-w-0 flex-1 space-y-1.5 mt-1">
            <Skeleton className="h-3 w-2/3" />
            <Skeleton className="h-2 w-1/2" />
          </div>
          <Skeleton className="h-4 w-8 rounded-full shrink-0" />
        </div>

        {/* Skills */}
        <div className="flex flex-wrap gap-1 mb-2.5 mt-2">
          <Skeleton className="h-4 w-10 rounded" />
          <Skeleton className="h-4 w-12 rounded" />
          <Skeleton className="h-4 w-8 rounded" />
        </div>

        {/* Footer */}
        <div className="flex items-center justify-between gap-2 mt-2">
          <Skeleton className="h-2 w-1/3" />
          <Skeleton className="h-5 w-16 rounded-lg" />
        </div>
      </div>
    </div>
  );
}
