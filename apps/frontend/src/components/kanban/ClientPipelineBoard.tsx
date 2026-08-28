"use client";

import { useEffect, useMemo, useState } from "react";
import type { PipelineBoardData, PipelineCard, KanbanStage } from "@/types";
import KanbanColumn from "./Column";
import {
  CLIENT_STAGES,
  CLIENT_STAGE_LABELS,
  type ClientStage,
} from "@/lib/constants/client-pipeline";

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

async function fetchBoard(): Promise<PipelineBoardData> {
  const res = await fetch(`${API_URL}/api/v1/pipeline/board`, { credentials: "include" });
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

import { DndContext } from "@dnd-kit/core";

import ClientActionModal from "./ClientActionModal";

const selectStyle = {
  background: "var(--color-canvas-val)",
  color: "var(--color-text-primary)",
  border: "1px solid var(--color-border-val)",
};

export default function ClientPipelineBoard({ positions }: Props) {
  const [board, setBoard] = useState<PipelineBoardData | null>(null);
  const [loading, setLoading] = useState(true);
  const [filters, setFilters] = useState<Filters>({ position_id: "" });

  // Modal state
  const [selectedCard, setSelectedCard] = useState<PipelineCard | null>(null);

  async function handleStageChange(card: PipelineCard, newStage: string) {
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
      alert("Failed to change stage: " + err);
    }
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
        <div
          className="flex flex-1 items-center justify-center text-sm"
          style={{ color: "var(--color-text-secondary)" }}
        >
          Loading…
        </div>
      ) : (
        <DndContext>
          <div className="flex flex-1 gap-4 overflow-x-auto pb-2">
            {clientStagesData.map((col) => (
              <KanbanColumn
                key={col.stage}
                stage={col.stage as unknown as import("@/types").KanbanStage}
                label={col.label}
                cards={col.mappings}
                readOnly={true}
                isClientBoard={true}
                onCardClick={(card) => setSelectedCard(card)}
                onStageChange={handleStageChange}
              />
            ))}
          </div>
        </DndContext>
      )}

      <ClientActionModal
        isOpen={!!selectedCard}
        onClose={() => setSelectedCard(null)}
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
