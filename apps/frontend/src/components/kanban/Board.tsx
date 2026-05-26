"use client";

import {
  DndContext,
  DragEndEvent,
  DragOverEvent,
  DragOverlay,
  DragStartEvent,
  PointerSensor,
  closestCorners,
  useSensor,
  useSensors,
} from "@dnd-kit/core";
import { useCallback } from "react";
import type { CandidateStatus } from "@/types";
import { usePipelineStore } from "@/stores/usePipelineStore";
import { useApiFetch } from "@/lib/api";
import KanbanColumn from "./Column";
import CandidateCardComponent from "./CandidateCard";

const COLUMNS: { id: CandidateStatus; label: string; color: string }[] = [
  { id: "pending", label: "Pending Review", color: "shadow-amber-500/20" },
  { id: "accepted", label: "Accepted", color: "shadow-emerald-500/20" },
  { id: "rejected", label: "Rejected", color: "shadow-red-500/20" },
];

export default function KanbanBoard({ positionId }: { positionId: string }) {
  const { columns, moveCard, activeCardId, setActiveCardId } = usePipelineStore();
  const apiFetch = useApiFetch();

  // Require 8px movement to activate drag — prevents accidental drags on click
  const sensors = useSensors(useSensor(PointerSensor, { activationConstraint: { distance: 8 } }));

  const findCardColumn = useCallback(
    (cardId: string): CandidateStatus | null => {
      for (const [colId, cards] of Object.entries(columns)) {
        if (cards.some((c) => c.id === cardId)) return colId as CandidateStatus;
      }
      return null;
    },
    [columns],
  );

  function handleDragStart(event: DragStartEvent) {
    setActiveCardId(event.active.id as string);
  }

  function handleDragOver(event: DragOverEvent) {
    const { active, over } = event;
    if (!over) return;
    const from = findCardColumn(active.id as string);
    const to = over.id as CandidateStatus;
    if (from && to && from !== to && COLUMNS.some((c) => c.id === to)) {
      moveCard(active.id as string, from, to);
    }
  }

  async function handleDragEnd(event: DragEndEvent) {
    const { active, over } = event;
    setActiveCardId(null);
    if (!over) return;

    const to = over.id as CandidateStatus;
    if (!COLUMNS.some((c) => c.id === to)) return;

    // Fire PATCH /api/v1/pipeline/match — optimistic UI already updated via handleDragOver
    try {
      await apiFetch("/api/v1/pipeline/match", {
        method: "PATCH",
        body: JSON.stringify({
          position_id: positionId,
          candidate_id: active.id,
          target_status: to,
        }),
      });
    } catch (err) {
      console.error("Failed to sync match:", err);
      // TODO: rollback optimistic update on error
    }
  }

  const activeCard = activeCardId
    ? Object.values(columns)
        .flat()
        .find((c) => c.id === activeCardId)
    : null;

  return (
    <DndContext
      sensors={sensors}
      collisionDetection={closestCorners}
      onDragStart={handleDragStart}
      onDragOver={handleDragOver}
      onDragEnd={handleDragEnd}
    >
      <div className="grid grid-cols-3 gap-4 h-full">
        {COLUMNS.map((col) => (
          <KanbanColumn
            key={col.id}
            id={col.id}
            label={col.label}
            color={col.color}
            cards={columns[col.id]}
          />
        ))}
      </div>

      <DragOverlay>
        {activeCard && <CandidateCardComponent card={activeCard} isDragging />}
      </DragOverlay>
    </DndContext>
  );
}
