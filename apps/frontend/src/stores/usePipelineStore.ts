import { create } from "zustand";
import type { CandidateCard, LegacyCandidateStatus } from "@/types";

export interface KanbanFilters {
  recruiter_id?: string;
  client_id?: string;
  tags?: string[];
  stage?: string;
  mapped_after?: string;
  mapped_before?: string;
}

interface PipelineState {
  columns: Record<LegacyCandidateStatus, CandidateCard[]>;
  setColumns: (columns: Record<LegacyCandidateStatus, CandidateCard[]>) => void;
  moveCard: (cardId: string, from: LegacyCandidateStatus, to: LegacyCandidateStatus) => void;
  activeCardId: string | null;
  setActiveCardId: (id: string | null) => void;
  // Filter state
  activeFilters: KanbanFilters;
  isFiltered: boolean;
  setActiveFilters: (filters: KanbanFilters) => void;
}

const MOCK_COLUMNS: Record<LegacyCandidateStatus, CandidateCard[]> = {
  pending: [
    {
      id: "c1",
      name: "Alice Smith",
      email: "alice@example.com",
      extracted_skills: ["React", "TypeScript", "Next.js"],
      resume_url: null,
      match_score: 0.95,
      status: "pending",
    },
    {
      id: "c2",
      name: "Bob Jones",
      email: "bob@example.com",
      extracted_skills: ["Node.js", "Express", "MongoDB"],
      resume_url: null,
      match_score: 0.82,
      status: "pending",
    },
  ],
  accepted: [
    {
      id: "c3",
      name: "Charlie Davis",
      email: "charlie@example.com",
      extracted_skills: ["Figma", "UI/UX", "Tailwind"],
      resume_url: null,
      match_score: 0.98,
      status: "accepted",
    },
  ],
  rejected: [
    {
      id: "c4",
      name: "Diana Prince",
      email: "diana@example.com",
      extracted_skills: ["Java", "Spring Boot"],
      resume_url: null,
      match_score: 0.45,
      status: "rejected",
    },
  ],
};

export const usePipelineStore = create<PipelineState>((set) => ({
  columns: MOCK_COLUMNS,

  setColumns: (columns) => set({ columns }),

  moveCard: (cardId, from, to) =>
    set((state) => {
      if (from === to) return state;
      const card = state.columns[from].find((c) => c.id === cardId);
      if (!card) return state;
      return {
        columns: {
          ...state.columns,
          [from]: state.columns[from].filter((c) => c.id !== cardId),
          [to]: [...state.columns[to], { ...card, status: to }],
        },
      };
    }),

  activeCardId: null,
  setActiveCardId: (id) => set({ activeCardId: id }),

  activeFilters: {},
  isFiltered: false,
  setActiveFilters: (filters) =>
    set({ activeFilters: filters, isFiltered: Object.keys(filters).length > 0 }),
}));

// Selector helpers
export const selectColumn = (status: LegacyCandidateStatus) => (state: PipelineState) =>
  state.columns[status];

export const selectAllCards = (state: PipelineState) => Object.values(state.columns).flat();
