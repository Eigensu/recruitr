"use client";

import { useCallback, useEffect, useState } from "react";
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
import type { CandidateCard, CandidateStatus } from "@/types";
import { usePipelineStore, type KanbanFilters } from "@/stores/usePipelineStore";
import { useApiFetch } from "@/lib/api";
import { fetchFilteredPipeline } from "@/lib/api/pipeline";
import KanbanColumn from "./Column";
import CandidateCardComponent from "./CandidateCard";
import KanbanFilterBar from "./KanbanFilterBar";
import AddCandidatesPanel from "./AddCandidatesPanel";

const COLUMNS: { id: CandidateStatus; label: string; color: string }[] = [
  { id: "pending", label: "Pending Review", color: "shadow-amber-500/20" },
  { id: "accepted", label: "Accepted", color: "shadow-emerald-500/20" },
  { id: "rejected", label: "Rejected", color: "shadow-red-500/20" },
];

interface Props {
  readonly positionId: string;
  readonly employees?: readonly { id: string; name: string }[];
  readonly clients?: readonly { id: string; label: string }[];
  readonly availableTags?: readonly string[];
}

export default function KanbanBoard({
  positionId,
  employees = [],
  clients = [],
  availableTags = [],
}: Props) {
  const {
    columns,
    moveCard,
    activeCardId,
    setActiveCardId,
    setColumns,
    setActiveFilters,
    isFiltered,
  } = usePipelineStore();
  const apiFetch = useApiFetch();
  const [boardLoading, setBoardLoading] = useState(false);
  const [showAddPanel, setShowAddPanel] = useState(false);

  const sensors = useSensors(useSensor(PointerSensor, { activationConstraint: { distance: 8 } }));

  const allCards = Object.values(columns).flat();
  const activeCard: CandidateCard | null =
    activeCardId ? (allCards.find((c) => c.id === activeCardId) ?? null) : null;

  const findCardColumn = useCallback(
    (cardId: string): CandidateStatus | null => {
      for (const [colId, cards] of Object.entries(columns)) {
        if (cards.some((c) => c.id === cardId)) return colId as CandidateStatus;
      }
      return null;
    },
    [columns],
  );

  const loadBoard = useCallback(
    async (filters: KanbanFilters) => {
      try {
        setColumns(await fetchFilteredPipeline(positionId, filters));
      } catch (err) {
        console.error("Failed to load pipeline board:", err);
      }
    },
    [positionId, setColumns],
  );

  useEffect(() => {
    void loadBoard({});
  }, [loadBoard]);

  async function handleFilterChange(filters: KanbanFilters) {
    setActiveFilters(filters);
    setBoardLoading(true);
    await loadBoard(filters);
    setBoardLoading(false);
  }

  function handleDragStart(event: DragStartEvent) {
    setActiveCardId(event.active.id as string);
  }

  function handleDragOver(event: DragOverEvent) {
    const { active, over } = event;
    if (!over) return;
    const from = findCardColumn(active.id as string);
    const to = over.id as CandidateStatus;
    if (from && from !== to && COLUMNS.some((c) => c.id === to)) {
      moveCard(active.id as string, from, to);
    }
  }

  async function handleDragEnd(event: DragEndEvent) {
    const { active, over } = event;
    setActiveCardId(null);
    if (!over) return;

    const cardId = active.id as string;
    const to = over.id as CandidateStatus;
    if (!COLUMNS.some((c) => c.id === to)) return;

    try {
      await apiFetch("/api/v1/pipeline/match", {
        method: "PATCH",
        body: JSON.stringify({
          position_id: positionId,
          candidate_id: cardId,
          target_status: to,
        }),
      });
      await loadBoard(usePipelineStore.getState().activeFilters);
    } catch (err) {
      console.error("Failed to sync match:", err);
      await loadBoard(usePipelineStore.getState().activeFilters);
    }
  }

  return (
    <div className="relative flex h-full flex-col gap-3">
      <div className="flex items-start justify-between gap-3">
        <KanbanFilterBar
          employees={employees}
          clients={clients}
          availableTags={availableTags}
          onFilterChange={handleFilterChange}
        />
        <button
          type="button"
          onClick={() => setShowAddPanel((v) => !v)}
          className="shrink-0 rounded-lg px-3 py-1.5 text-sm font-semibold"
          style={{ background: "var(--color-yellow)", color: "#002348" }}
        >
          + Add Candidates
        </button>
      </div>

      {isFiltered && (
        <p className="text-xs" style={{ color: "var(--color-text-secondary)" }}>
          Filtered view — drag still updates candidate status.
        </p>
      )}

      {showAddPanel && (
        <div className="absolute right-0 top-12 z-20 h-[calc(100%-3rem)]">
          <AddCandidatesPanel
            positionId={positionId}
            onAssigned={() => loadBoard(usePipelineStore.getState().activeFilters)}
            onClose={() => setShowAddPanel(false)}
          />
        </div>
      )}

      {boardLoading ? (
        <div
          className="flex flex-1 items-center justify-center text-sm"
          style={{ color: "var(--color-text-secondary)" }}
        >
          Loading…
        </div>
      ) : (
        <DndContext
          sensors={sensors}
          collisionDetection={closestCorners}
          onDragStart={handleDragStart}
          onDragOver={handleDragOver}
          onDragEnd={handleDragEnd}
        >
          <div className="grid flex-1 grid-cols-3 gap-4">
            {COLUMNS.map((col) => (
              <KanbanColumn
                key={col.id}
                id={col.id}
                label={isFiltered ? `${col.label} (${columns[col.id].length})` : col.label}
                color={col.color}
                cards={columns[col.id]}
              />
            ))}
          </div>

          <DragOverlay>
            {activeCard ? <CandidateCardComponent card={activeCard} isDragging /> : null}
          </DragOverlay>
        </DndContext>
      )}
    </div>
  );
}
