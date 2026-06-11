"use client";

import { useState } from "react";
import type { Candidate, CandidateFilters } from "@/types";
import { clientFetchCandidates } from "@/lib/api/candidates.client";
import CandidateFilterBar from "./CandidateFilterBar";
import CandidateTable from "./CandidateTable";
import AddCandidateForm from "./AddCandidateForm";
import BulkUploadDrawer from "./BulkUploadDrawer";

interface Props {
  initialCandidates: Candidate[];
  availableTags: string[];
}

const drawerStyle = {
  background: "var(--color-surface-val)",
  border: "1px solid var(--color-border-val)",
};

export default function CandidatesClient({ initialCandidates, availableTags }: Props) {
  const [candidates, setCandidates] = useState<Candidate[]>(initialCandidates);
  const [loading, setLoading] = useState(false);
  const [showAddForm, setShowAddForm] = useState(false);
  const [showBulkUpload, setShowBulkUpload] = useState(false);

  async function handleFilterChange(filters: Partial<CandidateFilters>) {
    setLoading(true);
    try {
      setCandidates(await clientFetchCandidates(filters));
    } catch {
      setCandidates([]);
    } finally {
      setLoading(false);
    }
  }

  function handleCandidateAdded(candidate: Candidate) {
    setCandidates((prev) => [candidate, ...prev]);
    setShowAddForm(false);
  }

  function handleBulkComplete() {
    clientFetchCandidates({ page: 1, limit: 50 })
      .then(setCandidates)
      .catch(() => undefined);
    setShowBulkUpload(false);
  }

  return (
    <div className="flex flex-col gap-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <span className="text-sm" style={{ color: "var(--color-text-secondary)" }}>
          {candidates.length} candidate{candidates.length !== 1 ? "s" : ""}
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

      {loading ? (
        <div className="py-8 text-center text-sm" style={{ color: "var(--color-text-secondary)" }}>
          Loading…
        </div>
      ) : (
        <CandidateTable candidates={candidates} />
      )}
    </div>
  );
}
