"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
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
import type { ApiCandidate, PipelineBoardData, PipelineCard, KanbanStage } from "@/types";
import CandidateDrawer from "@/components/candidates/CandidateDrawer";
import { useToast } from "@/components/ui/Toast";
import { apiErrorMessage, useApiFetch } from "@/lib/api";
import { getCandidate } from "@/lib/api/candidates";
import { JOINED_ARCHIVE_DAYS } from "@/lib/constants/pipeline";
import KanbanColumn from "./Column";
import KanbanCard from "./CandidateCard";
import ClientActionModal from "./ClientActionModal";
import JoiningDetailsPanel from "./JoiningDetailsPanel";
import OfferLetterDialog from "./OfferLetterDialog";

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

/** The live board, or the joined cards it has archived (see JOINED_ARCHIVE_DAYS). */
type BoardView = "active" | "archived";

async function fetchBoard(view: BoardView): Promise<PipelineBoardData> {
  // no-store: the board is re-read after every action and whenever the user
  // navigates back to it, so a cached response shows the state from before
  // the action they just took — an uploaded offer letter looking like it was
  // never saved. The page's server-side fetches already pass this.
  const query = view === "archived" ? "?archived=true" : "";
  const res = await fetch(`${API_URL}/api/v1/pipeline/board${query}`, {
    credentials: "include",
    cache: "no-store",
  });
  if (!res.ok) throw new Error(`Board fetch failed: ${res.status}`);
  return res.json();
}

/** Archived joined cards: read-only, but each still opens the candidate drawer. */
function ArchivedJoined({
  cards,
  filtered,
  onOpen,
}: Readonly<{ cards: PipelineCard[]; filtered: boolean; onOpen: (card: PipelineCard) => void }>) {
  return (
    <section aria-label="Archived joined candidates" className="flex flex-1 flex-col gap-3">
      <p className="text-xs" style={{ color: "var(--color-text-secondary)" }}>
        Joined candidates move here {JOINED_ARCHIVE_DAYS} days after they were moved to Joined.
        Nothing is deleted, and clients still see them on their own board.
      </p>
      {cards.length === 0 ? (
        <p className="py-10 text-center text-sm" style={{ color: "var(--color-text-secondary)" }}>
          {filtered ? "Nothing archived matches these filters." : "Nothing archived yet."}
        </p>
      ) : (
        // A context so the cards' (disabled) draggable hooks have one to sit in.
        <DndContext>
          <div className="grid grid-cols-[repeat(auto-fill,minmax(15rem,1fr))] gap-3">
            {cards.map((card) => (
              <KanbanCard key={card.mapping_id} card={card} readOnly onCardClick={onOpen} />
            ))}
          </div>
        </DndContext>
      )}
    </section>
  );
}

async function moveMapping(
  mappingId: string,
  newStage: KanbanStage,
  extra: Record<string, unknown> = {},
): Promise<void> {
  const res = await fetch(`${API_URL}/api/v1/pipeline/mappings/${mappingId}/move`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    credentials: "include",
    body: JSON.stringify({ new_stage: newStage, ...extra }),
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
  /** Seeded from /pipeline?position=<id> so a link in from the Positions page
   *  lands on the board already narrowed to that role. */
  readonly initialPositionId?: string;
  /** Seeded from /pipeline?client=<name>. */
  readonly initialClient?: string;
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

export default function GlobalPipelineBoard({
  employees,
  positions,
  initialPositionId,
  initialClient,
}: Props) {
  const [board, setBoard] = useState<PipelineBoardData | null>(null);
  const [loading, setLoading] = useState(true);
  const [view, setView] = useState<BoardView>("active");
  // Only the newest request may set the board: switching views while a read
  // is in flight would otherwise show one view's cards under the other's tab.
  const requestRef = useRef(0);
  const [activeDragId, setActiveDragId] = useState<string | null>(null);
  const [selectedMappingId, setSelectedMappingId] = useState<string | null>(null);
  const [offerLetterMappingId, setOfferLetterMappingId] = useState<string | null>(null);
  // A joined card opens the candidate drawer rather than the action modal:
  // there is nothing left to decide, and what's wanted is the joining date and
  // the person's whole history.
  const [viewing, setViewing] = useState<{ mappingId: string; candidate: ApiCandidate } | null>(
    null,
  );
  // Drops a slow candidate fetch that lands after another card was clicked.
  const openingRef = useRef<string | null>(null);
  const apiFetch = useApiFetch();
  const toast = useToast();
  const [filters, setFilters] = useState<Filters>({
    recruiter_id: "",
    position_id: initialPositionId ?? "",
    client: initialClient ?? "",
  });

  const sensors = useSensors(useSensor(PointerSensor, { activationConstraint: { distance: 8 } }));

  const load = useCallback(() => {
    const request = ++requestRef.current;
    fetchBoard(view)
      .then((data) => {
        if (request === requestRef.current) setBoard(data);
      })
      .catch((err) => console.error("Failed to load pipeline board:", err))
      .finally(() => {
        if (request === requestRef.current) setLoading(false);
      });
  }, [view]);

  useEffect(() => {
    load();
  }, [load]);

  function switchView(next: BoardView) {
    if (next === view) return;
    setLoading(true);
    setBoard(null);
    setSelectedMappingId(null);
    setOfferLetterMappingId(null);
    setView(next);
  }

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
    // localeCompare, not the default sort: that compares UTF-16 code units, so
    // any client name outside plain ASCII lands in the wrong place.
    return out.sort((a, b) => a.localeCompare(b));
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
        const isLegacy = false;
        if (isLegacy) {
          const originalCol = board.stages.find((c) => c.stage === col.stage);
          if (!originalCol || originalCol.mappings.length === 0) return false;
        }
        return true;
      });
  }, [board, filters]);

  // Derived rather than stored: the modal must reflect the board's current row,
  // so that state an action unlocks (an uploaded offer letter, a new stage) is
  // visible as soon as the refetch lands, without reopening the card. The
  // offer-letter dialog and the joining details read the board the same way.
  function cardById(mappingId: string | null): PipelineCard | null {
    if (!mappingId) return null;
    return (
      board?.stages.flatMap((col) => col.mappings).find((m) => m.mapping_id === mappingId) ?? null
    );
  }
  const selectedCard = cardById(selectedMappingId);
  const offerLetterCard = cardById(offerLetterMappingId);
  const viewingCard = cardById(viewing?.mappingId ?? null);

  async function openJoinedCard(card: PipelineCard) {
    const id = card.mapping_id;
    openingRef.current = id;
    try {
      const candidate = await getCandidate(apiFetch, card.candidate_id);
      if (openingRef.current === id) setViewing({ mappingId: id, candidate });
    } catch (err) {
      if (openingRef.current === id)
        toast(apiErrorMessage(err, "Could not load this candidate."), "error");
    } finally {
      if (openingRef.current === id) openingRef.current = null;
    }
  }

  function handleCardClick(card: PipelineCard) {
    if (card.stage === "joined") openJoinedCard(card);
    else setSelectedMappingId(card.mapping_id);
  }

  // Find the active drag card across all columns
  const activeCard = useMemo((): PipelineCard | null => {
    if (!activeDragId || !board) return null;
    for (const col of board.stages) {
      const found = col.mappings.find((m) => m.mapping_id === activeDragId);
      if (found) return found;
    }
    return null;
  }, [activeDragId, board]);

  async function handleStageChange(card: PipelineCard, newStage: string) {
    try {
      let extra = {};
      if (newStage === "candidate_dropped") {
        const notes = window.prompt("Reason for candidate drop:");
        if (!notes) return;
        extra = { dropped_notes: notes };
      }
      const res = await fetch(`${API_URL}/api/v1/pipeline/mappings/${card.mapping_id}/move`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        credentials: "include",
        body: JSON.stringify({ new_stage: newStage, ...extra }),
      });
      if (!res.ok) throw new Error(await res.text());
      // Refresh board
      load();
    } catch (err) {
      console.error(err);
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
      let extra = {};
      if (newStage === "candidate_dropped") {
        const notes = window.prompt("Reason for candidate drop:");
        if (!notes) {
          // Cancel drop if no reason is given
          load();
          return;
        }
        extra = { dropped_notes: notes };
      }
      // Wait, moveMapping only takes mappingId and newStage currently
      // I should update moveMapping to take extra payload
      await moveMapping(mappingId, newStage, extra);
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
        <div
          role="group"
          aria-label="Board view"
          className="flex rounded-lg p-0.5"
          style={selectStyle}
        >
          {(["active", "archived"] as const).map((option) => (
            <button
              key={option}
              type="button"
              aria-pressed={view === option}
              onClick={() => switchView(option)}
              className="rounded-md px-2.5 py-1 text-xs font-semibold transition-colors"
              style={
                view === option
                  ? { background: "var(--color-yellow)", color: "#002348" }
                  : { color: "var(--color-text-secondary)" }
              }
            >
              {option === "active" ? "Active" : "Archived"}
            </button>
          ))}
        </div>

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
        <div className="flex flex-1 gap-4 overflow-x-auto pb-2 animate-in fade-in duration-300">
          {[1, 2, 3, 4, 5, 6].map((colIndex) => (
            <div
              key={colIndex}
              className="flex w-[320px] shrink-0 flex-col rounded-2xl p-4 bg-surface"
              style={{
                border: "1px solid var(--color-border-val)",
                background: "var(--color-surface-val)",
              }}
            >
              {/* Column Header */}
              <div className="mb-4 flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <span className="size-2 rounded-full shrink-0 bg-surface-2" />
                  <div className="h-4 w-24 rounded-full bg-surface-2 animate-pulse" />
                </div>
                <div className="h-5 w-8 rounded-full bg-surface-2 animate-pulse" />
              </div>
              {/* Column Cards */}
              <div className="flex-1 space-y-2.5 overflow-y-auto">
                {[1, 2, 3].map((cardIndex) => (
                  <div
                    key={cardIndex}
                    className="group relative rounded-xl border p-3 min-h-[120px] bg-surface-panel animate-pulse"
                    style={{ border: "1px solid rgba(255,255,255,0.08)" }}
                  >
                    {/* Card Content Skeleton */}
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
      ) : view === "archived" ? (
        <ArchivedJoined
          cards={filteredStages.find((col) => col.stage === "joined")?.mappings ?? []}
          filtered={!!hasFilters}
          onOpen={handleCardClick}
        />
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
                onStageChange={handleStageChange}
                onCardClick={handleCardClick}
                onOfferLetterClick={(card) => setOfferLetterMappingId(card.mapping_id)}
              />
            ))}
          </div>

          <DragOverlay>
            {activeCard ? <KanbanCard card={activeCard} isDragOverlay /> : null}
          </DragOverlay>
        </DndContext>
      )}
      <ClientActionModal
        key={selectedCard?.mapping_id ?? "none"}
        isOpen={!!selectedCard}
        onClose={() => setSelectedMappingId(null)}
        card={selectedCard}
        onStageChange={async (newStage) => {
          if (!selectedCard) return;
          // `new_stage` is what StageMoveRequest declares, and the session
          // cookie is what authenticates it. This posted `to_stage` with no
          // credentials, so every action in this modal 401'd or 422'd and then
          // reported nothing but a console line — the modal just closed as if
          // it had worked.
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
          load();
        }}
        onActionComplete={load}
      />
      <OfferLetterDialog
        key={`offer-${offerLetterCard?.mapping_id ?? "none"}`}
        card={offerLetterCard}
        onClose={() => setOfferLetterMappingId(null)}
        onUploaded={load}
      />
      <CandidateDrawer
        candidate={viewing?.candidate ?? null}
        onClose={() => setViewing(null)}
        onUpdate={(candidate) => setViewing((prev) => (prev ? { ...prev, candidate } : prev))}
        topSection={
          viewingCard ? (
            <JoiningDetailsPanel
              key={viewingCard.mapping_id}
              card={viewingCard}
              onSaved={load}
              readOnly={view === "archived"}
            />
          ) : null
        }
      />
    </div>
  );
}
