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

export default function RecruiterLineGraph({ recruiters }: RecruiterLineGraphProps) {
  const graphRef = useRef<HTMLElement>(null);
  const isInView = useInView(graphRef, { once: true, amount: 0.28 });
  const [activeRecruiter, setActiveRecruiter] = useState(recruiters[0]?.name);
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

    const rawValues = recruiters.map((recruiter) => recruiter.inPipeline);
    const rawMax = Math.max(...rawValues, 1);
    const rawMin = Math.min(...rawValues, 0);
    // Fit domain tightly to the data so the line uses most of the height.
    // Add a tiny padding only to avoid points touching the border.
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

  const active =
    recruiters.find((recruiter) => recruiter.name === activeRecruiter) ?? recruiters[0];
  const activePoint =
    chart.points.find((point) => point.recruiter.name === activeRecruiter) ?? chart.points[0];

  return (
    <motion.section
      ref={graphRef}
      initial={{ opacity: 0, y: 18 }}
      whileInView={{ opacity: 1, y: 0 }}
      viewport={{ once: true, amount: 0.25 }}
      transition={{ duration: 0.45, ease: "easeOut" }}
      className={cn(DASHBOARD_PANEL_CLASS, "flex h-full flex-col p-5")}
    >
      <div className="flex items-start justify-between gap-3">
        <div>
          <h2 className="font-heading text-xl text-white">Recruiter Line Graph</h2>
          <p className="mt-1 text-sm text-white">Pipeline load by recruiter</p>
        </div>
        <IconChartLine className="size-6 text-yellow" />
      </div>

      <div
        className="relative mt-4 flex flex-1 flex-col overflow-hidden rounded-lg border border-white/10 bg-white/3"
        onMouseLeave={() => setTooltip((prev) => ({ ...prev, visible: false }))}
      >
        {tooltip.visible && active ? (
          <div
            className="pointer-events-none absolute z-10 w-55 -translate-x-1/2 rounded-md border border-white/10 bg-[#0b1220]/95 p-2.5 shadow-lg shadow-black/30 backdrop-blur"
            style={{
              left: tooltip.x,
              top: Math.max(tooltip.y - 10, 8),
            }}
            role="status"
            aria-live="polite"
          >
            <p className="text-xs font-semibold uppercase tracking-normal text-white">
              {active.focus}
            </p>
            <p className="mt-0.5 text-sm font-semibold text-white">{active.name}</p>
            <div className="mt-2 grid grid-cols-3 gap-1.5">
              <div className="rounded-md border border-white/10 bg-white/3 px-1.5 py-1">
                <p className="text-[9px] font-semibold uppercase tracking-normal text-white">
                  Pipeline
                </p>
                <p className="mt-0.5 font-heading text-sm text-yellow">{active.inPipeline}</p>
              </div>
              <div className="rounded-md border border-white/10 bg-white/3 px-1.5 py-1">
                <p className="text-[9px] font-semibold uppercase tracking-normal text-white">
                  Joined
                </p>
                <p className="mt-0.5 text-sm font-semibold text-white">{active.joined}</p>
              </div>
              <div className="rounded-md border border-white/10 bg-white/3 px-1.5 py-1">
                <p className="text-[9px] font-semibold uppercase tracking-normal text-white">
                  Seats
                </p>
                <p className="mt-0.5 text-sm font-semibold text-white">{active.openSeats}</p>
              </div>
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
                <stop offset="0%" stopColor="#F3FF54" stopOpacity="0.95" />
                <stop offset="100%" stopColor="#F3FF54" stopOpacity="0.25" />
              </linearGradient>
            </defs>

            {chart.yTicks.map((tick) => (
              <g key={tick.value}>
                <line
                  x1={chart.padding.left}
                  x2={chart.width - chart.padding.right}
                  y1={tick.y}
                  y2={tick.y}
                  stroke="rgba(255,255,255,0.08)"
                  strokeWidth="1"
                />
                <text
                  x={chart.padding.left - 10}
                  y={tick.y + 5}
                  textAnchor="end"
                  fontSize="16"
                  fill="rgba(255,255,255,0.5)"
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
              fill="rgba(243,255,84,0.09)"
              initial={{ opacity: 0 }}
              animate={isInView ? { opacity: 1 } : { opacity: 0 }}
              transition={{ duration: 0.6, delay: 0.2 }}
            />

            {activePoint ? (
              <g>
                <line
                  x1={activePoint.x}
                  x2={activePoint.x}
                  y1={chart.padding.top}
                  y2={chart.height - chart.padding.bottom}
                  stroke="rgba(243,255,84,0.26)"
                  strokeWidth="1"
                />
                <circle cx={activePoint.x} cy={activePoint.y} r={11} fill="rgba(243,255,84,0.16)" />
              </g>
            ) : null}

            {chart.points.map((point) => {
              const isActive = point.recruiter.name === activeRecruiter;
              return (
                <g key={point.recruiter.name}>
                  <circle
                    cx={point.x}
                    cy={point.y}
                    r={isActive ? 9 : 6.5}
                    fill={isActive ? "#F3FF54" : "rgba(255,255,255,0.65)"}
                    stroke={isActive ? "rgba(0,0,0,0.35)" : "rgba(0,0,0,0.25)"}
                    strokeWidth="2"
                    className="cursor-pointer"
                    onMouseEnter={(event) => {
                      const box = (
                        event.currentTarget.ownerSVGElement as SVGSVGElement | null
                      )?.getBoundingClientRect();
                      setActiveRecruiter(point.recruiter.name);
                      setTooltip({
                        x: box ? event.clientX - box.left : 0,
                        y: box ? event.clientY - box.top : 0,
                        visible: true,
                      });
                    }}
                    onMouseMove={(event) => {
                      const box = (
                        event.currentTarget.ownerSVGElement as SVGSVGElement | null
                      )?.getBoundingClientRect();
                      setTooltip((prev) => ({
                        x: box ? event.clientX - box.left : prev.x,
                        y: box ? event.clientY - box.top : prev.y,
                        visible: true,
                      }));
                    }}
                    onFocus={() => {
                      setActiveRecruiter(point.recruiter.name);
                      setTooltip({
                        x: point.x,
                        y: point.y,
                        visible: true,
                      });
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
                  key={`${point.recruiter.name}-${idx}`}
                  x={point.x}
                  y={chart.height - 10}
                  textAnchor="middle"
                  fontSize="21"
                  fill="rgba(255,255,255,0.42)"
                >
                  {point.recruiter.name.length > 10
                    ? `${point.recruiter.name.slice(0, 10)}…`
                    : point.recruiter.name}
                </text>
              );
            })}
          </svg>

          <p className="mt-2 text-[10px] leading-none text-white">
            Hover a point to see recruiter stats.
          </p>
        </div>
      </div>

      <div className="mt-5 border-t border-white/10 pt-4">
        <p className="text-xs leading-relaxed text-white">
          <span className="text-white">Recruiter Performance:</span> The line graph shows pipeline
          volume per recruiter. Recruiters with higher peaks are managing larger candidate pools.
          Consistent high values indicate sustained activity, while fluctuations may suggest
          seasonal hiring patterns or workload redistribution across your team.
        </p>
      </div>
    </motion.section>
  );
}
