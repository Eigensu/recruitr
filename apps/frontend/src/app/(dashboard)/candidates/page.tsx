import {
  getCandidates,
  getCandidateTags,
  getCandidateRoles,
  getRecruiters,
} from "@/lib/api/candidates.server";
import CandidatesClient from "@/components/candidates/CandidatesClient";
import type { ApiCandidate, RecruiterOption } from "@/types";

export default async function CandidatesPage({
  searchParams,
}: Readonly<{
  searchParams: Promise<{ [key: string]: string | string[] | undefined }>;
}>) {
  // "?add=1" — the dashboard's Add candidate shortcut — opens the form.
  const openAdd = (await searchParams).add === "1";
  let initialCandidates: ApiCandidate[] = [];
  let initialTotal = 0;
  let availableTags: string[] = [];
  let availableRoles: string[] = [];
  let recruiters: RecruiterOption[] = [];

  try {
    const [candidatePage, tags, roles] = await Promise.all([
      // Leaves out anyone still waiting in a recruiter's Review tab; PENDING
      // people are on the Leads page, not here.
      getCandidates({ page: 1, limit: 50, exclude_in_review: true }),
      getCandidateTags(),
      getCandidateRoles().catch((err) => {
        console.error("Failed to load candidate roles:", err);
        return [];
      }),
    ]);
    initialCandidates = candidatePage.items ?? [];
    initialTotal = candidatePage.meta?.total ?? initialCandidates.length;
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
          openAdd={openAdd}
          initialCandidates={initialCandidates}
          initialTotal={initialTotal}
          availableTags={availableTags}
          availableRoles={availableRoles}
          recruiters={recruiters}
        />
      </div>
    </div>
  );
}
