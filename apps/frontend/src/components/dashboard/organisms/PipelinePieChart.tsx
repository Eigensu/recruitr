"use client";

import { useMemo, useRef, useState } from "react";
import { motion, useInView } from "motion/react";
import { IconChartPie } from "@tabler/icons-react";
import AnimatedNumber from "@/components/dashboard/atoms/AnimatedNumber";
import { DASHBOARD_PANEL_CLASS } from "@/components/common/constants/dashboard-constants";
import { cn } from "@/lib/utils";
import type { PipelineStageMetric } from "@/types/dashboard";

const segmentColors = [
  "#F3FF54",
  "#3DDC97",
  "#60A5FA",
  "#F7C948",
  "#FF8A8A",
  "#C084FC",
  "#FB923C",
  "#2DD4BF",
  "#FFFFFF",
  "#94A3B8",
];

interface PipelinePieChartProps {
  stages: PipelineStageMetric[];
}

export default function PipelinePieChart({ stages }: PipelinePieChartProps) {
  const chartRef = useRef<HTMLDivElement>(null);
  const isInView = useInView(chartRef, { once: true, amount: 0.42 });
  const [activeStage, setActiveStage] = useState(stages[0]?.stage);
  const total = stages.reduce((sum, stage) => sum + stage.count, 0);
  const active = stages.find((stage) => stage.stage === activeStage) ?? stages[0];

  const segments = useMemo(() => {
    const gap = 0.75;

    return stages.reduce(
      (acc, stage, index) => {
        const rawLength = total === 0 ? 0 : (stage.count / total) * 100;
        const length = Math.max(rawLength - gap, 0);
        const segment = {
          ...stage,
          color: segmentColors[index % segmentColors.length],
          dash: `${length} ${100 - length}`,
          offset: -acc.cursor,
        };

        return {
          cursor: acc.cursor + rawLength,
          items: [...acc.items, segment],
        };
      },
      {
        cursor: 0,
        items: [] as Array<
          PipelineStageMetric & {
            color: string;
            dash: string;
            offset: number;
          }
        >,
      },
    ).items;
  }, [stages, total]);

  return (
    <section ref={chartRef} className={cn(DASHBOARD_PANEL_CLASS, "flex h-full flex-col p-5")}>
      <div className="flex items-start justify-between gap-3">
        <div>
          <h2 className="font-heading text-xl text-white">Pipeline Pie Chart</h2>
          <p className="mt-1 text-sm text-white">Interactive share of pipeline stages</p>
        </div>
        <IconChartPie className="size-6 text-yellow" />
      </div>

      <div className="mt-4 flex flex-1 items-center justify-center">
        <motion.div
          initial={{ opacity: 0, scale: 0.94 }}
          animate={isInView ? { opacity: 1, scale: 1 } : { opacity: 0, scale: 0.94 }}
          transition={{ duration: 0.45, ease: "easeOut" }}
          className="relative mx-auto aspect-square w-full max-w-[24rem]"
        >
          <svg viewBox="0 0 120 120" className="size-full -rotate-90 drop-shadow-lg">
            <circle
              cx="60"
              cy="60"
              r="45"
              fill="none"
              stroke="rgba(255,255,255,0.08)"
              strokeWidth="17"
            />
            {segments.map((segment, index) => {
              const isActive = segment.stage === activeStage;

              return (
                <motion.circle
                  key={segment.stage}
                  cx="60"
                  cy="60"
                  r="45"
                  fill="none"
                  stroke={segment.color}
                  strokeWidth="17"
                  strokeLinecap="butt"
                  pathLength={100}
                  strokeDashoffset={segment.offset}
                  initial={{ strokeDasharray: "0 100", opacity: 0 }}
                  animate={
                    isInView
                      ? { strokeDasharray: segment.dash, opacity: isActive ? 1 : 0.78 }
                      : { strokeDasharray: "0 100", opacity: 0 }
                  }
                  transition={{ duration: 0.72, delay: index * 0.08, ease: "easeOut" }}
                  onMouseEnter={() => setActiveStage(segment.stage)}
                  onFocus={() => setActiveStage(segment.stage)}
                  tabIndex={0}
                  role="img"
                  aria-label={`${segment.label}: ${segment.count} candidates, ${segment.percent}% of pipeline`}
                  className="cursor-pointer outline-none transition-opacity"
                />
              );
            })}
          </svg>

          <div className="absolute inset-10 flex flex-col items-center justify-center rounded-full border border-white/10 bg-[#111827] p-5 text-center shadow-inner shadow-black/50">
            <p className="text-xs font-semibold uppercase tracking-normal text-white">Selected</p>
            <p className="mt-2 font-heading text-3xl text-white">
              <AnimatedNumber value={active?.count ?? total} />
            </p>
            <p className="mt-1 text-sm text-yellow">{active?.label ?? "All stages"}</p>
            <p className="mt-1 text-xs text-white">
              <AnimatedNumber value={active?.percent ?? 100} suffix="%" /> of pipeline
            </p>
          </div>
        </motion.div>
      </div>

      <div className="mt-5 border-t border-white/10 pt-4">
        <p className="text-xs leading-relaxed text-white">
          <span className="text-white">Pipeline Overview:</span> Your recruitment pipeline is
          distributed across {stages.length} stages. The largest concentration is in{" "}
          {segments[0]?.label}, which represents{" "}
          <span className="font-semibold text-white">
            {segments[0]?.percent}% of total candidates
          </span>
          . Monitor stage progression to identify potential bottlenecks and optimize time-to-hire.
        </p>
      </div>
    </section>
  );
}
