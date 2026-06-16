"use client";

import { useDraggable } from "@dnd-kit/core";
import { CSS } from "@dnd-kit/utilities";
import { IconGripVertical, IconSparkles } from "@tabler/icons-react";
import { cn } from "@/lib/utils";
import type { CandidateCard } from "@/types";

interface Props {
  readonly card: CandidateCard;
  readonly isDragging?: boolean;
}

function scoreColor(score: number | null | undefined): string {
  if (score == null) return "text-text-muted bg-surface-2 border-border";
  if (score >= 0.75) return "text-emerald-400 bg-emerald-500/10 border-emerald-500/20";
  if (score >= 0.5) return "text-yellow bg-yellow/10 border-yellow/20";
  return "text-red-400 bg-red-500/10 border-red-500/20";
}

export default function TriageCard({ card, isDragging: isDragOverlay = false }: Readonly<Props>) {
  const { attributes, listeners, setNodeRef, transform, isDragging } = useDraggable({
    id: card.id,
    data: { card },
  });

  const style = transform ? { transform: CSS.Translate.toString(transform) } : undefined;

  return (
    <div
      ref={setNodeRef}
      style={style}
      {...attributes}
      className={cn(
        "group relative select-none rounded-xl border bg-surface-panel p-3 transition-all duration-150",
        isDragging && !isDragOverlay && "scale-95 opacity-40",
        isDragOverlay &&
          "rotate-1 cursor-grabbing shadow-2xl shadow-black/50 ring-1 ring-yellow/30",
        !isDragging && !isDragOverlay && "cursor-grab hover:border-border hover:shadow-sm",
        "border-border",
      )}
    >
      <div
        {...listeners}
        className="absolute right-2.5 top-2.5 cursor-grab opacity-0 transition-opacity group-hover:opacity-40"
      >
        <IconGripVertical className="size-3.5 text-text-muted" />
      </div>

      <div className="mb-2 pr-4">
        <p className="truncate text-sm font-semibold leading-tight text-text-primary">
          {card.name}
        </p>
        <p className="mt-0.5 truncate text-[11px] text-text-muted">{card.email}</p>
      </div>

      {card.extracted_skills && card.extracted_skills.length > 0 && (
        <div className="mb-2 flex flex-wrap gap-1">
          {card.extracted_skills.slice(0, 3).map((s) => (
            <span key={s} className="rounded bg-surface-2 px-1.5 py-0.5 text-[9px] text-text-muted">
              {s}
            </span>
          ))}
        </div>
      )}

      {card.match_score != null && (
        <div className="flex justify-end">
          <span
            className={cn(
              "flex items-center gap-0.5 rounded-full border px-1.5 py-0.5 text-[10px] font-bold",
              scoreColor(card.match_score),
            )}
          >
            <IconSparkles className="size-2.5" />
            {Math.round(card.match_score * 100)}%
          </span>
        </div>
      )}
    </div>
  );
}
