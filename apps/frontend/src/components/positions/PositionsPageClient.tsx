"use client";

import React, { useState, useEffect } from "react";
import { useSearchParams } from "next/navigation";
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
  IconTrash,
  IconPencil,
} from "@tabler/icons-react";
import { cn } from "@/lib/utils";
import { useApiFetch } from "@/lib/api";
import {
  listPositions,
  getPositionFilters,
  getTopCandidates,
  mapCandidateToPosition,
  unmapCandidateFromPosition,
  deletePosition,
  reopenPosition,
} from "@/lib/api/positions";
import { clientFetchCandidates } from "@/lib/api/candidates.client";
import type { ApiClientOption, ApiPosition, ApiTopCandidate, ApiPositionFilters } from "@/types";
import AddPositionModal from "@/components/positions/AddPositionModal";
import { useToast } from "@/components/ui/Toast";
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
import PositionCardSkeleton from "@/components/positions/skeletons/PositionCardSkeleton";
import PositionTableSkeleton from "@/components/positions/skeletons/PositionTableSkeleton";

// ─── Helpers ─────────────────────────────────────────────────────────────────

const POSITION_STATUS_LABELS: Record<string, string> = {
  open: "Open",
  on_hold: "On Hold",
  closed: "Closed",
};

function mappedLabel(count: number, preview: ApiPosition["mapped_preview"]): string {
  if (count === 1 && preview[0]) return preview[0].full_name;
  if (count <= 3)
    return preview
      .slice(0, count)
      .map((mp) => mp.full_name.split(" ")[0])
      .join(", ");
  return `${count} mapped`;
}

function applyMappingDelta(
  positions: ApiPosition[],
  positionId: string,
  delta: 1 | -1,
  candidate: Pick<ApiTopCandidate, "id" | "full_name">,
): ApiPosition[] {
  return positions.map((p) => {
    if (p.id !== positionId) return p;
    if (delta === 1) {
      return {
        ...p,
        mapped_count: p.mapped_count + 1,
        mapped_preview:
          p.mapped_preview.length < 5
            ? [...p.mapped_preview, { id: candidate.id, full_name: candidate.full_name }]
            : p.mapped_preview,
      };
    }
    return {
      ...p,
      mapped_count: Math.max(0, p.mapped_count - 1),
      mapped_preview: p.mapped_preview.filter((mp) => mp.id !== candidate.id),
    };
  });
}

// ─── Position Card ────────────────────────────────────────────────────────────

function PositionCard({
  position,
  isSelected,
  onClick,
  isMaintainer,
  onDelete,
  onReopen,
  onEdit,
}: Readonly<{
  position: ApiPosition;
  isSelected: boolean;
  onClick: () => void;
  isMaintainer?: boolean;
  onDelete?: (id: string) => Promise<void>;
  onReopen?: (id: string) => Promise<void>;
  onEdit?: (position: ApiPosition) => void;
}>) {
  const { setNodeRef, isOver } = useDroppable({ id: position.id });
  const [confirmDelete, setConfirmDelete] = React.useState(false);
  const [deleting, setDeleting] = React.useState(false);
  const [reopening, setReopening] = React.useState(false);

  const total = position.total_seats;
  const filled = position.mapped_count;
  const progress = total > 0 ? Math.min((filled / total) * 100, 100) : 0;
  const isActive = position.status === "open";
  const statusLabel = POSITION_STATUS_LABELS[position.status] ?? "Closed";

  async function handleDeleteClick(e: React.MouseEvent) {
    e.stopPropagation();
    if (!confirmDelete) {
      setConfirmDelete(true);
      return;
    }
    if (!onDelete) return;
    setDeleting(true);
    try {
      await onDelete(position.id);
    } finally {
      setDeleting(false);
      setConfirmDelete(false);
    }
  }

  async function handleReopenClick(e: React.MouseEvent) {
    e.stopPropagation();
    if (!onReopen) return;
    setReopening(true);
    try {
      await onReopen(position.id);
    } finally {
      setReopening(false);
    }
  }

  return (
    <motion.div
      ref={setNodeRef}
      layout
      initial={{ opacity: 0, y: 6 }}
      animate={{ opacity: 1, y: 0 }}
      onClick={onClick}
      onKeyDown={(e) => {
        if (e.key === "Enter" || e.key === " ") {
          e.preventDefault();
          onClick();
        }
      }}
      tabIndex={0}
      role="button"
      aria-pressed={isSelected}
      className={cn(
        "relative p-4 rounded-xl border cursor-pointer select-none overflow-hidden transition-all duration-200 focus:outline-none focus-visible:ring-2 focus-visible:ring-yellow",
        isSelected
          ? "border-yellow bg-surface-panel shadow-md shadow-yellow/5"
          : "border-border bg-surface-panel hover:border-border hover:shadow-sm",
        isOver && "border-yellow/70 shadow-lg shadow-yellow/10 scale-[1.01]",
        !isActive && "opacity-60",
      )}
    >
      {isSelected && (
        <div className="absolute left-0 top-3 bottom-3 w-0.75 bg-yellow rounded-r-full" />
      )}

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

      {/* Top row */}
      <div className="flex items-start justify-between gap-3 mb-2">
        <div className="flex-1 min-w-0">
          <div className="mb-1 flex items-center gap-2">
            <span
              className={cn(
                "inline-flex items-center gap-0.5 text-[10px] font-bold px-1.5 py-0.5 rounded-full uppercase",
                isActive
                  ? "text-emerald-600 bg-emerald-500/10 border border-emerald-500/20"
                  : "text-red-500 bg-red-500/10 border border-red-500/20",
              )}
            >
              {isActive ? (
                <IconCircleCheck className="size-2.5" />
              ) : (
                <IconAlertCircle className="size-2.5" />
              )}
              {statusLabel}
            </span>
            {!isActive && isMaintainer && onReopen && (
              <button
                type="button"
                onClick={handleReopenClick}
                disabled={reopening}
                className="pointer-events-auto relative z-10 text-[10px] font-bold px-2 py-0.5 rounded-full bg-emerald-500/10 text-emerald-600 border border-emerald-500/20 hover:bg-emerald-500/20 transition-colors disabled:opacity-60"
              >
                {reopening ? "…" : "Reopen"}
              </button>
            )}
          </div>
          <h3 className="font-heading font-bold text-text-primary text-[15px] leading-snug truncate">
            {position.role}
          </h3>
          <p className="text-xs text-text-secondary mt-0.5 truncate font-medium">
            {position.client_name}
          </p>
        </div>
        <div className="shrink-0 flex flex-col items-center gap-1 min-w-9">
          <div className="text-center">
            <div className="text-2xl font-black text-teal-500 leading-none">{total}</div>
            <div className="text-[9px] text-text-muted uppercase font-bold tracking-wider mt-0.5">
              seats
            </div>
          </div>
          {isMaintainer && (
            <div className="flex gap-0.5">
              {onEdit && (
                <button
                  type="button"
                  onClick={(e) => {
                    e.stopPropagation();
                    onEdit(position);
                  }}
                  aria-label="Edit position"
                  className="pointer-events-auto p-1 rounded-lg text-text-muted hover:text-yellow hover:bg-yellow/10 transition-colors z-10 relative"
                >
                  <IconPencil className="size-3.5" />
                </button>
              )}
              {onDelete &&
                (confirmDelete ? (
                  <button
                    type="button"
                    onClick={handleDeleteClick}
                    disabled={deleting}
                    className="pointer-events-auto text-[10px] font-bold px-2 py-0.5 rounded-lg bg-red-500/90 text-white hover:bg-red-600 transition-colors disabled:opacity-60 z-10 relative"
                  >
                    {deleting ? "…" : "Confirm?"}
                  </button>
                ) : (
                  <button
                    type="button"
                    onClick={handleDeleteClick}
                    aria-label="Delete position"
                    className="pointer-events-auto p-1 rounded-lg text-text-muted hover:text-red-400 hover:bg-red-500/10 transition-colors z-10 relative"
                  >
                    <IconTrash className="size-3.5" />
                  </button>
                ))}
            </div>
          )}
        </div>
      </div>
      {confirmDelete && (
        <button
          type="button"
          aria-label="Cancel delete"
          className="fixed inset-0 z-0 cursor-default"
          onClick={(e) => {
            e.stopPropagation();
            setConfirmDelete(false);
          }}
        />
      )}

      {/* Tags row */}
      <div className="flex flex-wrap gap-1.5 mb-3">
        {position.department && (
          <span className="text-[10px] px-2 py-0.5 rounded-full bg-surface-2 border border-border text-text-secondary font-medium">
            {position.department}
          </span>
        )}
        <span
          className={cn(
            "text-[10px] px-2 py-0.5 rounded-full font-bold",
            position.seniority?.toLowerCase() === "junior" &&
              "bg-blue-500/10 text-blue-500 border border-blue-500/20",
            position.seniority?.toLowerCase() === "mid" &&
              "bg-yellow/20 text-navy border border-yellow/40",
            position.seniority?.toLowerCase() === "senior" &&
              "bg-purple-500/10 text-purple-500 border border-purple-500/20",
          )}
        >
          {position.seniority}
        </span>
        {position.city && (
          <span className="text-[10px] px-2 py-0.5 rounded-full bg-surface-2 border border-border text-text-muted flex items-center gap-0.5">
            <IconMapPin className="size-2.5 shrink-0" />
            {position.city}
          </span>
        )}
      </div>

      {/* Pipeline fill progress */}
      <div className="mb-2.5">
        <div className="flex justify-between items-center mb-1">
          <span className="text-[10px] text-text-muted font-semibold uppercase tracking-wider">
            Pipeline
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

      {/* Mapped candidate avatars */}
      {position.mapped_preview.length > 0 && (
        <div className="flex items-center gap-2 mt-1.5">
          <div className="flex -space-x-1.5">
            {position.mapped_preview.slice(0, 5).map((mp) => (
              <div
                key={mp.id}
                title={mp.full_name}
                className="size-6 rounded-full bg-yellow border-2 border-surface flex items-center justify-center text-[9px] font-black text-navy"
              >
                {mp.full_name
                  .split(" ")
                  .map((n) => n[0])
                  .join("")
                  .slice(0, 2)}
              </div>
            ))}
            {position.mapped_count > 5 && (
              <div className="size-6 rounded-full bg-surface-2 border-2 border-surface flex items-center justify-center text-[9px] font-bold text-text-muted">
                +{position.mapped_count - 5}
              </div>
            )}
          </div>
          <span className="text-[10px] text-text-secondary font-medium truncate">
            {mappedLabel(position.mapped_count, position.mapped_preview)}
          </span>
        </div>
      )}
    </motion.div>
  );
}

// ─── Candidate Card ────────────────────────────────────────────────────────────

function DraggableCandidateCard({
  cand,
  rank,
  isMapped,
  isClient,
  onToggleMap,
}: Readonly<{
  cand: ApiTopCandidate;
  rank: number;
  isMapped: boolean;
  isClient?: boolean;
  onToggleMap: () => void;
}>) {
  const { attributes, listeners, setNodeRef, transform, isDragging } = useDraggable({
    id: cand.id,
    data: { cand },
  });

  const style = transform
    ? { transform: `translate3d(${transform.x}px, ${transform.y}px, 0)` }
    : undefined;

  // match_score is 0..1 from the API; convert to percentage integer
  const score = typeof cand.match_score === "number" ? Math.round(cand.match_score * 100) : null;

  const scoreBadgeClass = cn(
    "text-xs font-black px-2.5 py-1 rounded-full shrink-0 leading-none",
    score !== null &&
      score >= 90 &&
      "bg-emerald-500/10 text-emerald-500 border border-emerald-500/30",
    score !== null &&
      score >= 70 &&
      score < 90 &&
      "bg-yellow/10 text-yellow border border-yellow/30",
    score !== null && score < 70 && "bg-surface-2 text-text-muted border border-border",
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

      {/* Drag handle */}
      {!isClient && (
        <div
          {...attributes}
          {...listeners}
          className="mt-0.5 text-text-muted hover:text-yellow cursor-grab active:cursor-grabbing p-1 rounded hover:bg-surface-2 shrink-0 touch-none transition-colors"
        >
          <IconGripVertical className="size-4" />
        </div>
      )}

      <div className="flex-1 min-w-0">
        {/* Name + score */}
        <div className="flex items-start justify-between gap-2 mb-1.5">
          <div className="min-w-0">
            <h4 className="font-semibold text-sm text-text-primary group-hover-accent truncate transition-colors">
              {cand.full_name}
            </h4>
            <p className="text-[11px] text-text-muted mt-0.5 truncate">
              {cand.previous_company ? `${cand.previous_company} · ` : ""}
              {cand.experience_years}y exp
            </p>
          </div>
          {score !== null && <div className={scoreBadgeClass}>{score}%</div>}
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
          {!isClient && (
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

function DragGhostCard({ cand }: Readonly<{ cand: ApiTopCandidate }>) {
  const score = typeof cand.match_score === "number" ? Math.round(cand.match_score * 100) : null;
  return (
    <div className="p-3.5 rounded-xl border border-yellow/50 bg-surface shadow-2xl shadow-yellow/20 w-64 rotate-1 opacity-95">
      <div className="flex items-center justify-between gap-2 mb-1.5">
        <h4 className="font-bold text-text-primary text-sm truncate">{cand.full_name}</h4>
        {score !== null && (
          <span className="text-xs font-black text-yellow bg-yellow/10 border border-yellow/30 px-2.5 py-1 rounded-full shrink-0">
            {score}%
          </span>
        )}
      </div>
      <p className="text-[11px] text-text-muted mb-2 truncate">{cand.previous_company}</p>
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

// ─── Main Page ────────────────────────────────────────────────────────────────

interface PositionsPageClientProps {
  /** Resolved server-side by the page and passed down — avoids the client
   *  re-fetching /auth/me and briefly rendering staff-only affordances
   *  (client filter, "+ New Position", drag hints) before the role is known. */
  isClient: boolean;
  isMaintainer: boolean;
}

export default function PositionsPageClient({ isClient, isMaintainer }: PositionsPageClientProps) {
  const apiFetch = useApiFetch();
  const searchParams = useSearchParams();

  const [positions, setPositions] = useState<ApiPosition[]>([]);
  const [positionsLoading, setPositionsLoading] = useState(true);
  const [filters, setFilters] = useState<ApiPositionFilters | null>(null);

  const [candidates, setCandidates] = useState<ApiTopCandidate[]>([]);
  const [candidatesLoading, setCandidatesLoading] = useState(false);

  const [searchTerm, setSearchTerm] = useState("");
  const [debouncedSearch, setDebouncedSearch] = useState("");
  const [candidateSearch, setCandidateSearch] = useState("");
  const [debouncedCandidateSearch, setDebouncedCandidateSearch] = useState("");
  const [selectedClientId, setSelectedClientId] = useState("");
  // Pre-select a position when arriving via a deep link (e.g. the dashboard's
  // "Your Open Positions" preview) — read once on mount, not kept in sync with
  // later URL changes, since selection afterwards is purely local UI state.
  const [selectedPositionId, setSelectedPositionId] = useState<string | null>(() =>
    searchParams.get("position"),
  );
  const [activeDragCand, setActiveDragCand] = useState<ApiTopCandidate | null>(null);
  const [addPositionOpen, setAddPositionOpen] = useState(false);
  const [editingPosition, setEditingPosition] = useState<ApiPosition | null>(null);

  const toast = useToast();

  // Debounce search inputs
  useEffect(() => {
    const t = setTimeout(() => {
      setDebouncedSearch(searchTerm);
      setDebouncedCandidateSearch(candidateSearch);
    }, 300);
    return () => clearTimeout(t);
  }, [searchTerm, candidateSearch]);

  // Load filter options once
  useEffect(() => {
    getPositionFilters(apiFetch).then(setFilters).catch(console.error);
  }, [apiFetch]);

  // Reload positions when search or client filter changes
  useEffect(() => {
    async function load() {
      setPositionsLoading(true);
      try {
        const res = await listPositions(apiFetch, {
          search: debouncedSearch || undefined,
          client_id: selectedClientId || undefined,
          limit: 100,
        });
        setPositions(res.items);
      } catch (err) {
        console.error(err);
      } finally {
        setPositionsLoading(false);
      }
    }
    void load();
  }, [apiFetch, debouncedSearch, selectedClientId]);

  // Load candidates when selected position or search changes
  useEffect(() => {
    async function load() {
      if (!selectedPositionId) {
        setCandidates([]);
        return;
      }
      setCandidatesLoading(true);
      try {
        if (debouncedCandidateSearch.trim()) {
          const res = await clientFetchCandidates({
            search: debouncedCandidateSearch.trim(),
            limit: 25,
            page: 1,
          });
          setCandidates((prev) => {
            const mappedPreviewIds = new Set(
              positions
                .find((p) => p.id === selectedPositionId)
                ?.mapped_preview.map((mp) => mp.id) ?? [],
            );
            return res.items.map((c) => ({
              id: c.id,
              full_name: c.full_name,
              email: c.email,
              phone: c.phone,
              previous_company: c.previous_company,
              experience_years: c.experience_years,
              education_level: c.education_level,
              skills: c.skills,
              tags: c.tags,
              preferred_train_line: c.preferred_train_line,
              resume_url: c.resume_url,
              match_score: null,
              is_mapped: prev.find((pc) => pc.id === c.id)?.is_mapped ?? mappedPreviewIds.has(c.id),
            }));
          });
        } else {
          const result = await getTopCandidates(apiFetch, selectedPositionId);
          setCandidates(result);
        }
      } catch (err) {
        console.error(err);
      } finally {
        setCandidatesLoading(false);
      }
    }
    void load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [apiFetch, selectedPositionId, debouncedCandidateSearch]);

  const selectedPosition = positions.find((p) => p.id === selectedPositionId) ?? null;

  /** Fold a client added from the position modal into the cached filter options
   *  so it appears in the client filter dropdown too, without a refetch. */
  function addClientToFilters(client: ApiClientOption) {
    setFilters((prev) => {
      if (!prev) return prev;
      if (prev.clients.some((c) => c.id === client.id)) return prev;
      return {
        ...prev,
        clients: [...prev.clients, client].sort((a, b) => a.name.localeCompare(b.name)),
      };
    });
  }

  function applyPositionMappingDelta(
    positionId: string,
    delta: 1 | -1,
    cand: Pick<ApiTopCandidate, "id" | "full_name">,
  ) {
    setPositions((prev) => applyMappingDelta(prev, positionId, delta, cand));
  }

  async function doMap(positionId: string, candidateId: string) {
    const cand = candidates.find((c) => c.id === candidateId);
    if (!cand) return;

    setCandidates((prev) =>
      prev.map((c) => (c.id === candidateId ? { ...c, is_mapped: true } : c)),
    );
    setPositions((prev) => applyMappingDelta(prev, positionId, 1, cand));

    try {
      await mapCandidateToPosition(apiFetch, positionId, candidateId);
    } catch {
      setCandidates((prev) =>
        prev.map((c) => (c.id === candidateId ? { ...c, is_mapped: false } : c)),
      );
      setPositions((prev) => applyMappingDelta(prev, positionId, -1, cand));
    }
  }

  async function doUnmap(positionId: string, candidateId: string) {
    const cand = candidates.find((c) => c.id === candidateId);
    if (!cand) return;

    const prevPos = positions.find((p) => p.id === positionId);
    const prevCount = prevPos?.mapped_count ?? 0;
    const prevPreview = prevPos?.mapped_preview ?? [];

    setCandidates((prev) =>
      prev.map((c) => (c.id === candidateId ? { ...c, is_mapped: false } : c)),
    );
    setPositions((prev) => applyMappingDelta(prev, positionId, -1, cand));

    try {
      await unmapCandidateFromPosition(apiFetch, positionId, candidateId);
    } catch {
      setCandidates((prev) =>
        prev.map((c) => (c.id === candidateId ? { ...c, is_mapped: true } : c)),
      );
      setPositions((prev) =>
        prev.map((p) =>
          p.id === positionId ? { ...p, mapped_count: prevCount, mapped_preview: prevPreview } : p,
        ),
      );
    }
  }

  async function handleDeletePosition(id: string) {
    await deletePosition(apiFetch, id);
    setPositions((prev) => prev.filter((p) => p.id !== id));
    if (selectedPositionId === id) setSelectedPositionId(null);
  }

  async function handleReopenPosition(id: string) {
    const updated = await reopenPosition(apiFetch, id);
    setPositions((prev) => prev.map((p) => (p.id === id ? { ...p, ...updated } : p)));
  }

  function handleUpdatePosition(updated: ApiPosition) {
    setPositions((prev) => prev.map((p) => (p.id === updated.id ? { ...p, ...updated } : p)));
    toast(`Position "${updated.role}" updated`, "success");
  }

  const sensors = useSensors(
    useSensor(PointerSensor, { activationConstraint: { distance: 5 } }),
    useSensor(KeyboardSensor),
  );

  function handleDragStart(event: DragStartEvent) {
    const cand = event.active.data.current?.cand as ApiTopCandidate | undefined;
    if (cand) setActiveDragCand(cand);
  }

  async function handleDragEnd(event: DragEndEvent) {
    const { active, over } = event;
    setActiveDragCand(null);
    if (!over) return;

    const candId = active.id as string;
    const positionId = over.id as string;
    if (!positions.some((p) => p.id === positionId)) return;

    const draggedCand = active.data.current?.cand as ApiTopCandidate | undefined;

    // If dropping onto the currently selected position, use full optimistic update
    if (selectedPositionId === positionId) {
      const alreadyMapped = candidates.find((c) => c.id === candId)?.is_mapped ?? false;
      if (!alreadyMapped) await doMap(positionId, candId);
      return;
    }

    // Dropping onto a different position — switch selection + partial optimistic update
    setSelectedPositionId(positionId);

    if (draggedCand) {
      applyPositionMappingDelta(positionId, 1, draggedCand);
      try {
        await mapCandidateToPosition(apiFetch, positionId, candId);
      } catch {
        applyPositionMappingDelta(positionId, -1, draggedCand);
      }
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
                Click a position to see top matched candidates.
                {!isClient && " Drag candidates onto a position to map them."}
              </p>
            </div>
            {!isClient && (
              <button
                type="button"
                onClick={() => setAddPositionOpen(true)}
                className="flex items-center gap-2 px-4 py-2 rounded-lg bg-yellow text-navy hover:bg-yellow-dark text-sm font-bold transition-all shadow-md shadow-yellow/10 shrink-0"
              >
                <IconPlus className="size-4" />
                New Position
              </button>
            )}
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
              {!isClient && (
                <div className="flex items-center gap-2">
                  <span className="text-[11px] text-text-muted font-semibold uppercase tracking-wider shrink-0">
                    Client
                  </span>
                  <select
                    value={selectedClientId}
                    onChange={(e) => setSelectedClientId(e.target.value)}
                    className="flex-1 px-3 py-1.5 text-sm rounded-lg bg-surface-2 border border-border text-text-primary focus:outline-none focus:border-yellow"
                  >
                    <option value="">All</option>
                    {filters?.clients.map((c) => (
                      <option key={c.id} value={c.id}>
                        {c.name}
                      </option>
                    ))}
                  </select>
                  <span className="text-[11px] text-text-muted shrink-0 font-medium">
                    {positions.length}
                  </span>
                </div>
              )}
            </div>

            {/* Position card list */}
            {(() => {
              if (positionsLoading) {
                return (
                  <div className="flex-1 overflow-y-auto p-4 space-y-3 dashboard-scrollbar">
                    {Array.from({ length: 5 }).map((_, i) => (
                      <PositionCardSkeleton key={i} />
                    ))}
                  </div>
                );
              }
              if (positions.length === 0) {
                return (
                  <div className="flex flex-col items-center justify-center h-40 text-text-muted gap-2">
                    <IconSearch className="size-8 opacity-20" />
                    <p className="text-sm">No positions match your filters.</p>
                  </div>
                );
              }
              return (
                <div className="flex-1 overflow-y-auto p-4 space-y-3 dashboard-scrollbar">
                  {positions.map((pos) => (
                    <PositionCard
                      key={pos.id}
                      position={pos}
                      isSelected={selectedPositionId === pos.id}
                      onClick={() => {
                        setSelectedPositionId(selectedPositionId === pos.id ? null : pos.id);
                        setCandidateSearch("");
                        setDebouncedCandidateSearch("");
                      }}
                      isMaintainer={isMaintainer}
                      onDelete={handleDeletePosition}
                      onReopen={handleReopenPosition}
                      onEdit={(p) => setEditingPosition(p)}
                    />
                  ))}
                </div>
              );
            })()}
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
                    className="w-full"
                  >
                    <div className="flex items-start justify-between gap-3">
                      <div>
                        <div className="flex items-center gap-2 mb-0.5">
                          {debouncedCandidateSearch ? (
                            <IconSearch className="size-4 text-yellow shrink-0" />
                          ) : (
                            <IconSparkles className="size-4 text-yellow shrink-0" />
                          )}
                          <h2 className="text-sm font-bold text-text-primary uppercase tracking-wider font-heading">
                            {debouncedCandidateSearch ? "Search Results" : "Top 10 Matches"}
                          </h2>
                        </div>
                        <p className="text-xs text-text-muted pl-6">
                          for{" "}
                          <span className="text-text-primary font-semibold">
                            {selectedPosition.role}
                          </span>{" "}
                          &bull; {selectedPosition.client_name}
                        </p>
                      </div>
                      <button
                        onClick={() => {
                          setSelectedPositionId(null);
                          setCandidateSearch("");
                          setDebouncedCandidateSearch("");
                        }}
                        className="p-1.5 rounded-lg text-text-muted hover:text-text-primary hover:bg-surface-2 border border-transparent hover:border-border transition-all shrink-0"
                      >
                        <IconX className="size-4" />
                      </button>
                    </div>
                    <div className="mt-4 relative">
                      <IconSearch className="absolute left-3 top-1/2 -translate-y-1/2 size-4 text-text-muted" />
                      <input
                        type="text"
                        placeholder="Search all candidates to map..."
                        value={candidateSearch}
                        onChange={(e) => setCandidateSearch(e.target.value)}
                        className="w-full pl-9 pr-4 py-2 text-sm rounded-lg bg-surface-2 border border-border text-text-primary placeholder:text-text-muted focus:outline-none focus:border-yellow transition-all"
                      />
                    </div>
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
                      Candidates
                    </h2>
                  </motion.div>
                )}
              </AnimatePresence>
            </div>

            {/* Empty state when no position selected */}
            <AnimatePresence>
              {!selectedPosition && (
                <motion.div
                  initial={{ opacity: 0 }}
                  animate={{ opacity: 1 }}
                  exit={{ opacity: 0 }}
                  className="flex-1 flex flex-col items-center justify-center gap-3 text-text-muted p-8"
                >
                  <IconBulb className="size-10 opacity-20" />
                  <p className="text-sm text-center leading-relaxed">
                    Select a position to see its top 10 matched candidates.
                  </p>
                  {!isClient && (
                    <p className="text-[11px] text-text-muted/60 text-center">
                      You can also drag candidates onto a position card to map them.
                    </p>
                  )}
                </motion.div>
              )}
            </AnimatePresence>

            {/* Candidate list */}
            {selectedPosition && (
              <>
                {(() => {
                  if (candidatesLoading) {
                    return (
                      <div className="flex-1 overflow-y-auto p-4 space-y-3 dashboard-scrollbar">
                        {Array.from({ length: 5 }).map((_, i) => (
                          <div key={i} className="pl-5">
                            <PositionTableSkeleton />
                          </div>
                        ))}
                      </div>
                    );
                  }
                  if (candidates.length === 0) {
                    return (
                      <div className="flex flex-col items-center justify-center h-40 text-text-muted gap-2">
                        <IconUsers className="size-8 opacity-20" />
                        <p className="text-sm">No matching candidates found.</p>
                      </div>
                    );
                  }
                  return (
                    <div className="flex-1 overflow-y-auto p-4 space-y-3 dashboard-scrollbar">
                      <AnimatePresence mode="popLayout">
                        {candidates.map((cand, idx) => (
                          <motion.div
                            key={cand.id}
                            layout
                            initial={{ opacity: 0, x: 10 }}
                            animate={{ opacity: 1, x: 0 }}
                            exit={{ opacity: 0, x: -10 }}
                            transition={{ duration: 0.15, delay: idx * 0.025 }}
                            className="pl-5"
                          >
                            <DraggableCandidateCard
                              cand={cand}
                              rank={idx + 1}
                              isMapped={cand.is_mapped}
                              isClient={isClient}
                              onToggleMap={() => {
                                if (cand.is_mapped) {
                                  doUnmap(selectedPosition.id, cand.id);
                                } else {
                                  doMap(selectedPosition.id, cand.id);
                                }
                              }}
                            />
                          </motion.div>
                        ))}
                      </AnimatePresence>
                    </div>
                  );
                })()}

                {/* Footer summary */}
                <div className="px-5 py-3 border-t border-border flex items-center justify-between text-xs text-text-muted shrink-0">
                  <span>
                    Pipeline:{" "}
                    <strong className="text-text-primary">{selectedPosition.mapped_count}</strong> /{" "}
                    {selectedPosition.total_seats} seats
                  </span>
                  <a
                    href={`/positions/${selectedPosition.id}/pipeline`}
                    className="font-bold text-navy bg-yellow/70 hover:bg-yellow px-3 py-1.5 rounded-lg transition-colors flex items-center gap-1"
                  >
                    Kanban Pipeline &rarr;
                  </a>
                </div>
              </>
            )}
          </div>
        </div>
      </div>

      {/* ── Drag overlay ── */}
      <DragOverlay dropAnimation={{ duration: 180, easing: "ease-out" }}>
        {activeDragCand ? <DragGhostCard cand={activeDragCand} /> : null}
      </DragOverlay>

      <AddPositionModal
        isOpen={addPositionOpen}
        onClose={() => setAddPositionOpen(false)}
        filters={filters}
        onCreated={(pos) => {
          setPositions((prev) => [pos, ...prev]);
          toast(`Position "${pos.role}" created`, "success");
        }}
        onClientCreated={addClientToFilters}
      />

      <AddPositionModal
        key={editingPosition?.id ?? "edit-closed"}
        isOpen={Boolean(editingPosition)}
        onClose={() => setEditingPosition(null)}
        filters={filters}
        position={editingPosition ?? undefined}
        onCreated={() => {}}
        onUpdated={(updated) => {
          handleUpdatePosition(updated);
          setEditingPosition(null);
        }}
      />
    </DndContext>
  );
}
