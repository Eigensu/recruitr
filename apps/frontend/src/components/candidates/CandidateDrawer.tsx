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
import { cn } from "@/lib/utils";
import { getAvatarColor, getInitials } from "./CandidateCard";

interface CandidateDrawerProps {
  candidate: ApiCandidate | null;
  onClose: () => void;
}

export default function CandidateDrawer({ candidate, onClose }: Readonly<CandidateDrawerProps>) {
  const apiFetch = useApiFetch();
  const [mappings, setMappings] = useState<ApiCandidateMappingItem[]>([]);
  const [loadingMappings, setLoadingMappings] = useState(false);

  // Load mappings whenever the drawer opens for a new candidate
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
            transition={{ type: "spring", damping: 25, stiffness: 220 }}
            className="fixed right-0 top-0 bottom-0 w-full sm:w-120 bg-(--color-surface) border-l border-border shadow-2xl z-50 flex flex-col"
          >
            {/* Header */}
            <div className="p-6 border-b border-border bg-(--color-surface) flex items-start justify-between">
              <div className="flex items-center gap-4">
                <div
                  className={cn(
                    "flex items-center justify-center size-16 rounded-full border shrink-0 font-bold text-2xl",
                    getAvatarColor(candidate.full_name),
                  )}
                >
                  {getInitials(candidate.full_name)}
                </div>
                <div>
                  <h2
                    id="candidateDrawerTitle"
                    className="text-2xl font-bold font-heading text-(--color-text-primary)"
                  >
                    {candidate.full_name}
                  </h2>
                  <p className="text-sm mt-0.5 text-gray-400">
                    {candidate.previous_company ?? "Independent"} &bull;{" "}
                    {candidate.experience_years} yrs exp
                  </p>
                </div>
              </div>
              <button
                type="button"
                onClick={onClose}
                aria-label="Close candidate details"
                className="p-1.5 rounded-lg bg-(--color-canvas) border border-border text-gray-400 hover:text-white transition-colors"
              >
                <IconX className="size-5" />
              </button>
            </div>

            {/* Quick contact */}
            <div className="px-6 py-4 bg-(--color-canvas) border-b border-border/80 flex flex-wrap gap-4">
              <div className="flex items-center gap-2 text-sm text-gray-300">
                <IconMail className="size-4 text-gray-500 shrink-0" />
                <a
                  href={`mailto:${candidate.email}`}
                  className="hover:text-yellow transition-colors"
                >
                  {candidate.email}
                </a>
              </div>
              {candidate.phone && (
                <div className="flex items-center gap-2 text-sm text-gray-300">
                  <IconPhone className="size-4 text-gray-500 shrink-0" />
                  <span>{candidate.phone}</span>
                </div>
              )}
            </div>

            {/* Scrollable content */}
            <div className="flex-1 overflow-y-auto p-6 space-y-8 dashboard-scrollbar bg-(--color-canvas)">
              {/* Skills */}
              <section>
                <h3 className="text-xs font-bold uppercase text-gray-500 tracking-wider mb-4">
                  Skills &amp; Expertise
                </h3>
                <div className="flex flex-wrap gap-2">
                  {candidate.skills.map((skill) => (
                    <span
                      key={skill}
                      className="text-xs font-bold px-3 py-1 rounded-full"
                      style={{
                        color: "var(--color-yellow)",
                        backgroundColor: "rgba(243,255,84,0.12)",
                        border: "1px solid rgba(243,255,84,0.25)",
                      }}
                    >
                      {skill}
                    </span>
                  ))}
                </div>
              </section>

              <hr className="border-border/60" />

              {/* Active mappings */}
              <section>
                <div className="flex items-center justify-between mb-4">
                  <h3 className="text-xs font-bold uppercase text-gray-500 tracking-wider">
                    Active Mappings
                  </h3>
                  <span className="text-xs font-bold bg-surface-2 px-2 py-0.5 rounded text-gray-300 border border-border">
                    {loadingMappings ? "…" : `${mappings.length} Positions`}
                  </span>
                </div>

                <MappingsList loadingMappings={loadingMappings} mappings={mappings} />
              </section>
            </div>
          </motion.div>
        </>
      )}
    </AnimatePresence>
  );
}

function MappingsList({
  loadingMappings,
  mappings,
}: Readonly<{ loadingMappings: boolean; mappings: ApiCandidateMappingItem[] }>) {
  if (loadingMappings) {
    return (
      <div className="h-20 rounded-xl border border-dashed border-border flex items-center justify-center text-gray-500 text-sm">
        Loading…
      </div>
    );
  }
  if (mappings.length === 0) {
    return (
      <div className="text-center p-6 border border-dashed border-border rounded-xl text-gray-500 bg-(--color-surface)">
        <IconBriefcase className="size-6 mx-auto mb-2 opacity-50" />
        <p className="text-sm">Not currently mapped to any open positions.</p>
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
    <div className="p-4 rounded-xl border border-border bg-(--color-surface) flex flex-col gap-3">
      <div className="flex justify-between items-start">
        <div>
          <span className="font-mono text-xs text-teal-400 font-bold px-1.5 py-0.5 bg-teal-500/10 rounded border border-teal-500/20 mb-1.5 inline-block">
            {mapping.position_code}
          </span>
          <h4 className="font-bold text-white text-base leading-tight">{mapping.role}</h4>
          <p className="text-xs text-gray-400 mt-1">
            {mapping.client_name}
            {mapping.city ? ` · ${mapping.city}` : ""}
          </p>
        </div>
        <span className="flex items-center gap-1 px-2 py-1 rounded bg-emerald-500/10 text-emerald-400 border border-emerald-500/20 text-[10px] font-bold uppercase shrink-0">
          <IconCircleCheck className="size-3" />
          {stageLabel}
        </span>
      </div>
      {mapping.match_score !== null && (
        <p className="text-[11px] text-gray-400">
          Match score:{" "}
          <span className="font-bold text-yellow">{Math.round(mapping.match_score * 100)}%</span>
        </p>
      )}
      <div className="pt-3 border-t border-border/50">
        <a
          href={`/positions/${mapping.position_id}/pipeline`}
          className="text-xs font-semibold text-yellow hover:underline flex items-center gap-1"
        >
          View Pipeline <IconExternalLink className="size-3" />
        </a>
      </div>
    </div>
  );
}
