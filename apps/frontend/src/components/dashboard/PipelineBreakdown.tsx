"use client";

import { motion } from "motion/react";
import AnimatedNumber from "@/components/dashboard/AnimatedNumber";
import { DASHBOARD_PANEL_CLASS } from "@/lib/dashboard-constants";
import { cn } from "@/lib/utils";
import type { PipelineStageMetric } from "@/types/dashboard";

interface PipelineBreakdownProps {
  stages: PipelineStageMetric[];
}

export default function PipelineBreakdown({ stages }: PipelineBreakdownProps) {
  const total = stages.reduce((sum, stage) => sum + stage.count, 0);

  return (
    <motion.section
      initial={{ opacity: 0, y: 18 }}
      whileInView={{ opacity: 1, y: 0 }}
      viewport={{ once: true, amount: 0.18 }}
      transition={{ duration: 0.45, ease: "easeOut" }}
      className={cn(DASHBOARD_PANEL_CLASS, "p-5")}
    >
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h2 className="font-heading text-xl text-white">Pipeline Stage Breakdown</h2>
          <p className="mt-1 text-sm text-white/50">
            <AnimatedNumber value={total} /> active stage records from demo data
          </p>
        </div>
        <span className="rounded-full bg-yellow px-3 py-1 text-xs font-bold text-navy">
          Live overview
        </span>
      </div>

      <div className="mt-6 space-y-4">
        {stages.map((stage, index) => (
          <motion.div
            key={stage.stage}
            initial={{ opacity: 0, y: 8 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true, amount: 0.35 }}
            transition={{ duration: 0.28, delay: index * 0.025 }}
          >
            <div className="mb-2 flex items-center justify-between gap-4">
              <div className="min-w-0">
                <p className="truncate text-sm font-medium text-white">{stage.label}</p>
                <p className="text-xs text-white/45">
                  <AnimatedNumber value={stage.count} /> candidates
                </p>
              </div>
              <span className="font-heading text-lg text-yellow">
                <AnimatedNumber value={stage.percent} suffix="%" />
              </span>
            </div>
            <div className="h-2 overflow-hidden rounded-full bg-white/10">
              <motion.div
                initial={{ width: 0 }}
                whileInView={{ width: `${Math.min(stage.percent, 100)}%` }}
                viewport={{ once: true, amount: 0.45 }}
                transition={{ duration: 0.7, delay: 0.12 + index * 0.035, ease: "easeOut" }}
                className="h-full rounded-full bg-yellow"
              />
            </div>
          </motion.div>
        ))}
      </div>
    </motion.section>
  );
}
