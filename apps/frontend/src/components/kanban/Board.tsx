"use client";

import { useEffect, useState } from "react";
import {
  DndContext,
  DragEndEvent,
  DragOverlay,
  DragStartEvent,
  PointerSensor,
  closestCorners,
  useSensor,
  useSensors,
} from "@dnd-kit/core";
import { IconLoader2, IconAlertCircle, IconRefresh } from "@tabler/icons-react";
import { useApiFetch } from "@/lib/api";
import { getPipelineBoard, moveMappingStage } from "@/lib/api/pipeline";
import type { KanbanStage, PipelineCard, PipelineColumn } from "@/types";
import KanbanColumn from "./Column";
import KanbanCard from "./CandidateCard";

export default function KanbanBoard() {
  const apiFetch = useApiFetch();
  const [columns, setColumns] = useState<PipelineColumn[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [activeCard, setActiveCard] = useState<PipelineCard | null>(null);

  const sensors = useSensors(useSensor(PointerSensor, { activationConstraint: { distance: 8 } }));

  async function loadBoard() {
    setLoading(true);
    setError(null);
    try {
      const board = await getPipelineBoard(apiFetch);
      setColumns(board.stages);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load pipeline");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect
    void loadBoard();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  function findCardColumn(mappingId: string): KanbanStage | null {
    for (const col of columns) {
      if (col.mappings.some((c) => c.mapping_id === mappingId)) return col.stage;
    }
    return null;
  }

  function handleDragStart(event: DragStartEvent) {
    const card = event.active.data.current?.card as PipelineCard | undefined;
    if (card) setActiveCard(card);
  }

  async function handleDragEnd(event: DragEndEvent) {
    const { active, over } = event;
    setActiveCard(null);
    if (!over) return;

    const mappingId = active.id as string;
    const toStage = over.id as KanbanStage;
    const fromStage = findCardColumn(mappingId);

    if (!fromStage || fromStage === toStage) return;
    if (!columns.some((c) => c.stage === toStage)) return;

    // Optimistic update
    const movingCard = columns
      .find((c) => c.stage === fromStage)
      ?.mappings.find((c) => c.mapping_id === mappingId);
    if (!movingCard) return;

    const snapshot = columns;
    setColumns((prev) =>
      prev.map((col) => {
        if (col.stage === fromStage) {
          return {
            ...col,
            count: col.count - 1,
            mappings: col.mappings.filter((c) => c.mapping_id !== mappingId),
          };
        }
        if (col.stage === toStage) {
          return {
            ...col,
            count: col.count + 1,
            mappings: [...col.mappings, { ...movingCard, stage: toStage }],
          };
        }
        return col;
      }),
    );

    try {
      await moveMappingStage(apiFetch, mappingId, toStage);
    } catch {
      setColumns(snapshot);
    }
  }

  if (loading) {
    return (
      <div className="flex flex-col items-center justify-center h-full gap-3 text-text-muted">
        <IconLoader2 className="size-8 animate-spin opacity-40" />
        <p className="text-sm">Loading pipeline…</p>
      </div>
    );
  }

  if (error) {
    return (
      <div className="flex flex-col items-center justify-center h-full gap-3">
        <IconAlertCircle className="size-8 text-red-400 opacity-60" />
        <p className="text-sm text-text-muted">{error}</p>
        <button
          type="button"
          onClick={() => void loadBoard()}
          className="flex items-center gap-2 px-3 py-1.5 text-xs font-semibold rounded-lg border border-border text-text-secondary hover:text-text-primary hover:border-yellow/40 transition-all"
        >
          <IconRefresh className="size-3.5" />
          Retry
        </button>
      </div>
    );
  }

  return (
    <DndContext
      id="pipeline-kanban"
      sensors={sensors}
      collisionDetection={closestCorners}
      onDragStart={handleDragStart}
      onDragEnd={handleDragEnd}
    >
      <div className="flex gap-3 h-full overflow-x-auto pb-2 px-1 dashboard-scrollbar">
        {columns.map((col) => (
          <KanbanColumn key={col.stage} stage={col.stage} label={col.label} cards={col.mappings} />
        ))}
      </div>

      <DragOverlay dropAnimation={{ duration: 160, easing: "ease-out" }}>
        {activeCard ? <KanbanCard card={activeCard} isDragOverlay /> : null}
      </DragOverlay>
    </DndContext>
  );
}
