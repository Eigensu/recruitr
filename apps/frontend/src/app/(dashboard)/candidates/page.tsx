import { getCandidates, getCandidateTags } from "@/lib/api/candidates.server";
import CandidatesClient from "@/components/candidates/CandidatesClient";
import type { ApiCandidate } from "@/types";

export default async function CandidatesPage() {
  let initialCandidates: ApiCandidate[] = [];
  let initialTotal = 0;
  let initialPendingCandidates: ApiCandidate[] = [];
  let availableTags: string[] = [];

  try {
    const [candidatePage, pendingPage, tags] = await Promise.all([
      getCandidates({ page: 1, limit: 50 }),
      getCandidates({ page: 1, limit: 50, status: "PENDING" }),
      getCandidateTags(),
    ]);
    initialCandidates = candidatePage.items ?? [];
    initialTotal = candidatePage.meta?.total ?? initialCandidates.length;
    initialPendingCandidates = pendingPage.items ?? [];
    availableTags = tags;
  } catch (err) {
    console.error("Failed to load candidates page data during SSR:", err);
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

        <CandidatesClient
          initialCandidates={initialCandidates}
          initialTotal={initialTotal}
          initialPendingCandidates={initialPendingCandidates}
          availableTags={availableTags}
        />
      </div>
    </div>
  );
}
