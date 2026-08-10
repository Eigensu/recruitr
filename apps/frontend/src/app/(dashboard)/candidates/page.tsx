import {
  getCandidates,
  getCandidateTags,
  getCandidateRoles,
  getRecruiters,
} from "@/lib/api/candidates.server";
import CandidatesClient from "@/components/candidates/CandidatesClient";
import type { ApiCandidate, RecruiterOption } from "@/types";

export default async function CandidatesPage() {
  let initialCandidates: ApiCandidate[] = [];
  let initialTotal = 0;
  let initialPendingCandidates: ApiCandidate[] = [];
  let availableTags: string[] = [];
  let availableRoles: string[] = [];
  let recruiters: RecruiterOption[] = [];

  try {
    const [candidatePage, pendingPage1, tags, roles] = await Promise.all([
      getCandidates({ page: 1, limit: 50 }),
      getCandidates({ page: 1, limit: 50, status: "PENDING" }),
      getCandidateTags(),
      getCandidateRoles().catch((err) => {
        console.error("Failed to load candidate roles:", err);
        return [];
      }),
    ]);
    initialCandidates = candidatePage.items ?? [];
    initialTotal = candidatePage.meta?.total ?? initialCandidates.length;

    let allPending = pendingPage1.items ?? [];
    const pendingMeta = pendingPage1.meta;
    if (pendingMeta && pendingMeta.pages > 1) {
      const promises = [];
      for (let p = 2; p <= pendingMeta.pages; p++) {
        promises.push(getCandidates({ page: p, limit: 50, status: "PENDING" }));
      }
      const restPages = await Promise.all(promises);
      for (const rp of restPages) {
        allPending = allPending.concat(rp.items ?? []);
      }
    }
    initialPendingCandidates = allPending;
    availableTags = tags;
    availableRoles = roles;
  } catch (err) {
    console.error("Failed to load candidates page data during SSR:", err);
  }

  // Separate from the block above on purpose: the recruiter list only feeds one
  // filter dropdown, and losing it should cost that dropdown, not the directory.
  try {
    recruiters = await getRecruiters();
  } catch (err) {
    console.error("Failed to load recruiters for the candidate filter:", err);
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
          availableRoles={availableRoles}
          recruiters={recruiters}
        />
      </div>
    </div>
  );
}
