"use client";

import React, { useState, useMemo } from "react";
import { AnimatePresence, motion } from "motion/react";
import {
  IconSearch,
  IconPlus,
  IconBriefcase,
  IconMapPin,
  IconCircleCheck,
  IconAlertCircle,
  IconUser,
  IconChevronRight,
  IconX,
  IconSparkles,
  IconBulb,
  IconGripVertical,
  IconArrowDown,
  IconUsers,
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

// --- Sub-components for DND ---

function DroppableZone({
  id,
  title,
  children,
  className,
  emptyState,
}: {
  id: string;
  title?: React.ReactNode;
  children: React.ReactNode;
  className?: string;
  emptyState?: React.ReactNode;
}) {
  const { setNodeRef, isOver } = useDroppable({ id });
  return (
    <div
      ref={setNodeRef}
      className={cn(
        "transition-all duration-200 min-h-[120px]",
        isOver && "bg-surface-2/80 outline-dashed outline-2 outline-yellow/50 rounded-xl",
        className,
      )}
    >
      {title && <div className="mb-3">{title}</div>}
      {React.Children.count(children) > 0 ? (
        <div className="space-y-3.5">{children}</div>
      ) : (
        emptyState
      )}
    </div>
  );
}

function DraggableCandidateCard({
  cand,
  isMapped,
  onAction,
}: {
  cand: MockCandidate & { dynamicScore: number };
  isMapped: boolean;
  onAction: () => void;
}) {
  const { attributes, listeners, setNodeRef, transform, isDragging } = useDraggable({
    id: cand.id,
    data: { cand, isMapped },
  });

  const style = transform
    ? {
        transform: `translate3d(${transform.x}px, ${transform.y}px, 0)`,
      }
    : undefined;

  return (
    <div
      ref={setNodeRef}
      style={style}
      className={cn(
        "p-4 rounded-xl border flex flex-col justify-between bg-surface-panel relative overflow-hidden group transition-all duration-200",
        isMapped
          ? "border-yellow/30 bg-yellow/[0.02]"
          : "border-border hover:border-gray-600 hover:shadow-lg",
        isDragging && "opacity-40 shadow-2xl scale-105 z-50 ring-2 ring-yellow",
      )}
    >
      {isMapped && <div className="absolute top-0 right-0 w-24 h-[3px] bg-yellow" />}

      <div className="flex items-start justify-between gap-2 mb-2">
        <div className="flex items-start gap-2">
          {/* Drag Handle */}
          <div
            {...attributes}
            {...listeners}
            className="mt-0.5 text-gray-500 hover:text-yellow cursor-grab active:cursor-grabbing p-1 -ml-1 rounded hover:bg-white/5"
          >
            <IconGripVertical className="size-4" />
          </div>
          <div>
            <h4 className="font-semibold text-white group-hover:text-yellow transition-colors">
              {cand.name}
            </h4>
            <p className="text-xs text-gray-400 mt-0.5">
              {cand.previousCompany} &bull; {cand.experienceYears} yrs exp
            </p>
          </div>
        </div>

        {/* Match score bubble */}
        <div
          className={cn(
            "text-xs font-bold px-2 py-1 rounded-lg flex items-center justify-center shrink-0",
            cand.dynamicScore >= 90
              ? "bg-emerald-500/10 text-emerald-400 border border-emerald-500/20"
              : cand.dynamicScore >= 80
                ? "bg-yellow/10 text-yellow border border-yellow/20"
                : "bg-gray-800 text-gray-400 border border-gray-700",
          )}
        >
          {cand.dynamicScore}% Match
        </div>
      </div>

      {/* Candidate Skills tags */}
      <div className="flex flex-wrap gap-1.5 mb-4 pl-8">
        {cand.skills.map((skill) => (
          <span
            key={skill}
            className="text-[10px] px-2 py-0.5 rounded bg-surface-2 text-gray-400 border border-border/50"
          >
            {skill}
          </span>
        ))}
      </div>

      {/* Map actions button */}
      <div className="flex items-center justify-between pt-3 border-t border-border/30 mt-auto pl-8">
        <span className="text-xs text-gray-500 flex items-center gap-1">
          <IconUser className="size-3 text-gray-500" />
          {cand.email}
        </span>

        {isMapped ? (
          <button
            onClick={onAction}
            className="flex items-center gap-1 px-3 py-1.5 rounded-lg text-xs font-semibold bg-emerald-500/15 text-emerald-400 border border-emerald-500/30 hover:bg-red-500/15 hover:text-red-400 hover:border-red-500/30 transition-colors cursor-pointer"
          >
            <IconCircleCheck className="size-4 shrink-0" />
            <span>Mapped</span>
          </button>
        ) : (
          <button
            onClick={onAction}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-semibold bg-surface-2 hover:bg-yellow hover:text-navy text-white border border-border hover:border-yellow transition-all cursor-pointer"
          >
            <IconChevronRight className="size-3.5" />
            <span>Map</span>
          </button>
        )}
      </div>
    </div>
  );
}

// --- Main Page Component ---

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

  const clients = useMemo(() => {
    const list = new Set(positions.map((p) => p.clientName));
    return ["All", ...Array.from(list)];
  }, [positions]);

  const filteredPositions = useMemo(() => {
    return positions.filter((pos) => {
      const matchesSearch =
        pos.id.toLowerCase().includes(searchTerm.toLowerCase()) ||
        pos.role.toLowerCase().includes(searchTerm.toLowerCase()) ||
        pos.clientName.toLowerCase().includes(searchTerm.toLowerCase()) ||
        pos.assignedTo.toLowerCase().includes(searchTerm.toLowerCase());

      const matchesClient = selectedClient === "All" || pos.clientName === selectedClient;

      return matchesSearch && matchesClient;
    });
  }, [positions, searchTerm, selectedClient]);

  const selectedPosition = useMemo(() => {
    return positions.find((p) => p.id === selectedPositionId) || null;
  }, [positions, selectedPositionId]);

  const suggestedCandidates = useMemo(() => {
    if (!selectedPosition) return [];

    return candidates
      .map((cand) => {
        let score = cand.matchScore;
        const role = selectedPosition.role.toLowerCase();
        const dept = selectedPosition.department.toLowerCase();
        const candSkills = cand.skills.map((s) => s.toLowerCase());

        if (role.includes("chef") || dept.includes("kitchen")) {
          const kitchenSkills = ["chef", "oven", "cuisine", "food safety", "cooking", "tandoor"];
          const matches = candSkills.filter((s) => kitchenSkills.some((k) => s.includes(k)));
          score = matches.length > 0 ? Math.min(score + 10, 100) : Math.max(score - 20, 40);
        } else if (
          role.includes("steward") ||
          role.includes("captain") ||
          role.includes("associate")
        ) {
          const serviceSkills = ["service", "table", "guest", "pos", "billing", "hostess"];
          const matches = candSkills.filter((s) => serviceSkills.some((k) => s.includes(k)));
          score = matches.length > 0 ? Math.min(score + 10, 100) : Math.max(score - 20, 40);
        } else if (role.includes("bartender")) {
          const barSkills = ["mixology", "cocktail", "pouring", "bar"];
          const matches = candSkills.filter((s) => barSkills.some((k) => s.includes(k)));
          score = matches.length > 0 ? Math.min(score + 15, 100) : Math.max(score - 25, 30);
        } else if (
          role.includes("manager") ||
          role.includes("head") ||
          dept.includes("operations")
        ) {
          const mgmtSkills = ["operation", "management", "scheduling", "p&l", "staff", "admin"];
          const matches = candSkills.filter((s) => mgmtSkills.some((k) => s.includes(k)));
          score = matches.length > 0 ? Math.min(score + 10, 100) : Math.max(score - 15, 45);
        }

        return {
          ...cand,
          dynamicScore: Math.round(score),
        };
      })
      .sort((a, b) => b.dynamicScore - a.dynamicScore);
  }, [candidates, selectedPosition]);

  // Split candidates for DND lists
  const mappedCandidatesList = useMemo(() => {
    if (!selectedPosition) return [];
    const mappedIds = mappings[selectedPosition.id] || [];
    return suggestedCandidates.filter((c) => mappedIds.includes(c.id));
  }, [suggestedCandidates, mappings, selectedPosition]);

  const unmappedCandidatesList = useMemo(() => {
    if (!selectedPosition) return [];
    const mappedIds = mappings[selectedPosition.id] || [];
    return suggestedCandidates.filter((c) => !mappedIds.includes(c.id));
  }, [suggestedCandidates, mappings, selectedPosition]);

  // DND Handlers
  const [activeDragCandidate, setActiveDragCandidate] = useState<
    (MockCandidate & { dynamicScore: number }) | null
  >(null);

  const sensors = useSensors(
    useSensor(PointerSensor, { activationConstraint: { distance: 5 } }),
    useSensor(KeyboardSensor),
  );

  const handleDragStart = (event: DragStartEvent) => {
    const { active } = event;
    setActiveDragCandidate(active.data.current?.cand || null);
  };

  const handleDragEnd = (event: DragEndEvent) => {
    const { active, over } = event;
    setActiveDragCandidate(null);

    if (!over || !selectedPosition) return;

    const candId = active.id as string;
    const isCurrentlyMapped = (mappings[selectedPosition.id] || []).includes(candId);

    if (over.id === "mapped-zone" && !isCurrentlyMapped) {
      mapCandidate(selectedPosition.id, candId);
    } else if (over.id === "suggested-zone" && isCurrentlyMapped) {
      unmapCandidate(selectedPosition.id, candId);
    }
  };

  return (
    <div className="p-6 md:p-8 flex flex-col h-full overflow-hidden bg-[var(--color-canvas)]">
      {/* Header controls */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 mb-6">
        <div>
          <h1 className="text-3xl font-bold font-heading text-white flex items-center gap-3 tracking-wide">
            Open Positions
          </h1>
          <p className="text-sm mt-1 text-gray-400">
            Manage active client positions, review quotas, and map suggested candidates.
          </p>
        </div>
        <div className="flex items-center gap-3">
          <a
            href="/positions/new"
            className="flex items-center gap-2 px-4 py-2 rounded-lg bg-yellow text-navy hover:bg-yellow-dark text-sm font-bold transition-all duration-200 cursor-pointer shadow-lg shadow-yellow/10"
          >
            <IconPlus className="size-4" />
            New Position
          </a>
        </div>
      </div>

      {/* Search & filters */}
      <div className="flex flex-col sm:flex-row items-center gap-3 mb-6 bg-surface p-4 rounded-xl border border-border shadow-sm">
        <div className="relative flex-1 w-full">
          <IconSearch className="absolute left-3 top-1/2 -translate-y-1/2 size-4 text-gray-500" />
          <input
            type="text"
            placeholder="Search by ID, role, client, or recruiter..."
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
            className="w-full pl-9 pr-4 py-2 text-sm rounded-lg bg-surface-2 border border-border text-white placeholder-gray-500 focus:outline-none focus:border-yellow transition-all"
          />
        </div>
        <div className="flex items-center gap-2 w-full sm:w-auto">
          <span className="text-xs font-semibold text-gray-400 uppercase tracking-wider shrink-0">
            Client:
          </span>
          <select
            value={selectedClient}
            onChange={(e) => setSelectedClient(e.target.value)}
            className="w-full sm:w-48 px-3 py-2 text-sm rounded-lg bg-surface-2 border border-border text-white focus:outline-none focus:border-yellow"
          >
            {clients.map((c) => (
              <option key={c} value={c}>
                {c}
              </option>
            ))}
          </select>
        </div>
      </div>

      {/* Client warning banner */}
      <div className="mb-4 flex items-center gap-3 px-4 py-2.5 rounded-lg bg-yellow/5 border border-yellow/20 text-yellow text-xs font-medium">
        <IconBulb className="size-4 shrink-0" />
        <span>
          Select Client Name &rarr; Position ID, Client ID, Filled and Remaining populate
          automatically. Teal columns are auto — do not edit.
        </span>
      </div>

      {/* Spreadsheet container */}
      <div className="flex-1 overflow-auto rounded-xl border border-border bg-surface shadow-xl dashboard-scrollbar relative">
        <table className="w-full text-left border-collapse min-w-[1200px]">
          <thead className="sticky top-0 z-10 bg-surface shadow-sm">
            {/* Sheet super title */}
            <tr className="bg-[var(--color-surface)] select-none">
              <th colSpan={11} className="py-3 px-6">
                <span className="font-heading text-sm tracking-widest text-white font-bold uppercase flex items-center gap-2">
                  OPEN POSITIONS REGISTRY
                </span>
              </th>
            </tr>
            {/* Sheet Column Headers */}
            <tr className="bg-surface-2 border-b border-border text-xs uppercase font-bold text-gray-400 tracking-wider">
              <th className="py-3.5 px-4 w-[140px] border-r border-border/50 text-yellow">
                Position ID
              </th>
              <th className="py-3.5 px-4 border-r border-border/50">Client Name</th>
              <th className="py-3.5 px-4 border-r border-border/50">Role</th>
              <th className="py-3.5 px-4 border-r border-border/50">Department</th>
              <th className="py-3.5 px-4 border-r border-border/50">City</th>
              <th className="py-3.5 px-4 border-r border-border/50">Seniority</th>
              <th className="py-3.5 px-4 border-r border-border/50">Date Opened</th>
              <th className="py-3.5 px-4 border-r border-border/50">Target Close</th>
              <th className="py-3.5 px-4 border-r border-border/50">Assigned To</th>
              <th className="py-3.5 px-4 border-r border-border/50 text-center w-[120px] bg-teal-950/20 text-teal-400">
                Openings
              </th>
              <th className="py-3.5 px-4 text-center w-[100px]">Status</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-border/40 text-sm text-gray-300">
            {filteredPositions.length === 0 ? (
              <tr>
                <td colSpan={11} className="py-12 text-center text-gray-500">
                  No positions matching search filters.
                </td>
              </tr>
            ) : (
              filteredPositions.map((pos) => {
                const isSelected = selectedPositionId === pos.id;

                return (
                  <tr
                    key={pos.id}
                    onClick={() => setSelectedPositionId(pos.id)}
                    className={cn(
                      "hover:bg-surface-2 cursor-pointer transition-colors border-r border-l border-transparent",
                      isSelected && "bg-surface-2 border-l-yellow border-r-yellow",
                      pos.status === "Closed" && "opacity-60",
                    )}
                  >
                    <td className="py-3.5 px-4 font-mono font-bold text-teal-400 border-r border-border/30">
                      {pos.id}
                    </td>
                    <td className="py-3.5 px-4 font-medium text-white border-r border-border/30">
                      {pos.clientName}
                    </td>
                    <td className="py-3.5 px-4 font-bold text-white border-r border-border/30">
                      {pos.role}
                      {pos.notes && (
                        <span className="ml-2 text-[10px] px-1.5 py-0.5 rounded bg-gray-800 text-gray-400 font-medium">
                          {pos.notes}
                        </span>
                      )}
                    </td>
                    <td className="py-3.5 px-4 border-r border-border/30">
                      <span className="text-[11px] font-semibold px-2.5 py-1 rounded-full bg-surface-2 text-gray-300 border border-border shadow-sm">
                        {pos.department}
                      </span>
                    </td>
                    <td className="py-3.5 px-4 border-r border-border/30 flex items-center gap-1.5 font-medium">
                      <IconMapPin className="size-3.5 text-gray-400 shrink-0" />
                      {pos.city}
                    </td>
                    <td className="py-3.5 px-4 border-r border-border/30">
                      <span
                        className={cn(
                          "text-[11px] font-bold px-2.5 py-1 rounded-full",
                          pos.seniority === "Junior" && "text-blue-400 bg-blue-500/10",
                          pos.seniority === "Mid" && "text-yellow bg-yellow/10",
                          pos.seniority === "Senior" && "text-purple-400 bg-purple-500/10",
                        )}
                      >
                        {pos.seniority}
                      </span>
                    </td>
                    <td className="py-3.5 px-4 border-r border-border/30 text-gray-400 font-medium">
                      {pos.dateOpened}
                    </td>
                    <td className="py-3.5 px-4 border-r border-border/30 text-gray-400 font-medium">
                      {pos.targetClose}
                    </td>
                    <td className="py-3.5 px-4 border-r border-border/30 font-semibold text-gray-200">
                      {pos.assignedTo}
                    </td>
                    <td className="py-3.5 px-4 border-r border-border/30 text-center bg-teal-950/10 font-bold text-teal-400 text-base">
                      {pos.openingsCount}
                    </td>
                    <td className="py-3.5 px-4 text-center">
                      <div className="flex items-center justify-center gap-1.5">
                        {pos.status === "Open" ? (
                          <span className="flex items-center gap-1 px-2.5 py-1 rounded-full text-[11px] font-bold bg-emerald-500/10 text-emerald-400 border border-emerald-500/20 shadow-sm">
                            <IconCircleCheck className="size-3.5" />
                            Open
                          </span>
                        ) : (
                          <span className="flex items-center gap-1 px-2.5 py-1 rounded-full text-[11px] font-bold bg-red-500/10 text-red-400 border border-red-500/20 shadow-sm">
                            <IconAlertCircle className="size-3.5" />
                            Closed
                          </span>
                        )}
                      </div>
                    </td>
                  </tr>
                );
              })
            )}
          </tbody>
        </table>
      </div>

      {/* Suggested Candidates Side Drawer / Panel */}
      <AnimatePresence>
        {selectedPosition && (
          <>
            {/* Backdrop Overlay */}
            <motion.div
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              onClick={() => setSelectedPositionId(null)}
              className="fixed inset-0 bg-black/60 backdrop-blur-sm z-40 transition-opacity"
            />

            {/* Slide-over panel */}
            <motion.div
              initial={{ x: "100%" }}
              animate={{ x: 0 }}
              exit={{ x: "100%" }}
              transition={{ type: "spring", damping: 25, stiffness: 220 }}
              className="fixed right-0 top-0 bottom-0 w-full sm:w-[480px] bg-[var(--color-surface)] border-l border-border shadow-2xl z-50 flex flex-col"
            >
              <DndContext
                id="positions-mapping-dnd-context"
                sensors={sensors}
                collisionDetection={closestCorners}
                onDragStart={handleDragStart}
                onDragEnd={handleDragEnd}
              >
                {/* Drawer Header */}
                <div className="p-6 border-b border-border bg-[var(--color-surface)] flex items-start justify-between">
                  <div>
                    <div className="flex items-center gap-2 mb-2">
                      <span className="font-mono text-xs text-teal-400 font-bold px-2 py-0.5 bg-teal-500/10 rounded">
                        {selectedPosition.id}
                      </span>
                      <span className="text-[10px] px-2 py-0.5 rounded-full border border-yellow/30 text-yellow font-bold uppercase tracking-wider">
                        {selectedPosition.status}
                      </span>
                    </div>
                    <h2 className="text-2xl font-bold font-heading text-white uppercase tracking-wide">
                      {selectedPosition.role}
                    </h2>
                    <p className="text-xs mt-1 text-gray-400 font-medium">
                      Quotas: {selectedPosition.clientName} &bull; {selectedPosition.department}
                    </p>
                  </div>
                  <button
                    onClick={() => setSelectedPositionId(null)}
                    className="p-1.5 rounded-lg bg-surface-2 border border-border text-gray-400 hover:text-white hover:bg-surface-3 transition-colors"
                  >
                    <IconX className="size-5" />
                  </button>
                </div>

                {/* Position metadata banner */}
                <div className="px-6 py-4 bg-[var(--color-canvas)] border-b border-border text-xs flex justify-between text-gray-300">
                  <div>
                    <span className="text-gray-500 block font-semibold mb-0.5 text-[10px]">
                      SENIORITY
                    </span>
                    <span className="font-bold text-white text-sm">
                      {selectedPosition.seniority}
                    </span>
                  </div>
                  <div>
                    <span className="text-gray-500 block font-semibold mb-0.5 text-[10px]">
                      CITY
                    </span>
                    <span className="font-bold text-white text-sm">{selectedPosition.city}</span>
                  </div>
                  <div>
                    <span className="text-gray-500 block font-semibold mb-0.5 text-[10px]">
                      ASSIGNED TO
                    </span>
                    <span className="font-bold text-white text-sm">
                      {selectedPosition.assignedTo}
                    </span>
                  </div>
                  <div>
                    <span className="text-gray-500 block font-semibold mb-0.5 text-[10px]">
                      OPENINGS
                    </span>
                    <span className="font-bold text-teal-400 text-lg text-center block leading-none">
                      {selectedPosition.openingsCount}
                    </span>
                  </div>
                </div>

                {/* Drawer list area */}
                <div className="flex-1 overflow-y-auto p-6 space-y-8 dashboard-scrollbar bg-[var(--color-canvas)]">
                  {/* MAPPED CANDIDATES DROP ZONE */}
                  <div className="relative">
                    <DroppableZone
                      id="mapped-zone"
                      title={
                        <div className="flex items-center justify-between">
                          <h3 className="text-xs font-bold uppercase text-emerald-400 flex items-center gap-1.5 tracking-wide">
                            <IconCircleCheck className="size-4" />
                            Mapped Candidates ({mappedCandidatesList.length})
                          </h3>
                        </div>
                      }
                      emptyState={
                        <div className="border-2 border-dashed border-border rounded-xl p-8 flex flex-col items-center justify-center text-gray-500 bg-surface-panel/30">
                          <IconArrowDown className="size-6 mb-2 text-gray-600 animate-bounce" />
                          <p className="text-sm font-medium">Drag candidates here to map them</p>
                          <p className="text-xs mt-1">
                            Or click &apos;Map&apos; on a candidate card
                          </p>
                        </div>
                      }
                    >
                      {mappedCandidatesList.map((cand) => (
                        <DraggableCandidateCard
                          key={cand.id}
                          cand={cand}
                          isMapped={true}
                          onAction={() => unmapCandidate(selectedPosition.id, cand.id)}
                        />
                      ))}
                    </DroppableZone>
                  </div>

                  <hr className="border-border/60" />

                  {/* SUGGESTED CANDIDATES DROP ZONE */}
                  <div>
                    <DroppableZone
                      id="suggested-zone"
                      title={
                        <div className="flex items-center justify-between mb-2">
                          <h3 className="text-xs font-bold uppercase text-yellow flex items-center gap-1.5 tracking-wide">
                            <IconSparkles className="size-4 text-yellow" />
                            Smart Candidate Matches
                          </h3>
                          <span className="text-[10px] text-gray-500 uppercase tracking-wider font-semibold">
                            Drag to re-assign
                          </span>
                        </div>
                      }
                      emptyState={
                        <div className="text-center p-8 text-gray-500">
                          <IconUsers className="size-8 mx-auto mb-2 opacity-50" />
                          <p className="text-sm">No more matches available.</p>
                        </div>
                      }
                    >
                      {unmappedCandidatesList.map((cand) => (
                        <DraggableCandidateCard
                          key={cand.id}
                          cand={cand}
                          isMapped={false}
                          onAction={() => mapCandidate(selectedPosition.id, cand.id)}
                        />
                      ))}
                    </DroppableZone>
                  </div>
                </div>

                {/* Drag Overlay (Visible only while dragging) */}
                <DragOverlay>
                  {activeDragCandidate ? (
                    <DraggableCandidateCard
                      cand={activeDragCandidate}
                      isMapped={(mappings[selectedPosition.id] || []).includes(
                        activeDragCandidate.id,
                      )}
                      onAction={() => {}}
                    />
                  ) : null}
                </DragOverlay>

                {/* Drawer Footer summary */}
                <div className="p-5 border-t border-border bg-[var(--color-surface)] flex items-center justify-between text-xs text-gray-400">
                  <span>
                    Mapped: <strong>{(mappings[selectedPosition.id] || []).length}</strong> /{" "}
                    {selectedPosition.openingsCount} Openings
                  </span>
                  <a
                    href={`/positions/${selectedPosition.id}/pipeline`}
                    className="font-bold text-yellow hover:underline flex items-center gap-1 bg-yellow/10 px-3 py-1.5 rounded-lg transition-colors hover:bg-yellow/20"
                  >
                    Go to Kanban Pipeline &rarr;
                  </a>
                </div>
              </DndContext>
            </motion.div>
          </>
        )}
      </AnimatePresence>
    </div>
  );
}
