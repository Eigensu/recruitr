"use client";

import { SortableContext, verticalListSortingStrategy } from "@dnd-kit/sortable";
import { useDroppable } from "@dnd-kit/core";
import type { CandidateCard, CandidateStatus } from "@/types";
import CandidateCardComponent from "./CandidateCard";

interface KanbanColumnProps {
  id: CandidateStatus;
  label: string;
  color: string;
  cards: CandidateCard[];
}

export default function KanbanColumn({ id, label, color, cards }: KanbanColumnProps) {
  const { setNodeRef, isOver } = useDroppable({ id });

  return (
    <div
      ref={setNodeRef}
      className={`flex flex-col rounded-xl bg-gray-900/50 shadow-md ${color} transition-colors ${
        isOver ? "bg-gray-800/60" : ""
      }`}
    >
      {/* Column header */}
      <div className="px-4 py-3 flex items-center justify-between">
        <h3 className="text-sm font-semibold text-white">{label}</h3>
        <span className="text-xs bg-gray-800 text-white rounded-full px-2 py-0.5">
          {cards.length}
        </span>
      </div>

      {/* Cards */}
      <SortableContext items={cards.map((c) => c.id)} strategy={verticalListSortingStrategy}>
        <div className="flex-1 p-3 space-y-2 overflow-y-auto min-h-[200px]">
          {cards.map((card) => (
            <CandidateCardComponent key={card.id} card={card} />
          ))}
          {cards.length === 0 && (
            <p className="text-xs text-white text-center pt-6">Drop candidates here</p>
          )}
        </div>
      </SortableContext>
    </div>
  );
}
