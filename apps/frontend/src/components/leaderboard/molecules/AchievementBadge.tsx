"use client";

import { useState } from "react";
import { motion, AnimatePresence } from "motion/react";
import { cn } from "@/lib/utils";
import { BADGE_DEFINITIONS, RARITY_STYLES, type LeaderboardBadgeKey } from "@/lib/leaderboard-data";

interface AchievementBadgeProps {
  badgeKey: LeaderboardBadgeKey;
  size?: "sm" | "md" | "lg";
  showTooltip?: boolean;
}

const sizeClasses = {
  sm: "size-10 text-lg",
  md: "size-14 text-2xl",
  lg: "size-20 text-4xl",
};

export function AchievementBadge({
  badgeKey,
  size = "md",
  showTooltip = true,
}: Readonly<AchievementBadgeProps>) {
  const [hovered, setHovered] = useState(false);
  const badge = BADGE_DEFINITIONS[badgeKey];
  const rarity = RARITY_STYLES[badge.rarity];

  return (
    <div className="relative inline-flex">
      <motion.div
        onHoverStart={() => setHovered(true)}
        onHoverEnd={() => setHovered(false)}
        whileHover={{ scale: 1.12, y: -2 }}
        transition={{ type: "spring", stiffness: 300 }}
        className={cn(
          "flex items-center justify-center rounded-xl cursor-pointer select-none",
          "shadow-lg transition-shadow duration-300",
          sizeClasses[size],
          rarity.bg,
          hovered && rarity.glow,
        )}
        aria-label={`${badge.label} badge (${badge.rarity})`}
      >
        <span role="img" aria-hidden="true">
          {badge.emoji}
        </span>
        {/* Shimmer overlay */}
        <motion.div
          initial={{ x: "-100%", opacity: 0 }}
          animate={hovered ? { x: "200%", opacity: 0.3 } : { x: "-100%", opacity: 0 }}
          transition={{ duration: 0.5 }}
          className="absolute inset-0 rounded-xl bg-linear-to-r from-transparent via-white/40 to-transparent pointer-events-none"
        />
      </motion.div>

      {showTooltip && (
        <AnimatePresence>
          {hovered && (
            <motion.div
              initial={{ opacity: 0, y: 6, scale: 0.95 }}
              animate={{ opacity: 1, y: 0, scale: 1 }}
              exit={{ opacity: 0, y: 6, scale: 0.95 }}
              transition={{ duration: 0.18 }}
              className={cn(
                "absolute bottom-full left-1/2 -translate-x-1/2 mb-2 z-50",
                "w-48 rounded-lg p-3 shadow-xl backdrop-blur",
                "bg-(--color-surface-val) pointer-events-none",
              )}
              role="tooltip"
            >
              <p className={cn("text-xs font-bold uppercase tracking-wider", rarity.label)}>
                {badge.rarity}
              </p>
              <p className="mt-0.5 text-sm font-semibold text-(--color-text-primary)">
                {badge.label}
              </p>
              <p className="mt-1 text-xs text-(--color-text-secondary) leading-snug">
                {badge.description}
              </p>
            </motion.div>
          )}
        </AnimatePresence>
      )}
    </div>
  );
}
