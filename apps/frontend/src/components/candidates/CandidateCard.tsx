"use client";

import React, { useEffect, useRef, useState } from "react";
import {
  IconMail,
  IconBriefcase,
  IconFileText,
  IconLink,
  IconLock,
  IconTrash,
  IconUserCheck,
} from "@tabler/icons-react";
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

function CandidateAvatar({
  palette,
  initials,
}: {
  palette: { bg: string; text: string; border: string };
  initials: string;
}) {
  return (
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
  );
}

function CandidateInfo({ candidate }: { candidate: ApiCandidate }) {
  return (
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
      {candidate.created_by_name && (
        <p className="text-[10px] text-text-muted mt-0.5 flex items-center gap-1 truncate">
          <IconUserCheck className="size-3 shrink-0 opacity-50" />
          <span className="truncate">Added by {candidate.created_by_name}</span>
        </p>
      )}
    </div>
  );
}

function CandidateSkills({ skills }: { skills: string[] }) {
  return (
    <div className="flex flex-wrap gap-1.5">
      {skills.slice(0, 4).map((skill) => (
        <span
          key={skill}
          className="skill-tag text-[10px] font-semibold px-2.5 py-0.5 rounded-full"
        >
          {skill}
        </span>
      ))}
      {skills.length > 4 && (
        <span className="text-[10px] px-2 py-0.5 rounded-full border border-border text-text-muted font-medium">
          +{skills.length - 4}
        </span>
      )}
    </div>
  );
}

function CandidateFooter({
  email,
  cvRef,
  hasCvLink,
  cvLocked,
  ownerName,
}: {
  email: string;
  cvRef: { href?: string | null } | null;
  hasCvLink: boolean;
  cvLocked?: boolean;
  ownerName?: string | null;
}) {
  return (
    <div className="mt-auto pt-3.5 border-t border-border/40 flex items-center justify-between gap-2 text-[11px] text-text-muted">
      <div className="flex items-center gap-1.5 min-w-0">
        <IconMail className="size-3.5 shrink-0 opacity-50" />
        <span className="truncate">{email}</span>
      </div>
      {cvLocked ? (
        <span
          className="pointer-events-auto relative z-10 flex shrink-0 items-center gap-1 font-medium opacity-40 cursor-default"
          title={
            ownerName
              ? `CV held by ${ownerName} — only they can open it`
              : "CV held by another recruiter"
          }
        >
          <IconLock className="size-3.5" />
          CV
        </span>
      ) : (
        cvRef &&
        (cvRef.href ? (
          <a
            href={cvRef.href}
            target="_blank"
            rel="noreferrer noopener"
            className="pointer-events-auto relative z-10 flex shrink-0 items-center gap-1 font-semibold text-yellow hover:opacity-80 transition-opacity"
          >
            {hasCvLink ? <IconLink className="size-3.5" /> : <IconFileText className="size-3.5" />}
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
        ))
      )}
    </div>
  );
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
  const [isActioning, setIsActioning] = useState(false);
  const wrapperRef = useRef<HTMLDivElement>(null);

  // Click-away cancel is a document listener rather than a rendered overlay:
  // hovering the card applies a translate to the card body, which makes it a
  // stacking context and traps the Confirm button's z-index underneath any
  // sibling overlay — the overlay then swallows the click meant for Confirm.
  useEffect(() => {
    if (!confirmDelete) return;
    function handlePointerDown(e: PointerEvent) {
      if (!wrapperRef.current?.contains(e.target as Node)) setConfirmDelete(false);
    }
    document.addEventListener("pointerdown", handlePointerDown);
    return () => document.removeEventListener("pointerdown", handlePointerDown);
  }, [confirmDelete]);

  function handleCardClick() {
    // While confirming, a click elsewhere on the card cancels instead of opening.
    if (confirmDelete) {
      setConfirmDelete(false);
      return;
    }
    onClick();
  }

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

  async function handleApprove(e: React.MouseEvent) {
    e.stopPropagation();
    if (!onApprove) return;
    setIsActioning(true);
    try {
      await onApprove();
    } finally {
      setIsActioning(false);
    }
  }

  async function handleReject(e: React.MouseEvent) {
    e.stopPropagation();
    if (!onReject) return;
    setIsActioning(true);
    try {
      await onReject();
    } finally {
      setIsActioning(false);
    }
  }

  return (
    <div ref={wrapperRef} className="group relative w-full h-full">
      <button
        type="button"
        onClick={handleCardClick}
        aria-label={`View details for ${candidate.full_name}`}
        className="absolute inset-0 rounded-2xl focus:outline-none focus-visible:ring-2 focus-visible:ring-yellow"
      />

      <div className="pointer-events-none relative flex flex-col h-full rounded-2xl bg-surface-panel border border-border overflow-hidden transition-all duration-200 group-hover:border-white/10 group-hover:-translate-y-px group-hover:shadow-[0_12px_40px_rgba(0,0,0,0.35)]">
        <div className="h-0.5 shrink-0" style={{ backgroundColor: palette.text, opacity: 0.55 }} />

        <div className="flex flex-col h-full p-5 gap-4">
          <div className="flex items-start gap-3.5">
            <CandidateAvatar palette={palette} initials={initials} />
            <CandidateInfo candidate={candidate} />
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

          {candidate.status !== "PENDING" && <CandidateSkills skills={candidate.skills} />}

          <CandidateFooter
            email={candidate.email}
            cvRef={cvRef}
            hasCvLink={!!candidate.cv_link}
            cvLocked={candidate.cv_locked}
            ownerName={candidate.created_by_name}
          />

          {isMaintainer && (onApprove || onReject) && (
            <div className="mt-3 pt-3 border-t border-border/40 flex items-center gap-2">
              {onApprove && (
                <button
                  type="button"
                  disabled={isActioning}
                  onClick={handleApprove}
                  className="pointer-events-auto relative z-10 flex-1 rounded bg-green-500/10 py-1.5 text-xs font-semibold text-green-500 transition-colors hover:bg-green-500/20 disabled:opacity-50"
                >
                  Approve
                </button>
              )}
              {onReject && (
                <button
                  type="button"
                  disabled={isActioning}
                  onClick={handleReject}
                  className="pointer-events-auto relative z-10 flex-1 rounded bg-red-500/10 py-1.5 text-xs font-semibold text-red-500 transition-colors hover:bg-red-500/20 disabled:opacity-50"
                >
                  Reject
                </button>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
