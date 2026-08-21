"use client";

import { useEffect, useRef, useState } from "react";
import { motion, useInView } from "motion/react";
import { IconChartFunnel } from "@tabler/icons-react";
import AnimatedNumber from "@/components/dashboard/atoms/AnimatedNumber";
import { DASHBOARD_PANEL_CLASS } from "@/components/common/constants/dashboard-constants";
import { clientFetchDashboardPipeline } from "@/lib/api/dashboard.client";
import { buildPipelineStages, PIPELINE_STAGE_COLORS } from "@/lib/pipeline-funnel";
import type { RecruiterOption } from "@/lib/pipeline-funnel";
import { cn } from "@/lib/utils";
import type { PipelineStageMetric } from "@/types/dashboard";

interface PipelinePieChartProps {
  stages: PipelineStageMetric[];
  /** Populates the recruiter filter; omit to render the funnel unfiltered. */
  recruiters?: RecruiterOption[];
}

const SELECT_STYLE = {
  background: "var(--color-canvas-val)",
  color: "var(--color-text-primary)",
  border: "1px solid var(--color-border-val)",
};

function FunnelShell({
  children,
  chartRef,
  filter,
}: Readonly<{
  children: React.ReactNode;
  chartRef: React.Ref<HTMLDivElement>;
  filter?: React.ReactNode;
}>) {
  return (
    <section
      ref={chartRef}
      className={cn(DASHBOARD_PANEL_CLASS, "flex h-full flex-col p-5")}
      style={{ color: "var(--color-text-primary)" }}
    >
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h2 className="font-heading text-xl" style={{ color: "var(--color-text-primary)" }}>
            Pipeline Funnel
          </h2>
          <p className="mt-1 text-sm" style={{ color: "var(--color-text-secondary)" }}>
            Candidate flow through pipeline stages
          </p>
        </div>
        <div className="flex items-center gap-2">
          {filter}
          <IconChartFunnel className="size-6 shrink-0 text-yellow" />
        </div>
      </div>
      {children}
    </section>
  );
}

export default function PipelinePieChart({
  stages: initialStages,
  recruiters = [],
}: Readonly<PipelinePieChartProps>) {
  const chartRef = useRef<HTMLDivElement>(null);
  const isInView = useInView(chartRef, { once: true, amount: 0.42 });
  const requestRef = useRef<AbortController | null>(null);
  const [filteredStages, setFilteredStages] = useState<PipelineStageMetric[] | null>(null);
  const [activeStage, setActiveStage] = useState(initialStages[0]?.stage);
  const [recruiterId, setRecruiterId] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [loadFailed, setLoadFailed] = useState(false);

  // The server-rendered props stand until a recruiter is picked, and again the
  // moment the filter is cleared.
  const stages = recruiterId && filteredStages ? filteredStages : initialStages;

  useEffect(() => () => requestRef.current?.abort(), []);

  function handleRecruiterChange(nextId: string) {
    requestRef.current?.abort();
    setRecruiterId(nextId);
    setLoadFailed(false);

    if (!nextId) {
      requestRef.current = null;
      setFilteredStages(null);
      setIsLoading(false);
      return;
    }

    const controller = new AbortController();
    requestRef.current = controller;
    setIsLoading(true);

    clientFetchDashboardPipeline(nextId, controller.signal)
      .then((response) => {
        if (!controller.signal.aborted) setFilteredStages(buildPipelineStages(response.stages));
      })
      .catch((error: unknown) => {
        if (controller.signal.aborted) return;
        console.error("Failed to filter the pipeline funnel by recruiter:", error);
        setLoadFailed(true);
      })
      .finally(() => {
        if (!controller.signal.aborted) setIsLoading(false);
      });
  }

  const filter =
    recruiters.length > 0 ? (
      <select
        value={recruiterId}
        onChange={(event) => handleRecruiterChange(event.target.value)}
        className="max-w-40 rounded-lg px-2 py-1.5 text-xs outline-none"
        style={SELECT_STYLE}
        aria-label="Filter pipeline funnel by recruiter"
      >
        <option value="">All Recruiters</option>
        {recruiters.map((recruiter) => (
          <option key={recruiter.id} value={recruiter.id}>
            {recruiter.name}
          </option>
        ))}
      </select>
    ) : null;

  const maxCount = stages.reduce((max, s) => Math.max(max, s.count), 1);
  const active = stages.find((stage) => stage.stage === activeStage) ?? stages[0];

  if (!stages.length) {
    return (
      <FunnelShell chartRef={chartRef} filter={filter}>
        <div className="flex flex-1 items-center justify-center">
          <p className="text-sm" style={{ opacity: 0.5 }}>
            No pipeline data available.
          </p>
        </div>
      </FunnelShell>
    );
  }

  return (
    <FunnelShell chartRef={chartRef} filter={filter}>
      {loadFailed && (
        <p className="mt-3 text-xs" style={{ color: "var(--color-card-negative-text)" }}>
          Couldn&apos;t load this recruiter&apos;s funnel. Showing the last loaded numbers.
        </p>
      )}

      <div
        className="mt-4 flex flex-1 flex-col justify-center gap-1.5 transition-opacity"
        style={{ opacity: isLoading ? 0.45 : 1 }}
        aria-busy={isLoading}
      >
        {stages.map((stage, index) => {
          const widthPct = (stage.count / maxCount) * 100;
          const color = PIPELINE_STAGE_COLORS[stage.stage];
          const isActive = stage.stage === activeStage;

          return (
            <button
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
    </FunnelShell>
  );
}
