"use client";

import { motion } from "motion/react";
import AnimatedNumber from "@/components/dashboard/atoms/AnimatedNumber";
import { cn } from "@/lib/utils";
import type { LeaderboardKpi } from "@/lib/leaderboard-data";

const toneStyles = {
  yellow: {
    card: "border-yellow/30 bg-yellow/[0.06]",
    value: "text-yellow",
    label: "text-yellow/60",
    icon: "bg-yellow/15 text-yellow",
    helper: "text-white/50",
  },
  green: {
    card: "border-emerald-400/25 bg-emerald-400/[0.05]",
    value: "text-emerald-300",
    label: "text-emerald-400/60",
    icon: "bg-emerald-400/15 text-emerald-300",
    helper: "text-white/50",
  },
  red: {
    card: "border-red-400/25 bg-red-400/[0.05]",
    value: "text-red-300",
    label: "text-red-400/60",
    icon: "bg-red-400/15 text-red-300",
    helper: "text-white/50",
  },
  navy: {
    card: "border-blue-400/25 bg-blue-900/20",
    value: "text-white",
    label: "text-white/50",
    icon: "bg-yellow/15 text-yellow",
    helper: "text-white/50",
  },
  neutral: {
    card: "border-white/10 bg-white/[0.035]",
    value: "text-white",
    label: "text-white/45",
    icon: "bg-white/10 text-white/70",
    helper: "text-white/45",
  },
};

interface LeaderboardKpiCardProps {
  kpi: LeaderboardKpi;
  index: number;
}

export function LeaderboardKpiCard({ kpi, index }: LeaderboardKpiCardProps) {
  const styles = toneStyles[kpi.tone];

  return (
    <motion.article
      initial={{ opacity: 0, y: 14 }}
      whileInView={{ opacity: 1, y: 0 }}
      viewport={{ once: true, amount: 0.35 }}
      transition={{ duration: 0.4, delay: index * 0.04, ease: "easeOut" }}
      whileHover={{ y: -2 }}
      className={cn("rounded-lg border p-4 transition-colors", styles.card)}
    >
      <p className={cn("text-[10px] font-semibold uppercase tracking-wider", styles.label)}>
        {kpi.label}
      </p>
      <p className={cn("mt-2 font-heading text-3xl leading-none tabular-nums", styles.value)}>
        <AnimatedNumber value={kpi.value} suffix={kpi.suffix ?? ""} />
      </p>
      <p className={cn("mt-2 text-xs", styles.helper)}>{kpi.helper}</p>
    </motion.article>
  );
}
