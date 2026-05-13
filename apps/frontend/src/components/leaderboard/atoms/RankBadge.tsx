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

const rankStyles: Record<number, { bg: string; text: string; shadow: string; border: string }> = {
  1: {
    bg: "bg-yellow",
    text: "text-navy font-bold",
    shadow: "shadow-yellow/40 shadow-md",
    border: "border-yellow/80",
  },
  2: {
    bg: "bg-white/20",
    text: "text-white font-bold",
    shadow: "shadow-white/20 shadow-sm",
    border: "border-white/40",
  },
  3: {
    bg: "bg-amber-600/30",
    text: "text-amber-300 font-bold",
    shadow: "shadow-amber-400/20 shadow-sm",
    border: "border-amber-500/40",
  },
};

export function RankBadge({ rank, size = "md" }: RankBadgeProps) {
  const style = rankStyles[rank] ?? {
    bg: "bg-white/8",
    text: "text-white/60 font-semibold",
    shadow: "",
    border: "border-white/10",
  };

  return (
    <motion.div
      initial={{ scale: 0.8, opacity: 0 }}
      animate={{ scale: 1, opacity: 1 }}
      transition={{ duration: 0.3, type: "spring", stiffness: 260 }}
      className={cn(
        "flex items-center justify-center rounded-full border shrink-0",
        sizeClasses[size],
        style.bg,
        style.text,
        style.shadow,
        style.border,
      )}
    >
      {rank >= 1 && rank <= 3 ? (rank === 1 ? "🥇" : rank === 2 ? "🥈" : "🥉") : `#${rank}`}
    </motion.div>
  );
}
