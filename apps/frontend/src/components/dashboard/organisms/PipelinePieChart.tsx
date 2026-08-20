"use client";

import { useRef, useState } from "react";
import { motion, useInView } from "motion/react";
import { IconChartFunnel } from "@tabler/icons-react";
import AnimatedNumber from "@/components/dashboard/atoms/AnimatedNumber";
import {
  CHART_COLORS,
  DASHBOARD_PANEL_CLASS,
} from "@/components/common/constants/dashboard-constants";
import { cn } from "@/lib/utils";
import type { PipelineStageMetric } from "@/types/dashboard";

interface PipelinePieChartProps {
  stages: PipelineStageMetric[];
}

export default function PipelinePieChart({ stages }: Readonly<PipelinePieChartProps>) {
  const chartRef = useRef<HTMLDivElement>(null);
  const isInView = useInView(chartRef, { once: true, amount: 0.42 });
  const [activeStage, setActiveStage] = useState(stages[0]?.stage);
  const maxCount = stages.reduce((max, s) => Math.max(max, s.count), 1);
  const active = stages.find((stage) => stage.stage === activeStage) ?? stages[0];

  if (!stages.length) {
    return (
      <section
        ref={chartRef}
        className={cn(DASHBOARD_PANEL_CLASS, "flex h-full flex-col p-5")}
        style={{ color: "var(--color-text-primary)" }}
      >
        <div className="flex items-start justify-between gap-3">
          <div>
            <h2 className="font-heading text-xl">Pipeline Funnel</h2>
            <p className="mt-1 text-sm" style={{ opacity: 0.6 }}>
              Candidate flow through pipeline stages
            </p>
          </div>
          <IconChartFunnel className="size-6 text-yellow" />
        </div>
        <div className="flex flex-1 items-center justify-center">
          <p className="text-sm" style={{ opacity: 0.5 }}>
            No pipeline data available.
          </p>
        </div>
      </section>
    );
  }

  return (
    <section
      ref={chartRef}
      className={cn(DASHBOARD_PANEL_CLASS, "flex h-full flex-col p-5")}
      style={{ color: "var(--color-text-primary)" }}
    >
      <div className="flex items-start justify-between gap-3">
        <div>
          <h2 className="font-heading text-xl" style={{ color: "var(--color-text-primary)" }}>
            Pipeline Funnel
          </h2>
          <p className="mt-1 text-sm" style={{ color: "var(--color-text-secondary)" }}>
            Candidate flow through pipeline stages
          </p>
        </div>
        <IconChartFunnel className="size-6 text-yellow" />
      </div>

      <div className="mt-4 flex flex-1 flex-col justify-center gap-1.5">
        {stages.map((stage, index) => {
          const widthPct = (stage.count / maxCount) * 100;
          const color = CHART_COLORS[index % CHART_COLORS.length] ?? "#FFFFFF";
          const isActive = stage.stage === activeStage;

          return (
            <button
              type="button"
              key={stage.stage}
              className="flex w-full items-center gap-2 outline-none"
              style={{ background: "none", border: "none", padding: 0, cursor: "pointer" }}
              onMouseEnter={() => setActiveStage(stage.stage)}
              onFocus={() => setActiveStage(stage.stage)}
              aria-label={`${stage.label}: ${stage.count} candidates, ${stage.percent}% of pipeline`}
            >
              <span
                className="w-24 shrink-0 truncate text-right text-xs transition-opacity"
                style={{
                  color: "var(--color-text-secondary)",
                  opacity: isActive ? 1 : 0.55,
                }}
              >
                {stage.label}
              </span>

              <div className="flex h-6 flex-1 items-center justify-center">
                <motion.div
                  className="relative flex h-full items-center justify-center overflow-hidden rounded-sm"
                  style={{ background: color, opacity: isActive ? 1 : 0.7 }}
                  initial={{ width: "0%" }}
                  animate={isInView ? { width: `${Math.max(widthPct, 1.5)}%` } : { width: "0%" }}
                  transition={{ duration: 0.55, delay: index * 0.07, ease: "easeOut" }}
                >
                  {isActive && (
                    <motion.span
                      initial={{ opacity: 0 }}
                      animate={{ opacity: 1 }}
                      className="whitespace-nowrap px-1.5 text-xs font-semibold text-white drop-shadow"
                    >
                      {stage.count}
                    </motion.span>
                  )}
                </motion.div>
              </div>

              <span
                className="w-10 shrink-0 text-left text-xs font-medium tabular-nums transition-opacity"
                style={{
                  color: "var(--color-text-secondary)",
                  opacity: isActive ? 1 : 0.55,
                }}
              >
                {stage.percent}%
              </span>
            </button>
          );
        })}
      </div>

      <div
        className="mt-4 flex items-center justify-between rounded-lg px-4 py-3"
        style={{ background: "var(--color-surface-2-val)" }}
      >
        <div>
          <p className="text-xs font-semibold uppercase tracking-wide" style={{ opacity: 0.6 }}>
            Selected
          </p>
          <p className="mt-1 font-heading text-2xl">
            <AnimatedNumber value={active?.count ?? 0} />
          </p>
          <p className="text-sm font-medium" style={{ color: "var(--color-text-primary)" }}>
            {active?.label ?? "—"}
          </p>
        </div>
        <div className="text-right">
          <p className="font-heading text-2xl">
            <AnimatedNumber value={active?.percent ?? 0} suffix="%" />
          </p>
          <p className="text-xs" style={{ opacity: 0.6 }}>
            of pipeline
          </p>
        </div>
      </div>
    </section>
  );
}
