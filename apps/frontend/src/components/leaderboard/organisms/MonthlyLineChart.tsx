"use client";

import { useRef } from "react";
import { motion, useInView } from "motion/react";
import { DASHBOARD_PANEL_CLASS } from "@/components/common/constants/dashboard-constants";
import { cn } from "@/lib/utils";
import { MOCK_RECRUITERS, MONTH_LABELS, type LeaderboardRecruiter } from "@/lib/leaderboard-data";

const CHART_COLORS = ["#F3FF54", "#3DDC97", "#60A5FA", "#F7C948", "#FB923C"];

/** Custom SVG multi-line chart — no external chart lib required. */
export function MonthlyLineChart({
  recruiters = MOCK_RECRUITERS,
  monthLabels = MONTH_LABELS,
}: {
  recruiters?: LeaderboardRecruiter[];
  monthLabels?: string[];
}) {
  const ref = useRef<HTMLElement>(null);
  const isInView = useInView(ref, { once: true, amount: 0.25 });

  // Top 5 recruiters
  const top5 = recruiters.slice(0, 5);

  const W = 600;
  const H = 220;
  const PAD = { t: 16, r: 20, b: 32, l: 36 };
  const iW = W - PAD.l - PAD.r;
  const iH = H - PAD.t - PAD.b;

  const allVals = top5.flatMap((r) => r.monthlyData);
  const maxVal = Math.max(...allVals, 1);
  const months = monthLabels.length;
  const stepX = iW / (months - 1);

  function toPoints(data: number[]) {
    return data
      .map((v, i) => {
        const x = PAD.l + i * stepX;
        const y = PAD.t + (1 - v / maxVal) * iH;
        return `${x},${y}`;
      })
      .join(" ");
  }

  const yTicks = [0, Math.round(maxVal * 0.5), maxVal];

  return (
    <motion.section
      ref={ref}
      initial={{ opacity: 0, y: 18 }}
      whileInView={{ opacity: 1, y: 0 }}
      viewport={{ once: true, amount: 0.25 }}
      transition={{ duration: 0.45, ease: "easeOut" }}
      className={cn(DASHBOARD_PANEL_CLASS, "p-5")}
    >
      <div className="flex items-start justify-between gap-3 mb-4">
        <div>
          <h2 className="font-heading text-xl text-white">Monthly Growth Trends</h2>
          <p className="mt-1 text-sm text-white/50">Top 5 recruiters — last 6 months</p>
        </div>
      </div>

      {/* Legend */}
      <div className="flex flex-wrap gap-3 mb-4">
        {top5.map((r, i) => (
          <div key={r.id} className="flex items-center gap-1.5">
            <span
              className="size-2 rounded-full inline-block"
              style={{ background: CHART_COLORS[i] }}
            />
            <span className="text-[10px] text-white/55">{r.name.split(" ")[0]}</span>
          </div>
        ))}
      </div>

      <div className="overflow-x-auto dashboard-scrollbar">
        <svg
          viewBox={`0 0 ${W} ${H}`}
          className="w-full min-w-[300px]"
          role="img"
          aria-label="Monthly recruiter growth chart"
        >
          <defs>
            {top5.map((_, i) => (
              <linearGradient key={i} id={`lg${i}`} x1="0" x2="0" y1="0" y2="1">
                <stop offset="0%" stopColor={CHART_COLORS[i]} stopOpacity="0.15" />
                <stop offset="100%" stopColor={CHART_COLORS[i]} stopOpacity="0" />
              </linearGradient>
            ))}
          </defs>

          {/* Grid */}
          {yTicks.map((v) => {
            const y = PAD.t + (1 - v / maxVal) * iH;
            return (
              <g key={v}>
                <line
                  x1={PAD.l}
                  x2={W - PAD.r}
                  y1={y}
                  y2={y}
                  stroke="rgba(255,255,255,0.06)"
                  strokeWidth="1"
                />
                <text
                  x={PAD.l - 6}
                  y={y + 4}
                  textAnchor="end"
                  fontSize="10"
                  fill="rgba(255,255,255,0.35)"
                >
                  {v}
                </text>
              </g>
            );
          })}

          {/* X labels */}
          {monthLabels.map((m, i) => (
            <text
              key={m}
              x={PAD.l + i * stepX}
              y={H - 6}
              textAnchor="middle"
              fontSize="10"
              fill="rgba(255,255,255,0.35)"
            >
              {m}
            </text>
          ))}

          {/* Lines */}
          {top5.map((r, i) => (
            <motion.polyline
              key={r.id}
              points={toPoints(r.monthlyData)}
              fill="none"
              stroke={CHART_COLORS[i]}
              strokeWidth="2.5"
              strokeLinecap="round"
              strokeLinejoin="round"
              initial={{ pathLength: 0, opacity: 0 }}
              animate={isInView ? { pathLength: 1, opacity: 1 } : {}}
              transition={{ duration: 0.9, delay: i * 0.12, ease: "easeOut" }}
            />
          ))}

          {/* Dots */}
          {top5.map((r, i) =>
            r.monthlyData.map((v, mi) => (
              <circle
                key={`${r.id}-${mi}`}
                cx={PAD.l + mi * stepX}
                cy={PAD.t + (1 - v / maxVal) * iH}
                r="3"
                fill={CHART_COLORS[i]}
                opacity="0.85"
              />
            )),
          )}
        </svg>
      </div>
    </motion.section>
  );
}
