"use client";

import { useRef, useState } from "react";
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
  const [externalTotal, setExternalTotal] = useState(0);
  const [externalPage, setExternalPage] = useState(1);
  const [externalLoading, setExternalLoading] = useState(false);
  const [externalLoadingMore, setExternalLoadingMore] = useState(false);
  const [externalLoaded, setExternalLoaded] = useState(false);
  const [externalFilters, setExternalFilters] = useState<Partial<CandidateFilters>>({});
  const [externalRefereeId, setExternalRefereeId] = useState("");
  const [externalReferees, setExternalReferees] = useState<CandidateReferrerOption[]>([]);
  // Bumped by every external fetch; a response whose id is stale is dropped.
  const externalRequestRef = useRef(0);

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
    // Search and referee changes fire a request each, undebounced, so two can
    // be in flight at once and resolve out of order. Only the newest may write.
    const requestId = ++externalRequestRef.current;
    setExternalLoading(true);
    try {
      const base = {
        ...filters,
        source: "external" as const,
        referee_id: refereeId || undefined,
        page: 1,
        limit: PAGE_SIZE,
      };
      const [pendingPage, approvedPage] = await Promise.all([
        clientFetchCandidates({ ...base, status: "PENDING" }),
        clientFetchCandidates({ ...base, status: "APPROVED" }),
      ]);
      if (requestId !== externalRequestRef.current) return;
      setExternalCandidates([...(pendingPage.items ?? []), ...(approvedPage.items ?? [])]);
      setExternalTotal((pendingPage.meta?.total ?? 0) + (approvedPage.meta?.total ?? 0));
      setExternalPage(1);
      // Success only: handleTabChange reloads while this is false, so setting
      // it in `finally` turned one failed fetch into a tab that stays empty
      // until the page is reloaded.
      setExternalLoaded(true);
    } catch {
      if (requestId !== externalRequestRef.current) return;
      setExternalCandidates([]);
      setExternalTotal(0);
      setExternalPage(1);
    } finally {
      if (requestId === externalRequestRef.current) setExternalLoading(false);
    }
  }

  // PENDING and APPROVED paginate independently server-side, so page N of one
  // can be shorter (or empty) than page N of the other once it runs out —
  // concatenating whatever each returns still converges on the full set.
  async function handleLoadMoreExternal() {
    const nextPage = externalPage + 1;
    const requestId = externalRequestRef.current;
    setExternalLoadingMore(true);
    try {
      const base = {
        ...externalFilters,
        source: "external" as const,
        referee_id: externalRefereeId || undefined,
        page: nextPage,
        limit: PAGE_SIZE,
      };
      const [pendingPage, approvedPage] = await Promise.all([
        clientFetchCandidates({ ...base, status: "PENDING" }),
        clientFetchCandidates({ ...base, status: "APPROVED" }),
      ]);
      // A filter change while this was in flight replaced the list underneath
      // it; appending page N of the old query onto page 1 of the new one is
      // worse than dropping it.
      if (requestId !== externalRequestRef.current) return;
      setExternalCandidates((prev) => [
        ...prev,
        ...(pendingPage.items ?? []),
        ...(approvedPage.items ?? []),
      ]);
      setExternalTotal((pendingPage.meta?.total ?? 0) + (approvedPage.meta?.total ?? 0));
      setExternalPage(nextPage);
    } catch {
      // leave existing external candidates as-is
    } finally {
      setExternalLoadingMore(false);
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

  function handleExternalFilterChange(filters: Partial<CandidateFilters>, refereeId?: string) {
    setExternalFilters(filters);
    if (refereeId !== undefined) setExternalRefereeId(refereeId);
    loadExternalCandidates({ filters, refereeId });
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

      // Same bookkeeping as `total` above: hasMoreExternal compares the loaded
      // rows against this count, so a stale count offers a "Load more" that
      // comes back with nothing.
      const wasExternal = externalCandidates.some((c) => c.id === id);
      setPendingCandidates((prev) => prev.filter((c) => c.id !== id));
      setExternalCandidates((prev) => prev.filter((c) => c.id !== id));
      if (wasExternal) setExternalTotal((t) => Math.max(0, t - 1));
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
      const wasExternal = externalCandidates.some((c) => c.id === id);
      setPendingCandidates((prev) => prev.filter((c) => c.id !== id));
      // Rejected candidates drop off entirely — neither PENDING nor APPROVED
      // status query picks them back up, same as the main pending section.
      setExternalCandidates((prev) => prev.filter((c) => c.id !== id));
      if (wasExternal) setExternalTotal((t) => Math.max(0, t - 1));
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

  const hasMoreExternal = externalCandidates.length < externalTotal;
  const externalCandidateLabel =
    externalTotal === 1 ? "1 candidate" : `${externalTotal} candidates`;
  const externalLabel = hasMoreExternal
    ? `Showing ${externalCandidates.length} of ${externalCandidateLabel}`
    : externalCandidateLabel;

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

          {!externalLoading && hasMoreExternal && (
            <div className="flex justify-center pt-2">
              <button
                type="button"
                onClick={handleLoadMoreExternal}
                disabled={externalLoadingMore}
                className="rounded-lg px-5 py-2 text-sm font-medium"
                style={{
                  background: "var(--color-surface-val)",
                  color: "var(--color-text-primary)",
                  border: "1px solid var(--color-border-val)",
                  opacity: externalLoadingMore ? 0.6 : 1,
                }}
              >
                {externalLoadingMore
                  ? "Loading…"
                  : `Load more (${externalTotal - externalCandidates.length} remaining)`}
              </button>
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
