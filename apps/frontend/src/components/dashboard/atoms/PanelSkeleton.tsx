import { cn } from "@/lib/utils";
import { SkeletonBlock } from "./SkeletonBlock";

interface PanelSkeletonProps {
  rows?: number;
  className?: string;
}

export function PanelSkeleton({ rows = 5, className }: PanelSkeletonProps) {
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
