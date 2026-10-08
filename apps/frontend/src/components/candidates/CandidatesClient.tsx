"use client";

import { useEffect, useRef, useState } from "react";
import type {
  ApiCandidate,
  CandidateFilters,
  CandidateReferrerOption,
  RecruiterOption,
} from "@/types";
import {
  clientDeleteCandidate,
  clientFetchCandidates,
  clientFetchCandidateReferees,
} from "@/lib/api/candidates.client";
import { apiErrorMessage, useApiFetch } from "@/lib/api";
import {
  fetchReviewLeads,
  recruiterAcceptLead,
  recruiterRejectLead,
  type IntakeLead,
  type IntakeRejectReason,
} from "@/lib/api/intake";
import { useCurrentUser } from "@/hooks/useCurrentUser";
import { useToast } from "@/components/ui/Toast";
import CandidateFilterBar from "./CandidateFilterBar";
import CandidateCard from "./CandidateCard";
import CandidateDrawer from "./CandidateDrawer";
import AddCandidateForm from "./AddCandidateForm";
import BulkUploadDrawer from "./BulkUploadDrawer";
import ReviewLeadCard from "./ReviewLeadCard";
import CandidateCardSkeleton from "./skeletons/CandidateCardSkeleton";

const PAGE_SIZE = 50;

type Tab = "candidates" | "review";

interface Props {
  initialCandidates: ApiCandidate[];
  initialTotal: number;
  availableTags: string[];
  availableRoles: string[];
  recruiters?: RecruiterOption[];
  /** Start with the add-candidate form open (the dashboard's shortcut). */
  openAdd?: boolean;
}

const drawerStyle = {
  background: "var(--color-surface-val)",
  border: "1px solid var(--color-border-val)",
};

const selectStyle = {
  background: "var(--color-canvas-val)",
  color: "var(--color-text-primary)",
  border: "1px solid var(--color-border-val)",
};

/**
 * The Candidate Directory: two tabs.
 *
 * Candidates — everyone APPROVED, except people still waiting in a recruiter's
 * Review tab. Un-actioned (PENDING) people are not here at all: they live on the
 * Leads page until a telecaller screens them.
 *
 * Review — leads a telecaller screened and an admin handed to a team, waiting
 * on the recruiter the team's round-robin picked. A recruiter sees their own;
 * a maintainer or admin sees everyone's and may decide on a recruiter's behalf.
 * Accept moves the person into the Candidates tab; reject archives them.
 */
export default function CandidatesClient({
  initialCandidates,
  initialTotal,
  availableTags,
  availableRoles = [],
  recruiters = [],
  openAdd = false,
}: Readonly<Props>) {
  const { isMaintainer } = useCurrentUser();
  const toast = useToast();
  const apiFetch = useApiFetch();
  const [activeTab, setActiveTab] = useState<Tab>("candidates");

  // ── Candidates tab ───────────────────────────────────────────────────────
  const [candidates, setCandidates] = useState<ApiCandidate[]>(initialCandidates);
  const [total, setTotal] = useState(initialTotal);
  const [page, setPage] = useState(1);
  const [activeFilters, setActiveFilters] = useState<Partial<CandidateFilters>>({});
  const [refereeId, setRefereeId] = useState("");
  const [referees, setReferees] = useState<CandidateReferrerOption[]>([]);
  const [loading, setLoading] = useState(false);
  const [loadingMore, setLoadingMore] = useState(false);
  const [showAddForm, setShowAddForm] = useState(openAdd);
  const [showBulkUpload, setShowBulkUpload] = useState(false);
  const [selectedCandidate, setSelectedCandidate] = useState<ApiCandidate | null>(null);
  // Search and referee changes fire a request each, undebounced, so two can be
  // in flight at once and resolve out of order. Only the newest may write.
  const requestRef = useRef(0);

  // ── Review tab ───────────────────────────────────────────────────────────
  // Loaded on mount rather than on first open, so the tab can show its count.
  const [reviewLeads, setReviewLeads] = useState<IntakeLead[] | null>(null);
  const [reviewRecruiterId, setReviewRecruiterId] = useState("");
  const [busyLeadId, setBusyLeadId] = useState<string | null>(null);
  const reviewRequestRef = useRef(0);

  function query(filters: Partial<CandidateFilters>, referee: string, nextPage: number) {
    return {
      ...filters,
      referee_id: referee || undefined,
      exclude_in_review: true,
      page: nextPage,
      limit: PAGE_SIZE,
    };
  }

  async function loadCandidates(
    filters: Partial<CandidateFilters> = activeFilters,
    referee: string = refereeId,
  ) {
    const requestId = ++requestRef.current;
    setLoading(true);
    try {
      const data = await clientFetchCandidates(query(filters, referee, 1));
      if (requestId !== requestRef.current) return;
      setCandidates(data.items ?? []);
      setTotal(data.meta?.total ?? 0);
      setPage(1);
    } catch {
      if (requestId !== requestRef.current) return;
      setCandidates([]);
      setTotal(0);
      setPage(1);
    } finally {
      if (requestId === requestRef.current) setLoading(false);
    }
  }

  async function loadReview(recruiterId: string = reviewRecruiterId) {
    const requestId = ++reviewRequestRef.current;
    try {
      const leads = await fetchReviewLeads(apiFetch, recruiterId || undefined);
      if (requestId === reviewRequestRef.current) setReviewLeads(leads);
    } catch (err) {
      if (requestId !== reviewRequestRef.current) return;
      setReviewLeads([]);
      toast(apiErrorMessage(err, "Could not load leads to review."), "error");
    }
  }

  useEffect(() => {
    // The server render already filled the Candidates tab, so only the two
    // side lists are fetched here.
    clientFetchCandidateReferees()
      .then(setReferees)
      .catch(() => setReferees([]));
    const requestId = ++reviewRequestRef.current;
    fetchReviewLeads(apiFetch)
      .then((leads) => {
        if (requestId === reviewRequestRef.current) setReviewLeads(leads);
      })
      .catch((err: unknown) => {
        if (requestId !== reviewRequestRef.current) return;
        setReviewLeads([]);
        toast(apiErrorMessage(err, "Could not load leads to review."), "error");
      });
  }, [apiFetch, toast]);

  function handleFilterChange(filters: Partial<CandidateFilters>, nextRefereeId?: string) {
    setActiveFilters(filters);
    const referee = nextRefereeId ?? refereeId;
    if (nextRefereeId !== undefined) setRefereeId(nextRefereeId);
    void loadCandidates(filters, referee);
  }

  function handleRefereeChange(nextRefereeId: string) {
    setRefereeId(nextRefereeId);
    void loadCandidates(activeFilters, nextRefereeId);
  }

  /** Referee badge "View all referrals" — filters the Candidates tab to them. */
  function handleViewReferee(nextRefereeId: string) {
    setActiveTab("candidates");
    handleRefereeChange(nextRefereeId);
  }

  async function handleLoadMore() {
    const nextPage = page + 1;
    const requestId = requestRef.current;
    setLoadingMore(true);
    try {
      const data = await clientFetchCandidates(query(activeFilters, refereeId, nextPage));
      // A filter change while this was in flight replaced the list underneath
      // it; appending page N of the old query onto page 1 of the new one is
      // worse than dropping it.
      if (requestId !== requestRef.current) return;
      setCandidates((prev) => [...prev, ...(data.items ?? [])]);
      setTotal(data.meta?.total ?? total);
      setPage(nextPage);
    } catch {
      // leave existing candidates as-is
    } finally {
      setLoadingMore(false);
    }
  }

  function hasFilters() {
    return !!refereeId || Object.values(activeFilters).some((v) => v !== undefined && v !== "");
  }

  function handleCandidateAdded(candidate: ApiCandidate) {
    if (!hasFilters() && page === 1) {
      setCandidates((prev) => [candidate, ...prev]);
      setTotal((t) => t + 1);
    } else {
      void loadCandidates();
    }
    setShowAddForm(false);
  }

  function handleCandidateUpdated(updated: ApiCandidate) {
    setCandidates((prev) => prev.map((c) => (c.id === updated.id ? updated : c)));
    setSelectedCandidate(updated);
  }

  async function handleDeleteCandidate(id: string) {
    try {
      await clientDeleteCandidate(id);
      if (candidates.some((c) => c.id === id)) {
        setCandidates((prev) => prev.filter((c) => c.id !== id));
        setTotal((t) => Math.max(0, t - 1));
      }
      if (selectedCandidate?.id === id) setSelectedCandidate(null);
    } catch (err) {
      toast(err instanceof Error ? err.message : "Failed to delete candidate", "error");
    }
  }

  function handleBulkComplete() {
    void loadCandidates();
    setShowBulkUpload(false);
  }

  // ── Review actions ───────────────────────────────────────────────────────

  function dropReviewLead(id: string) {
    setReviewLeads((prev) => prev?.filter((l) => l.id !== id) ?? prev);
  }

  async function handleAcceptLead(lead: IntakeLead) {
    setBusyLeadId(lead.id);
    try {
      await recruiterAcceptLead(apiFetch, lead.id);
    } catch (err) {
      toast(apiErrorMessage(err, "Could not accept the lead."), "error");
      // Someone else may have decided it; the reload shows what is left.
      void loadReview();
      return;
    } finally {
      setBusyLeadId(null);
    }
    dropReviewLead(lead.id);
    toast(`${lead.full_name} moved to Candidates`, "success");
    // They are in the Candidates tab now; refetch rather than splice, since the
    // card there needs the full candidate row, not the lead.
    void loadCandidates();
  }

  async function handleRejectLead(
    lead: IntakeLead,
    reason: IntakeRejectReason | undefined,
    notes: string,
  ) {
    setBusyLeadId(lead.id);
    try {
      await recruiterRejectLead(apiFetch, lead.id, reason, notes);
    } catch (err) {
      toast(apiErrorMessage(err, "Could not reject the lead."), "error");
      void loadReview();
      return;
    } finally {
      setBusyLeadId(null);
    }
    dropReviewLead(lead.id);
    toast(`${lead.full_name} rejected and archived`, "success");
  }

  async function handleViewLeadProfile(lead: IntakeLead) {
    try {
      setSelectedCandidate(await apiFetch<ApiCandidate>(`/api/v1/candidates/${lead.candidate_id}`));
    } catch (err) {
      toast(apiErrorMessage(err, "Could not open the profile."), "error");
    }
  }

  function handleReviewRecruiterChange(recruiterId: string) {
    setReviewRecruiterId(recruiterId);
    setReviewLeads(null);
    void loadReview(recruiterId);
  }

  const hasMore = candidates.length < total;
  const candidateLabel = total === 1 ? "1 candidate" : `${total} candidates`;
  const countLabel = hasMore ? `Showing ${candidates.length} of ${candidateLabel}` : candidateLabel;
  const reviewCount = reviewLeads?.length ?? 0;
  const reviewLabel =
    reviewLeads === null
      ? "Loading…"
      : `${reviewCount} ${reviewCount === 1 ? "lead" : "leads"} waiting for a decision`;

  return (
    <div className="flex flex-col gap-4">
      <div className="flex gap-1 border-b" style={{ borderColor: "var(--color-border-val)" }}>
        {(
          [
            { key: "candidates", label: "Candidates" },
            { key: "review", label: reviewCount > 0 ? `Review (${reviewCount})` : "Review" },
          ] as const
        ).map((tab) => (
          <button
            key={tab.key}
            type="button"
            onClick={() => setActiveTab(tab.key)}
            className="px-4 py-2 text-sm font-medium transition-colors"
            style={{
              color:
                activeTab === tab.key ? "var(--color-text-primary)" : "var(--color-text-secondary)",
              borderBottom:
                activeTab === tab.key ? "2px solid var(--color-yellow)" : "2px solid transparent",
            }}
          >
            {tab.label}
          </button>
        ))}
      </div>

      <div className="flex flex-wrap items-center justify-between gap-3">
        <span className="text-sm" style={{ color: "var(--color-text-secondary)" }}>
          {activeTab === "candidates" ? countLabel : reviewLabel}
        </span>
        {activeTab === "candidates" && (
          <div className="flex gap-2">
            <button
              type="button"
              onClick={() => {
                setShowBulkUpload((v) => !v);
                setShowAddForm(false);
              }}
              className="rounded-lg px-3 py-1.5 text-sm font-medium"
              style={{
                background: "var(--color-surface-val)",
                color: "var(--color-text-primary)",
                border: "1px solid var(--color-border-val)",
              }}
            >
              Bulk Upload
            </button>
            <button
              type="button"
              onClick={() => {
                setShowAddForm((v) => !v);
                setShowBulkUpload(false);
              }}
              className="rounded-lg px-3 py-1.5 text-sm font-semibold"
              style={{ background: "var(--color-yellow)", color: "#002348" }}
            >
              + Add Candidate
            </button>
          </div>
        )}
        {activeTab === "review" && isMaintainer && (
          <select
            value={reviewRecruiterId}
            onChange={(e) => handleReviewRecruiterChange(e.target.value)}
            className="rounded-lg px-3 py-1.5 text-sm outline-none"
            style={selectStyle}
            aria-label="Filter review leads by recruiter"
          >
            <option value="">All Recruiters</option>
            {recruiters.map((r) => (
              <option key={r.id} value={r.id}>
                {r.name}
              </option>
            ))}
          </select>
        )}
      </div>

      {activeTab === "candidates" && (
        <>
          <CandidateFilterBar
            availableTags={availableTags}
            availableRoles={availableRoles}
            recruiters={recruiters}
            onFilterChange={handleFilterChange}
            referees={referees}
            refereeId={refereeId}
            onRefereeChange={handleRefereeChange}
          />

          {showAddForm && (
            <div className="rounded-lg" style={drawerStyle}>
              <AddCandidateForm
                onSuccess={handleCandidateAdded}
                onCancel={() => setShowAddForm(false)}
              />
            </div>
          )}

          {showBulkUpload && (
            <div className="rounded-lg" style={drawerStyle}>
              <BulkUploadDrawer
                onComplete={handleBulkComplete}
                onClose={() => setShowBulkUpload(false)}
              />
            </div>
          )}

          {loading && (
            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
              {Array.from({ length: 8 }).map((_, i) => (
                <CandidateCardSkeleton key={i} />
              ))}
            </div>
          )}
          {!loading && candidates.length === 0 && (
            <div
              className="py-12 text-center text-sm"
              style={{ color: "var(--color-text-secondary)" }}
            >
              No candidates found. Adjust your filters or add a new candidate.
            </div>
          )}
          {!loading && candidates.length > 0 && (
            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
              {candidates.map((c) => (
                <CandidateCard
                  key={c.id}
                  candidate={c}
                  onClick={() => setSelectedCandidate(c)}
                  isMaintainer={isMaintainer}
                  onDelete={handleDeleteCandidate}
                  onViewReferee={handleViewReferee}
                />
              ))}
            </div>
          )}

          {!loading && hasMore && (
            <div className="flex justify-center pt-2">
              <button
                type="button"
                onClick={handleLoadMore}
                disabled={loadingMore}
                className="rounded-lg px-5 py-2 text-sm font-medium"
                style={{
                  background: "var(--color-surface-val)",
                  color: "var(--color-text-primary)",
                  border: "1px solid var(--color-border-val)",
                  opacity: loadingMore ? 0.6 : 1,
                }}
              >
                {loadingMore ? "Loading…" : `Load more (${total - candidates.length} remaining)`}
              </button>
            </div>
          )}
        </>
      )}

      {activeTab === "review" && (
        <>
          {reviewLeads === null && (
            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
              {Array.from({ length: 4 }).map((_, i) => (
                <CandidateCardSkeleton key={i} />
              ))}
            </div>
          )}
          {reviewLeads?.length === 0 && (
            <div
              className="py-12 text-center text-sm"
              style={{ color: "var(--color-text-secondary)" }}
            >
              Nothing to review. Leads a telecaller screens and an admin assigns to your team will
              show up here.
            </div>
          )}
          {reviewLeads && reviewLeads.length > 0 && (
            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
              {reviewLeads.map((lead) => (
                <ReviewLeadCard
                  key={lead.id}
                  lead={lead}
                  busy={busyLeadId === lead.id}
                  showRecruiter={isMaintainer}
                  onAccept={() => handleAcceptLead(lead)}
                  onReject={(reason, notes) => handleRejectLead(lead, reason, notes)}
                  onViewProfile={() => handleViewLeadProfile(lead)}
                />
              ))}
            </div>
          )}
        </>
      )}

      <CandidateDrawer
        candidate={selectedCandidate}
        onClose={() => setSelectedCandidate(null)}
        onUpdate={handleCandidateUpdated}
        isMaintainer={isMaintainer}
      />
    </div>
  );
}
