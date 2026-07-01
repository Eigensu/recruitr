import { Skeleton } from "@/components/common/skeletons/Skeleton";

export default function CandidateCardSkeleton() {
  return (
    <div className="relative flex flex-col h-full rounded-2xl bg-surface-panel border border-border overflow-hidden">
      <div className="h-0.5 shrink-0 bg-surface-2" />
      <div className="flex flex-col h-full p-5 gap-4">
        {/* Identity row */}
        <div className="flex items-start gap-3.5">
          <Skeleton className="size-10 rounded-xl shrink-0" />
          <div className="flex-1 pt-0.5 space-y-2">
            <Skeleton className="h-4 w-3/4" />
            <Skeleton className="h-3 w-1/2" />
          </div>
        </div>

        {/* Skills */}
        <div className="flex flex-wrap gap-1.5">
          <Skeleton className="h-5 w-12 rounded-full" />
          <Skeleton className="h-5 w-16 rounded-full" />
          <Skeleton className="h-5 w-14 rounded-full" />
        </div>

        {/* Contact footer */}
        <div className="mt-auto pt-3.5 border-t border-border/40 flex items-center justify-between gap-2">
          <div className="flex items-center gap-1.5 flex-1">
            <Skeleton className="size-3.5 rounded" />
            <Skeleton className="h-3 w-2/3" />
          </div>
          <Skeleton className="h-4 w-8 rounded" />
        </div>
      </div>
    </div>
  );
}
