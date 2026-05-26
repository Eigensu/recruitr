"use client";

import { useSortable } from "@dnd-kit/sortable";
import { CSS } from "@dnd-kit/utilities";
import type { CandidateCard } from "@/types";

interface CandidateCardProps {
  card: CandidateCard;
  isDragging?: boolean;
}

export default function CandidateCardComponent({ card, isDragging = false }: CandidateCardProps) {
  const {
    attributes,
    listeners,
    setNodeRef,
    transform,
    transition,
    isDragging: isSortableDragging,
  } = useSortable({ id: card.id });

  const style = {
    transform: CSS.Transform.toString(transform),
    transition,
  };

  return (
    <div
      ref={setNodeRef}
      style={style}
      {...attributes}
      {...listeners}
      className={`
        rounded-lg bg-gray-800 p-3 cursor-grab active:cursor-grabbing shadow-sm
        hover:bg-gray-750 transition-all select-none
        ${isSortableDragging || isDragging ? "opacity-50 shadow-2xl scale-105" : ""}
      `}
    >
      <div className="flex items-start justify-between gap-2">
        <div className="min-w-0">
          <p className="text-sm font-medium text-white truncate">{card.name}</p>
          <p className="text-xs text-white truncate">{card.email}</p>
        </div>
        {card.match_score !== undefined && (
          <span className="shrink-0 text-xs font-bold text-violet-400 bg-violet-500/10 rounded px-1.5 py-0.5">
            {Math.round(card.match_score * 100)}%
          </span>
        )}
      </div>

      {card.extracted_skills.length > 0 && (
        <div className="mt-2 flex flex-wrap gap-1">
          {card.extracted_skills.slice(0, 3).map((skill) => (
            <span key={skill} className="text-[10px] bg-gray-700 text-white rounded px-1.5 py-0.5">
              {skill}
            </span>
          ))}
          {card.extracted_skills.length > 3 && (
            <span className="text-[10px] text-white">+{card.extracted_skills.length - 3}</span>
          )}
        </div>
      )}

      {card.resume_url && (
        <a
          href={card.resume_url}
          target="_blank"
          rel="noreferrer"
          onClick={(e) => e.stopPropagation()}
          className="mt-2 block text-[10px] text-violet-400 hover:text-violet-300 transition-colors"
        >
          View Resume ↗
        </a>
      )}
    </div>
  );
}
