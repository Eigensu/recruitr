"use client";

import { useEffect, useMemo, useState } from "react";
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
import type { PipelineBoardData, PipelineCard, KanbanStage } from "@/types";
import KanbanColumn from "./Column";
import KanbanCard from "./CandidateCard";

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

async function fetchBoard(): Promise<PipelineBoardData> {
  const res = await fetch(`${API_URL}/api/v1/pipeline/board`, { credentials: "include" });
  if (!res.ok) throw new Error(`Board fetch failed: ${res.status}`);
  return res.json();
}

async function moveMapping(mappingId: string, newStage: KanbanStage): Promise<void> {
  const res = await fetch(`${API_URL}/api/v1/pipeline/mappings/${mappingId}/move`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    credentials: "include",
    body: JSON.stringify({ new_stage: newStage }),
  });
  if (!res.ok) throw new Error(await res.text());
}

interface Employee {
  readonly id: string;
  readonly name: string;
}

interface PositionOption {
  readonly id: string;
  readonly label: string;
  readonly client: string;
}

interface Props {
  readonly employees: readonly Employee[];
  readonly positions: readonly PositionOption[];
}

interface Filters {
  recruiter_id: string;
  position_id: string;
  client: string;
}

const STAGE_LABELS: Record<KanbanStage, string> = {
  sourced: "Sourced",
  sent_to_client: "Sent to Client",
  interview: "Interview",
  decision_pending: "Decision Pending",
  offer: "Offer",
  offer_accepted: "Offer Accepted",
  position_close: "Joined (Legacy)",
  selected: "Selected",
  joined: "Joined",
  rejected: "Rejected",
  candidate_dropped: "Candidate Dropped",
  on_hold: "On Hold",
};

const ALL_STAGES: KanbanStage[] = [
  "sourced",
  "sent_to_client",
  "interview",
  "decision_pending",
  "offer",
  "offer_accepted",
  "position_close",
  "selected",
  "joined",
  "rejected",
  "candidate_dropped",
  "on_hold",
];

const selectStyle = {
  background: "var(--color-canvas-val)",
  color: "var(--color-text-primary)",
  border: "1px solid var(--color-border-val)",
};

export default function GlobalPipelineBoard({ employees, positions }: Props) {
  const [board, setBoard] = useState<PipelineBoardData | null>(null);
  const [loading, setLoading] = useState(true);
  const [activeDragId, setActiveDragId] = useState<string | null>(null);
  const [filters, setFilters] = useState<Filters>({
    recruiter_id: "",
    position_id: "",
    client: "",
  });

  const sensors = useSensors(useSensor(PointerSensor, { activationConstraint: { distance: 8 } }));

  function load() {
    fetchBoard()
      .then((data) => setBoard(data))
      .catch((err) => console.error("Failed to load pipeline board:", err))
      .finally(() => setLoading(false));
  }

  useEffect(() => {
    load();
  }, []);

  // Derive unique clients from position options (or board data)
  const clientOptions = useMemo(() => {
    const seen = new Set<string>();
    const out: string[] = [];
    for (const p of positions) {
      if (!seen.has(p.client)) {
        seen.add(p.client);
        out.push(p.client);
      }
    }
    if (board) {
      for (const col of board.stages) {
        for (const m of col.mappings) {
          if (!seen.has(m.position_client)) {
            seen.add(m.position_client);
            out.push(m.position_client);
          }
        }
      }
    }
    return out.sort();
  }, [positions, board]);

  // Positions offered in the dropdown, narrowed to the selected client. The
  // client filter comes first in the bar, so picking one is how you get to a
  // short, readable position list instead of every open role in the agency.
  const positionOptions = useMemo(() => {
    if (!filters.client) return positions;
    return positions.filter((p) => p.client === filters.client);
  }, [positions, filters.client]);

  // Apply client-side filters to board columns
  const filteredStages = useMemo(() => {
    if (!board) return [];
    const orderedStages = ALL_STAGES.map((s) => {
      const found = board.stages.find((col) => col.stage === s);
      return found || { stage: s, label: STAGE_LABELS[s], mappings: [] };
    });

    return orderedStages
      .map((col) => ({
        ...col,
        mappings: col.mappings.filter((m) => {
          if (filters.recruiter_id && m.employee_id !== filters.recruiter_id) return false;
          if (filters.position_id && m.position_id !== filters.position_id) return false;
          if (filters.client && m.position_client !== filters.client) return false;
          return true;
        }),
      }))
      .filter((col) => {
        // Hide legacy columns if they are completely empty in the source board data
        const isLegacy =
          col.stage === "decision_pending" ||
          col.stage === "offer" ||
          col.stage === "offer_accepted" ||
          col.stage === "position_close";
        if (isLegacy) {
          const originalCol = board.stages.find((c) => c.stage === col.stage);
          if (!originalCol || originalCol.mappings.length === 0) return false;
        }
        return true;
      });
  }, [board, filters]);

  // Find the active drag card across all columns
  const activeCard = useMemo((): PipelineCard | null => {
    if (!activeDragId || !board) return null;
    for (const col of board.stages) {
      const found = col.mappings.find((m) => m.mapping_id === activeDragId);
      if (found) return found;
    }
    return null;
  }, [activeDragId, board]);

  function handleDragStart(e: DragStartEvent) {
    setActiveDragId(e.active.id as string);
  }

  async function handleDragEnd(e: DragEndEvent) {
    setActiveDragId(null);
    const { active, over } = e;
    if (!over || !board) return;
    const mappingId = active.id as string;
    const newStage = over.id as KanbanStage;
    if (!ALL_STAGES.includes(newStage)) return;

    // Optimistically update local state
    setBoard((prev) => {
      if (!prev) return prev;
      let card: PipelineCard | undefined;
      const stages = prev.stages.map((col) => {
        const idx = col.mappings.findIndex((m) => m.mapping_id === mappingId);
        if (idx === -1) return col;
        card = { ...col.mappings[idx], stage: newStage };
        return { ...col, mappings: col.mappings.filter((_, i) => i !== idx), count: col.count - 1 };
      });
      if (!card) return prev;
      const finalCard = card;
      return {
        stages: stages.map((col) =>
          col.stage === newStage
            ? { ...col, mappings: [...col.mappings, finalCard], count: col.count + 1 }
            : col,
        ),
      };
    });

    try {
      await moveMapping(mappingId, newStage);
    } catch {
      load(); // revert on failure
    }
  }

  function updateFilter<K extends keyof Filters>(key: K, value: string) {
    setFilters((prev) => {
      const next = { ...prev, [key]: value };
      // Changing the client leaves any position selected under the previous one
      // stranded: it is no longer in the dropdown, but it would keep filtering
      // the board down to nothing.
      if (key === "client" && prev.position_id) {
        const stillListed = positions.some(
          (p) => p.id === prev.position_id && (!value || p.client === value),
        );
        if (!stillListed) next.position_id = "";
      }
      return next;
    });
  }

  const hasFilters = filters.recruiter_id || filters.position_id || filters.client;
  const selectCls = "rounded-lg px-2 py-1.5 text-xs outline-none";

  return (
    <div className="flex h-full flex-col gap-3">
      {/* Filter bar */}
      <div className="flex flex-wrap items-center gap-2 pb-1">
        <select
          value={filters.recruiter_id}
          onChange={(e) => updateFilter("recruiter_id", e.target.value)}
          className={selectCls}
          style={selectStyle}
        >
          <option value="">All Recruiters</option>
          {employees.map((emp) => (
            <option key={emp.id} value={emp.id}>
              {emp.name}
            </option>
          ))}
        </select>

        <select
          value={filters.client}
          onChange={(e) => updateFilter("client", e.target.value)}
          className={selectCls}
          style={selectStyle}
        >
          <option value="">All Clients</option>
          {clientOptions.map((c) => (
            <option key={c} value={c}>
              {c}
            </option>
          ))}
        </select>

        <select
          value={filters.position_id}
          onChange={(e) => updateFilter("position_id", e.target.value)}
          className={selectCls}
          style={selectStyle}
        >
          <option value="">
            {filters.client ? `All ${filters.client} Positions` : "All Positions"}
          </option>
          {positionOptions.map((p) => (
            <option key={p.id} value={p.id}>
              {p.label}
            </option>
          ))}
        </select>

        {hasFilters && (
          <button
            type="button"
            onClick={() => setFilters({ recruiter_id: "", position_id: "", client: "" })}
            className="text-xs underline"
            style={{ color: "var(--color-text-secondary)" }}
          >
            Clear filters
          </button>
        )}
      </div>

      {/* Board */}
      {loading ? (
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
          onDragEnd={handleDragEnd}
        >
          <div className="flex flex-1 gap-4 overflow-x-auto pb-2">
            {filteredStages.map((col) => (
              <KanbanColumn
                key={col.stage}
                stage={col.stage as KanbanStage}
                label={STAGE_LABELS[col.stage as KanbanStage] ?? col.label}
                cards={col.mappings}
              />
            ))}
          </div>

          <DragOverlay>
            {activeCard ? <KanbanCard card={activeCard} isDragOverlay /> : null}
          </DragOverlay>
        </DndContext>
      )}
    </div>
  );
}
