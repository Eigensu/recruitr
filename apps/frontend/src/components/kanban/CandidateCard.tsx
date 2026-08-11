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
    </div>
  );
}
