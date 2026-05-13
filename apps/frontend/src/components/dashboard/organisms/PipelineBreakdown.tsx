"use client";

import { motion } from "motion/react";
import AnimatedNumber from "@/components/dashboard/atoms/AnimatedNumber";
import { DASHBOARD_PANEL_CLASS } from "@/components/common/constants/dashboard-constants";
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
      className={cn(DASHBOARD_PANEL_CLASS, "flex h-full flex-col p-5")}
    >
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h2 className="font-heading text-xl text-white">Pipeline Stage Breakdown</h2>
          <p className="mt-1 text-sm text-white">
            <AnimatedNumber value={total} /> active stage records from demo data
          </p>
        </div>
        <span className="rounded-full bg-yellow px-3 py-1 text-xs font-bold text-navy">
          Live overview
        </span>
      </div>

      <div className="mt-4 flex-1 overflow-hidden rounded-xl border border-white/10 bg-white/3">
        <div className="overflow-x-auto">
          <table className="min-w-full table-fixed border-separate border-spacing-0">
            <thead>
              <tr className="bg-[#0f2747] text-white">
                <th className="w-[52%] px-4 py-3 text-left font-heading text-lg">Stage</th>
                <th className="w-[22%] px-4 py-3 text-center font-heading text-lg">Count</th>
                <th className="w-[26%] px-4 py-3 text-center font-heading text-lg">
                  % of Pipeline
                </th>
              </tr>
            </thead>
            <tbody>
              {stages.map((stage, index) => {
                const isOdd = index % 2 === 1;
                return (
                  <tr
                    key={stage.stage}
                    className={cn(isOdd ? "bg-white/5" : "bg-white/3", "border-t border-white/10")}
                  >
                    <td className="max-w-0 px-4 py-2 text-left text-base font-medium text-white">
                      <span className="block truncate">{stage.label}</span>
                    </td>
                    <td className="px-4 py-2 text-center font-heading text-xl text-white">
                      <AnimatedNumber value={stage.count} />
                    </td>
                    <td className="px-4 py-2 text-center text-base font-medium text-white">
                      <AnimatedNumber value={stage.percent} suffix="%" />
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </div>
    </motion.section>
  );
}
