"use client";

import React, { useCallback, useEffect, useState } from "react";
import { IconSearch, IconPlus, IconUsers } from "@tabler/icons-react";
import { useApiFetch } from "@/lib/api";
import {
  listCandidates,
  type CandidateListParams,
  type ExperienceFilter,
} from "@/lib/api/candidates";
import type { ApiCandidate } from "@/types";
import CandidateCard from "@/components/candidates/CandidateCard";
import CandidateDrawer from "@/components/candidates/CandidateDrawer";
import AddCandidateModal from "@/components/candidates/AddCandidateModal";

const EXP_OPTIONS: Array<{ value: ExperienceFilter | ""; label: string }> = [
  { value: "", label: "All" },
  { value: "lt2", label: "< 2 yrs" },
  { value: "2to5", label: "2–5 yrs" },
  { value: "gt5", label: "> 5 yrs" },
];

export default function CandidatesPage() {
  const apiFetch = useApiFetch();

  const [candidates, setCandidates] = useState<ApiCandidate[]>([]);
  const [totalCount, setTotalCount] = useState(0);
  const [isLoading, setIsLoading] = useState(true);
  const [searchTerm, setSearchTerm] = useState("");
  const [experienceFilter, setExperienceFilter] = useState<ExperienceFilter | "">("");
  const [selectedCandidate, setSelectedCandidate] = useState<ApiCandidate | null>(null);
  const [isAddModalOpen, setIsAddModalOpen] = useState(false);

  const loadCandidates = useCallback(async () => {
    setIsLoading(true);
    try {
      const params: CandidateListParams = { limit: 60 };
      if (searchTerm) params.search = searchTerm;
      if (experienceFilter) params.experience = experienceFilter;

      const result = await listCandidates(apiFetch, params);
      setCandidates(result.items);
      setTotalCount(result.meta.total);
    } catch (err) {
      console.error("Failed to load candidates:", err);
    } finally {
      setIsLoading(false);
    }
  }, [apiFetch, searchTerm, experienceFilter]);

  useEffect(() => {
    const timer = setTimeout(loadCandidates, searchTerm ? 300 : 0);
    return () => clearTimeout(timer);
  }, [loadCandidates, searchTerm]);

  function handleCandidateCreated(created: ApiCandidate) {
    setCandidates((prev) => [created, ...prev]);
    setTotalCount((n) => n + 1);
  }

  const hasFilters = Boolean(searchTerm || experienceFilter);
  const emptyMessage = hasFilters ? "No candidates match your filters." : "No candidates yet.";

  return (
    <div className="flex flex-col h-full overflow-hidden bg-(--color-canvas)">
      {/* Header */}
      <div className="px-8 pt-8 pb-5 shrink-0 border-b border-border/50">
        <div className="flex items-start justify-between gap-6">
          <div>
            <h1 className="font-heading text-[2.5rem] font-bold text-text-primary tracking-tight leading-none">
              Candidates
            </h1>
            <p className="text-sm text-text-muted mt-2">
              {isLoading ? (
                <span className="opacity-50">Loading…</span>
              ) : (
                <>
                  <span className="font-semibold text-text-secondary">
                    {totalCount.toLocaleString()}
                  </span>{" "}
                  {totalCount === 1 ? "candidate" : "candidates"} in your talent pool
                </>
              )}
            </p>
          </div>
          <button
            type="button"
            onClick={() => setIsAddModalOpen(true)}
            className="flex items-center gap-2 px-4 py-2.5 rounded-xl bg-yellow text-navy font-bold text-sm hover:bg-yellow-dark transition-all shadow-lg shadow-yellow/15 shrink-0 mt-1"
          >
            <IconPlus className="size-4" />
            Add Candidate
          </button>
        </div>

        {/* Search + experience segmented filter */}
        <div className="flex items-center gap-3 mt-5">
          <div className="relative flex-1 max-w-md">
            <IconSearch className="absolute left-3.5 top-1/2 -translate-y-1/2 size-4 text-text-muted pointer-events-none" />
            <input
              type="text"
              placeholder="Search name, email, skills…"
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              className="w-full pl-10 pr-4 py-2.5 text-sm rounded-xl bg-(--color-surface) border border-border text-text-primary placeholder:text-text-muted focus:outline-none focus:border-white/20 transition-all"
            />
          </div>
          <div className="flex items-center bg-(--color-surface) border border-border rounded-xl p-1 gap-0.5 shrink-0">
            {EXP_OPTIONS.map((opt) => (
              <button
                key={opt.value}
                type="button"
                onClick={() => setExperienceFilter(opt.value)}
                className={`px-3 py-1.5 text-xs font-semibold rounded-lg transition-all whitespace-nowrap ${
                  experienceFilter === opt.value
                    ? "bg-yellow text-navy"
                    : "text-text-muted hover:text-text-primary"
                }`}
              >
                {opt.label}
              </button>
            ))}
          </div>
        </div>
      </div>

      {/* Grid */}
      <div className="flex-1 overflow-y-auto dashboard-scrollbar px-8 py-6">
        <CandidateGrid
          isLoading={isLoading}
          candidates={candidates}
          hasFilters={hasFilters}
          emptyMessage={emptyMessage}
          onSelect={setSelectedCandidate}
          onAdd={() => setIsAddModalOpen(true)}
        />
      </div>

      <CandidateDrawer candidate={selectedCandidate} onClose={() => setSelectedCandidate(null)} />
      <AddCandidateModal
        isOpen={isAddModalOpen}
        onClose={() => setIsAddModalOpen(false)}
        onCreated={handleCandidateCreated}
      />
    </div>
  );
}

const SKELETON_KEYS = ["sk-a", "sk-b", "sk-c", "sk-d", "sk-e", "sk-f", "sk-g", "sk-h", "sk-i"];

interface CandidateGridProps {
  isLoading: boolean;
  candidates: ApiCandidate[];
  hasFilters: boolean;
  emptyMessage: string;
  onSelect: (c: ApiCandidate) => void;
  onAdd: () => void;
}

function CandidateGrid({
  isLoading,
  candidates,
  hasFilters,
  emptyMessage,
  onSelect,
  onAdd,
}: Readonly<CandidateGridProps>) {
  if (isLoading) {
    return (
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-5">
        {SKELETON_KEYS.map((k) => (
          <SkeletonCard key={k} />
        ))}
      </div>
    );
  }

  if (candidates.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center h-64 gap-3">
        <IconUsers className="size-10 text-text-muted opacity-20" />
        <p className="text-sm text-text-muted">{emptyMessage}</p>
        {!hasFilters && (
          <button type="button" onClick={onAdd} className="text-xs text-yellow hover:underline">
            Add your first candidate →
          </button>
        )}
      </div>
    );
  }

  return (
    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-5">
      {candidates.map((cand, idx) => (
        <div
          key={cand.id}
          className="candidate-card-reveal"
          style={{ animationDelay: `${Math.min(idx * 30, 450)}ms` }}
        >
          <CandidateCard candidate={cand} onClick={() => onSelect(cand)} />
        </div>
      ))}
    </div>
  );
}

function SkeletonCard() {
  return (
    <div className="rounded-2xl border border-border bg-surface-panel overflow-hidden animate-pulse">
      <div className="h-0.5 bg-border" />
      <div className="p-5 flex flex-col gap-4">
        <div className="flex items-start gap-3.5">
          <div className="size-10 rounded-xl bg-border/40 shrink-0" />
          <div className="flex-1 pt-0.5 space-y-2">
            <div className="h-3.5 rounded-full bg-border/50 w-3/4" />
            <div className="h-2.5 rounded-full bg-border/30 w-1/2" />
          </div>
        </div>
        <div className="flex gap-1.5 flex-wrap">
          <div className="h-5 w-16 rounded-full bg-border/30" />
          <div className="h-5 w-20 rounded-full bg-border/30" />
          <div className="h-5 w-12 rounded-full bg-border/30" />
        </div>
        <div className="pt-3.5 border-t border-border/40">
          <div className="h-2.5 rounded-full bg-border/30 w-2/3" />
        </div>
      </div>
    </div>
  );
}
