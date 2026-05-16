"use client";

import { motion } from "motion/react";
import AnimatedNumber from "@/components/dashboard/atoms/AnimatedNumber";
import { TONE_STYLES } from "@/components/common/constants/dashboard-constants";
import { cn } from "@/lib/utils";
import type { LeaderboardKpi } from "@/lib/leaderboard-data";

interface LeaderboardKpiCardProps {
  readonly kpi: LeaderboardKpi;
  readonly index: number;
}

export function LeaderboardKpiCard(props: LeaderboardKpiCardProps) {
  const { kpi, index } = props;
  const tone = TONE_STYLES[kpi.tone] ?? TONE_STYLES.neutral;

  return (
    <motion.article
      initial={{ opacity: 0, y: 14 }}
      whileInView={{ opacity: 1, y: 0 }}
      viewport={{ once: true, amount: 0.35 }}
      transition={{ duration: 0.4, delay: index * 0.04, ease: "easeOut" }}
      whileHover={{ y: -2 }}
      className={cn("rounded-lg p-4 transition-colors shadow-md")}
      style={{ background: tone.cardBg, color: tone.cardText, boxShadow: tone.shadow }}
    >
      <p
        className="text-[10px] font-semibold uppercase tracking-wider"
        style={{ opacity: tone.mutedOpacity }}
      >
        {kpi.label}
      </p>
      <p className="mt-2 font-heading text-3xl leading-none tabular-nums">
        <AnimatedNumber value={kpi.value} suffix={kpi.suffix ?? ""} />
      </p>
      <p className="mt-2 text-xs" style={{ opacity: tone.mutedOpacity }}>
        {kpi.helper}
      </p>
    </motion.article>
  );
}
