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
      style={{ color: "var(--color-text-primary)" }}
    >
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h2 className="font-heading text-xl">Pipeline Stage Breakdown</h2>
          <p className="mt-1 text-sm" style={{ opacity: 0.6 }}>
            <AnimatedNumber value={total} /> active stage records from demo data
          </p>
        </div>
        <span className="rounded-full bg-yellow px-3 py-1 text-xs font-bold text-navy">
          Live overview
        </span>
      </div>

      <div
        className="mt-4 flex-1 overflow-hidden rounded-xl"
        style={{ background: "var(--color-border-val)" }}
      >
        <div className="overflow-x-auto">
          <table className="min-w-full table-fixed border-separate border-spacing-0">
            <thead>
              <tr
                style={{
                  background: "var(--color-surface-2-val)",
                  color: "var(--color-text-primary)",
                }}
              >
                <th scope="col" className="w-[52%] px-4 py-3 text-left font-heading text-lg">
                  Stage
                </th>
                <th scope="col" className="w-[22%] px-4 py-3 text-center font-heading text-lg">
                  Count
                </th>
                <th scope="col" className="w-[26%] px-4 py-3 text-center font-heading text-lg">
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
                    style={{ background: isOdd ? "var(--color-surface-val)" : "transparent" }}
                  >
                    <td className="max-w-0 px-4 py-2 text-left text-base font-medium">
                      <span className="block truncate">{stage.label}</span>
                    </td>
                    <td className="px-4 py-2 text-center font-heading text-xl">
                      <AnimatedNumber value={stage.count} />
                    </td>
                    <td className="px-4 py-2 text-center text-base font-medium">
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
