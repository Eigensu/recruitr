"use client";

import { useRef } from "react";
import { motion, useInView } from "motion/react";
import { DASHBOARD_PANEL_CLASS } from "@/components/common/constants/dashboard-constants";
import { cn } from "@/lib/utils";
import { MOCK_RECRUITERS } from "@/lib/leaderboard-data";

const BAR_COLORS = [
  "#F3FF54",
  "#3DDC97",
  "#60A5FA",
  "#F7C948",
  "#FB923C",
  "#C084FC",
  "#2DD4BF",
  "#FF8A8A",
  "#94A3B8",
  "#6B7280",
];

/** Custom SVG bar chart comparing recruiter mappings. */
export function RecruiterBarChart() {
  const ref = useRef<HTMLElement>(null);
  const isInView = useInView(ref, { once: true, amount: 0.25 });

  const W = 600;
  const H = 220;
  const PAD = { t: 16, r: 20, b: 52, l: 36 };
  const iW = W - PAD.l - PAD.r;
  const iH = H - PAD.t - PAD.b;

  const maxVal = Math.max(...MOCK_RECRUITERS.map((r) => r.totalMappings), 1);
  const barW = iW / MOCK_RECRUITERS.length;
  const barPad = barW * 0.2;

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
          <h2 className="font-heading text-xl text-white">Total Mappings Comparison</h2>
          <p className="mt-1 text-sm text-white/50">All recruiters this cycle</p>
        </div>
      </div>

      <div className="overflow-x-auto dashboard-scrollbar">
        <svg
          viewBox={`0 0 ${W} ${H}`}
          className="w-full min-w-[320px]"
          role="img"
          aria-label="Recruiter mappings bar chart"
        >
          {/* Grid lines */}
          {[0, 0.5, 1].map((frac) => {
            const y = PAD.t + (1 - frac) * iH;
            return (
              <g key={frac}>
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
                  {Math.round(maxVal * frac)}
                </text>
              </g>
            );
          })}

          {/* Bars */}
          {MOCK_RECRUITERS.map((r, i) => {
            const barHeight = (r.totalMappings / maxVal) * iH;
            const x = PAD.l + i * barW + barPad / 2;
            const y = PAD.t + iH - barHeight;
            const bw = barW - barPad;

            return (
              <g key={r.id}>
                {/* Background */}
                <rect
                  x={x}
                  y={PAD.t}
                  width={bw}
                  height={iH}
                  fill="rgba(255,255,255,0.025)"
                  rx="3"
                />
                {/* Bar */}
                <motion.rect
                  x={x}
                  width={bw}
                  rx="3"
                  fill={BAR_COLORS[i % BAR_COLORS.length]}
                  fillOpacity={0.85}
                  initial={{ y: PAD.t + iH, height: 0 }}
                  animate={isInView ? { y, height: barHeight } : {}}
                  transition={{ duration: 0.7, delay: i * 0.06, ease: "easeOut" }}
                />
                {/* Name */}
                <text
                  x={x + bw / 2}
                  y={H - 6}
                  textAnchor="middle"
                  fontSize="9"
                  fill="rgba(255,255,255,0.4)"
                >
                  {r.name.split(" ")[0].slice(0, 7)}
                </text>
                {/* Value */}
                <text
                  x={x + bw / 2}
                  y={y - 4}
                  textAnchor="middle"
                  fontSize="10"
                  fill={BAR_COLORS[i % BAR_COLORS.length]}
                  fontWeight="bold"
                >
                  {r.totalMappings}
                </text>
              </g>
            );
          })}
        </svg>
      </div>
    </motion.section>
  );
}
