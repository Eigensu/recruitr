import React, { useMemo } from "react";
import { AnimatePresence, motion } from "motion/react";
import {
  IconX,
  IconBriefcase,
  IconMail,
  IconPhone,
  IconExternalLink,
  IconCircleCheck,
} from "@tabler/icons-react";
import { usePositionsStore, MockCandidate } from "@/stores/usePositionsStore";
import { cn } from "@/lib/utils";
import { getAvatarColor, getInitials } from "./CandidateCard";

interface CandidateDrawerProps {
  candidateId: string | null;
  onClose: () => void;
}

export default function CandidateDrawer({ candidateId, onClose }: CandidateDrawerProps) {
  const { candidates, positions, mappings } = usePositionsStore();

  const candidate = useMemo(() => {
    return candidates.find((c) => c.id === candidateId) || null;
  }, [candidates, candidateId]);

  // Find all positions this candidate is mapped to
  const mappedPositions = useMemo(() => {
    if (!candidate) return [];

    const mappedIds: string[] = [];
    for (const [posId, candIds] of Object.entries(mappings)) {
      if (candIds.includes(candidate.id)) {
        mappedIds.push(posId);
      }
    }

    return positions.filter((p) => mappedIds.includes(p.id));
  }, [candidate, mappings, positions]);

  if (!candidate && candidateId) return null;

  return (
    <AnimatePresence>
      {candidate && (
        <>
          {/* Backdrop Overlay */}
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            onClick={onClose}
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
            {/* Drawer Header */}
            <div className="p-6 border-b border-border bg-[var(--color-surface)] flex items-start justify-between">
              <div className="flex items-center gap-4">
                <div
                  className={cn(
                    "flex items-center justify-center size-16 rounded-full border shrink-0 font-bold text-2xl",
                    getAvatarColor(candidate.name),
                  )}
                >
                  {getInitials(candidate.name)}
                </div>
                <div>
                  <h2 className="text-2xl font-bold font-heading text-[var(--color-text-primary)]">
                    {candidate.name}
                  </h2>
                  <p className="text-sm mt-0.5 text-gray-400">
                    {candidate.previousCompany || "Independent"} &bull; {candidate.experienceYears}{" "}
                    yrs exp
                  </p>
                </div>
              </div>
              <button
                onClick={onClose}
                className="p-1.5 rounded-lg bg-[var(--color-canvas)] border border-border text-gray-400 hover:text-white transition-colors"
              >
                <IconX className="size-5" />
              </button>
            </div>

            {/* Quick Contact Info */}
            <div className="px-6 py-4 bg-[var(--color-canvas)] border-b border-border/80 flex justify-between gap-4">
              <div className="flex items-center gap-2 text-sm text-gray-300">
                <IconMail className="size-4 text-gray-500" />
                <a
                  href={`mailto:${candidate.email}`}
                  className="hover:text-yellow transition-colors"
                >
                  {candidate.email}
                </a>
              </div>
              <div className="flex items-center gap-2 text-sm text-gray-300">
                <IconPhone className="size-4 text-gray-500" />
                <span>{candidate.phone}</span>
              </div>
            </div>

            {/* Scrollable Content */}
            <div className="flex-1 overflow-y-auto p-6 space-y-8 dashboard-scrollbar bg-[var(--color-canvas)]">
              {/* Skills */}
              <section>
                <h3 className="text-xs font-bold uppercase text-gray-500 tracking-wider mb-4">
                  Skills & Expertise
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

              {/* Active Mappings */}
              <section>
                <div className="flex items-center justify-between mb-4">
                  <h3 className="text-xs font-bold uppercase text-gray-500 tracking-wider">
                    Active Mappings
                  </h3>
                  <span className="text-xs font-bold bg-surface-2 px-2 py-0.5 rounded text-gray-300 border border-border">
                    {mappedPositions.length} Positions
                  </span>
                </div>

                {mappedPositions.length === 0 ? (
                  <div className="text-center p-6 border border-dashed border-border rounded-xl text-gray-500 bg-[var(--color-surface)]">
                    <IconBriefcase className="size-6 mx-auto mb-2 opacity-50" />
                    <p className="text-sm">Not currently mapped to any open positions.</p>
                  </div>
                ) : (
                  <div className="space-y-3">
                    {mappedPositions.map((pos) => (
                      <div
                        key={pos.id}
                        className="p-4 rounded-xl border border-border bg-[var(--color-surface)] flex flex-col gap-3"
                      >
                        <div className="flex justify-between items-start">
                          <div>
                            <span className="font-mono text-xs text-teal-400 font-bold px-1.5 py-0.5 bg-teal-500/10 rounded border border-teal-500/20 mb-1.5 inline-block">
                              {pos.id}
                            </span>
                            <h4 className="font-bold text-white text-base leading-tight">
                              {pos.role}
                            </h4>
                            <p className="text-xs text-gray-400 mt-1">
                              {pos.clientName} &bull; {pos.city}
                            </p>
                          </div>
                          <span className="flex items-center gap-1 px-2 py-1 rounded bg-emerald-500/10 text-emerald-400 border border-emerald-500/20 text-[10px] font-bold uppercase">
                            <IconCircleCheck className="size-3" />
                            Mapped
                          </span>
                        </div>
                        <div className="pt-3 border-t border-border/50">
                          <a
                            href={`/positions/${pos.id}/pipeline`}
                            className="text-xs font-semibold text-yellow hover:underline flex items-center gap-1"
                          >
                            View Pipeline <IconExternalLink className="size-3" />
                          </a>
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </section>
            </div>
          </motion.div>
        </>
      )}
    </AnimatePresence>
  );
}
