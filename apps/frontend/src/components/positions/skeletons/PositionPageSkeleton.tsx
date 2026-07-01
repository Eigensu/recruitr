import { Skeleton } from "@/components/common/skeletons/Skeleton";
import PositionCardSkeleton from "@/components/positions/skeletons/PositionCardSkeleton";

export default function PositionPageSkeleton() {
  return (
    <div className="flex flex-col h-full overflow-hidden bg-canvas">
      {/* ── Page header ── */}
      <div className="px-6 pt-6 pb-5 border-b border-border shrink-0">
        <div className="flex items-center justify-between gap-4">
          <div>
            <Skeleton className="h-8 w-48 mb-2" />
            <Skeleton className="h-4 w-96" />
          </div>
          <Skeleton className="h-10 w-32 rounded-lg shrink-0" />
        </div>
      </div>

      {/* ── Split pane ── */}
      <div className="flex flex-1 overflow-hidden">
        {/* ── LEFT: Positions ── */}
        <div className="w-[46%] flex flex-col border-r border-border overflow-hidden bg-canvas">
          <div className="p-4 border-b border-border shrink-0 space-y-2.5 bg-surface">
            <Skeleton className="h-10 w-full rounded-lg" />
            <div className="flex items-center gap-2">
              <Skeleton className="h-4 w-12 shrink-0" />
              <Skeleton className="h-8 flex-1 rounded-lg" />
              <Skeleton className="h-4 w-8 shrink-0" />
            </div>
          </div>
          <div className="flex-1 overflow-y-auto p-4 space-y-3 dashboard-scrollbar">
            {Array.from({ length: 5 }).map((_, i) => (
              <PositionCardSkeleton key={i} />
            ))}
          </div>
        </div>

        {/* ── RIGHT: Candidates ── */}
        <div className="flex-1 flex flex-col overflow-hidden bg-surface">
          <div className="px-5 py-4 border-b border-border shrink-0">
            <div className="flex items-center gap-2">
              <Skeleton className="size-4 shrink-0" />
              <Skeleton className="h-4 w-32" />
            </div>
          </div>
          <div className="flex-1 flex flex-col items-center justify-center gap-3 p-8">
            <Skeleton className="size-10 rounded-full" />
            <Skeleton className="h-4 w-64" />
            <Skeleton className="h-3 w-80" />
          </div>
        </div>
      </div>
    </div>
  );
}
