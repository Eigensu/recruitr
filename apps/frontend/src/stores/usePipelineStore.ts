import { create } from "zustand";
import type { CandidateCard, CandidateStatus } from "@/types";

interface PipelineState {
  columns: Record<CandidateStatus, CandidateCard[]>;
  setColumns: (columns: Record<CandidateStatus, CandidateCard[]>) => void;
  moveCard: (cardId: string, from: CandidateStatus, to: CandidateStatus) => void;
  activeCardId: string | null;
  setActiveCardId: (id: string | null) => void;
}

const MOCK_COLUMNS: Record<CandidateStatus, CandidateCard[]> = {
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
}));

// Selector helpers
export const selectColumn = (status: CandidateStatus) => (state: PipelineState) =>
  state.columns[status];

export const selectAllCards = (state: PipelineState) => Object.values(state.columns).flat();
