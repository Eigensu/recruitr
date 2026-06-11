import { getCandidates, getCandidateTags } from "@/lib/api/candidates";
import CandidatesClient from "@/components/candidates/CandidatesClient";
import type { Candidate } from "@/types";

export default async function CandidatesPage() {
  let initialCandidates: Candidate[] = [];
  let availableTags: string[] = [];

  try {
    [initialCandidates, availableTags] = await Promise.all([
      getCandidates({ page: 1, limit: 50 }),
      getCandidateTags(),
    ]);
  } catch {
    // Backend unreachable during SSR — render empty; client can retry via filters.
  }

  return (
    <div
      className="min-h-full px-4 py-5 sm:px-6 lg:px-8"
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

        <CandidatesClient initialCandidates={initialCandidates} availableTags={availableTags} />
      </div>
    </div>
  );
}
