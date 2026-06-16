import React from "react";
import { IconMail, IconBriefcase, IconFileText, IconLink } from "@tabler/icons-react";
import type { ApiCandidate } from "@/types";
import { resolveCvRef } from "@/lib/api/candidates";

interface CandidateCardProps {
  candidate: ApiCandidate;
  onClick: () => void;
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

export default function CandidateCard({ candidate, onClick }: Readonly<CandidateCardProps>) {
  const palette = getAvatarPalette(candidate.full_name);
  const initials = getInitials(candidate.full_name);
  const cvRef = resolveCvRef(candidate.cv_link, candidate.resume_url);

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
                  {candidate.previous_company ?? "Independent"} · {candidate.experience_years}y
                </span>
              </p>
            </div>
          </div>

          {/* Skills */}
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
        </div>
      </div>
    </div>
  );
}
