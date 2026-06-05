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

  // Reload on filter change; debounce search by 300 ms
  useEffect(() => {
    const timer = setTimeout(loadCandidates, searchTerm ? 300 : 0);
    return () => clearTimeout(timer);
  }, [loadCandidates, searchTerm]);

  function handleCandidateCreated(created: ApiCandidate) {
    setCandidates((prev) => [created, ...prev]);
    setTotalCount((n) => n + 1);
  }

  const candidateWord = totalCount === 1 ? "candidate" : "candidates";
  const subtitleText = isLoading
    ? "Loading talent pool…"
    : `${totalCount} ${candidateWord} in your talent pool`;

  const emptyMessage =
    searchTerm || experienceFilter
      ? "No candidates match your filters."
      : "No candidates yet — add the first one.";

  return (
    <div className="p-6 md:p-8 flex flex-col h-full overflow-hidden bg-(--color-canvas)">
      {/* Header */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 mb-6 shrink-0">
        <div>
          <h1 className="text-3xl font-bold font-heading text-text-primary flex items-center gap-3 tracking-wide">
            <IconUsers className="size-8 text-text-primary" />
            Candidates Directory
          </h1>
          <p className="text-sm mt-1 text-text-secondary">{subtitleText}</p>
        </div>
        <button
          type="button"
          onClick={() => setIsAddModalOpen(true)}
          className="flex items-center gap-2 px-4 py-2 rounded-lg bg-yellow text-navy hover:bg-yellow-dark text-sm font-bold transition-all duration-200 shadow-lg shadow-yellow/10 self-start"
        >
          <IconPlus className="size-4" />
          Add Candidate
        </button>
      </div>

      {/* Search & filters */}
      <div className="flex flex-col sm:flex-row items-center gap-3 mb-6 bg-(--color-surface) p-4 rounded-xl border border-border shadow-sm shrink-0">
        <div className="relative flex-1 w-full">
          <IconSearch className="absolute left-3 top-1/2 -translate-y-1/2 size-4 text-text-muted" />
          <input
            type="text"
            placeholder="Search by name, email, company, or skills…"
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
            className="w-full pl-9 pr-4 py-2 text-sm rounded-lg bg-canvas border border-border text-text-primary placeholder:text-text-muted focus:outline-none focus:border-yellow transition-all"
          />
        </div>
        <div className="flex items-center gap-2 w-full sm:w-auto">
          <span className="text-xs font-semibold text-text-secondary uppercase tracking-wider shrink-0">
            Experience:
          </span>
          <select
            value={experienceFilter}
            onChange={(e) => setExperienceFilter(e.target.value as ExperienceFilter | "")}
            className="w-full sm:w-40 px-3 py-2 text-sm rounded-lg bg-canvas border border-border text-text-primary focus:outline-none focus:border-yellow transition-all"
          >
            <option value="">All Levels</option>
            <option value="lt2">&lt; 2 yrs</option>
            <option value="2to5">2 – 5 yrs</option>
            <option value="gt5">&gt; 5 yrs</option>
          </select>
        </div>
      </div>

      {/* Candidate grid */}
      <div className="flex-1 overflow-y-auto dashboard-scrollbar">
        {isLoading ? (
          <div className="flex flex-col items-center justify-center h-64 text-text-muted gap-3">
            <div className="size-8 border-2 border-yellow/30 border-t-yellow rounded-full animate-spin" />
            <p className="text-sm font-medium">Loading candidates…</p>
          </div>
        ) : candidates.length === 0 ? (
          <div className="flex flex-col items-center justify-center h-64 text-text-muted">
            <IconUsers className="size-12 mb-3 opacity-20" />
            <p className="text-sm font-medium">{emptyMessage}</p>
          </div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6 pb-8">
            {candidates.map((cand) => (
              <CandidateCard
                key={cand.id}
                candidate={cand}
                onClick={() => setSelectedCandidate(cand)}
              />
            ))}
          </div>
        )}
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
