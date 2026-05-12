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
  recruiter: LeaderboardRecruiter;
  index: number;
}

const TOP3_ROW: Record<number, string> = {
  1: "bg-yellow/[0.045] border-yellow/20",
  2: "bg-white/[0.025] border-white/10",
  3: "bg-amber-600/[0.04] border-amber-500/15",
};

export function LeaderboardTableRow({ recruiter, index }: LeaderboardTableRowProps) {
  const [expanded, setExpanded] = useState(false);
  const isTop3 = recruiter.rank <= 3;
  const rowBg = TOP3_ROW[recruiter.rank] ?? "border-white/5 hover:bg-white/[0.02]";

  return (
    <>
      <motion.tr
        initial={{ opacity: 0, x: -12 }}
        whileInView={{ opacity: 1, x: 0 }}
        viewport={{ once: true, amount: 0.5 }}
        transition={{ duration: 0.35, delay: index * 0.04, ease: "easeOut" }}
        onClick={() => setExpanded((p) => !p)}
        className={cn("border-b transition-colors cursor-pointer group", rowBg)}
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
              <p
                className={cn(
                  "text-sm font-semibold truncate",
                  isTop3 ? "text-white" : "text-white/80",
                )}
              >
                {recruiter.name}
              </p>
              <p className="text-[10px] text-white/40">
                Lv {recruiter.level} · {recruiter.xp.toLocaleString()} XP
              </p>
            </div>
          </div>
        </td>

        {/* Mappings */}
        <td className="px-4 py-3 text-center text-sm font-heading text-white/80 hidden sm:table-cell">
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
            <span className="text-[10px] text-white/50 tabular-nums w-8">
              {recruiter.successRate}%
            </span>
          </div>
        </td>

        {/* Growth */}
        <td className="px-4 py-3 text-center hidden 2xl:table-cell">
          <span
            className={cn(
              "text-xs font-semibold px-2 py-0.5 rounded-full",
              recruiter.monthlyGrowth >= 30
                ? "bg-emerald-400/15 text-emerald-300"
                : recruiter.monthlyGrowth >= 15
                  ? "bg-yellow/15 text-yellow"
                  : "bg-white/10 text-white/55",
            )}
          >
            +{recruiter.monthlyGrowth}%
          </span>
        </td>

        {/* Badge */}
        <td className="px-4 py-3 text-center">
          <AchievementBadge badgeKey={recruiter.badge} size="sm" />
        </td>
      </motion.tr>

      {/* Expanded mini-chart row */}
      {expanded && (
        <tr className="border-b border-white/5 bg-white/[0.015]">
          <td colSpan={9} className="px-6 py-3">
            <motion.div
              initial={{ opacity: 0, height: 0 }}
              animate={{ opacity: 1, height: "auto" }}
              exit={{ opacity: 0, height: 0 }}
              className="flex flex-wrap items-center gap-6 text-xs text-white/60"
            >
              <span>
                📊 <strong className="text-white">{recruiter.totalMappings}</strong> mappings
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
                ⚡ <strong className="text-white">{recruiter.xp.toLocaleString()}</strong> XP
              </span>
              <span className="ml-auto text-white/30 text-[10px]">Click row to collapse</span>
            </motion.div>
          </td>
        </tr>
      )}
    </>
  );
}
