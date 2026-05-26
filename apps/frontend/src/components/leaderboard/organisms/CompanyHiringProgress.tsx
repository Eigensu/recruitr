"use client";

import { motion } from "motion/react";
import { AnimatedProgressBar } from "@/components/leaderboard/atoms/AnimatedProgressBar";
import { DASHBOARD_PANEL_CLASS } from "@/components/common/constants/dashboard-constants";
import { cn } from "@/lib/utils";
import type { CompanyHiringItem } from "@/lib/leaderboard-data";

interface CompanyHiringProgressProps {
  readonly companies: CompanyHiringItem[];
}

export function CompanyHiringProgress(props: CompanyHiringProgressProps) {
  const { companies } = props;
  return (
    <motion.section
      initial={{ opacity: 0, y: 18 }}
      whileInView={{ opacity: 1, y: 0 }}
      viewport={{ once: true, amount: 0.12 }}
      transition={{ duration: 0.45, ease: "easeOut" }}
      className={cn(DASHBOARD_PANEL_CLASS, "p-5")}
      style={{ color: "var(--color-text-primary)" }}
    >
      <div className="flex items-start justify-between gap-3 mb-5">
        <div>
          <h2 className="font-heading text-xl">Company Hiring Progress</h2>
          <p className="mt-1 text-sm" style={{ color: "var(--color-text-secondary)" }}>
            Open mandate completion rates
          </p>
        </div>
      </div>

      <div className="space-y-4">
        {companies.map((company, index) => {
          const totalSeats = Number(company.totalSeats);
          const filled = Number(company.filled);
          const rawPct = totalSeats > 0 ? Math.round((filled / totalSeats) * 100) : 0;
          const pct = Math.max(0, Math.min(100, Number.isFinite(rawPct) ? rawPct : 0));
          const isFull = company.filled >= company.totalSeats;
          let barColor = "#60A5FA";
          if (isFull) {
            barColor = "#3DDC97";
          } else if (pct >= 50) {
            barColor = "#F3FF54";
          }
          const recruiterLabel = company.recruiterCount === 1 ? "" : "s";

          return (
            <motion.div
              key={`${company.company}-${company.role}`}
              initial={{ opacity: 0, x: -8 }}
              whileInView={{ opacity: 1, x: 0 }}
              viewport={{ once: true, amount: 0.5 }}
              transition={{ duration: 0.35, delay: index * 0.05 }}
              className="group"
            >
              <div className="flex items-center justify-between mb-1.5 gap-2">
                <div className="min-w-0">
                  <p className="text-sm font-semibold truncate group-hover:text-inherit transition-colors">
                    {company.company}
                  </p>
                  <p className="text-[10px]" style={{ color: "var(--color-text-secondary)" }}>
                    {company.role}
                  </p>
                </div>
                <div className="flex items-center gap-3 shrink-0">
                  <span
                    className={cn(
                      "text-xs font-bold tabular-nums",
                      isFull ? "text-emerald-400" : "",
                    )}
                    style={isFull ? undefined : { color: "var(--color-text-secondary)" }}
                  >
                    {company.filled}/{company.totalSeats}
                  </span>
                  <span
                    className={cn(
                      "rounded-full px-1.5 py-0.5 text-[9px] font-bold",
                      isFull ? "bg-emerald-400/15 text-emerald-300" : "",
                    )}
                    style={
                      isFull
                        ? undefined
                        : {
                            background: "var(--color-surface-2-val)",
                            color: "var(--color-text-secondary)",
                          }
                    }
                  >
                    {pct}%
                  </span>
                </div>
              </div>
              <AnimatedProgressBar value={pct} color={barColor} height="sm" delay={index * 0.06} />
              <p className="mt-1 text-[10px]" style={{ color: "var(--color-text-secondary)" }}>
                {company.recruiterCount} recruiter{recruiterLabel} assigned
              </p>
            </motion.div>
          );
        })}
      </div>
    </motion.section>
  );
}
