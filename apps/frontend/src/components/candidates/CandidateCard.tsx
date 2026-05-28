import React from "react";
import { IconMail, IconPhone, IconBriefcase, IconCircleCheck } from "@tabler/icons-react";
import { MockCandidate } from "@/stores/usePositionsStore";
import { cn } from "@/lib/utils";

interface CandidateCardProps {
  candidate: MockCandidate;
  onClick: () => void;
}

const AVATAR_COLORS = [
  "bg-emerald-500/15 text-emerald-400 border-emerald-500/30",
  "bg-blue-500/15 text-blue-400 border-blue-500/30",
  "bg-purple-500/15 text-purple-400 border-purple-500/30",
  "bg-pink-500/15 text-pink-400 border-pink-500/30",
  "bg-yellow/15 text-yellow border-yellow/30",
];

export function getAvatarColor(name: string) {
  let hash = 0;
  for (let i = 0; i < name.length; i++) {
    hash = name.charCodeAt(i) + ((hash << 5) - hash);
  }
  const index = Math.abs(hash) % AVATAR_COLORS.length;
  return AVATAR_COLORS[index];
}

export function getInitials(name: string) {
  return name
    .split(" ")
    .map((n) => n[0])
    .slice(0, 2)
    .join("")
    .toUpperCase();
}

export default function CandidateCard({ candidate, onClick }: CandidateCardProps) {
  const avatarStyle = getAvatarColor(candidate.name);

  return (
    <div
      onClick={onClick}
      className="p-5 rounded-xl border border-border bg-surface-panel hover:border-yellow/50 hover:shadow-lg hover:shadow-yellow/5 transition-all duration-200 cursor-pointer flex flex-col h-full group"
    >
      <div className="flex items-start gap-4 mb-4">
        {/* Avatar */}
        <div
          className={cn(
            "flex items-center justify-center size-12 rounded-full border shrink-0 font-bold text-lg",
            avatarStyle,
          )}
        >
          {getInitials(candidate.name)}
        </div>

        <div className="flex-1 min-w-0">
          <h3 className="font-bold text-white text-lg truncate group-hover:text-yellow transition-colors">
            {candidate.name}
          </h3>
          <p className="text-sm text-gray-400 flex items-center gap-1.5 truncate mt-0.5">
            <IconBriefcase className="size-3.5 shrink-0" />
            <span className="truncate">
              {candidate.previousCompany || "Freelance"} &bull; {candidate.experienceYears} yrs
            </span>
          </p>
        </div>
      </div>

      {/* Skills */}
      <div className="flex flex-wrap gap-1.5 mb-5">
        {candidate.skills.slice(0, 3).map((skill) => (
          <span
            key={skill}
            className="text-[11px] font-semibold px-2 py-0.5 rounded-full"
            style={{
              color: "var(--color-yellow)",
              backgroundColor: "rgba(243,255,84,0.12)",
              border: "1px solid rgba(243,255,84,0.25)",
            }}
          >
            {skill}
          </span>
        ))}
        {candidate.skills.length > 3 && (
          <span className="text-[10px] px-1.5 py-0.5 text-gray-500 font-medium">
            +{candidate.skills.length - 3} more
          </span>
        )}
      </div>

      {/* Contact Info (Footer) */}
      <div className="mt-auto pt-4 border-t border-border/50 flex flex-col gap-2">
        <div className="flex items-center text-xs text-gray-400 truncate">
          <IconMail className="size-3.5 mr-2 shrink-0 opacity-70" />
          <span className="truncate">{candidate.email}</span>
        </div>
        <div className="flex items-center text-xs text-gray-400">
          <IconPhone className="size-3.5 mr-2 shrink-0 opacity-70" />
          <span>{candidate.phone}</span>
        </div>
      </div>
    </div>
  );
}
