"use client";

import { useMemo, useRef, useState } from "react";
import { motion, useInView } from "motion/react";
import { IconChartLine } from "@tabler/icons-react";
import { DASHBOARD_PANEL_CLASS } from "@/components/common/constants/dashboard-constants";
import { cn } from "@/lib/utils";
import type { RecruiterDashboardStat } from "@/types/dashboard";

interface RecruiterLineGraphProps {
  recruiters: RecruiterDashboardStat[];
}

type ChartPoint = {
  recruiter: RecruiterDashboardStat;
  x: number;
  y: number;
};

export default function RecruiterLineGraph({ recruiters }: Readonly<RecruiterLineGraphProps>) {
  const graphRef = useRef<HTMLElement>(null);
  const isInView = useInView(graphRef, { once: true, amount: 0.28 });
  const defaultRecruiter = recruiters[0]?.name ?? "";
  const [activeRecruiter, setActiveRecruiter] = useState(defaultRecruiter);
  const [tooltip, setTooltip] = useState<{ x: number; y: number; visible: boolean }>({
    x: 0,
    y: 0,
    visible: false,
  });

  const chart = useMemo(() => {
    const width = 760;
    const height = 360;
    const padding = { top: 10, right: 104, bottom: 42, left: 104 };
    const innerWidth = width - padding.left - padding.right;
    const innerHeight = height - padding.top - padding.bottom;

    const rawValues = recruiters.map((r) => r.inPipeline);
    const rawMax = Math.max(...rawValues, 1);
    const rawMin = Math.min(...rawValues, 0);
    const domainPadding = Math.max(Math.round((rawMax - rawMin) * 0.05), 0);
    const domainMin = Math.max(rawMin - domainPadding, 0);
    const domainMax = rawMax + domainPadding;
    const domainSpan = Math.max(domainMax - domainMin, 1);
    const stepX = recruiters.length > 1 ? innerWidth / (recruiters.length - 1) : 0;

    const points: ChartPoint[] = recruiters.map((recruiter, index) => {
      const normalized = Math.min(Math.max((recruiter.inPipeline - domainMin) / domainSpan, 0), 1);
      const x = padding.left + index * stepX;
      const y = padding.top + (1 - normalized) * innerHeight;
      return { recruiter, x, y };
    });

    const polyline = points.map((p) => `${p.x},${p.y}`).join(" ");

    const ticks = 4;
    const yTicks = Array.from({ length: ticks + 1 }, (_, idx) => {
      const value = Math.round(domainMin + (domainSpan * idx) / ticks);
      const y = padding.top + (1 - idx / ticks) * innerHeight;
      return { value, y };
    });

    return {
      width,
      height,
      padding,
      innerWidth,
      innerHeight,
      domainMin,
      domainMax,
      points,
      polyline,
      yTicks,
    };
  }, [recruiters]);

  if (!recruiters.length) {
    return (
      <section
        ref={graphRef}
        className={cn(DASHBOARD_PANEL_CLASS, "flex h-full flex-col p-5")}
        style={{ color: "var(--color-text-primary)" }}
      >
        <div className="flex items-start justify-between gap-3">
          <div>
            <h2 className="font-heading text-xl">Recruiter Line Graph</h2>
            <p className="mt-1 text-sm" style={{ opacity: 0.6 }}>
              Pipeline load by recruiter
            </p>
          </div>
          <IconChartLine className="size-6 text-yellow" />
        </div>
        <div className="flex flex-1 items-center justify-center">
          <p className="text-sm" style={{ opacity: 0.5 }}>
            No recruiter pipeline data available.
          </p>
        </div>
      </section>
    );
  }

  const active = recruiters.find((r) => r.name === activeRecruiter) ?? recruiters[0];
  const activePoint =
    chart.points.find((p) => p.recruiter.name === activeRecruiter) ?? chart.points[0];

  return (
    <motion.section
      ref={graphRef}
      initial={{ opacity: 0, y: 18 }}
      whileInView={{ opacity: 1, y: 0 }}
      viewport={{ once: true, amount: 0.25 }}
      transition={{ duration: 0.45, ease: "easeOut" }}
      className={cn(DASHBOARD_PANEL_CLASS, "flex h-full flex-col p-5")}
      style={{ color: "var(--color-text-primary)" }}
    >
      <div className="flex items-start justify-between gap-3">
        <div>
          <h2 className="font-heading text-xl">Recruiter Line Graph</h2>
          <p className="mt-1 text-sm" style={{ opacity: 0.6 }}>
            Pipeline load by recruiter
          </p>
        </div>
        <IconChartLine className="size-6 text-yellow" />
      </div>

      <div
        className="relative mt-4 flex flex-1 flex-col overflow-hidden rounded-lg"
        style={{ background: "var(--color-surface-val)" }}
        onMouseLeave={() => setTooltip((prev) => ({ ...prev, visible: false }))}
      >
        {tooltip.visible && active ? (
          <div
            className="pointer-events-none absolute z-10 w-55 -translate-x-1/2 rounded-md p-2.5 shadow-lg shadow-black/30 backdrop-blur"
            style={{
              left: tooltip.x,
              top: Math.max(tooltip.y - 10, 8),
              background: "var(--color-surface-2-val)",
              color: "var(--color-text-primary)",
            }}
            role="status"
            aria-live="polite"
          >
            <p className="text-xs font-semibold uppercase tracking-normal">{active.focus}</p>
            <p className="mt-0.5 text-sm font-semibold">{active.name}</p>
            <div className="mt-2 grid grid-cols-3 gap-1.5">
              {[
                {
                  label: "Pipeline",
                  value: (
                    <span
                      className="mt-0.5 font-heading text-sm font-bold"
                      style={{ color: "var(--color-chart-line-val)" }}
                    >
                      {active.inPipeline}
                    </span>
                  ),
                },
                {
                  label: "Joined",
                  value: <span className="mt-0.5 text-sm font-semibold">{active.joined}</span>,
                },
                {
                  label: "Seats",
                  value: <span className="mt-0.5 text-sm font-semibold">{active.openSeats}</span>,
                },
              ].map(({ label, value }) => (
                <div
                  key={label}
                  className="rounded-md px-1.5 py-1"
                  style={{ background: "var(--color-border-val)" }}
                >
                  <p
                    className="text-[9px] font-semibold uppercase tracking-normal"
                    style={{ opacity: 0.6 }}
                  >
                    {label}
                  </p>
                  {value}
                </div>
              ))}
            </div>
          </div>
        ) : null}

        <div className="flex flex-1 min-h-0 flex-col">
          <svg
            viewBox={`0 0 ${chart.width} ${chart.height}`}
            className="h-full w-full flex-1"
            role="img"
            aria-label="Line graph of pipeline by recruiter"
          >
            <defs>
              <linearGradient id="recruiterLine" x1="0" x2="0" y1="0" y2="1">
                <stop
                  offset="0%"
                  style={{ stopColor: "var(--color-chart-line-val)", stopOpacity: 0.9 }}
                />
                <stop
                  offset="100%"
                  style={{ stopColor: "var(--color-chart-line-val)", stopOpacity: 0.15 }}
                />
              </linearGradient>
            </defs>

            {chart.yTicks.map((tick, i) => (
              <g key={`ytick-${i}`}>
                <line
                  x1={chart.padding.left}
                  x2={chart.width - chart.padding.right}
                  y1={tick.y}
                  y2={tick.y}
                  stroke="var(--color-border-val)"
                  strokeWidth="1"
                />
                <text
                  x={chart.padding.left - 10}
                  y={tick.y + 5}
                  textAnchor="end"
                  fontSize="16"
                  fill="currentColor"
                  opacity="0.4"
                >
                  {tick.value}
                </text>
              </g>
            ))}

            <motion.polyline
              points={chart.polyline}
              fill="none"
              stroke="url(#recruiterLine)"
              strokeWidth="4.5"
              strokeLinejoin="round"
              strokeLinecap="round"
              initial={{ pathLength: 0, opacity: 0 }}
              animate={isInView ? { pathLength: 1, opacity: 1 } : { pathLength: 0, opacity: 0 }}
              transition={{ duration: 0.9, ease: "easeOut" }}
            />

            <motion.path
              d={`M ${chart.polyline} L ${chart.width - chart.padding.right},${chart.height - chart.padding.bottom} L ${chart.padding.left},${chart.height - chart.padding.bottom} Z`}
              style={{ fill: "var(--color-chart-line-val)" }}
              fillOpacity={0.08}
              initial={{ opacity: 0 }}
              animate={isInView ? { opacity: 1 } : { opacity: 0 }}
              transition={{ duration: 0.6, delay: 0.2 }}
            />

            {activePoint && (
              <g>
                <line
                  x1={activePoint.x}
                  x2={activePoint.x}
                  y1={chart.padding.top}
                  y2={chart.height - chart.padding.bottom}
                  style={{ stroke: "var(--color-chart-line-val)" }}
                  strokeOpacity={0.3}
                  strokeWidth="1"
                  strokeDasharray="4 3"
                />
                <circle
                  cx={activePoint.x}
                  cy={activePoint.y}
                  r={11}
                  style={{ fill: "var(--color-chart-line-val)" }}
                  fillOpacity={0.18}
                />
              </g>
            )}

            {chart.points.map((point, index) => {
              const isActive = point.recruiter.name === activeRecruiter;
              return (
                <g key={`${point.recruiter.name}-${index}`}>
                  <circle
                    cx={point.x}
                    cy={point.y}
                    r={isActive ? 9 : 6.5}
                    style={{
                      fill: isActive ? "var(--color-chart-line-val)" : "var(--color-chart-dot-val)",
                      stroke: isActive ? "var(--color-chart-line-val)" : "var(--color-border-val)",
                    }}
                    strokeWidth="2"
                    className="cursor-pointer"
                    onMouseEnter={(e) => {
                      const box = (
                        e.currentTarget.ownerSVGElement as SVGSVGElement | null
                      )?.getBoundingClientRect();
                      setActiveRecruiter(point.recruiter.name);
                      setTooltip({
                        x: box ? e.clientX - box.left : 0,
                        y: box ? e.clientY - box.top : 0,
                        visible: true,
                      });
                    }}
                    onMouseMove={(e) => {
                      const box = (
                        e.currentTarget.ownerSVGElement as SVGSVGElement | null
                      )?.getBoundingClientRect();
                      setTooltip((prev) => ({
                        x: box ? e.clientX - box.left : prev.x,
                        y: box ? e.clientY - box.top : prev.y,
                        visible: true,
                      }));
                    }}
                    onFocus={(e) => {
                      setActiveRecruiter(point.recruiter.name);
                      const svg = e.currentTarget.ownerSVGElement as SVGSVGElement | null;
                      if (svg) {
                        const box = svg.getBoundingClientRect();
                        const ctm = svg.getScreenCTM();
                        if (ctm) {
                          const svgPoint = svg.createSVGPoint();
                          svgPoint.x = point.x;
                          svgPoint.y = point.y;
                          const screenPoint = svgPoint.matrixTransform(ctm);
                          setTooltip({
                            x: screenPoint.x - box.left,
                            y: screenPoint.y - box.top,
                            visible: true,
                          });
                          return;
                        }
                      }
                      setTooltip({ x: point.x, y: point.y, visible: true });
                    }}
                    tabIndex={0}
                    role="button"
                    aria-label={`${point.recruiter.name}: ${point.recruiter.inPipeline} in pipeline`}
                  />
                </g>
              );
            })}

            {chart.points.map((point, idx) => {
              const showLabel =
                recruiters.length <= 8 ||
                idx === 0 ||
                idx === recruiters.length - 1 ||
                idx % 2 === 0;
              if (!showLabel) return null;
              return (
                <text
                  key={`label-${idx}`}
                  x={point.x}
                  y={chart.height - 10}
                  textAnchor="middle"
                  fontSize="21"
                  fill="currentColor"
                  opacity="0.4"
                >
                  {point.recruiter.name.split(" ")[0]}
                </text>
              );
            })}
          </svg>

          <p className="mt-2 text-[10px] leading-none" style={{ opacity: 0.5 }}>
            Hover a point to see recruiter stats.
          </p>
        </div>
      </div>

      <div
        className="mt-5 rounded-lg px-4 py-3"
        style={{ background: "var(--color-surface-2-val)" }}
      >
        <p className="text-xs leading-relaxed" style={{ color: "var(--color-text-secondary)" }}>
          <span className="font-semibold" style={{ color: "var(--color-text-primary)" }}>
            {"Recruiter Performance: "}
          </span>
          {
            "The line graph shows pipeline volume per recruiter. Recruiters with higher peaks are managing larger candidate pools. Consistent high values indicate sustained activity, while fluctuations may suggest seasonal hiring patterns or workload redistribution."
          }
        </p>
      </div>
    </motion.section>
  );
}
