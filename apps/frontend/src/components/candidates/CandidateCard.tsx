"use client";

import React, { useEffect, useRef, useState } from "react";
import {
  IconMail,
  IconBriefcase,
  IconFileText,
  IconLink,
  IconLock,
  IconPhone,
  IconTrash,
  IconUserCheck,
  IconUsers,
} from "@tabler/icons-react";
import type { ApiCandidate } from "@/types";
import { resolveCvRef } from "@/lib/api/candidates";
import { clientFetchCandidates } from "@/lib/api/candidates.client";
import { useApiFetch } from "@/lib/api";
import { listReferees } from "@/lib/api/referees";

interface CandidateCardProps {
  candidate: ApiCandidate;
  onClick: () => void;
  isMaintainer?: boolean;
  onDelete?: (id: string) => Promise<void>;
  onApprove?: () => Promise<void>;
  onReject?: () => Promise<void>;
  /** Present only where the caller can act on it (the External Candidates tab). */
  onViewReferee?: (refereeId: string) => void;
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

/**
 * How this candidate entered the system — referred by a referee (clickable,
 * drills into their other referrals), self-applied through the public form,
 * or manually tagged external by a recruiter (LinkedIn, Naukri, …).
 *
 * Only renders for source="external" candidates; internal ones show nothing
 * here (the "Added by {recruiter}" line below already covers them).
 */
function SourceBadge({
  candidate,
  isMaintainer,
  onViewReferee,
}: {
  candidate: ApiCandidate;
  isMaintainer?: boolean;
  onViewReferee?: (refereeId: string) => void;
}) {
  if (candidate.source !== "external") return null;
  if (candidate.referee_id && candidate.referee_name) {
    return (
      <RefereeBadge
        refereeId={candidate.referee_id}
        refereeName={candidate.referee_name}
        isMaintainer={isMaintainer}
        onViewReferee={onViewReferee}
      />
    );
  }
  // created_by_id is null exactly when nobody on staff sourced them — the
  // public form is the only other way a candidate lands with source=external.
  if (!candidate.created_by_id) {
    return (
      <span className="inline-flex w-fit items-center gap-1 rounded-full px-2 py-0.5 text-[10px] font-semibold bg-[rgba(96,165,250,0.1)] text-[#4453c4] dark:text-[#8b97f0]">
        {candidate.source_channel
          ? `Public application · ${candidate.source_channel}`
          : "Public application"}
      </span>
    );
  }
  if (candidate.source_channel) {
    return (
      <span className="inline-flex w-fit items-center gap-1 rounded-full px-2 py-0.5 text-[10px] font-semibold text-text-muted border border-border">
        {candidate.source_channel}
      </span>
    );
  }
  return null;
}

function RefereeBadge({
  refereeId,
  refereeName,
  isMaintainer,
  onViewReferee,
}: {
  refereeId: string;
  refereeName: string;
  isMaintainer?: boolean;
  onViewReferee?: (refereeId: string) => void;
}) {
  const [open, setOpen] = useState(false);
  const [loading, setLoading] = useState(false);
  const [count, setCount] = useState<number | null>(null);
  const [contact, setContact] = useState<{ email: string; connect_code: string | null } | null>(
    null,
  );
  const wrapperRef = useRef<HTMLDivElement>(null);
  const apiFetch = useApiFetch();

  useEffect(() => {
    if (!open) return;
    function handlePointerDown(e: PointerEvent) {
      if (!wrapperRef.current?.contains(e.target as Node)) setOpen(false);
    }
    document.addEventListener("pointerdown", handlePointerDown);
    return () => document.removeEventListener("pointerdown", handlePointerDown);
  }, [open]);

  useEffect(() => {
    if (!open) return;
    let cancelled = false;

    async function loadDetails() {
      setLoading(true);
      try {
        // Two calls, not one: omitting `status` doesn't mean "all statuses" —
        // list_candidates defaults it to APPROVED, which silently dropped
        // pending referrals from this count. Pending + approved matches what
        // "View all referrals" actually navigates to on the External tab.
        const [pendingPage, approvedPage, referees] = await Promise.all([
          clientFetchCandidates({
            source: "external",
            referee_id: refereeId,
            status: "PENDING",
            page: 1,
            limit: 1,
          }),
          clientFetchCandidates({
            source: "external",
            referee_id: refereeId,
            status: "APPROVED",
            page: 1,
            limit: 1,
          }),
          // Email/connect code stay behind the same maintainer gate GET /referees
          // already enforces — an ordinary recruiter never issues this call.
          isMaintainer ? listReferees(apiFetch) : Promise.resolve(null),
        ]);
        if (cancelled) return;
        setCount((pendingPage.meta?.total ?? 0) + (approvedPage.meta?.total ?? 0));
        const match = referees?.find((r) => r.id === refereeId);
        if (match) setContact({ email: match.email, connect_code: match.connect_code });
      } catch {
        if (!cancelled) setCount(null);
      } finally {
        if (!cancelled) setLoading(false);
      }
    }

    loadDetails();
    return () => {
      cancelled = true;
    };
  }, [open, refereeId, isMaintainer, apiFetch]);

  return (
    // z-30, not z-10: the Approve/Reject block lower in the card is also
    // `relative z-10`, and with equal z-index the later element in DOM order
    // wins the tie — which was letting those buttons paint over this popover
    // despite its own z-20. Outranking their z-10 here fixes it regardless of
    // where in the card this badge renders.
    <div ref={wrapperRef} className="pointer-events-auto relative z-30 w-fit">
      <button
        type="button"
        onClick={(e) => {
          e.stopPropagation();
          setOpen((o) => !o);
        }}
        className="inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-[10px] font-semibold bg-[rgba(52,211,153,0.1)] text-[#1f7a63] dark:text-[#4fbd9f] hover:opacity-80 transition-opacity"
      >
        <IconUsers className="size-3" />
        Referred by {refereeName}
      </button>
      {open && (
        <div
          onClick={(e) => e.stopPropagation()}
          className="absolute left-0 top-full z-20 mt-1 w-56 rounded-lg p-3 text-xs shadow-xl bg-surface-panel border border-border"
        >
          <p className="font-heading font-bold text-text-primary text-[13px]">{refereeName}</p>
          <p className="mt-1 text-text-muted">
            {loading
              ? "Loading…"
              : count == null
                ? "—"
                : `${count} candidate${count === 1 ? "" : "s"} referred`}
          </p>
          {isMaintainer && contact && (
            <div className="mt-2 pt-2 border-t border-border/40 space-y-0.5 text-text-muted">
              <p className="truncate">{contact.email}</p>
              {contact.connect_code && <p className="font-mono">{contact.connect_code}</p>}
            </div>
          )}
          {onViewReferee && (
            <button
              type="button"
              onClick={(e) => {
                e.stopPropagation();
                onViewReferee(refereeId);
                setOpen(false);
              }}
              className="mt-2 text-[11px] font-semibold text-yellow hover:opacity-80"
            >
              View all referrals →
            </button>
          )}
        </div>
      )}
    </div>
  );
}

function CandidateInfo({
  candidate,
  isMaintainer,
  onViewReferee,
}: {
  candidate: ApiCandidate;
  isMaintainer?: boolean;
  onViewReferee?: (refereeId: string) => void;
}) {
  let salaryStr: string | null = null;
  if (candidate.salary != null) {
    salaryStr = `₹${candidate.salary.toLocaleString("en-IN")}`;
  } else if (candidate.expected_salary != null) {
    salaryStr = `₹${candidate.expected_salary.toLocaleString("en-IN")} Expected`;
  }

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
            : candidate.previous_company
              ? candidate.previous_company
              : `Independent · ${candidate.experience_years}y`}
        </span>
      </p>
      {(candidate.city || candidate.area || salaryStr || candidate.age) && (
        <p className="text-[10px] text-text-muted mt-0.5 capitalize truncate">
          {[
            [candidate.city, candidate.area].filter(Boolean).join(" • "),
            [salaryStr, candidate.age ? `${candidate.age} yrs` : null].filter(Boolean).join(" • "),
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
      {candidate.source === "external" && (
        <div className="mt-1.5">
          <SourceBadge
            candidate={candidate}
            isMaintainer={isMaintainer}
            onViewReferee={onViewReferee}
          />
        </div>
      )}
    </div>
  );
}

function CandidateTags({ tags }: { tags: string[] }) {
  return (
    <div className="flex flex-wrap gap-1.5">
      {tags.slice(0, 4).map((tag) => (
        <span
          key={tag}
          className={`${tag.startsWith("Edu:") ? "block" : "inline-flex items-center gap-1"} rounded-full px-2 py-0.5 text-[10px] font-semibold truncate max-w-[120px]`}
          style={{
            background: "rgba(96,165,250,0.1)",
            color: "#60a5fa",
            border: "1px solid rgba(96,165,250,0.25)",
          }}
        >
          {tag}
        </span>
      ))}
      {tags.length > 4 && (
        <span className="text-[10px] px-2 py-0.5 rounded-full border border-border text-text-muted font-medium">
          +{tags.length - 4}
        </span>
      )}
    </div>
  );
}

function CandidateFooter({
  phone,
  email,
  cvRef,
  hasCvLink,
  cvLocked,
  ownerName,
}: {
  phone: string | null;
  email: string | null;
  cvRef: { href?: string | null } | null;
  hasCvLink: boolean;
  cvLocked?: boolean;
  ownerName?: string | null;
}) {
  // Phone leads: it's the mandatory contact field now, email is not. Older
  // candidates predating that change may still only have an email on file.
  const contact = phone ?? email;
  return (
    <div className="mt-auto pt-3.5 border-t border-border/40 flex items-center justify-between gap-2 text-[11px] text-text-muted">
      <div className="flex items-center gap-1.5 min-w-0">
        {phone ? (
          <IconPhone className="size-3.5 shrink-0 opacity-50" />
        ) : (
          <IconMail className="size-3.5 shrink-0 opacity-50" />
        )}
        <span className="truncate">{contact ?? "No contact info"}</span>
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
  onViewReferee,
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
            <CandidateInfo
              candidate={candidate}
              isMaintainer={isMaintainer}
              onViewReferee={onViewReferee}
            />
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

          {candidate.status !== "PENDING" && (
            <CandidateTags
              tags={
                [
                  candidate.communication ? `Comm: ${candidate.communication}` : null,
                  candidate.education ? `Edu: ${candidate.education}` : null,
                  candidate.brand_experience ? `Exp: ${candidate.brand_experience}` : null,
                  candidate.department
                    ? `Dept: ${candidate.department.replace("Kitchen (BOH)", "BOH").replace("Front of House (Service)", "Service")}`
                    : null,
                  candidate.specialization ? `Spec: ${candidate.specialization}` : null,
                  candidate.establishment_tag
                    ? `Establishment: ${candidate.establishment_tag}`
                    : null,
                ].filter(Boolean) as string[]
              }
            />
          )}

          <CandidateFooter
            phone={candidate.phone}
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
