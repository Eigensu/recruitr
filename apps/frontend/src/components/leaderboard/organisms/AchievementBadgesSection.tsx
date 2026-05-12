"use client";

import { motion } from "motion/react";
import { AchievementBadge } from "@/components/leaderboard/molecules/AchievementBadge";
import { DASHBOARD_PANEL_CLASS } from "@/components/common/constants/dashboard-constants";
import { BADGE_DEFINITIONS, RARITY_STYLES } from "@/lib/leaderboard-data";
import { cn } from "@/lib/utils";

const ALL_BADGES = Object.values(BADGE_DEFINITIONS);

export function AchievementBadgesSection() {
  return (
    <motion.section
      initial={{ opacity: 0, y: 18 }}
      whileInView={{ opacity: 1, y: 0 }}
      viewport={{ once: true, amount: 0.12 }}
      transition={{ duration: 0.45, ease: "easeOut" }}
      className={cn(DASHBOARD_PANEL_CLASS, "p-5")}
    >
      <div className="flex items-start justify-between gap-3 mb-5">
        <div>
          <h2 className="font-heading text-xl text-white">Achievement Badges</h2>
          <p className="mt-1 text-sm text-white/50">Gamified recruiter milestones</p>
        </div>
        <div className="flex gap-1.5 flex-wrap justify-end">
          {(["legendary", "epic", "rare", "uncommon"] as const).map((r) => (
            <span
              key={r}
              className={cn(
                "text-[9px] font-bold uppercase px-1.5 py-0.5 rounded border",
                RARITY_STYLES[r].label,
                RARITY_STYLES[r].border,
                RARITY_STYLES[r].bg,
              )}
            >
              {r}
            </span>
          ))}
        </div>
      </div>

      <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
        {ALL_BADGES.map((badge, index) => {
          const rarity = RARITY_STYLES[badge.rarity];
          return (
            <motion.div
              key={badge.key}
              initial={{ opacity: 0, scale: 0.88 }}
              whileInView={{ opacity: 1, scale: 1 }}
              viewport={{ once: true, amount: 0.4 }}
              transition={{ duration: 0.35, delay: index * 0.06, type: "spring", stiffness: 180 }}
              className={cn(
                "flex flex-col items-center gap-2 rounded-xl border p-4 text-center",
                rarity.bg,
                rarity.border,
              )}
            >
              <AchievementBadge badgeKey={badge.key} size="md" />
              <div>
                <p className={cn("text-xs font-bold", rarity.label)}>{badge.label}</p>
                <p className="mt-0.5 text-[9px] text-white/40 leading-snug">{badge.description}</p>
              </div>
              <span
                className={cn(
                  "mt-auto text-[8px] font-bold uppercase tracking-widest px-1.5 py-0.5 rounded border",
                  rarity.label,
                  rarity.border,
                  "opacity-70",
                )}
              >
                {badge.rarity}
              </span>
            </motion.div>
          );
        })}
      </div>
    </motion.section>
  );
}
