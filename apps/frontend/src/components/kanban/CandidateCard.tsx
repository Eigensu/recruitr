"use client";

import { useDraggable } from "@dnd-kit/core";
import { CSS } from "@dnd-kit/utilities";
import { IconGripVertical, IconSparkles } from "@tabler/icons-react";
import { cn } from "@/lib/utils";
import type { PipelineCard } from "@/types";

interface Props {
  card: PipelineCard;
  isDragOverlay?: boolean;
  readOnly?: boolean;
  onCardClick?: (card: PipelineCard) => void;
}

function scoreColor(score: number | null): string {
  if (score === null) return "text-text-muted bg-surface-2 border-border";
  if (score >= 0.75) return "text-emerald-400 bg-emerald-500/10 border-emerald-500/20";
  if (score >= 0.5) return "text-yellow bg-yellow/10 border-yellow/20";
  return "text-red-400 bg-red-500/10 border-red-500/20";
}

export default function KanbanCard({
  card,
  isDragOverlay = false,
  readOnly = false,
  onCardClick,
}: Readonly<Props>) {
  const { attributes, listeners, setNodeRef, transform, isDragging } = useDraggable({
    id: card.mapping_id,
    data: { card },
    disabled: readOnly,
  });

  const style = transform ? { transform: CSS.Translate.toString(transform) } : undefined;

  return (
    <div
      ref={setNodeRef}
      style={style}
      {...attributes}
      className={cn(
        "group relative rounded-xl border bg-surface-panel p-3 select-none",
        "transition-all duration-150",
        isDragging && !isDragOverlay && "opacity-40 scale-95",
        isDragOverlay &&
          "shadow-2xl shadow-black/50 rotate-1 cursor-grabbing ring-1 ring-yellow/30",
        !isDragging &&
          !isDragOverlay &&
          !readOnly &&
          "hover:border-border hover:shadow-sm cursor-grab",
        "border-border",
      )}
    >
      {/* Drag handle */}
      {!readOnly && (
        <div
          {...listeners}
          className="absolute top-2.5 right-2.5 opacity-0 group-hover:opacity-40 transition-opacity cursor-grab"
        >
          <IconGripVertical className="size-3.5 text-text-muted" />
        </div>
      )}

      {/* Candidate */}
      <div className="pr-4 mb-2">
        <p className="text-sm font-semibold text-text-primary truncate leading-tight">
          {card.candidate_name}
        </p>
        {!readOnly && (
          <p className="text-[11px] text-text-muted truncate mt-0.5">{card.candidate_email}</p>
        )}
      </div>

      {/* Position */}
      <div className="flex items-center gap-1.5 mb-2.5">
        <span className="text-[10px] font-medium text-text-secondary truncate">
          {card.position_role}
        </span>
        {!readOnly && (
          <>
            <span className="text-text-muted/40">·</span>
            <span className="text-[10px] text-text-muted truncate">{card.position_client}</span>
          </>
        )}
      </div>

      {/* Footer */}
      <div className="flex flex-col gap-1.5 mt-2">
        <div className="flex items-center justify-between gap-2">
          <span className="text-[9px] font-bold text-text-muted/60 uppercase tracking-wider">
            {card.position_code}
          </span>
          {!readOnly && card.match_score !== null && (
            <span
              className={cn(
                "flex items-center gap-0.5 text-[10px] font-bold px-1.5 py-0.5 rounded-full border",
                scoreColor(card.match_score),
              )}
            >
              <IconSparkles className="size-2.5" />
              {Math.round(card.match_score * 100)}%
            </span>
          )}
        </div>

        {card.stage === "joined" && (
          <div className="flex flex-col gap-1 pt-1.5 border-t border-border/50">
            {card.joining_date && (
              <span className="text-[10px] text-text-muted">
                Joined:{" "}
                <strong className="text-emerald-400">
                  {new Date(card.joining_date).toLocaleDateString()}
                </strong>
              </span>
            )}
            {card.salary_offered && (
              <span className="text-[10px] text-text-muted">
                Salary:{" "}
                <strong className="text-yellow">₹{card.salary_offered.toLocaleString()}</strong>
              </span>
            )}
          </div>
        )}

        {card.stage === "candidate_dropped" && card.dropped_notes && (
          <div className="flex flex-col gap-1 pt-1.5 border-t border-border/50">
            <span className="text-[10px] text-text-muted italic break-words">
              &quot;{card.dropped_notes}&quot;
            </span>
          </div>
        )}
      </div>

      {/* Action Button for Client Portal */}
      {onCardClick &&
        card.stage !== "joined" &&
        card.stage !== "rejected" &&
        card.stage !== "candidate_dropped" && (
          <div className="mt-3 pt-3 border-t border-border">
            <button
              onClick={() => onCardClick(card)}
              className="w-full rounded-lg bg-indigo-500/10 border border-indigo-500/20 px-3 py-1.5 text-xs font-semibold text-indigo-400 hover:bg-indigo-500/20 transition-all"
            >
              Review Action
            </button>
          </div>
        )}
    </div>
  );
}
