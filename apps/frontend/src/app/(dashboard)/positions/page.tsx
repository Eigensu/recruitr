"use client";

import React, { useState, useMemo } from "react";
import { motion, AnimatePresence } from "motion/react";
import {
  IconSearch,
  IconPlus,
  IconMapPin,
  IconCircleCheck,
  IconGripVertical,
  IconSparkles,
  IconUsers,
  IconX,
  IconChevronRight,
  IconBulb,
  IconAlertCircle,
} from "@tabler/icons-react";
import { usePositionsStore, MockPosition, MockCandidate } from "@/stores/usePositionsStore";
import { cn } from "@/lib/utils";
import {
  DndContext,
  DragOverlay,
  closestCorners,
  KeyboardSensor,
  PointerSensor,
  useSensor,
  useSensors,
  useDroppable,
  useDraggable,
  DragStartEvent,
  DragEndEvent,
} from "@dnd-kit/core";

// ─── Position Card (left panel, droppable) ────────────────────────────────────

function PositionCard({
  position,
  isSelected,
  mappedCandidates,
  onClick,
}: Readonly<{
  position: MockPosition;
  isSelected: boolean;
  mappedCandidates: MockCandidate[];
  onClick: () => void;
}>) {
  const { setNodeRef, isOver } = useDroppable({ id: position.id });

  const filled = mappedCandidates.length;
  const total = position.openingsCount;
  const progress = total > 0 ? Math.min((filled / total) * 100, 100) : 0;

  return (
    <motion.div
      ref={setNodeRef}
      layout
      initial={{ opacity: 0, y: 6 }}
      animate={{ opacity: 1, y: 0 }}
      onClick={onClick}
      className={cn(
        "relative p-4 rounded-xl border cursor-pointer select-none overflow-hidden transition-all duration-200",
        isSelected
          ? "border-yellow bg-surface-panel shadow-md shadow-yellow/5"
          : "border-border bg-surface-panel hover:border-border hover:shadow-sm",
        isOver && "border-yellow/70 shadow-lg shadow-yellow/10 scale-[1.01]",
        position.status === "Closed" && "opacity-40 pointer-events-none",
      )}
    >
      {/* Selected left accent */}
      {isSelected && (
        <div className="absolute left-0 top-3 bottom-3 w-0.75 bg-yellow rounded-r-full" />
      )}

      {/* Drop overlay */}
      <AnimatePresence>
        {isOver && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            className="absolute inset-0 border-2 border-dashed border-yellow/50 rounded-xl pointer-events-none z-10 flex items-center justify-center bg-navy/80"
          >
            <span className="text-[11px] font-bold text-yellow flex items-center gap-1.5 bg-navy px-3 py-1.5 rounded-lg border border-yellow/40">
              <IconCircleCheck className="size-3.5" />
              Drop to map
            </span>
          </motion.div>
        )}
      </AnimatePresence>

      {/* ── Top row: Role + Status + Openings ── */}
      <div className="flex items-start justify-between gap-3 mb-2">
        <div className="flex-1 min-w-0">
          {/* Status badge — small, above role */}
          <div className="mb-1">
            <span
              className={cn(
                "inline-flex items-center gap-0.5 text-[10px] font-bold px-1.5 py-0.5 rounded-full uppercase",
                position.status === "Open"
                  ? "text-emerald-600 bg-emerald-500/10 border border-emerald-500/20"
                  : "text-red-500 bg-red-500/10 border border-red-500/20",
              )}
            >
              {position.status === "Open" ? (
                <IconCircleCheck className="size-2.5" />
              ) : (
                <IconAlertCircle className="size-2.5" />
              )}
              {position.status}
            </span>
          </div>

          {/* Role — primary heading, font-heading */}
          <h3 className="font-heading font-bold text-text-primary text-[15px] leading-snug truncate">
            {position.role}
          </h3>

          {/* Client name — secondary */}
          <p className="text-xs text-text-secondary mt-0.5 truncate font-medium">
            {position.clientName}
          </p>
        </div>

        {/* Openings count */}
        <div className="shrink-0 text-center min-w-9">
          <div className="text-2xl font-black text-teal-500 leading-none">{total}</div>
          <div className="text-[9px] text-text-muted uppercase font-bold tracking-wider mt-0.5">
            open
          </div>
        </div>
      </div>

      {/* ── Tags row: dept + seniority + city ── */}
      <div className="flex flex-wrap gap-1.5 mb-3">
        <span className="text-[10px] px-2 py-0.5 rounded-full bg-surface-2 border border-border text-text-secondary font-medium">
          {position.department}
        </span>
        <span
          className={cn(
            "text-[10px] px-2 py-0.5 rounded-full font-bold",
            position.seniority === "Junior" &&
              "bg-blue-500/10 text-blue-500 border border-blue-500/20",
            position.seniority === "Mid" && "bg-yellow/20 text-navy border border-yellow/40",
            position.seniority === "Senior" &&
              "bg-purple-500/10 text-purple-500 border border-purple-500/20",
          )}
        >
          {position.seniority}
        </span>
        <span className="text-[10px] px-2 py-0.5 rounded-full bg-surface-2 border border-border text-text-muted flex items-center gap-0.5">
          <IconMapPin className="size-2.5 shrink-0" />
          {position.city}
        </span>
      </div>

      {/* ── Fill progress ── */}
      <div className="mb-2.5">
        <div className="flex justify-between items-center mb-1">
          <span className="text-[10px] text-text-muted font-semibold uppercase tracking-wider">
            Filled
          </span>
          <span className="text-[10px] font-bold text-text-secondary">
            {filled} / {total}
          </span>
        </div>
        <div className="h-1.5 rounded-full bg-surface-2 overflow-hidden">
          <motion.div
            className={cn("h-full rounded-full", progress === 100 ? "bg-emerald-500" : "bg-yellow")}
            initial={{ width: 0 }}
            animate={{ width: `${progress}%` }}
            transition={{ duration: 0.5, ease: "easeOut" }}
          />
        </div>
      </div>

      {/* ── Mapped candidate avatars ── */}
      {mappedCandidates.length > 0 && (
        <div className="flex items-center gap-2 pt-2.5 border-t border-border">
          <div className="flex -space-x-1.5">
            {mappedCandidates.slice(0, 5).map((c) => (
              <div
                key={c.id}
                title={c.name}
                className="size-6 rounded-full bg-yellow/20 border-2 border-surface flex items-center justify-center text-[9px] font-black text-navy"
              >
                {c.name
                  .split(" ")
                  .map((n) => n[0])
                  .join("")
                  .slice(0, 2)}
              </div>
            ))}
            {mappedCandidates.length > 5 && (
              <div className="size-6 rounded-full bg-surface-2 border-2 border-surface flex items-center justify-center text-[9px] font-bold text-text-muted">
                +{mappedCandidates.length - 5}
              </div>
            )}
          </div>
          <span className="text-[10px] text-text-muted">{mappedCandidates.length} mapped</span>
        </div>
      )}
    </motion.div>
  );
}

// ─── Candidate Card (right panel, draggable) ──────────────────────────────────

function DraggableCandidateCard({
  cand,
  rank,
  isMapped,
  onToggleMap,
  hasPosition,
}: Readonly<{
  cand: MockCandidate & { dynamicScore: number };
  rank?: number;
  isMapped: boolean;
  onToggleMap: () => void;
  hasPosition: boolean;
}>) {
  const { attributes, listeners, setNodeRef, transform, isDragging } = useDraggable({
    id: cand.id,
    data: { cand },
  });

  const style = transform
    ? { transform: `translate3d(${transform.x}px, ${transform.y}px, 0)` }
    : undefined;

  const scoreBadgeClass = cn(
    "text-xs font-black px-2 py-1 rounded-lg shrink-0 leading-none",
    cand.dynamicScore >= 90 && "bg-emerald-500/10 text-emerald-600 border border-emerald-500/20",
    cand.dynamicScore >= 80 &&
      cand.dynamicScore < 90 &&
      "bg-yellow/20 text-navy border border-yellow/40",
    cand.dynamicScore < 80 && "bg-surface-2 text-text-muted border border-border",
  );

  return (
    <div
      ref={setNodeRef}
      style={style}
      className={cn(
        "p-3.5 rounded-xl border flex items-start gap-2.5 transition-all duration-200 group relative",
        isMapped
          ? "border-yellow/30 bg-surface-panel"
          : "border-border bg-surface-panel hover:border-border/80 hover:shadow-sm",
        isDragging && "opacity-30 scale-95",
      )}
    >
      {/* Rank badge */}
      {rank !== undefined && (
        <div
          className={cn(
            "absolute -left-3 top-1/2 -translate-y-1/2 size-5 rounded-full flex items-center justify-center text-[9px] font-black border",
            rank <= 3
              ? "bg-yellow text-navy border-yellow shadow-sm"
              : "bg-surface-2 text-text-muted border-border",
          )}
        >
          {rank}
        </div>
      )}

      {/* Drag handle */}
      <div
        {...attributes}
        {...listeners}
        className="mt-0.5 text-text-muted hover:text-yellow cursor-grab active:cursor-grabbing p-1 rounded hover:bg-surface-2 shrink-0 touch-none transition-colors"
      >
        <IconGripVertical className="size-4" />
      </div>

      <div className="flex-1 min-w-0">
        {/* Name + score */}
        <div className="flex items-start justify-between gap-2 mb-1.5">
          <div className="min-w-0">
            <h4 className="font-semibold text-sm text-text-primary group-hover-accent truncate transition-colors">
              {cand.name}
            </h4>
            <p className="text-[11px] text-text-muted mt-0.5 truncate">
              {cand.previousCompany} &bull; {cand.experienceYears}y exp
            </p>
          </div>
          <div className={scoreBadgeClass}>{cand.dynamicScore}%</div>
        </div>

        {/* Skills */}
        <div className="flex flex-wrap gap-1 mb-2.5">
          {cand.skills.slice(0, 3).map((skill) => (
            <span
              key={skill}
              className="text-[10px] px-1.5 py-0.5 rounded bg-surface-2 text-text-secondary border border-border"
            >
              {skill}
            </span>
          ))}
          {cand.skills.length > 3 && (
            <span className="text-[10px] px-1.5 py-0.5 rounded bg-surface-2 text-text-muted border border-border">
              +{cand.skills.length - 3}
            </span>
          )}
        </div>

        {/* Footer */}
        <div className="flex items-center justify-between gap-2">
          <span className="text-[10px] text-text-muted truncate">{cand.email}</span>

          {hasPosition && (
            <button
              onClick={(e) => {
                e.stopPropagation();
                onToggleMap();
              }}
              className={cn(
                "shrink-0 text-[11px] font-bold px-2.5 py-1 rounded-lg border transition-all cursor-pointer flex items-center gap-1 leading-none",
                isMapped
                  ? "bg-emerald-500/10 text-emerald-600 border-emerald-500/20 hover:bg-red-500/10 hover:text-red-500 hover:border-red-500/20"
                  : "bg-surface-2 text-text-primary border-border hover:bg-yellow hover:text-navy hover:border-yellow",
              )}
            >
              {isMapped ? (
                <>
                  <IconCircleCheck className="size-3" />
                  Mapped
                </>
              ) : (
                <>
                  <IconChevronRight className="size-3" />
                  Map
                </>
              )}
            </button>
          )}
        </div>
      </div>
    </div>
  );
}

// ─── Drag overlay ghost ───────────────────────────────────────────────────────

function DragGhostCard({ cand }: Readonly<{ cand: MockCandidate & { dynamicScore: number } }>) {
  return (
    <div className="p-3.5 rounded-xl border border-yellow/50 bg-surface shadow-2xl shadow-yellow/20 w-64 rotate-1 opacity-95">
      <div className="flex items-center justify-between gap-2 mb-1.5">
        <h4 className="font-bold text-text-primary text-sm truncate">{cand.name}</h4>
        <span className="text-xs font-black text-navy bg-yellow/80 border border-yellow px-2 py-0.5 rounded-lg shrink-0">
          {cand.dynamicScore}%
        </span>
      </div>
      <p className="text-[11px] text-text-muted mb-2 truncate">{cand.previousCompany}</p>
      <div className="flex flex-wrap gap-1">
        {cand.skills.slice(0, 2).map((s) => (
          <span
            key={s}
            className="text-[9px] px-1.5 py-0.5 rounded bg-surface-2 text-text-secondary border border-border"
          >
            {s}
          </span>
        ))}
      </div>
    </div>
  );
}

// ─── Score computation ────────────────────────────────────────────────────────

function computeScore(cand: MockCandidate, position: MockPosition | null): number {
  let score = cand.matchScore;
  if (!position) return score;

  const role = position.role.toLowerCase();
  const dept = position.department.toLowerCase();
  const candSkills = cand.skills.map((s) => s.toLowerCase());

  if (role.includes("chef") || dept.includes("kitchen")) {
    const kw = ["chef", "oven", "cuisine", "food safety", "cooking", "tandoor"];
    const hits = candSkills.filter((s) => kw.some((k) => s.includes(k)));
    score = hits.length > 0 ? Math.min(score + 10, 100) : Math.max(score - 20, 40);
  } else if (role.includes("steward") || role.includes("captain") || role.includes("associate")) {
    const kw = ["service", "table", "guest", "pos", "billing", "hostess"];
    const hits = candSkills.filter((s) => kw.some((k) => s.includes(k)));
    score = hits.length > 0 ? Math.min(score + 10, 100) : Math.max(score - 20, 40);
  } else if (role.includes("bartender")) {
    const kw = ["mixology", "cocktail", "pouring", "bar"];
    const hits = candSkills.filter((s) => kw.some((k) => s.includes(k)));
    score = hits.length > 0 ? Math.min(score + 15, 100) : Math.max(score - 25, 30);
  } else if (role.includes("manager") || role.includes("head") || dept.includes("operations")) {
    const kw = ["operation", "management", "scheduling", "p&l", "staff", "admin"];
    const hits = candSkills.filter((s) => kw.some((k) => s.includes(k)));
    score = hits.length > 0 ? Math.min(score + 10, 100) : Math.max(score - 15, 45);
  }

  return Math.round(score);
}

// ─── Main Page ────────────────────────────────────────────────────────────────

export default function PositionsPage() {
  const {
    positions,
    candidates,
    mappings,
    selectedPositionId,
    setSelectedPositionId,
    mapCandidate,
    unmapCandidate,
  } = usePositionsStore();

  const [searchTerm, setSearchTerm] = useState("");
  const [selectedClient, setSelectedClient] = useState("All");
  const [activeDragCand, setActiveDragCand] = useState<
    (MockCandidate & { dynamicScore: number }) | null
  >(null);

  const clients = useMemo(
    () => ["All", ...Array.from(new Set(positions.map((p) => p.clientName)))],
    [positions],
  );

  const filteredPositions = useMemo(() => {
    const q = searchTerm.toLowerCase();
    return positions.filter((pos) => {
      const matchSearch =
        pos.role.toLowerCase().includes(q) ||
        pos.clientName.toLowerCase().includes(q) ||
        pos.department.toLowerCase().includes(q) ||
        pos.city.toLowerCase().includes(q);
      const matchClient = selectedClient === "All" || pos.clientName === selectedClient;
      return matchSearch && matchClient;
    });
  }, [positions, searchTerm, selectedClient]);

  const selectedPosition = useMemo(
    () => positions.find((p) => p.id === selectedPositionId) ?? null,
    [positions, selectedPositionId],
  );

  const displayedCandidates = useMemo(() => {
    const scored = candidates
      .map((c) => ({ ...c, dynamicScore: computeScore(c, selectedPosition) }))
      .sort((a, b) => b.dynamicScore - a.dynamicScore);
    return selectedPosition ? scored.slice(0, 10) : scored;
  }, [candidates, selectedPosition]);

  const sensors = useSensors(
    useSensor(PointerSensor, { activationConstraint: { distance: 5 } }),
    useSensor(KeyboardSensor),
  );

  function handleDragStart(event: DragStartEvent) {
    const cand = event.active.data.current?.cand as MockCandidate | undefined;
    if (cand) {
      setActiveDragCand({ ...cand, dynamicScore: computeScore(cand, selectedPosition) });
    }
  }

  function handleDragEnd(event: DragEndEvent) {
    const { active, over } = event;
    setActiveDragCand(null);
    if (!over) return;

    const candId = active.id as string;
    const positionId = over.id as string;
    const targetPos = positions.find((p) => p.id === positionId);
    if (!targetPos) return;

    const alreadyMapped = (mappings[positionId] ?? []).includes(candId);
    if (!alreadyMapped) {
      mapCandidate(positionId, candId);
      setSelectedPositionId(positionId);
    }
  }

  return (
    <DndContext
      id="positions-dnd"
      sensors={sensors}
      collisionDetection={closestCorners}
      onDragStart={handleDragStart}
      onDragEnd={handleDragEnd}
    >
      <div className="flex flex-col h-full overflow-hidden bg-canvas">
        {/* ── Page header ── */}
        <div className="px-6 pt-6 pb-5 border-b border-border shrink-0">
          <div className="flex items-center justify-between gap-4">
            <div>
              <h1 className="text-3xl font-heading font-bold text-text-primary tracking-wide">
                Open Positions
              </h1>
              <p className="text-sm mt-1 text-text-muted">
                Drag candidates onto a position to map them, or click a position to see top matches.
              </p>
            </div>
            <a
              href="/positions/new"
              className="flex items-center gap-2 px-4 py-2 rounded-lg bg-yellow text-navy hover:bg-yellow-dark text-sm font-bold transition-all shadow-md shadow-yellow/10 shrink-0"
            >
              <IconPlus className="size-4" />
              New Position
            </a>
          </div>
        </div>

        {/* ── Split pane ── */}
        <div className="flex flex-1 overflow-hidden">
          {/* ── LEFT: Positions ── */}
          <div className="w-[46%] flex flex-col border-r border-border overflow-hidden bg-canvas">
            {/* Search + filter */}
            <div className="p-4 border-b border-border shrink-0 space-y-2.5 bg-surface">
              <div className="relative">
                <IconSearch className="absolute left-3 top-1/2 -translate-y-1/2 size-4 text-text-muted" />
                <input
                  type="text"
                  placeholder="Search by role, client, dept, city..."
                  value={searchTerm}
                  onChange={(e) => setSearchTerm(e.target.value)}
                  className="w-full pl-9 pr-4 py-2 text-sm rounded-lg bg-surface-2 border border-border text-text-primary placeholder:text-text-muted focus:outline-none focus:border-yellow transition-all"
                />
              </div>
              <div className="flex items-center gap-2">
                <span className="text-[11px] text-text-muted font-semibold uppercase tracking-wider shrink-0">
                  Client
                </span>
                <select
                  value={selectedClient}
                  onChange={(e) => setSelectedClient(e.target.value)}
                  className="flex-1 px-3 py-1.5 text-sm rounded-lg bg-surface-2 border border-border text-text-primary focus:outline-none focus:border-yellow"
                >
                  {clients.map((c) => (
                    <option key={c} value={c}>
                      {c}
                    </option>
                  ))}
                </select>
                <span className="text-[11px] text-text-muted shrink-0 font-medium">
                  {filteredPositions.length}
                </span>
              </div>
            </div>

            {/* Position card list */}
            <div className="flex-1 overflow-y-auto p-4 space-y-3 dashboard-scrollbar">
              {filteredPositions.length === 0 ? (
                <div className="flex flex-col items-center justify-center h-40 text-text-muted gap-2">
                  <IconSearch className="size-8 opacity-20" />
                  <p className="text-sm">No positions match your filters.</p>
                </div>
              ) : (
                filteredPositions.map((pos) => {
                  const mappedCands = (mappings[pos.id] ?? [])
                    .map((id) => candidates.find((c) => c.id === id))
                    .filter(Boolean) as MockCandidate[];

                  return (
                    <PositionCard
                      key={pos.id}
                      position={pos}
                      isSelected={selectedPositionId === pos.id}
                      mappedCandidates={mappedCands}
                      onClick={() =>
                        setSelectedPositionId(selectedPositionId === pos.id ? null : pos.id)
                      }
                    />
                  );
                })
              )}
            </div>
          </div>

          {/* ── RIGHT: Candidates ── */}
          <div className="flex-1 flex flex-col overflow-hidden bg-surface">
            {/* Panel header */}
            <div className="px-5 py-4 border-b border-border shrink-0">
              <AnimatePresence mode="wait">
                {selectedPosition ? (
                  <motion.div
                    key="selected"
                    initial={{ opacity: 0, y: -4 }}
                    animate={{ opacity: 1, y: 0 }}
                    exit={{ opacity: 0, y: 4 }}
                    transition={{ duration: 0.15 }}
                    className="flex items-start justify-between gap-3"
                  >
                    <div>
                      <div className="flex items-center gap-2 mb-0.5">
                        <IconSparkles className="size-4 text-yellow shrink-0" />
                        <h2 className="text-sm font-bold text-text-primary uppercase tracking-wider font-heading">
                          Top 10 Matches
                        </h2>
                        <span className="text-[10px] font-bold text-navy bg-yellow/70 px-1.5 py-0.5 rounded-full border border-yellow/40">
                          AI Ranked
                        </span>
                      </div>
                      <p className="text-xs text-text-muted pl-6">
                        for{" "}
                        <span className="text-text-primary font-semibold">
                          {selectedPosition.role}
                        </span>{" "}
                        &bull; {selectedPosition.clientName}
                      </p>
                    </div>
                    <button
                      onClick={() => setSelectedPositionId(null)}
                      className="p-1.5 rounded-lg text-text-muted hover:text-text-primary hover:bg-surface-2 border border-transparent hover:border-border transition-all shrink-0"
                    >
                      <IconX className="size-4" />
                    </button>
                  </motion.div>
                ) : (
                  <motion.div
                    key="all"
                    initial={{ opacity: 0, y: -4 }}
                    animate={{ opacity: 1, y: 0 }}
                    exit={{ opacity: 0, y: 4 }}
                    transition={{ duration: 0.15 }}
                    className="flex items-center gap-2"
                  >
                    <IconUsers className="size-4 text-text-muted" />
                    <h2 className="text-sm font-bold text-text-primary uppercase tracking-wider font-heading">
                      Candidate Pool
                    </h2>
                    <span className="text-[11px] text-text-muted ml-1">
                      {candidates.length} total
                    </span>
                  </motion.div>
                )}
              </AnimatePresence>
            </div>

            {/* Hint banner */}
            <AnimatePresence>
              {!selectedPosition && (
                <motion.div
                  initial={{ opacity: 0, height: 0 }}
                  animate={{ opacity: 1, height: "auto" }}
                  exit={{ opacity: 0, height: 0 }}
                  className="overflow-hidden shrink-0"
                >
                  <div className="mx-4 mt-3 flex items-start gap-2.5 px-3 py-2.5 rounded-lg bg-yellow/5 border border-yellow/20 text-text-primary text-xs font-medium">
                    <IconBulb className="size-4 shrink-0 mt-0.5" />
                    <span>
                      Click a position on the left to see its top 10 matched candidates. You can
                      also drag any candidate directly onto a position card to map them.
                    </span>
                  </div>
                </motion.div>
              )}
            </AnimatePresence>

            {/* Candidate list */}
            <div className="flex-1 overflow-y-auto p-4 space-y-3 dashboard-scrollbar">
              <AnimatePresence mode="popLayout">
                {displayedCandidates.map((cand, idx) => {
                  const isMapped = selectedPosition
                    ? (mappings[selectedPosition.id] ?? []).includes(cand.id)
                    : false;

                  return (
                    <motion.div
                      key={cand.id}
                      layout
                      initial={{ opacity: 0, x: 10 }}
                      animate={{ opacity: 1, x: 0 }}
                      exit={{ opacity: 0, x: -10 }}
                      transition={{ duration: 0.15, delay: idx * 0.025 }}
                      className={selectedPosition ? "pl-5" : ""}
                    >
                      <DraggableCandidateCard
                        cand={cand}
                        rank={selectedPosition ? idx + 1 : undefined}
                        isMapped={isMapped}
                        hasPosition={!!selectedPosition}
                        onToggleMap={() => {
                          if (!selectedPosition) return;
                          if (isMapped) {
                            unmapCandidate(selectedPosition.id, cand.id);
                          } else {
                            mapCandidate(selectedPosition.id, cand.id);
                          }
                        }}
                      />
                    </motion.div>
                  );
                })}
              </AnimatePresence>
            </div>

            {/* Footer summary when position selected */}
            {selectedPosition && (
              <div className="px-5 py-3 border-t border-border flex items-center justify-between text-xs text-text-muted shrink-0">
                <span>
                  Mapped:{" "}
                  <strong className="text-text-primary">
                    {(mappings[selectedPosition.id] ?? []).length}
                  </strong>{" "}
                  / {selectedPosition.openingsCount} openings
                </span>
                <a
                  href={`/positions/${selectedPosition.id}/pipeline`}
                  className="font-bold text-navy bg-yellow/70 hover:bg-yellow px-3 py-1.5 rounded-lg transition-colors flex items-center gap-1"
                >
                  Kanban Pipeline &rarr;
                </a>
              </div>
            )}
          </div>
        </div>
      </div>

      {/* ── Drag overlay ── */}
      <DragOverlay dropAnimation={{ duration: 180, easing: "ease-out" }}>
        {activeDragCand ? <DragGhostCard cand={activeDragCand} /> : null}
      </DragOverlay>
    </DndContext>
  );
}
