"use client";

import { useEffect, useMemo, useState } from "react";
import {
  DndContext,
  DragOverlay,
  PointerSensor,
  closestCorners,
  useSensor,
  useSensors,
  type DragEndEvent,
  type DragStartEvent,
} from "@dnd-kit/core";
import type { PipelineBoardData, PipelineCard, KanbanStage } from "@/types";
import KanbanColumn from "./Column";
import KanbanCard from "./CandidateCard";
import ClientActionModal from "./ClientActionModal";
import {
  CLIENT_STAGES,
  CLIENT_STAGE_LABELS,
  isClientTransitionAllowed,
  type ClientStage,
} from "@/lib/constants/client-pipeline";

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

async function fetchBoard(): Promise<PipelineBoardData> {
  // no-store: the board is re-read after every action and whenever the user
  // navigates back to it, so a cached response shows the state from before
  // the action they just took — an uploaded offer letter looking like it was
  // never saved. The page's server-side fetches already pass this.
  const res = await fetch(`${API_URL}/api/v1/pipeline/board`, {
    credentials: "include",
    cache: "no-store",
  });
  if (!res.ok) throw new Error(`Board fetch failed: ${res.status}`);
  return res.json();
}

interface PositionOption {
  readonly id: string;
  readonly label: string;
  readonly client: string;
}

interface Props {
  readonly positions: readonly PositionOption[];
  /** Seeded from /pipeline?position=<id> — see the Positions page link. */
  readonly initialPositionId?: string;
}

interface Filters {
  position_id: string;
}

function mapToClientStage(stage: KanbanStage): ClientStage | null {
  switch (stage) {
    case "sent_to_client":
    case "interview":
    case "selected":
    case "joined":
    case "rejected":
      return stage;
    case "on_hold":
    default:
      return null;
  }
}

const selectStyle = {
  background: "var(--color-canvas-val)",
  color: "var(--color-text-primary)",
  border: "1px solid var(--color-border-val)",
};

export default function ClientPipelineBoard({ positions, initialPositionId }: Props) {
  const [board, setBoard] = useState<PipelineBoardData | null>(null);
  const [loading, setLoading] = useState(true);
  const [filters, setFilters] = useState<Filters>({ position_id: initialPositionId ?? "" });

  // Modal state
  const [selectedMappingId, setSelectedMappingId] = useState<string | null>(null);

  const [activeDragId, setActiveDragId] = useState<string | null>(null);
  const sensors = useSensors(useSensor(PointerSensor, { activationConstraint: { distance: 8 } }));

  function findCard(mappingId: string): PipelineCard | undefined {
    return board?.stages.flatMap((col) => col.mappings).find((m) => m.mapping_id === mappingId);
  }

  /** Move the card between columns before the request lands, so the board
   *  doesn't sit still until the refetch returns. `load()` reconciles. */
  function applyStageLocally(mappingId: string, newStage: KanbanStage) {
    setBoard((prev) => {
      if (!prev) return prev;
      let moved: PipelineCard | undefined;
      const stripped = prev.stages.map((col) => {
        const idx = col.mappings.findIndex((m) => m.mapping_id === mappingId);
        if (idx === -1) return col;
        moved = { ...col.mappings[idx], stage: newStage };
        return { ...col, mappings: col.mappings.filter((_, i) => i !== idx), count: col.count - 1 };
      });
      if (!moved) return prev;
      const finalCard = moved;
      return {
        stages: stripped.map((col) =>
          col.stage === newStage
            ? { ...col, mappings: [...col.mappings, finalCard], count: col.count + 1 }
            : col,
        ),
      };
    });
  }

  async function handleStageChange(card: PipelineCard, newStage: string) {
    // The backend rejects anything outside the client whitelist with a 403, so
    // checking here keeps an illegal move from ever leaving the browser.
    if (!isClientTransitionAllowed(card.stage, newStage)) return;

    applyStageLocally(card.mapping_id, newStage as KanbanStage);
    try {
      const res = await fetch(`${API_URL}/api/v1/pipeline/mappings/${card.mapping_id}/move`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        credentials: "include",
        body: JSON.stringify({ new_stage: newStage }),
      });
      if (!res.ok) throw new Error(await res.text());
      load();
    } catch (err) {
      console.error(err);
      // Roll the optimistic move back by re-reading the server's state.
      load();
      alert("Failed to change stage: " + err);
    }
  }

  function handleDragStart(e: DragStartEvent) {
    setActiveDragId(e.active.id as string);
  }

  async function handleDragEnd(e: DragEndEvent) {
    setActiveDragId(null);
    const { active, over } = e;
    if (!over || !board) return;

    const card = findCard(active.id as string);
    if (!card) return;

    const newStage = over.id as string;
    if (card.stage === newStage) return;

    await handleStageChange(card, newStage);
  }

  function load() {
    fetchBoard()
      .then((data) => setBoard(data))
      .catch((err) => console.error("Failed to load pipeline board:", err))
      .finally(() => setLoading(false));
  }

  useEffect(() => {
    load();
  }, []);

  const clientStagesData = useMemo(() => {
    if (!board) return [];

    // Initialize client stages
    const columns: Record<ClientStage, PipelineCard[]> = {
      sent_to_client: [],
      interview: [],
      selected: [],
      joined: [],
      rejected: [],
    };

    // Filter and map
    for (const col of board.stages) {
      for (const m of col.mappings) {
        if (filters.position_id && m.position_id !== filters.position_id) continue;

        const clientStage = mapToClientStage(m.stage as KanbanStage);
        if (clientStage) {
          columns[clientStage].push(m);
        }
      }
    }

    return CLIENT_STAGES.map((stage) => ({
      stage,
      label: CLIENT_STAGE_LABELS[stage],
      mappings: columns[stage],
      count: columns[stage].length,
    }));
  }, [board, filters]);

  function updateFilter<K extends keyof Filters>(key: K, value: string) {
    setFilters((prev) => ({ ...prev, [key]: value }));
  }

  const activeCard = activeDragId ? findCard(activeDragId) : undefined;
  // Derived rather than stored: the modal must reflect the board's current row,
  // so that state an action unlocks (an uploaded offer letter, a new stage) is
  // visible as soon as the refetch lands, without reopening the card.
  const selectedCard = selectedMappingId ? (findCard(selectedMappingId) ?? null) : null;
  const hasFilters = filters.position_id;
  const selectCls = "rounded-lg px-2 py-1.5 text-xs outline-none";

  return (
    <div className="flex h-full flex-col gap-3">
      {/* Filter bar */}
      <div className="flex flex-wrap items-center gap-2 pb-1">
        <select
          value={filters.position_id}
          onChange={(e) => updateFilter("position_id", e.target.value)}
          className={selectCls}
          style={selectStyle}
        >
          <option value="">All Positions</option>
          {positions.map((p) => (
            <option key={p.id} value={p.id}>
              {p.label}
            </option>
          ))}
        </select>

        {hasFilters && (
          <button
            type="button"
            onClick={() => setFilters({ position_id: "" })}
            className="text-xs underline"
            style={{ color: "var(--color-text-secondary)" }}
          >
            Clear filter
          </button>
        )}
      </div>

      {/* Board */}
      {loading ? (
        <div className="flex flex-1 gap-4 overflow-x-auto pb-2 animate-in fade-in duration-300">
          {[1, 2, 3, 4].map((colIndex) => (
            <div
              key={colIndex}
              className="flex w-[320px] shrink-0 flex-col rounded-2xl p-4 bg-surface"
              style={{
                border: "1px solid var(--color-border-val)",
                background: "var(--color-surface-val)",
              }}
            >
              <div className="mb-4 flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <span className="size-2 rounded-full shrink-0 bg-surface-2" />
                  <div className="h-4 w-24 rounded-full bg-surface-2 animate-pulse" />
                </div>
                <div className="h-5 w-8 rounded-full bg-surface-2 animate-pulse" />
              </div>
              <div className="flex-1 space-y-2.5 overflow-y-auto">
                {[1, 2, 3].map((cardIndex) => (
                  <div
                    key={cardIndex}
                    className="group relative rounded-xl border p-3 min-h-[120px] bg-surface-panel animate-pulse"
                    style={{ border: "1px solid rgba(255,255,255,0.08)" }}
                  >
                    <div className="h-4 w-3/4 rounded-full bg-surface-2 mb-2" />
                    <div className="h-3 w-1/2 rounded-full bg-surface-2 mb-2" />
                    <div className="h-3 w-1/3 rounded-full bg-surface-2 mb-4" />
                    <div className="flex justify-between items-center mt-auto">
                      <div className="h-4 w-12 rounded-full bg-surface-2" />
                      <div className="h-4 w-12 rounded-full bg-surface-2" />
                    </div>
                  </div>
                ))}
              </div>
            </div>
          ))}
        </div>
      ) : (
        <DndContext
          sensors={sensors}
          collisionDetection={closestCorners}
          onDragStart={handleDragStart}
          onDragEnd={handleDragEnd}
        >
          <div className="flex flex-1 gap-4 overflow-x-auto pb-2">
            {clientStagesData.map((col) => (
              <KanbanColumn
                key={col.stage}
                stage={col.stage as unknown as KanbanStage}
                label={col.label}
                cards={col.mappings}
                readOnly={false}
                dropDisabled={
                  !!activeCard &&
                  activeCard.stage !== col.stage &&
                  !isClientTransitionAllowed(activeCard.stage, col.stage)
                }
                isClientBoard={true}
                onCardClick={(card) => setSelectedMappingId(card.mapping_id)}
                onStageChange={handleStageChange}
              />
            ))}
          </div>

          <DragOverlay>
            {activeCard ? <KanbanCard card={activeCard} isClientBoard isDragOverlay /> : null}
          </DragOverlay>
        </DndContext>
      )}

      <ClientActionModal
        isOpen={!!selectedCard}
        onClose={() => setSelectedMappingId(null)}
        card={selectedCard}
        onStageChange={async (newStage) => {
          if (!selectedCard) return;
          const res = await fetch(
            `${API_URL}/api/v1/pipeline/mappings/${selectedCard.mapping_id}/move`,
            {
              method: "POST",
              headers: { "Content-Type": "application/json" },
              credentials: "include",
              body: JSON.stringify({ new_stage: newStage }),
            },
          );
          if (!res.ok) throw new Error(await res.text());
        }}
        onActionComplete={() => load()}
      />
    </div>
  );
}
