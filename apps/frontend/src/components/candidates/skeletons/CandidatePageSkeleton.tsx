import { Skeleton } from "@/components/common/skeletons/Skeleton";
import CandidateCardSkeleton from "@/components/candidates/skeletons/CandidateCardSkeleton";

export default function CandidatePageSkeleton() {
  return (
    <div
      className="min-h-full px-4 py-5 sm:px-6 lg:px-8 bg-canvas"
      style={{ background: "var(--color-canvas)", color: "var(--color-text-primary)" }}
    >
      <div className="mx-auto flex w-full max-w-400 flex-col gap-5">
        <header className="pb-4" style={{ borderBottom: "1px solid var(--color-border-val)" }}>
          <p
            className="text-xs font-bold uppercase tracking-normal"
            style={{ color: "var(--color-text-secondary)" }}
          >
            Talent Pool
          </p>
          <h1
            className="mt-2 font-heading text-4xl leading-tight sm:text-5xl"
            style={{ color: "var(--color-text-primary)" }}
          >
            Candidate Directory
          </h1>
        </header>

        <div className="flex flex-col gap-4">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <Skeleton className="h-4 w-32" />
            <div className="flex gap-2">
              <Skeleton className="h-8 w-24 rounded-lg" />
              <Skeleton className="h-8 w-32 rounded-lg" />
            </div>
          </div>

          {/* Filter Bar Skeleton */}
          <div className="flex flex-wrap items-center gap-3 rounded-lg p-3 bg-surface border border-border">
            <Skeleton className="h-8 min-w-[200px] flex-1 rounded-lg" />
            <Skeleton className="h-8 w-32 rounded-lg" />
            <Skeleton className="h-8 w-24 rounded-lg" />
            <Skeleton className="h-8 w-28 rounded-lg" />
            <Skeleton className="h-8 w-28 rounded-lg" />
          </div>

          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
            {Array.from({ length: 8 }).map((_, i) => (
              <CandidateCardSkeleton key={i} />
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}
