import React, { useEffect, useState } from "react";
import { AnimatePresence, motion } from "motion/react";
import {
  IconX,
  IconMail,
  IconPhone,
  IconExternalLink,
  IconCircleCheck,
  IconBriefcase,
} from "@tabler/icons-react";
import type { ApiCandidate, ApiCandidateMappingItem } from "@/types";
import { useApiFetch } from "@/lib/api";
import { getCandidateMappings } from "@/lib/api/candidates";
import { getAvatarPalette, getInitials } from "./CandidateCard";

interface CandidateDrawerProps {
  candidate: ApiCandidate | null;
  onClose: () => void;
}

export default function CandidateDrawer({ candidate, onClose }: Readonly<CandidateDrawerProps>) {
  const apiFetch = useApiFetch();
  const [mappings, setMappings] = useState<ApiCandidateMappingItem[]>([]);
  const [loadingMappings, setLoadingMappings] = useState(false);

  useEffect(() => {
    if (!candidate) return;
    let cancelled = false;
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setLoadingMappings(true);
    getCandidateMappings(apiFetch, candidate.id)
      .then((data) => {
        if (!cancelled) setMappings(data);
      })
      .catch(() => {
        if (!cancelled) setMappings([]);
      })
      .finally(() => {
        if (!cancelled) setLoadingMappings(false);
      });
    return () => {
      cancelled = true;
    };
  }, [apiFetch, candidate]);

  return (
    <AnimatePresence>
      {candidate && (
        <>
          {/* Backdrop */}
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            onClick={onClose}
            className="fixed inset-0 bg-black/60 backdrop-blur-sm z-40"
          />

          {/* Slide-over panel */}
          <motion.div
            role="dialog"
            aria-modal="true"
            aria-labelledby="candidateDrawerTitle"
            initial={{ x: "100%" }}
            animate={{ x: 0 }}
            exit={{ x: "100%" }}
            transition={{ type: "spring", damping: 28, stiffness: 250 }}
            className="fixed right-0 top-0 bottom-0 w-full sm:w-120 bg-(--color-surface) border-l border-border shadow-2xl z-50 flex flex-col"
          >
            <DrawerInner
              candidate={candidate}
              onClose={onClose}
              loadingMappings={loadingMappings}
              mappings={mappings}
            />
          </motion.div>
        </>
      )}
    </AnimatePresence>
  );
}

function DrawerInner({
  candidate,
  onClose,
  loadingMappings,
  mappings,
}: Readonly<{
  candidate: ApiCandidate;
  onClose: () => void;
  loadingMappings: boolean;
  mappings: ApiCandidateMappingItem[];
}>) {
  const palette = getAvatarPalette(candidate.full_name);
  const initials = getInitials(candidate.full_name);

  return (
    <>
      {/* Header */}
      <div className="p-6 border-b border-border">
        <div className="flex items-start justify-between mb-4">
          <div
            className="size-14 rounded-2xl flex items-center justify-center font-heading font-bold text-xl"
            style={{
              backgroundColor: palette.bg,
              color: palette.text,
              border: `1px solid ${palette.border}`,
            }}
          >
            {initials}
          </div>
          <button
            type="button"
            onClick={onClose}
            aria-label="Close candidate details"
            className="p-2 rounded-xl border border-border text-text-muted hover:text-text-primary hover:border-white/20 transition-all"
          >
            <IconX className="size-4" />
          </button>
        </div>

        <h2
          id="candidateDrawerTitle"
          className="font-heading font-bold text-text-primary text-2xl leading-tight"
        >
          {candidate.full_name}
        </h2>
        <p className="text-sm text-text-muted mt-1 flex items-center gap-1.5">
          <IconBriefcase className="size-3.5 shrink-0" />
          {candidate.previous_company ?? "Independent"} · {candidate.experience_years} yrs exp
        </p>

        {/* Contact */}
        <div className="mt-4 flex flex-col gap-2">
          <a
            href={`mailto:${candidate.email}`}
            className="flex items-center gap-2 text-xs text-text-muted hover:text-yellow transition-colors w-fit"
          >
            <IconMail className="size-3.5 shrink-0" />
            {candidate.email}
          </a>
          {candidate.phone && (
            <span className="flex items-center gap-2 text-xs text-text-muted">
              <IconPhone className="size-3.5 shrink-0" />
              {candidate.phone}
            </span>
          )}
        </div>
      </div>

      {/* Scrollable body */}
      <div className="flex-1 overflow-y-auto dashboard-scrollbar p-6 space-y-6 bg-(--color-canvas)">
        {/* Skills */}
        <section>
          <h3 className="text-[10px] font-bold uppercase tracking-widest text-text-muted mb-3">
            Skills &amp; Expertise
          </h3>
          <div className="flex flex-wrap gap-2">
            {candidate.skills.map((skill) => (
              <span
                key={skill}
                className="skill-tag text-[11px] font-semibold px-3 py-1 rounded-full"
              >
                {skill}
              </span>
            ))}
          </div>
        </section>

        <div className="h-px bg-border/50" />

        {/* Mapped positions */}
        <section>
          <div className="flex items-center justify-between mb-3">
            <h3 className="text-[10px] font-bold uppercase tracking-widest text-text-muted">
              Mapped Positions
            </h3>
            <span className="text-[10px] font-bold px-2 py-0.5 rounded-full bg-surface-panel border border-border text-text-secondary">
              {loadingMappings ? "…" : mappings.length}
            </span>
          </div>
          <MappingsList loadingMappings={loadingMappings} mappings={mappings} />
        </section>
      </div>
    </>
  );
}

function MappingsList({
  loadingMappings,
  mappings,
}: Readonly<{ loadingMappings: boolean; mappings: ApiCandidateMappingItem[] }>) {
  if (loadingMappings) {
    return (
      <div className="h-16 rounded-xl border border-dashed border-border flex items-center justify-center">
        <div className="size-4 border-2 border-border border-t-text-muted rounded-full animate-spin" />
      </div>
    );
  }
  if (mappings.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center p-8 rounded-xl border border-dashed border-border bg-surface-panel gap-2">
        <IconBriefcase className="size-5 text-text-muted opacity-30" />
        <p className="text-xs text-text-muted text-center">Not mapped to any open positions</p>
      </div>
    );
  }
  return (
    <div className="space-y-3">
      {mappings.map((m) => (
        <MappingCard key={m.mapping_id} mapping={m} />
      ))}
    </div>
  );
}

function MappingCard({ mapping }: Readonly<{ mapping: ApiCandidateMappingItem }>) {
  const stageLabel = mapping.stage.replaceAll("_", " ");
  return (
    <div className="p-4 rounded-xl border border-border bg-surface-panel">
      <div className="flex items-start justify-between gap-2 mb-2">
        <div className="min-w-0">
          <span className="text-[10px] font-mono font-bold px-1.5 py-0.5 rounded bg-teal-500/10 text-teal-400 border border-teal-500/20 inline-block mb-1.5">
            {mapping.position_code}
          </span>
          <h4 className="font-heading font-bold text-text-primary text-sm leading-snug">
            {mapping.role}
          </h4>
          <p className="text-[11px] text-text-muted mt-0.5">
            {mapping.client_name}
            {mapping.city ? ` · ${mapping.city}` : ""}
          </p>
        </div>
        <span className="flex items-center gap-1 px-2 py-1 rounded-lg bg-emerald-500/10 text-emerald-400 border border-emerald-500/20 text-[9px] font-bold uppercase shrink-0">
          <IconCircleCheck className="size-3" />
          {stageLabel}
        </span>
      </div>

      {mapping.match_score !== null && (
        <div className="flex items-center gap-2 mt-2">
          <div className="flex-1 h-1 rounded-full bg-border overflow-hidden">
            <div
              className="h-full rounded-full bg-yellow"
              style={{ width: `${Math.round(mapping.match_score * 100)}%` }}
            />
          </div>
          <span className="text-[10px] font-bold text-yellow shrink-0">
            {Math.round(mapping.match_score * 100)}%
          </span>
        </div>
      )}

      <div className="mt-3 pt-3 border-t border-border/40">
        <a
          href={`/positions/${mapping.position_id}/pipeline`}
          className="text-[11px] font-semibold text-text-muted hover:text-yellow transition-colors flex items-center gap-1"
        >
          View Pipeline <IconExternalLink className="size-3" />
        </a>
      </div>
    </div>
  );
}
