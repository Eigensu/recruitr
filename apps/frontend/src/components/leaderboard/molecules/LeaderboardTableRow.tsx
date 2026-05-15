"use client";

import { useState } from "react";
import { motion } from "motion/react";
import { RankBadge } from "@/components/leaderboard/atoms/RankBadge";
import { RecruiterAvatar } from "@/components/leaderboard/atoms/RecruiterAvatar";
import { AnimatedProgressBar } from "@/components/leaderboard/atoms/AnimatedProgressBar";
import { AchievementBadge } from "@/components/leaderboard/molecules/AchievementBadge";
import { cn } from "@/lib/utils";
import type { LeaderboardRecruiter } from "@/lib/leaderboard-data";

interface LeaderboardTableRowProps {
  readonly recruiter: LeaderboardRecruiter;
  readonly index: number;
}

const TOP3_ROW: Record<number, string> = {
  1: "bg-yellow/[0.045]",
  2: "bg-(--color-surface-2-val)",
  3: "bg-amber-600/[0.04]",
};

export function LeaderboardTableRow(props: LeaderboardTableRowProps) {
  const { recruiter, index } = props;
  const [expanded, setExpanded] = useState(false);
  const isTop3 = recruiter.rank <= 3;
  const rowBg = TOP3_ROW[recruiter.rank] ?? "hover:bg-(--color-surface-2-val)";

  return (
    <>
      <motion.tr
        initial={{ opacity: 0, x: -12 }}
        whileInView={{ opacity: 1, x: 0 }}
        viewport={{ once: true, amount: 0.5 }}
        transition={{ duration: 0.35, delay: index * 0.04, ease: "easeOut" }}
        className={cn("transition-colors group text-(--color-text-primary)", rowBg)}
      >
        {/* Rank */}
        <td className="px-4 py-3 w-14">
          <RankBadge rank={recruiter.rank} size="sm" />
        </td>

        {/* Recruiter */}
        <td className="px-4 py-3">
          <div className="flex items-center gap-3 min-w-0">
            <RecruiterAvatar
              initials={recruiter.initials}
              color={recruiter.avatarColor}
              size="sm"
              pulse={recruiter.rank === 1}
            />
            <div className="min-w-0">
              <p className="text-sm font-semibold truncate">{recruiter.name}</p>
              <p className="text-[10px] text-(--color-text-secondary)">
                Lv {recruiter.level} · {recruiter.xp.toLocaleString()} XP
              </p>
            </div>
          </div>
        </td>

        {/* Mappings */}
        <td className="px-4 py-3 text-center text-sm font-heading hidden sm:table-cell">
          {recruiter.totalMappings}
        </td>

        {/* Offers */}
        <td className="px-4 py-3 text-center text-sm text-yellow/90 hidden md:table-cell">
          {recruiter.offersReceived}
        </td>

        {/* Joins */}
        <td className="px-4 py-3 text-center text-sm text-emerald-400 hidden lg:table-cell">
          {recruiter.joined}
        </td>

        {/* Rejected */}
        <td className="px-4 py-3 text-center text-sm text-red-400/80 hidden xl:table-cell">
          {recruiter.rejected}
        </td>

        {/* Success rate */}
        <td className="px-4 py-3 w-32 hidden xl:table-cell">
          <div className="flex items-center gap-2">
            <AnimatedProgressBar
              value={recruiter.successRate}
              color={isTop3 ? "#F3FF54" : "#3DDC97"}
              height="xs"
              delay={index * 0.04}
              className="flex-1"
            />
            <span className="text-[10px] text-(--color-text-secondary) tabular-nums w-8">
              {recruiter.successRate}%
            </span>
          </div>
        </td>

        {/* Growth */}
        <td className="px-4 py-3 text-center hidden 2xl:table-cell">
          {(() => {
            let growthClass = "bg-(--color-surface-2-val) text-(--color-text-secondary)";
            if (recruiter.monthlyGrowth >= 30) {
              growthClass = "bg-emerald-400/15 text-emerald-300";
            } else if (recruiter.monthlyGrowth >= 15) {
              growthClass = "bg-yellow/15 text-yellow";
            }

            return (
              <span className={cn("text-xs font-semibold px-2 py-0.5 rounded-full", growthClass)}>
                +{recruiter.monthlyGrowth}%
              </span>
            );
          })()}
        </td>

        {/* Badge */}
        <td className="px-4 py-3 text-center">
          <button
            type="button"
            onClick={() => setExpanded((p) => !p)}
            aria-expanded={expanded}
            className="rounded-full focus:outline-none focus-visible:ring-2 focus-visible:ring-yellow focus-visible:ring-offset-2"
            style={{ ["--tw-ring-offset-color" as string]: "var(--color-surface-val)" }}
          >
            <AchievementBadge badgeKey={recruiter.badge} size="sm" />
          </button>
        </td>
      </motion.tr>

      {/* Expanded mini-chart row */}
      {expanded && (
        <tr className="bg-(--color-surface-2-val)">
          <td colSpan={9} className="px-6 py-3">
            <motion.div
              initial={{ opacity: 0, height: 0 }}
              animate={{ opacity: 1, height: "auto" }}
              exit={{ opacity: 0, height: 0 }}
              className="flex flex-wrap items-center gap-6 text-xs text-(--color-text-secondary)"
            >
              <span>
                📊{" "}
                <strong className="text-(--color-text-primary)">{recruiter.totalMappings}</strong>{" "}
                mappings
              </span>
              <span>
                🎯 <strong className="text-yellow">{recruiter.offersReceived}</strong> offers
              </span>
              <span>
                ✅ <strong className="text-emerald-300">{recruiter.joined}</strong> joined
              </span>
              <span>
                ❌ <strong className="text-red-400">{recruiter.rejected}</strong> rejected
              </span>
              <span>
                ⚡{" "}
                <strong className="text-(--color-text-primary)">
                  {recruiter.xp.toLocaleString()}
                </strong>{" "}
                XP
              </span>
              <span className="ml-auto text-(--color-text-secondary) text-[10px]">
                Click row to collapse
              </span>
            </motion.div>
          </td>
        </tr>
      )}
    </>
  );
}
