"use client";

import { useState } from "react";
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
  clientApproveCandidate,
  clientRejectCandidate,
} from "@/lib/api/candidates.client";
import { useCurrentUser } from "@/hooks/useCurrentUser";
import { useToast } from "@/components/ui/Toast";
import CandidateFilterBar from "./CandidateFilterBar";
import CandidateCard from "./CandidateCard";
import CandidateDrawer from "./CandidateDrawer";
import AddCandidateForm from "./AddCandidateForm";
import BulkUploadDrawer from "./BulkUploadDrawer";
import CandidateCardSkeleton from "./skeletons/CandidateCardSkeleton";

const PAGE_SIZE = 50;

interface Props {
  initialCandidates: ApiCandidate[];
  initialTotal: number;
  initialPendingCandidates?: ApiCandidate[];
  availableTags: string[];
  availableRoles: string[];
  recruiters?: RecruiterOption[];
}

const drawerStyle = {
  background: "var(--color-surface-val)",
  border: "1px solid var(--color-border-val)",
};

export default function CandidatesClient({
  initialCandidates,
  initialTotal,
  initialPendingCandidates = [],
  availableTags,
  availableRoles = [],
  recruiters = [],
}: Readonly<Props>) {
  const { isMaintainer } = useCurrentUser();
  const toast = useToast();
  const [candidates, setCandidates] = useState<ApiCandidate[]>(initialCandidates);
  const [pendingCandidates, setPendingCandidates] =
    useState<ApiCandidate[]>(initialPendingCandidates);
  const [total, setTotal] = useState(initialTotal);
  const [page, setPage] = useState(1);
  const [activeFilters, setActiveFilters] = useState<Partial<CandidateFilters>>({});
  const [loading, setLoading] = useState(false);
  const [loadingMore, setLoadingMore] = useState(false);
  const [showAddForm, setShowAddForm] = useState(false);
  const [showBulkUpload, setShowBulkUpload] = useState(false);
  const [selectedCandidate, setSelectedCandidate] = useState<ApiCandidate | null>(null);

  // ── External Candidates tab ──────────────────────────────────────────────
  // Referrals, public-form applicants, and manually-tagged external candidates
  // — pending and approved together, lazy-loaded the first time the tab opens
  // so it never slows down the default "All Candidates" load.
  const [activeTab, setActiveTab] = useState<"all" | "external">("all");
  const [externalCandidates, setExternalCandidates] = useState<ApiCandidate[]>([]);
  const [externalLoading, setExternalLoading] = useState(false);
  const [externalLoaded, setExternalLoaded] = useState(false);
  const [externalFilters, setExternalFilters] = useState<Partial<CandidateFilters>>({});
  const [externalRefereeId, setExternalRefereeId] = useState("");
  const [externalReferees, setExternalReferees] = useState<CandidateReferrerOption[]>([]);

  async function handleFilterChange(filters: Partial<CandidateFilters>) {
    setLoading(true);
    setActiveFilters(filters);
    setPage(1);
    try {
      const data = await clientFetchCandidates({ ...filters, page: 1, limit: PAGE_SIZE });
      setCandidates(data.items ?? []);
      setTotal(data.meta?.total ?? 0);
    } catch {
      setCandidates([]);
      setTotal(0);
    } finally {
      setLoading(false);
    }
  }

  async function handleLoadMore() {
    const nextPage = page + 1;
    setLoadingMore(true);
    try {
      const data = await clientFetchCandidates({
        ...activeFilters,
        page: nextPage,
        limit: PAGE_SIZE,
      });
      setCandidates((prev) => [...prev, ...(data.items ?? [])]);
      setTotal(data.meta?.total ?? total);
      setPage(nextPage);
    } catch {
      // leave existing candidates as-is
    } finally {
      setLoadingMore(false);
    }
  }

  async function loadExternalCandidates(
    overrides: { filters?: Partial<CandidateFilters>; refereeId?: string } = {},
  ) {
    const filters = overrides.filters ?? externalFilters;
    const refereeId = overrides.refereeId ?? externalRefereeId;
    setExternalLoading(true);
    try {
      const base = {
        ...filters,
        source: "external" as const,
        referee_id: refereeId || undefined,
        page: 1,
        limit: 50,
      };
      const [pendingPage, approvedPage] = await Promise.all([
        clientFetchCandidates({ ...base, status: "PENDING" }),
        clientFetchCandidates({ ...base, status: "APPROVED" }),
      ]);
      setExternalCandidates([...(pendingPage.items ?? []), ...(approvedPage.items ?? [])]);
    } catch {
      setExternalCandidates([]);
    } finally {
      setExternalLoading(false);
      setExternalLoaded(true);
    }
  }

  async function loadExternalReferees() {
    try {
      setExternalReferees(await clientFetchCandidateReferees());
    } catch {
      setExternalReferees([]);
    }
  }

  function handleTabChange(tab: "all" | "external") {
    setActiveTab(tab);
    if (tab === "external" && !externalLoaded) {
      loadExternalCandidates();
      loadExternalReferees();
    }
  }

  function handleExternalFilterChange(filters: Partial<CandidateFilters>) {
    setExternalFilters(filters);
    loadExternalCandidates({ filters });
  }

  function handleExternalRefereeChange(refereeId: string) {
    setExternalRefereeId(refereeId);
    loadExternalCandidates({ refereeId });
  }

  /** Referee badge "View all referrals" — jumps to the tab and filters to them. */
  function handleViewReferee(refereeId: string) {
    setActiveTab("external");
    setExternalRefereeId(refereeId);
    if (!externalLoaded) loadExternalReferees();
    loadExternalCandidates({ refereeId });
  }

  function handleCandidateAdded(candidate: ApiCandidate) {
    const hasFilters = Object.values(activeFilters).some((v) => v !== undefined && v !== "");
    if (!hasFilters && page === 1) {
      setCandidates((prev) => [candidate, ...prev]);
      setTotal((t) => t + 1);
    } else {
      clientFetchCandidates({ ...activeFilters, page: 1, limit: PAGE_SIZE })
        .then((data) => {
          setCandidates(data.items ?? []);
          setTotal(data.meta?.total ?? 0);
          setPage(1);
        })
        .catch(() => undefined);
    }
    setShowAddForm(false);
  }

  function handleCandidateUpdated(updated: ApiCandidate) {
    setCandidates((prev) => prev.map((c) => (c.id === updated.id ? updated : c)));
    // Pending applications are edited in the drawer before being approved, so
    // that list needs the same refresh — otherwise the card keeps the old data.
    setPendingCandidates((prev) => prev.map((c) => (c.id === updated.id ? updated : c)));
    setExternalCandidates((prev) => prev.map((c) => (c.id === updated.id ? updated : c)));
    setSelectedCandidate(updated);
  }

  async function handleDeleteCandidate(id: string) {
    try {
      await clientDeleteCandidate(id);

      const isApproved = candidates.some((c) => c.id === id);
      if (isApproved) {
        setCandidates((prev) => prev.filter((c) => c.id !== id));
        setTotal((t) => Math.max(0, t - 1));
      }

      setPendingCandidates((prev) => prev.filter((c) => c.id !== id));
      setExternalCandidates((prev) => prev.filter((c) => c.id !== id));
      if (selectedCandidate?.id === id) setSelectedCandidate(null);
    } catch (err) {
      toast(err instanceof Error ? err.message : "Failed to delete candidate", "error");
    }
  }

  async function handleApproveCandidate(id: string) {
    // Only the approval itself decides success or failure. Folding the refresh
    // below into the same try reported an approval that had already landed as
    // "Failed to approve" whenever the follow-up fetch happened to fail.
    let updated: ApiCandidate;
    try {
      updated = await clientApproveCandidate(id);
    } catch (err) {
      toast(err instanceof Error ? err.message : "Failed to approve candidate", "error");
      return;
    }

    setPendingCandidates((prev) => prev.filter((c) => c.id !== id));
    // In place, not filtered out — an approved external candidate stays on
    // the External Candidates tab, just without the Approve/Reject buttons.
    setExternalCandidates((prev) => prev.map((c) => (c.id === id ? updated : c)));
    // Only on success — a failed approve keeps the drawer open on the details.
    if (selectedCandidate?.id === id) setSelectedCandidate(null);
    toast("Candidate approved successfully", "success");

    const hasFilters = Object.values(activeFilters).some((v) => v !== undefined && v !== "");
    if (!hasFilters && page === 1) {
      setCandidates((prev) => [updated, ...prev]);
      setTotal((t) => t + 1);
      return;
    }
    try {
      const data = await clientFetchCandidates({ ...activeFilters, page: 1, limit: PAGE_SIZE });
      setCandidates(data.items ?? []);
      setTotal(data.meta?.total ?? 0);
      setPage(1);
    } catch {
      // The approval stands; the filtered list is just one candidate stale.
    }
  }

  async function handleRejectCandidate(id: string) {
    try {
      await clientRejectCandidate(id);
      setPendingCandidates((prev) => prev.filter((c) => c.id !== id));
      // Rejected candidates drop off entirely — neither PENDING nor APPROVED
      // status query picks them back up, same as the main pending section.
      setExternalCandidates((prev) => prev.filter((c) => c.id !== id));
      if (selectedCandidate?.id === id) setSelectedCandidate(null);
      toast("Candidate rejected", "success");
    } catch (err) {
      toast(err instanceof Error ? err.message : "Failed to reject candidate", "error");
    }
  }

  function handleBulkComplete() {
    clientFetchCandidates({ page: 1, limit: PAGE_SIZE })
      .then((data) => {
        setCandidates(data.items ?? []);
        setTotal(data.meta?.total ?? 0);
        setPage(1);
      })
      .catch(() => undefined);
    setShowBulkUpload(false);
  }

  const hasMore = candidates.length < total;
  const candidateLabel = total === 1 ? "1 candidate" : `${total} candidates`;
  const countLabel = hasMore ? `Showing ${candidates.length} of ${candidateLabel}` : candidateLabel;

  const externalLabel =
    externalCandidates.length === 1 ? "1 candidate" : `${externalCandidates.length} candidates`;

  return (
    <div className="flex flex-col gap-4">
      <div className="flex gap-1 border-b" style={{ borderColor: "var(--color-border-val)" }}>
        {(
          [
            { key: "all", label: "All Candidates" },
            { key: "external", label: "External Candidates" },
          ] as const
        ).map((tab) => (
          <button
            key={tab.key}
            type="button"
            onClick={() => handleTabChange(tab.key)}
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
          {activeTab === "all" ? countLabel : externalLabel}
        </span>
        {activeTab === "all" && (
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
      </div>

      {activeTab === "all" && (
        <>
          <CandidateFilterBar
            availableTags={availableTags}
            availableRoles={availableRoles}
            recruiters={recruiters}
            onFilterChange={handleFilterChange}
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

          {pendingCandidates.length > 0 && !loading && (
            <div className="mb-6">
              <h2 className="mb-3 text-lg font-bold text-yellow-600">
                Pending Applications ({pendingCandidates.length})
              </h2>
              <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
                {pendingCandidates.map((c) => (
                  <CandidateCard
                    key={c.id}
                    candidate={c}
                    onClick={() => setSelectedCandidate(c)}
                    isMaintainer={isMaintainer}
                    onDelete={handleDeleteCandidate}
                    onApprove={() => handleApproveCandidate(c.id)}
                    onReject={() => handleRejectCandidate(c.id)}
                    onViewReferee={handleViewReferee}
                  />
                ))}
              </div>
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

      {activeTab === "external" && (
        <>
          <CandidateFilterBar
            availableTags={availableTags}
            availableRoles={availableRoles}
            recruiters={recruiters}
            onFilterChange={handleExternalFilterChange}
            mode="external"
            referees={externalReferees}
            refereeId={externalRefereeId}
            onRefereeChange={handleExternalRefereeChange}
          />

          {externalLoading && (
            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
              {Array.from({ length: 8 }).map((_, i) => (
                <CandidateCardSkeleton key={i} />
              ))}
            </div>
          )}
          {!externalLoading && externalCandidates.length === 0 && (
            <div
              className="py-12 text-center text-sm"
              style={{ color: "var(--color-text-secondary)" }}
            >
              No external candidates found. Referrals and public applications will show up here.
            </div>
          )}
          {!externalLoading && externalCandidates.length > 0 && (
            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
              {externalCandidates.map((c) => (
                <CandidateCard
                  key={c.id}
                  candidate={c}
                  onClick={() => setSelectedCandidate(c)}
                  isMaintainer={isMaintainer}
                  onDelete={handleDeleteCandidate}
                  onViewReferee={handleViewReferee}
                  onApprove={
                    c.status === "PENDING" ? () => handleApproveCandidate(c.id) : undefined
                  }
                  onReject={c.status === "PENDING" ? () => handleRejectCandidate(c.id) : undefined}
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
        onApprove={handleApproveCandidate}
        onReject={handleRejectCandidate}
      />
    </div>
  );
}
