"use client";

import React, { useState, useMemo } from "react";
import { IconSearch, IconPlus, IconUsers } from "@tabler/icons-react";
import { usePositionsStore } from "@/stores/usePositionsStore";
import CandidateCard from "@/components/candidates/CandidateCard";
import CandidateDrawer from "@/components/candidates/CandidateDrawer";
import AddCandidateModal from "@/components/candidates/AddCandidateModal";

export default function CandidatesPage() {
  const { candidates } = usePositionsStore();

  const [searchTerm, setSearchTerm] = useState("");
  const [experienceFilter, setExperienceFilter] = useState("All");

  const [selectedCandidateId, setSelectedCandidateId] = useState<string | null>(null);
  const [isAddModalOpen, setIsAddModalOpen] = useState(false);

  const filteredCandidates = useMemo(() => {
    return candidates.filter((cand) => {
      // Search filter
      const searchLower = searchTerm.toLowerCase();
      const matchesSearch =
        cand.name.toLowerCase().includes(searchLower) ||
        cand.email.toLowerCase().includes(searchLower) ||
        (cand.previousCompany && cand.previousCompany.toLowerCase().includes(searchLower)) ||
        cand.skills.some((skill) => skill.toLowerCase().includes(searchLower));

      // Experience filter
      let matchesExp = true;
      if (experienceFilter === "< 2 yrs") {
        matchesExp = cand.experienceYears < 2;
      } else if (experienceFilter === "2-5 yrs") {
        matchesExp = cand.experienceYears >= 2 && cand.experienceYears <= 5;
      } else if (experienceFilter === "> 5 yrs") {
        matchesExp = cand.experienceYears > 5;
      }

      return matchesSearch && matchesExp;
    });
  }, [candidates, searchTerm, experienceFilter]);

  return (
    <div className="p-6 md:p-8 flex flex-col h-full overflow-hidden bg-[var(--color-canvas)]">
      {/* Header controls */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 mb-6 shrink-0">
        <div>
          <h1 className="text-3xl font-bold font-heading text-text-primary flex items-center gap-3 tracking-wide">
            <IconUsers className="size-8 text-text-primary" />
            Candidates Directory
          </h1>
          <p className="text-sm mt-1 text-text-secondary">
            Manage your talent pool, review candidate profiles, and track position mappings.
          </p>
        </div>
        <div className="flex items-center gap-3">
          <button
            onClick={() => setIsAddModalOpen(true)}
            className="flex items-center gap-2 px-4 py-2 rounded-lg bg-yellow text-navy hover:bg-yellow-dark text-sm font-bold transition-all duration-200 shadow-lg shadow-yellow/10"
          >
            <IconPlus className="size-4" />
            Add Candidate
          </button>
        </div>
      </div>

      {/* Search & filters */}
      <div className="flex flex-col sm:flex-row items-center gap-3 mb-6 bg-[var(--color-surface)] p-4 rounded-xl border border-border shadow-sm shrink-0">
        <div className="relative flex-1 w-full">
          <IconSearch className="absolute left-3 top-1/2 -translate-y-1/2 size-4 text-text-muted" />
          <input
            type="text"
            placeholder="Search by name, email, company, or skills..."
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
            onChange={(e) => setExperienceFilter(e.target.value)}
            className="w-full sm:w-40 px-3 py-2 text-sm rounded-lg bg-canvas border border-border text-text-primary focus:outline-none focus:border-yellow transition-all"
          >
            <option value="All">All Levels</option>
            <option value="< 2 yrs">&lt; 2 yrs</option>
            <option value="2-5 yrs">2-5 yrs</option>
            <option value="> 5 yrs">&gt; 5 yrs</option>
          </select>
        </div>
      </div>

      {/* Candidate Grid */}
      <div className="flex-1 overflow-y-auto dashboard-scrollbar">
        {filteredCandidates.length === 0 ? (
          <div className="flex flex-col items-center justify-center h-64 text-text-muted">
            <IconUsers className="size-12 mb-3 opacity-20" />
            <p className="text-sm font-medium">No candidates match your search filters.</p>
          </div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6 pb-8">
            {filteredCandidates.map((cand) => (
              <CandidateCard
                key={cand.id}
                candidate={cand}
                onClick={() => setSelectedCandidateId(cand.id)}
              />
            ))}
          </div>
        )}
      </div>

      {/* Drawer and Modal */}
      <CandidateDrawer
        candidateId={selectedCandidateId}
        onClose={() => setSelectedCandidateId(null)}
      />

      <AddCandidateModal isOpen={isAddModalOpen} onClose={() => setIsAddModalOpen(false)} />
    </div>
  );
}
