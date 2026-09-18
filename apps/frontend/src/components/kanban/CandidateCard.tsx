"use client";

import type { KeyboardEvent } from "react";
import { useDraggable } from "@dnd-kit/core";
import { CSS } from "@dnd-kit/utilities";
import { IconFileText, IconGripVertical, IconSparkles } from "@tabler/icons-react";
import { isAbsoluteUrl } from "@/lib/api/candidates";
import { cn } from "@/lib/utils";
import type { PipelineCard } from "@/types";

interface Props {
  card: PipelineCard;
  isDragOverlay?: boolean;
  readOnly?: boolean;
  isClientBoard?: boolean;
  onCardClick?: (card: PipelineCard) => void;
  onStageChange?: (card: PipelineCard, newStage: string) => void;
}

function scoreColor(score: number | null): string {
  if (score === null) return "text-text-muted bg-surface-2 border-border";
  if (score >= 0.75) return "text-emerald-400 bg-emerald-500/10 border-emerald-500/20";
  if (score >= 0.5) return "text-yellow bg-yellow/10 border-yellow/20";
  return "text-red-400 bg-red-500/10 border-red-500/20";
}

export default function KanbanCard({
  card,
  isDragOverlay = false,
  readOnly = false,
  isClientBoard = false,
  onCardClick,
  onStageChange,
}: Readonly<Props>) {
  const { attributes, listeners, setNodeRef, transform, isDragging } = useDraggable({
    id: card.mapping_id,
    data: { card },
    disabled: readOnly,
  });

  const style = transform ? { transform: CSS.Translate.toString(transform) } : undefined;

  const daysInStage = card.stage_entered_at
    ? Math.floor(
        (new Date().getTime() - new Date(card.stage_entered_at).getTime()) / (1000 * 3600 * 24),
      )
    : 0;

  let badgeStyle = "text-emerald-400 bg-emerald-400/10 border-emerald-400/20";
  if (daysInStage >= 2 && daysInStage <= 5) {
    badgeStyle = "text-yellow bg-yellow/10 border-yellow/20";
  } else if (daysInStage > 5) {
    badgeStyle = "text-red-400 bg-red-400/10 border-red-400/20";
  }

  const daysLabel = daysInStage === 1 ? "1 day" : `${daysInStage} days`;

  const offerLetterHref =
    card.offer_letter_url && isAbsoluteUrl(card.offer_letter_url) ? card.offer_letter_url : null;

  // The card body opens the action modal. Without this the client board could
  // never reach ClientActionModal: onCardClick was only ever wired to the
  // "Upload Offer Letter" button, which only renders on `selected` cards.
  // Drag is bound to the grip handle's `listeners`, not the root, so a root
  // click handler doesn't swallow drags.
  const clickable = !!onCardClick && !isDragOverlay && !readOnly;
  const clickProps = clickable
    ? {
        onClick: () => onCardClick?.(card),
        onKeyDown: (e: KeyboardEvent) => {
          if (e.key === "Enter" || e.key === " ") {
            e.preventDefault();
            onCardClick?.(card);
          }
        },
        tabIndex: 0,
        role: "button",
        // Without an explicit name, this role="button" takes its accessible
        // name from the card's whole text content — every label, badge and
        // nested button's caption run together. Screen readers announce that
        // wall of text as the control's name.
        "aria-label": `Open ${card.candidate_name}`,
      }
    : {};

  return (
    <div
      ref={setNodeRef}
      style={style}
      {...attributes}
      {...clickProps}
      className={cn(
        "group relative rounded-xl border bg-surface-panel p-3 select-none",
        "transition-all duration-150",
        isDragging && !isDragOverlay && "opacity-40 scale-95",
        isDragOverlay &&
          "shadow-2xl shadow-black/50 rotate-1 cursor-grabbing ring-1 ring-yellow/30",
        !isDragging &&
          !isDragOverlay &&
          !readOnly &&
          "hover:border-border-strong hover:shadow-md cursor-grab",
        clickable && "focus:outline-none focus-visible:ring-2 focus-visible:ring-yellow",
        "border-border/60",
      )}
    >
      {/* Drag handle.
          `touch-none` is load-bearing, not cosmetic: without touch-action none
          the browser claims the gesture as a scroll and dnd-kit's pointer
          sensor never gets to start a drag, so the board was completely
          immovable on a phone. The hover-only reveal compounded it — a
          touch device has no hover, so the handle was invisible too. Shown
          by default where hover isn't available; the same pattern the
          Positions board already uses.
          The larger padding (offset by the negative margin so the layout is
          unchanged) gives it a finger-sized tap target. */}
      {!readOnly && (
        <div
          {...listeners}
          // The card root opens the modal; a tap that lands on the grip is a
          // drag attempt, not a request to open it.
          onClick={(e) => e.stopPropagation()}
          className="absolute top-2.5 right-2.5 -m-2 p-2 touch-none cursor-grab active:cursor-grabbing opacity-0 group-hover:opacity-40 [@media(hover:none)]:opacity-40 transition-opacity"
        >
          <IconGripVertical className="size-3.5 text-text-muted" />
        </div>
      )}

      {/* Candidate and Position Info */}
      <div className="mb-2 min-w-0">
        <p className="text-sm font-semibold text-text-primary truncate leading-tight w-full">
          {card.candidate_name}
        </p>
        <div className="flex items-center justify-between mt-1.5 gap-2 pr-1">
          <p className="text-[11px] font-medium text-text-secondary truncate">
            {card.position_role}
          </p>
          <span
            className={cn(
              "text-[9px] px-1.5 py-0.5 rounded-sm border whitespace-nowrap shrink-0",
              badgeStyle,
            )}
          >
            {daysLabel}
          </span>
        </div>
        <p className="text-[11px] text-text-muted truncate mt-0.5">{card.position_client}</p>
      </div>

      {/* Footer */}
      <div className="flex flex-col gap-1.5 mt-2">
        {/* Staff-only: `joined -> rejected` isn't in the client transition whitelist
            (it would 403), and the match score is agency-internal. */}
        {!readOnly && !isClientBoard && (
          <div className="flex items-center justify-between gap-2">
            <div className="flex-1">
              {card.stage === "joined" && onStageChange && (
                <button
                  type="button"
                  onClick={(e) => {
                    e.stopPropagation();
                    onStageChange(card, "rejected");
                  }}
                  className="rounded-lg bg-red-500/10 border border-red-500/20 px-3 py-1.5 text-[11px] font-semibold text-red-400 hover:bg-red-500/20 transition-all flex items-center justify-center gap-1 w-fit"
                >
                  Mark as Rejected
                </button>
              )}
            </div>
            {card.match_score !== null && (
              <span
                className={cn(
                  "flex items-center gap-0.5 text-[10px] font-bold px-1.5 py-0.5 rounded-full border shrink-0",
                  scoreColor(card.match_score),
                )}
              >
                <IconSparkles className="size-2.5" />
                {Math.round(card.match_score * 100)}%
              </span>
            )}
          </div>
        )}

        {/* Shown from `selected`, which is where the joining details are
            entered. Gating this on `joined` alone hid them for the whole wait
            until the joining date — and that move is left to a daily job — so
            a save that had worked looked, on both boards, like nothing had
            been stored. */}
        {(card.stage === "selected" || card.stage === "joined") &&
          (card.joining_date || card.salary_offered != null) && (
            <div className="flex flex-col gap-1">
              {card.joining_date && (
                <span className="text-[10px] text-text-muted">
                  {card.stage === "joined" ? "Joined" : "Joining"}:{" "}
                  <strong className="text-emerald-400">
                    {new Date(card.joining_date).toLocaleDateString()}
                  </strong>
                </span>
              )}
              {card.salary_offered != null && (
                <span className="text-[10px] text-text-muted">
                  Salary:{" "}
                  <strong className="text-yellow">₹{card.salary_offered.toLocaleString()}</strong>
                </span>
              )}
            </div>
          )}

        {offerLetterHref && (
          <a
            href={offerLetterHref}
            target="_blank"
            rel="noreferrer noopener"
            // The card root opens the modal on click and on Enter — the latter
            // with preventDefault, which would otherwise cancel this link.
            onClick={(e) => e.stopPropagation()}
            onKeyDown={(e) => e.stopPropagation()}
            className="flex w-fit items-center gap-1 text-[10px] font-semibold text-emerald-400 hover:underline"
          >
            <IconFileText className="size-3 shrink-0" />
            Offer letter
          </a>
        )}

        {card.stage === "candidate_dropped" && card.dropped_notes && (
          <div className="flex flex-col gap-1">
            <span className="text-[10px] text-text-muted italic break-words">
              &quot;{card.dropped_notes}&quot;
            </span>
          </div>
        )}
      </div>

      {/* Select / Reject, on both the client's pipeline and the recruiter's.
          Gated on onStageChange rather than onCardClick: the decision is the
          same one on either board, but only the client board opens a card
          modal, so hanging these off onCardClick left the recruiter with
          drag-and-drop as the sole way to take them. */}
      {!readOnly && (onStageChange || onCardClick) && (
        <div className="mt-3 flex gap-2">
          {isClientBoard && card.stage === "sent_to_client" && onStageChange && (
            <>
              <button
                type="button"
                onClick={(e) => {
                  e.stopPropagation();
                  onStageChange(card, "interview");
                }}
                className="flex-1 rounded-lg bg-emerald-500/10 border border-emerald-500/20 px-2 py-1.5 text-[10px] font-semibold text-emerald-400 hover:bg-emerald-500/20 transition-all flex items-center justify-center gap-1"
              >
                ✓ Select
              </button>
              <button
                type="button"
                onClick={(e) => {
                  e.stopPropagation();
                  onStageChange(card, "rejected");
                }}
                className="flex-1 rounded-lg bg-red-500/10 border border-red-500/20 px-2 py-1.5 text-[10px] font-semibold text-red-400 hover:bg-red-500/20 transition-all flex items-center justify-center gap-1"
              >
                ✕ Reject
              </button>
            </>
          )}
          {isClientBoard && card.stage === "interview" && onStageChange && (
            <>
              <button
                type="button"
                onClick={(e) => {
                  e.stopPropagation();
                  onStageChange(card, "selected");
                }}
                className="flex-1 rounded-lg bg-indigo-500/10 border border-indigo-500/20 px-2 py-1.5 text-[10px] font-semibold text-indigo-400 hover:bg-indigo-500/20 transition-all flex items-center justify-center gap-1"
              >
                ✓ Select
              </button>
              <button
                type="button"
                onClick={(e) => {
                  e.stopPropagation();
                  onStageChange(card, "rejected");
                }}
                className="flex-1 rounded-lg bg-red-500/10 border border-red-500/20 px-2 py-1.5 text-[10px] font-semibold text-red-400 hover:bg-red-500/20 transition-all flex items-center justify-center gap-1"
              >
                ✕ Reject
              </button>
            </>
          )}
          {/* Only until there is a letter: after that the card carries the
              "Offer letter" link instead, and replacing it is in the modal. */}
          {card.stage === "selected" && !card.offer_letter_url && onCardClick && (
            <button
              type="button"
              onClick={(e) => {
                e.stopPropagation();
                onCardClick(card);
              }}
              className="w-full rounded-lg bg-yellow/10 border border-yellow/20 px-3 py-1.5 text-[11px] font-semibold text-yellow hover:bg-yellow/20 transition-all"
            >
              Upload Offer Letter
            </button>
          )}
        </div>
      )}
    </div>
  );
}
