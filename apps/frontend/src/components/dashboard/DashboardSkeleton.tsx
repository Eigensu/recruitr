import { cn } from "@/lib/utils";

function SkeletonBlock({ className }: { className?: string }) {
  return <div className={cn("animate-pulse rounded-md bg-white/10", className)} />;
}

export function KpiGridSkeleton() {
  return (
    <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 xl:grid-cols-4">
      {Array.from({ length: 8 }, (_, index) => (
        <div key={index} className="rounded-lg border border-white/10 bg-white/[0.04] p-4">
          <div className="flex justify-between">
            <SkeletonBlock className="h-3 w-28" />
            <SkeletonBlock className="size-10" />
          </div>
          <SkeletonBlock className="mt-5 h-9 w-16" />
          <SkeletonBlock className="mt-5 h-4 w-full" />
        </div>
      ))}
    </div>
  );
}

export function PanelSkeleton({ rows = 5, className }: { rows?: number; className?: string }) {
  return (
    <div className={cn("rounded-lg border border-white/10 bg-white/[0.04] p-5", className)}>
      <SkeletonBlock className="h-5 w-40" />
      <SkeletonBlock className="mt-2 h-3 w-56 max-w-full" />
      <div className="mt-6 space-y-3">
        {Array.from({ length: rows }, (_, index) => (
          <SkeletonBlock key={index} className="h-9 w-full" />
        ))}
      </div>
    </div>
  );
}
