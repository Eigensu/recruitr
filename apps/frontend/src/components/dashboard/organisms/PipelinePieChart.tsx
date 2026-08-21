"use client";

import { useEffect, useRef, useState } from "react";
import { motion, useInView, useReducedMotion } from "motion/react";
import { IconChartFunnel } from "@tabler/icons-react";
import { DASHBOARD_PANEL_CLASS } from "@/components/common/constants/dashboard-constants";
import { clientFetchDashboardPipeline } from "@/lib/api/dashboard.client";
import {
  buildPipelineStages,
  formatPipelinePercent,
  FUNNEL_GROUPS,
  PIPELINE_FUNNEL_ORDER,
  PIPELINE_STAGE_COLORS,
} from "@/lib/pipeline-funnel";
import type { RecruiterOption } from "@/lib/pipeline-funnel";
import { cn } from "@/lib/utils";
import type { PipelineStageMetric } from "@/types/dashboard";

interface PipelinePieChartProps {
  stages: PipelineStageMetric[];
  /** Populates the recruiter filter; omit to render the funnel unfiltered. */
  recruiters?: RecruiterOption[];
}

/** Stages fetched for one recruiter, tagged with whose they are. */
interface AppliedFilter {
  recruiterId: string;
  stages: PipelineStageMetric[];
}

const SELECT_STYLE = {
  background: "var(--color-canvas-val)",
  color: "var(--color-text-primary)",
  border: "1px solid var(--color-border-val)",
};

function GroupHeading({ label }: Readonly<{ label: string }>) {
  return (
    <div className="flex items-center gap-2">
      <span
        className="text-[10px] font-semibold uppercase tracking-[0.16em]"
        style={{ color: "var(--color-text-secondary)" }}
      >
        {label}
      </span>
      <span
        className="h-px flex-1"
        style={{ background: "color-mix(in srgb, currentColor 12%, transparent)" }}
      />
    </div>
  );
}

function StageRow({
  stage,
  widthPct,
  animate,
  delay,
}: Readonly<{
  stage: PipelineStageMetric;
  widthPct: number;
  animate: boolean;
  delay: number;
}>) {
  const isEmpty = stage.count === 0;

  return (
    <li className="flex flex-col gap-1.5">
      <div className="flex items-baseline justify-between gap-2">
        <span
          className="truncate text-[13px]"
          style={{ color: isEmpty ? "var(--color-text-secondary)" : "var(--color-text-primary)" }}
        >
          {stage.label}
        </span>
        <span className="flex shrink-0 items-baseline gap-2 tabular-nums">
          <span
            className="text-sm font-semibold"
            style={{ color: isEmpty ? "var(--color-text-secondary)" : "var(--color-text-primary)" }}
          >
            {stage.count}
          </span>
          <span
            className="w-9 text-right text-[11px]"
            style={{ color: "var(--color-text-secondary)" }}
          >
            {formatPipelinePercent(stage.percent)}
          </span>
        </span>
      </div>

      <div
        aria-hidden="true"
        className="h-2 w-full overflow-hidden rounded-full"
        style={{ background: "color-mix(in srgb, currentColor 9%, transparent)" }}
      >
        <motion.div
          className="h-full rounded-full"
          style={{ background: PIPELINE_STAGE_COLORS[stage.stage] }}
          initial={{ width: 0 }}
          animate={{ width: animate ? `${widthPct}%` : 0 }}
          transition={{ duration: 0.5, delay, ease: "easeOut" }}
        />
      </div>
    </li>
  );
}

export default function PipelinePieChart({
  stages: initialStages,
  recruiters = [],
}: Readonly<PipelinePieChartProps>) {
  const chartRef = useRef<HTMLDivElement>(null);
  const isInView = useInView(chartRef, { once: true, amount: 0.3 });
  const prefersReducedMotion = useReducedMotion();
  const requestRef = useRef<AbortController | null>(null);
  const [applied, setApplied] = useState<AppliedFilter | null>(null);
  const [recruiterId, setRecruiterId] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [loadFailed, setLoadFailed] = useState(false);

  // Only ever render numbers we know belong to the current selection: a
  // pending or failed request falls back to the unfiltered server data rather
  // than leaving the previous recruiter's funnel under someone else's name.
  // The subtitle says which of the two is on screen.
  const showingFiltered = applied !== null && applied.recruiterId === recruiterId;
  const stages = showingFiltered ? applied.stages : initialStages;
  const subtitle = showingFiltered
    ? `Candidate flow for ${recruiters.find((r) => r.id === recruiterId)?.name ?? "this recruiter"}`
    : "Candidate flow across all recruiters";

  useEffect(() => () => requestRef.current?.abort(), []);

  function handleRecruiterChange(nextId: string) {
    requestRef.current?.abort();
    setRecruiterId(nextId);
    setLoadFailed(false);

    if (!nextId) {
      requestRef.current = null;
      setApplied(null);
      setIsLoading(false);
      return;
    }

    const controller = new AbortController();
    requestRef.current = controller;
    setIsLoading(true);

    clientFetchDashboardPipeline(nextId, controller.signal)
      .then((response) => {
        if (!controller.signal.aborted) {
          setApplied({ recruiterId: nextId, stages: buildPipelineStages(response.stages) });
        }
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

  const byStage = new Map(stages.map((stage) => [stage.stage, stage]));
  const total = stages.reduce((sum, stage) => sum + stage.count, 0);
  // Bars are scaled against the busiest stage, so the widest one always fills
  // the track and the small ones stay legible next to it.
  const maxCount = stages.reduce((max, stage) => Math.max(max, stage.count), 1);
  const shouldAnimate = isInView && !prefersReducedMotion;
  const rowOrder = new Map(PIPELINE_FUNNEL_ORDER.map((stage, index) => [stage, index]));

  return (
    <section
      ref={chartRef}
      className={cn(DASHBOARD_PANEL_CLASS, "flex h-full flex-col p-5")}
      style={{ color: "var(--color-text-primary)" }}
    >
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <h2 className="font-heading text-xl">Pipeline Funnel</h2>
          <p className="mt-1 truncate text-sm" style={{ color: "var(--color-text-secondary)" }}>
            {subtitle}
          </p>
        </div>
        <IconChartFunnel className="size-6 shrink-0 text-yellow" />
      </div>

      <div
        className={cn(
          "mt-4 flex flex-wrap items-center gap-2",
          recruiters.length > 0 ? "justify-between" : "justify-end",
        )}
      >
        {recruiters.length > 0 && (
          <select
            value={recruiterId}
            onChange={(event) => handleRecruiterChange(event.target.value)}
            className="min-w-0 max-w-full rounded-lg px-2 py-1.5 text-xs"
            style={SELECT_STYLE}
            aria-label="Filter pipeline funnel by recruiter"
          >
            <option value="">All recruiters</option>
            {recruiters.map((recruiter) => (
              <option key={recruiter.id} value={recruiter.id}>
                {recruiter.name}
              </option>
            ))}
          </select>
        )}
        <p className="text-xs tabular-nums" style={{ color: "var(--color-text-secondary)" }}>
          <span className="font-semibold" style={{ color: "var(--color-text-primary)" }}>
            {total}
          </span>{" "}
          {total === 1 ? "candidate" : "candidates"}
        </p>
      </div>

      {loadFailed && (
        <p className="mt-3 text-xs" style={{ color: "var(--color-card-negative-text)" }}>
          Couldn&apos;t load this recruiter&apos;s funnel — showing every recruiter instead.
        </p>
      )}

      {total === 0 ? (
        <div className="flex flex-1 items-center justify-center py-8">
          <p className="text-sm" style={{ color: "var(--color-text-secondary)" }}>
            No candidates mapped to a stage yet.
          </p>
        </div>
      ) : (
        <div
          className="mt-5 flex flex-1 flex-col justify-between gap-5 transition-opacity"
          style={{ opacity: isLoading ? 0.45 : 1 }}
          aria-busy={isLoading}
        >
          {FUNNEL_GROUPS.map((group) => (
            <div key={group.id} className="flex flex-col gap-3">
              <GroupHeading label={group.label} />
              <ul className="flex flex-col gap-3">
                {group.stages.map((stageId) => {
                  const stage = byStage.get(stageId);
                  if (!stage) return null;
                  return (
                    <StageRow
                      key={stageId}
                      stage={stage}
                      widthPct={(stage.count / maxCount) * 100}
                      animate={shouldAnimate}
                      delay={(rowOrder.get(stageId) ?? 0) * 0.05}
                    />
                  );
                })}
              </ul>
            </div>
          ))}
        </div>
      )}
    </section>
  );
}
