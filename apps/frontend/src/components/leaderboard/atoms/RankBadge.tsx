"use client";

import { motion } from "motion/react";
import { cn } from "@/lib/utils";

interface RankBadgeProps {
  rank: number;
  size?: "sm" | "md" | "lg";
}

const sizeClasses = {
  sm: "size-6 text-xs",
  md: "size-8 text-sm",
  lg: "size-10 text-base",
};

const rankStyles: Record<number, { bg: string; text: string; shadow: string }> = {
  1: {
    bg: "bg-yellow",
    text: "text-navy font-bold",
    shadow: "shadow-yellow/40 shadow-md",
  },
  2: {
    bg: "bg-[color:var(--color-surface-2-val)]",
    text: "text-[color:var(--color-text-primary)] font-bold",
    shadow: "shadow-sm",
  },
  3: {
    bg: "bg-amber-600/30",
    text: "text-amber-300 font-bold",
    shadow: "shadow-amber-400/20 shadow-sm",
  },
};

export function RankBadge({ rank, size = "md" }: Readonly<RankBadgeProps>) {
  const style = rankStyles[rank] ?? {
    bg: "bg-(--color-surface-2-val)",
    text: "text-(--color-text-secondary) font-semibold",
    shadow: "",
  };

  let badgeLabel = `#${rank}`;
  if (rank === 1) {
    badgeLabel = "🥇";
  } else if (rank === 2) {
    badgeLabel = "🥈";
  } else if (rank === 3) {
    badgeLabel = "🥉";
  }

  return (
    <motion.div
      initial={{ scale: 0.8, opacity: 0 }}
      animate={{ scale: 1, opacity: 1 }}
      transition={{ duration: 0.3, type: "spring", stiffness: 260 }}
      className={cn(
        "flex items-center justify-center rounded-full shrink-0",
        sizeClasses[size],
        style.bg,
        style.text,
        style.shadow,
      )}
    >
      {badgeLabel}
    </motion.div>
  );
}
