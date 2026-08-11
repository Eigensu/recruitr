"use client";

import { motion } from "motion/react";
import { IconArrowUpRight } from "@tabler/icons-react";
import AnimatedNumber from "@/components/dashboard/atoms/AnimatedNumber";
import { TONE_STYLES, KPI_ICON_MAP } from "@/components/common/constants/dashboard-constants";
import type { DashboardKpi } from "@/types/dashboard";

interface DashboardKpiCardProps {
  metric: DashboardKpi;
  index: number;
}

export default function DashboardKpiCard({ metric, index }: DashboardKpiCardProps) {
  const tone = TONE_STYLES[metric.tone] ?? TONE_STYLES.neutral;
  const Icon = KPI_ICON_MAP[metric.id as keyof typeof KPI_ICON_MAP] ?? IconArrowUpRight;

  return (
    <motion.article
      initial={{ opacity: 0 }}
      whileInView={{ opacity: 1 }}
      viewport={{ once: true, amount: 0.35 }}
      transition={{ duration: 0.3, delay: index * 0.035 }}
      className="rounded-lg p-3 h-full cursor-default hover:-translate-y-0.5 active:scale-[0.98]"
      style={{
        background: tone.cardBg,
        color: tone.cardText,
        boxShadow: tone.shadow,
        transition: "transform 100ms ease-out",
      }}
    >
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          {/* Muted label — inherits card text colour, reduced via opacity */}
          <p
            className="text-xs font-semibold uppercase tracking-normal"
            style={{ opacity: tone.mutedOpacity }}
          >
            {metric.label}
          </p>
          {/* Value — inherits card text colour */}
          <p className="mt-2 font-heading text-4xl leading-none">
            <AnimatedNumber value={metric.value} suffix={metric.suffix ? ` ${metric.suffix}` : ""} />
          </p>
        </div>
        {/* Icon chip */}
        <div
          className="flex size-10 shrink-0 items-center justify-center rounded-lg"
          style={{ background: tone.chipBg, color: tone.chipText }}
        >
          <Icon className="size-5" />
        </div>
      </div>
      <div className="mt-3 flex items-center justify-between gap-3">
        <span className="text-sm" style={{ opacity: tone.mutedOpacity }}>
          {metric.helper}
        </span>
        <span
          className="shrink-0 whitespace-nowrap rounded-full px-2 py-1 text-[11px] font-semibold"
          style={{ background: tone.chipBg, color: tone.chipText }}
        >
          {metric.trend}
        </span>
      </div>
    </motion.article>
  );
}
