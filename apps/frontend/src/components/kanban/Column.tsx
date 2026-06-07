"use client";

import { useDroppable } from "@dnd-kit/core";
import { cn } from "@/lib/utils";
import type { KanbanStage, PipelineCard } from "@/types";
import KanbanCard from "./CandidateCard";

const STAGE_ACCENT: Record<KanbanStage, string> = {
  sent_to_client: "text-blue-400 border-blue-500/30 bg-blue-500/5",
  interview: "text-purple-400 border-purple-500/30 bg-purple-500/5",
  decision_pending: "text-amber-400 border-amber-500/30 bg-amber-500/5",
  offer: "text-yellow border-yellow/30 bg-yellow/5",
  offer_accepted: "text-emerald-400 border-emerald-500/30 bg-emerald-500/5",
  position_close: "text-teal-400 border-teal-500/30 bg-teal-500/5",
};

const STAGE_DOT: Record<KanbanStage, string> = {
  sent_to_client: "bg-blue-400",
  interview: "bg-purple-400",
  decision_pending: "bg-amber-400",
  offer: "bg-yellow",
  offer_accepted: "bg-emerald-400",
  position_close: "bg-teal-400",
};

interface Props {
  stage: KanbanStage;
  label: string;
  cards: PipelineCard[];
}

export default function KanbanColumn({ stage, label, cards }: Readonly<Props>) {
  const { setNodeRef, isOver } = useDroppable({ id: stage });
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
        <span className={cn("text-[10px] font-bold px-2 py-0.5 rounded-full border", accent)}>
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
          <KanbanCard key={card.mapping_id} card={card} />
        ))}
        {cards.length === 0 && (
          <div className="flex items-center justify-center h-16">
            <p className="text-[11px] text-text-muted/50 text-center">Drop cards here</p>
          </div>
        )}
      </div>
    </div>
  );
}
