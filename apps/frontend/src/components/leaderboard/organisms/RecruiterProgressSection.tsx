"use client";

import { motion } from "motion/react";
import { RecruiterAvatar } from "@/components/leaderboard/atoms/RecruiterAvatar";
import { AnimatedProgressBar } from "@/components/leaderboard/atoms/AnimatedProgressBar";
import AnimatedNumber from "@/components/dashboard/atoms/AnimatedNumber";
import { DASHBOARD_PANEL_CLASS } from "@/components/common/constants/dashboard-constants";
import { cn } from "@/lib/utils";
import type { LeaderboardRecruiter } from "@/lib/leaderboard-data";

interface RecruiterProgressSectionProps {
  recruiters: LeaderboardRecruiter[];
}

export function RecruiterProgressSection({ recruiters }: RecruiterProgressSectionProps) {
  // Show top 6
  const displayed = recruiters.slice(0, 6);

  return (
    <motion.section
      initial={{ opacity: 0, y: 18 }}
      whileInView={{ opacity: 1, y: 0 }}
      viewport={{ once: true, amount: 0.1 }}
      transition={{ duration: 0.45, ease: "easeOut" }}
      className={cn(DASHBOARD_PANEL_CLASS, "p-5")}
    >
      <div className="flex items-start justify-between gap-3 mb-5">
        <div>
          <h2 className="font-heading text-xl text-white">Recruiter Progress</h2>
          <p className="mt-1 text-sm text-white/50">XP and goal completion</p>
        </div>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
        {displayed.map((recruiter, index) => {
          const xpPct = Math.max(
            0,
            Math.min(100, Number.isFinite(recruiter.xp) ? (recruiter.xp / 10000) * 100 : 0),
          );
          const totalMappings = Number(recruiter.totalMappings);
          const joined = Number(recruiter.joined);
          const joinPctRaw =
            totalMappings > 0 && Number.isFinite(joined) && Number.isFinite(totalMappings)
              ? Math.round((joined / totalMappings) * 100)
              : 0;
          const joinPct = Math.max(0, Math.min(100, joinPctRaw));

          return (
            <motion.div
              key={recruiter.id}
              initial={{ opacity: 0, y: 10 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true, amount: 0.5 }}
              transition={{ duration: 0.35, delay: index * 0.05 }}
              whileHover={{ y: -2 }}
              className="rounded-lg border border-white/8 bg-white/[0.025] p-4"
            >
              <div className="flex items-center gap-3 mb-3">
                <RecruiterAvatar
                  initials={recruiter.initials}
                  color={recruiter.avatarColor}
                  size="sm"
                />
                <div className="min-w-0 flex-1">
                  <p className="text-sm font-semibold text-white/80 truncate">{recruiter.name}</p>
                  <p className="text-[10px] text-white/35">Level {recruiter.level}</p>
                </div>
                <span className="text-xs font-bold text-yellow tabular-nums">
                  <AnimatedNumber value={recruiter.xp} /> XP
                </span>
              </div>

              {/* XP bar */}
              <div className="mb-2">
                <div className="flex justify-between text-[10px] text-white/35 mb-1">
                  <span>XP Progress</span>
                  <span>{Math.round(xpPct)}%</span>
                </div>
                <AnimatedProgressBar
                  value={xpPct}
                  color="#F3FF54"
                  height="xs"
                  delay={index * 0.05}
                />
              </div>

              {/* Join conversion bar */}
              <div>
                <div className="flex justify-between text-[10px] text-white/35 mb-1">
                  <span>Join Conversion</span>
                  <span>{joinPct}%</span>
                </div>
                <AnimatedProgressBar
                  value={joinPct}
                  color="#3DDC97"
                  height="xs"
                  delay={index * 0.05 + 0.1}
                />
              </div>
            </motion.div>
          );
        })}
      </div>
    </motion.section>
  );
}
