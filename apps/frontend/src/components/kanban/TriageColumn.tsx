"use client";

import { useDroppable } from "@dnd-kit/core";
import { cn } from "@/lib/utils";
import type { CandidateCard, CandidateStatus } from "@/types";
import TriageCard from "./TriageCard";

interface Props {
  readonly id: CandidateStatus;
  readonly label: string;
  readonly color: string;
  readonly cards: CandidateCard[];
}

const HEADER_ACCENT: Record<CandidateStatus, string> = {
  pending: "text-amber-400 border-amber-500/30 bg-amber-500/5",
  accepted: "text-emerald-400 border-emerald-500/30 bg-emerald-500/5",
  rejected: "text-red-400 border-red-500/30 bg-red-500/5",
};

const HEADER_DOT: Record<CandidateStatus, string> = {
  pending: "bg-amber-400",
  accepted: "bg-emerald-400",
  rejected: "bg-red-400",
};

export default function TriageColumn({ id, label, cards }: Readonly<Props>) {
  const { setNodeRef, isOver } = useDroppable({ id });
  const accent = HEADER_ACCENT[id];
  const dot = HEADER_DOT[id];

  return (
    <div
      className={cn(
        "flex flex-col rounded-2xl border bg-surface-panel transition-colors duration-150",
        isOver ? "border-yellow/40 bg-yellow/2" : "border-border",
      )}
    >
      <div
        className={cn(
          "flex items-center justify-between rounded-t-2xl border-b px-3.5 py-2.5",
          accent,
        )}
      >
        <div className="flex items-center gap-2">
          <span className={cn("size-2 shrink-0 rounded-full", dot)} />
          <span className="text-xs font-bold uppercase tracking-wider">{label}</span>
        </div>
        <span className={cn("rounded-full border px-2 py-0.5 text-[10px] font-bold", accent)}>
          {cards.length}
        </span>
      </div>

      <div
        ref={setNodeRef}
        className={cn(
          "dashboard-scrollbar max-h-[calc(100vh-240px)] min-h-30 flex-1 space-y-2.5 overflow-y-auto p-3",
          isOver && "bg-yellow/1.5",
        )}
      >
        {cards.map((card) => (
          <TriageCard key={card.id} card={card} />
        ))}
        {cards.length === 0 && (
          <div className="flex h-16 items-center justify-center">
            <p className="text-center text-[11px] text-text-muted/50">Drop cards here</p>
          </div>
        )}
      </div>
    </div>
  );
}
