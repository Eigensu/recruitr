"use client";

import { motion } from "motion/react";
import { IconArrowUpRight } from "@tabler/icons-react";
import AnimatedNumber from "@/components/dashboard/atoms/AnimatedNumber";
import { TONE_CLASSES, KPI_ICON_MAP } from "@/components/common/constants/dashboard-constants";
import { cn } from "@/lib/utils";
import type { DashboardKpi } from "@/types/dashboard";

interface DashboardKpiCardProps {
  metric: DashboardKpi;
  index: number;
}

export default function DashboardKpiCard({ metric, index }: DashboardKpiCardProps) {
  const tone = TONE_CLASSES[metric.tone];
  const Icon = KPI_ICON_MAP[metric.id as keyof typeof KPI_ICON_MAP] ?? IconArrowUpRight;

  return (
    <motion.article
      initial={{ opacity: 0, y: 14 }}
      whileInView={{ opacity: 1, y: 0 }}
      viewport={{ once: true, amount: 0.35 }}
      transition={{ duration: 0.4, delay: index * 0.035, ease: "easeOut" }}
      whileHover={{ y: -2 }}
      className={cn("rounded-lg border p-3 shadow-sm transition-colors h-full", tone.card)}
    >
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <p className={cn("text-xs font-semibold uppercase tracking-normal", tone.muted)}>
            {metric.label}
          </p>
          <p className={cn("mt-2 font-heading text-4xl leading-none", tone.text)}>
            <AnimatedNumber value={metric.value} />
          </p>
        </div>
        <div
          className={cn("flex size-10 shrink-0 items-center justify-center rounded-lg", tone.chip)}
        >
          <Icon className="size-5" />
        </div>
      </div>
      <div className="mt-3 flex items-center justify-between gap-3">
        <span className={cn("text-sm", tone.muted)}>{metric.helper}</span>
        <span className={cn("rounded-full px-2 py-1 text-[11px] font-semibold", tone.chip)}>
          {metric.trend}
        </span>
      </div>
    </motion.article>
  );
}
