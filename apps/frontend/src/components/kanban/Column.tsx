"use client";

import { useDroppable } from "@dnd-kit/core";
import { cn } from "@/lib/utils";
import type { KanbanStage, PipelineCard } from "@/types";
import KanbanCard from "./CandidateCard";

const STAGE_ACCENT: Record<KanbanStage, string> = {
  sourced: "text-text-primary border-slate-500/30 bg-slate-500/10",
  sent_to_client: "text-text-primary border-blue-500/30 bg-blue-500/10",
  interview: "text-text-primary border-purple-500/30 bg-purple-500/10",
  selected: "text-text-primary border-indigo-500/30 bg-indigo-500/10",
  joined: "text-text-primary border-emerald-500/30 bg-emerald-500/10",
  rejected: "text-text-primary border-red-500/30 bg-red-500/10",
  candidate_dropped: "text-text-primary border-red-600/30 bg-red-600/10",
  on_hold: "text-text-primary border-gray-500/30 bg-gray-500/10",
};

const STAGE_DOT: Record<KanbanStage, string> = {
  sourced: "bg-slate-500",
  sent_to_client: "bg-blue-500",
  interview: "bg-purple-500",
  selected: "bg-indigo-500",
  joined: "bg-emerald-500",
  rejected: "bg-red-500",
  candidate_dropped: "bg-red-600",
  on_hold: "bg-gray-500",
};

interface Props {
  stage: KanbanStage;
  label: string;
  cards: PipelineCard[];
  readOnly?: boolean;
  isClientBoard?: boolean;
  onCardClick?: (card: PipelineCard) => void;
  onStageChange?: (card: PipelineCard, newStage: string) => void;
}

export default function KanbanColumn({
  stage,
  label,
  cards,
  readOnly,
  isClientBoard,
  onCardClick,
  onStageChange,
}: Readonly<Props>) {
  const { setNodeRef, isOver } = useDroppable({
    id: stage,
    disabled: readOnly,
  });
  const accent = STAGE_ACCENT[stage];
  const dot = STAGE_DOT[stage];

  return (
    <div
      className={cn(
        "flex flex-col min-w-60 w-60 rounded-2xl border bg-surface-panel",
        "transition-colors duration-150",
        isOver ? "border-yellow/40 bg-yellow/2" : "border-border",
      )}
    >
      {/* Header */}
      <div
        className={cn(
          "px-3.5 py-2.5 border-b flex items-center justify-between rounded-t-2xl",
          accent,
        )}
      >
        <div className="flex items-center gap-2">
          <span className={cn("size-2 rounded-full shrink-0", dot)} />
          <span className="text-xs font-bold uppercase tracking-wider">{label}</span>
        </div>
        <span className={cn("text-[10px] font-bold px-2 py-0.5 rounded-full", accent)}>
          {cards.length}
        </span>
      </div>

      {/* Cards */}
      <div
        ref={setNodeRef}
        className={cn(
          "flex-1 p-3 space-y-2.5 overflow-y-auto min-h-30 max-h-[calc(100vh-220px)]",
          "dashboard-scrollbar",
          isOver && "bg-yellow/1.5",
        )}
      >
        {cards.map((card) => (
          <KanbanCard
            key={card.mapping_id}
            card={card}
            readOnly={readOnly}
            isClientBoard={isClientBoard}
            onCardClick={onCardClick}
            onStageChange={onStageChange}
          />
        ))}
        {cards.length === 0 && (
          <div className="flex items-center justify-center h-16">
            <p className="text-[11px] text-text-muted/50 text-center">
              {readOnly ? "No candidates" : "Drop cards here"}
            </p>
          </div>
        )}
      </div>
    </div>
  );
}
