import { SkeletonBlock } from "@/components/dashboard/atoms/SkeletonBlock";

export function DashboardSkeleton() {
  return (
    <div className="space-y-6">
      {/* KPI Grid */}
      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 xl:grid-cols-4">
        {Array.from({ length: 8 }, (_, index) => (
          <div key={index} className="rounded-lg bg-white/8 shadow-sm p-4">
            <div className="flex justify-between">
              <SkeletonBlock className="h-3 w-28" />
              <SkeletonBlock className="size-10" />
            </div>
            <SkeletonBlock className="mt-5 h-9 w-16" />
            <SkeletonBlock className="mt-5 h-4 w-full" />
          </div>
        ))}
      </div>

      {/* Main panels */}
      <div className="grid gap-6 lg:grid-cols-2">
        <SkeletonPanelSkeleton rows={5} />
        <SkeletonPanelSkeleton rows={5} />
      </div>

      {/* Full width panel */}
      <SkeletonPanelSkeleton rows={8} />
    </div>
  );
}

function SkeletonPanelSkeleton({ rows = 5 }: { rows?: number }) {
  return (
    <div className="rounded-lg bg-white/8 shadow-sm p-5">
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
