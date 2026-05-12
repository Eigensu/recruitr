import { SkeletonBlock } from "./SkeletonBlock";

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
