"use client";

import React, { useState } from "react";
import { IconMail, IconBriefcase, IconFileText, IconLink, IconTrash } from "@tabler/icons-react";
import type { ApiCandidate } from "@/types";
import { resolveCvRef } from "@/lib/api/candidates";

interface CandidateCardProps {
  candidate: ApiCandidate;
  onClick: () => void;
  isMaintainer?: boolean;
  onDelete?: (id: string) => Promise<void>;
  onApprove?: () => Promise<void>;
  onReject?: () => Promise<void>;
}

const PALETTES = [
  { bg: "rgba(52,211,153,0.1)", text: "#34d399", border: "rgba(52,211,153,0.18)" },
  { bg: "rgba(96,165,250,0.1)", text: "#60a5fa", border: "rgba(96,165,250,0.18)" },
  { bg: "rgba(167,139,250,0.1)", text: "#a78bfa", border: "rgba(167,139,250,0.18)" },
  { bg: "rgba(251,146,60,0.1)", text: "#fb923c", border: "rgba(251,146,60,0.18)" },
  { bg: "rgba(243,255,84,0.1)", text: "#f3ff54", border: "rgba(243,255,84,0.18)" },
];

export function getAvatarPalette(name: string) {
  let hash = 0;
  for (let i = 0; i < name.length; i++) {
    hash = (name.codePointAt(i) ?? 0) + ((hash << 5) - hash);
  }
  return PALETTES[Math.abs(hash) % PALETTES.length];
}

export function getInitials(name: string) {
  return name
    .split(" ")
    .map((n) => n[0])
    .slice(0, 2)
    .join("")
    .toUpperCase();
}

export default function CandidateCard({
  candidate,
  onClick,
  isMaintainer,
  onDelete,
  onApprove,
  onReject,
}: Readonly<CandidateCardProps>) {
  const palette = getAvatarPalette(candidate.full_name);
  const initials = getInitials(candidate.full_name);
  const cvRef = resolveCvRef(candidate.cv_link, candidate.resume_url);
  const [confirmDelete, setConfirmDelete] = useState(false);
  const [deleting, setDeleting] = useState(false);

  async function handleDeleteClick(e: React.MouseEvent) {
    e.stopPropagation();
    if (!confirmDelete) {
      setConfirmDelete(true);
      return;
    }
    if (!onDelete) return;
    setDeleting(true);
    try {
      await onDelete(candidate.id);
    } finally {
      setDeleting(false);
      setConfirmDelete(false);
    }
  }

  return (
    <div className="group relative w-full h-full">
      {/* Full-card click target — sits behind content so the CV link stays on top */}
      <button
        type="button"
        onClick={onClick}
        aria-label={`View details for ${candidate.full_name}`}
        className="absolute inset-0 rounded-2xl focus:outline-none focus-visible:ring-2 focus-visible:ring-yellow"
      />

      {/* Visual card — pointer-events-none so clicks fall through to the button above */}
      <div className="pointer-events-none relative flex flex-col h-full rounded-2xl bg-surface-panel border border-border overflow-hidden transition-all duration-200 group-hover:border-white/10 group-hover:-translate-y-px group-hover:shadow-[0_12px_40px_rgba(0,0,0,0.35)]">
        {/* Palette accent bar */}
        <div className="h-0.5 shrink-0" style={{ backgroundColor: palette.text, opacity: 0.55 }} />

        <div className="flex flex-col h-full p-5 gap-4">
          {/* Identity row */}
          <div className="flex items-start gap-3.5">
            <div
              className="size-10 rounded-xl shrink-0 flex items-center justify-center font-heading font-bold text-sm"
              style={{
                backgroundColor: palette.bg,
                color: palette.text,
                border: `1px solid ${palette.border}`,
              }}
            >
              {initials}
            </div>
            <div className="flex-1 min-w-0 pt-0.5">
              <h3 className="font-heading font-bold text-text-primary text-[15px] leading-snug truncate">
                {candidate.full_name}
              </h3>
              <p className="text-[11px] text-text-muted mt-0.5 flex items-center gap-1.5 truncate">
                <IconBriefcase className="size-3 shrink-0" />
                <span className="truncate">
                  {candidate.current_role
                    ? `${candidate.current_role} · ${candidate.experience_years}y`
                    : candidate.previous_role
                      ? `${candidate.previous_role} · ${candidate.experience_years}y`
                      : candidate.previous_company
                        ? candidate.previous_company
                        : `Independent · ${candidate.experience_years}y`}
                </span>
              </p>
              {(candidate.city || candidate.area || candidate.gender || candidate.age) && (
                <p className="text-[10px] text-text-muted mt-0.5 capitalize truncate">
                  {[
                    [candidate.city, candidate.area].filter(Boolean).join(" • "),
                    [candidate.gender, candidate.age ? `${candidate.age} yrs` : null]
                      .filter(Boolean)
                      .join(" • "),
                  ]
                    .filter(Boolean)
                    .join(" | ")}
                </p>
              )}
            </div>
            {isMaintainer && onDelete && (
              <div className="pointer-events-auto relative z-10 shrink-0">
                {confirmDelete ? (
                  <button
                    type="button"
                    onClick={handleDeleteClick}
                    disabled={deleting}
                    className="text-[10px] font-bold px-2 py-1 rounded-lg bg-red-500/90 text-white hover:bg-red-600 transition-colors disabled:opacity-60"
                  >
                    {deleting ? "…" : "Confirm"}
                  </button>
                ) : (
                  <button
                    type="button"
                    onClick={handleDeleteClick}
                    aria-label="Delete candidate"
                    className="p-1.5 rounded-lg text-text-muted hover:text-red-400 hover:bg-red-500/10 transition-colors opacity-0 group-hover:opacity-100"
                  >
                    <IconTrash className="size-3.5" />
                  </button>
                )}
              </div>
            )}
          </div>

          {/* Skills */}
          {candidate.status !== "PENDING" && candidate.status !== "pending" && (
            <div className="flex flex-wrap gap-1.5">
              {candidate.skills.slice(0, 4).map((skill) => (
                <span
                  key={skill}
                  className="skill-tag text-[10px] font-semibold px-2.5 py-0.5 rounded-full"
                >
                  {skill}
                </span>
              ))}
              {candidate.skills.length > 4 && (
                <span className="text-[10px] px-2 py-0.5 rounded-full border border-border text-text-muted font-medium">
                  +{candidate.skills.length - 4}
                </span>
              )}
            </div>
          )}

          {/* Contact footer */}
          <div className="mt-auto pt-3.5 border-t border-border/40 flex items-center justify-between gap-2 text-[11px] text-text-muted">
            <div className="flex items-center gap-1.5 min-w-0">
              <IconMail className="size-3.5 shrink-0 opacity-50" />
              <span className="truncate">{candidate.email}</span>
            </div>
            {cvRef &&
              (cvRef.href ? (
                <a
                  href={cvRef.href}
                  target="_blank"
                  rel="noreferrer noopener"
                  className="pointer-events-auto relative z-10 flex shrink-0 items-center gap-1 font-semibold text-yellow hover:opacity-80 transition-opacity"
                >
                  {candidate.cv_link ? (
                    <IconLink className="size-3.5" />
                  ) : (
                    <IconFileText className="size-3.5" />
                  )}
                  CV
                </a>
              ) : (
                <span
                  className="pointer-events-auto relative z-10 flex shrink-0 items-center gap-1 font-medium opacity-40 cursor-default"
                  title="CV on file — not yet uploaded"
                >
                  <IconFileText className="size-3.5" />
                  CV
                </span>
              ))}
          </div>

          {/* Action buttons (for pending candidates) */}
          {(onApprove || onReject) && (
            <div className="mt-3 pt-3 border-t border-border/40 flex items-center gap-2">
              {onApprove && (
                <button
                  type="button"
                  onClick={(e) => {
                    e.stopPropagation();
                    onApprove();
                  }}
                  className="pointer-events-auto relative z-10 flex-1 rounded bg-green-500/10 py-1.5 text-xs font-semibold text-green-500 transition-colors hover:bg-green-500/20"
                >
                  Approve
                </button>
              )}
              {onReject && (
                <button
                  type="button"
                  onClick={(e) => {
                    e.stopPropagation();
                    onReject();
                  }}
                  className="pointer-events-auto relative z-10 flex-1 rounded bg-red-500/10 py-1.5 text-xs font-semibold text-red-500 transition-colors hover:bg-red-500/20"
                >
                  Reject
                </button>
              )}
            </div>
          )}
        </div>
      </div>

      {/* Click-away to cancel confirm state */}
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
    </div>
  );
}
