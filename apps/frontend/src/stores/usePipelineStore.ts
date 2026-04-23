import { create } from "zustand";
import type { CandidateCard, CandidateStatus } from "@/types";

interface PipelineState {
  columns: Record<CandidateStatus, CandidateCard[]>;
  setColumns: (columns: Record<CandidateStatus, CandidateCard[]>) => void;
  moveCard: (cardId: string, from: CandidateStatus, to: CandidateStatus) => void;
  activeCardId: string | null;
  setActiveCardId: (id: string | null) => void;
}

const EMPTY_COLUMNS: Record<CandidateStatus, CandidateCard[]> = {
  pending: [],
  accepted: [],
  rejected: [],
};

export const usePipelineStore = create<PipelineState>((set) => ({
  columns: EMPTY_COLUMNS,

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
