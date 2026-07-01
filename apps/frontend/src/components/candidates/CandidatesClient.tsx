"use client";

import { useState } from "react";
import type { ApiCandidate, CandidateFilters } from "@/types";
import { clientDeleteCandidate, clientFetchCandidates } from "@/lib/api/candidates.client";
import { useCurrentUser } from "@/hooks/useCurrentUser";
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
  availableTags: string[];
}

const drawerStyle = {
  background: "var(--color-surface-val)",
  border: "1px solid var(--color-border-val)",
};

export default function CandidatesClient({
  initialCandidates,
  initialTotal,
  availableTags,
}: Readonly<Props>) {
  const { isMaintainer } = useCurrentUser();
  const [candidates, setCandidates] = useState<ApiCandidate[]>(initialCandidates);
  const [total, setTotal] = useState(initialTotal);
  const [page, setPage] = useState(1);
  const [activeFilters, setActiveFilters] = useState<Partial<CandidateFilters>>({});
  const [loading, setLoading] = useState(false);
  const [loadingMore, setLoadingMore] = useState(false);
  const [showAddForm, setShowAddForm] = useState(false);
  const [showBulkUpload, setShowBulkUpload] = useState(false);
  const [selectedCandidate, setSelectedCandidate] = useState<ApiCandidate | null>(null);

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

  function handleCandidateAdded(candidate: ApiCandidate) {
    setCandidates((prev) => [candidate, ...prev]);
    setTotal((t) => t + 1);
    setShowAddForm(false);
  }

  function handleCandidateUpdated(updated: ApiCandidate) {
    setCandidates((prev) => prev.map((c) => (c.id === updated.id ? updated : c)));
    setSelectedCandidate(updated);
  }

  async function handleDeleteCandidate(id: string) {
    await clientDeleteCandidate(id);
    setCandidates((prev) => prev.filter((c) => c.id !== id));
    setTotal((t) => t - 1);
    if (selectedCandidate?.id === id) setSelectedCandidate(null);
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

  return (
    <div className="flex flex-col gap-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <span className="text-sm" style={{ color: "var(--color-text-secondary)" }}>
          {countLabel}
        </span>
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
      </div>

      <CandidateFilterBar availableTags={availableTags} onFilterChange={handleFilterChange} />

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
        <div className="py-12 text-center text-sm" style={{ color: "var(--color-text-secondary)" }}>
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

      <CandidateDrawer
        candidate={selectedCandidate}
        onClose={() => setSelectedCandidate(null)}
        onUpdate={handleCandidateUpdated}
      />
    </div>
  );
}
