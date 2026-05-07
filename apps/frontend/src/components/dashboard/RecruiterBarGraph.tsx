"use client";

import { useRef, useState } from "react";
import { motion, useInView } from "motion/react";
import { IconChartBar } from "@tabler/icons-react";
import AnimatedNumber from "@/components/dashboard/AnimatedNumber";
import { DASHBOARD_PANEL_CLASS } from "@/lib/dashboard-constants";
import { cn } from "@/lib/utils";
import type { RecruiterDashboardStat } from "@/types/dashboard";

interface RecruiterBarGraphProps {
  recruiters: RecruiterDashboardStat[];
}

export default function RecruiterBarGraph({ recruiters }: RecruiterBarGraphProps) {
  const graphRef = useRef<HTMLElement>(null);
  const isInView = useInView(graphRef, { once: true, amount: 0.28 });
  const [activeRecruiter, setActiveRecruiter] = useState(recruiters[0]?.name);
  const maxPipeline = Math.max(...recruiters.map((recruiter) => recruiter.inPipeline), 1);

  return (
    <motion.section
      ref={graphRef}
      initial={{ opacity: 0, y: 18 }}
      whileInView={{ opacity: 1, y: 0 }}
      viewport={{ once: true, amount: 0.25 }}
      transition={{ duration: 0.45, ease: "easeOut" }}
      className={cn(DASHBOARD_PANEL_CLASS, "p-5")}
    >
      <div className="flex items-start justify-between gap-3">
        <div>
          <h2 className="font-heading text-xl text-white">Recruiter Bar Graph</h2>
          <p className="mt-1 text-sm text-white/50">Pipeline load by recruiter</p>
        </div>
        <IconChartBar className="size-6 text-yellow" />
      </div>

      <div className="mt-6 space-y-4">
        {recruiters.map((recruiter, index) => {
          const width = Math.max((recruiter.inPipeline / maxPipeline) * 100, 4);
          const isActive = recruiter.name === activeRecruiter;

          return (
            <button
              key={recruiter.name}
              type="button"
              onMouseEnter={() => setActiveRecruiter(recruiter.name)}
              onFocus={() => setActiveRecruiter(recruiter.name)}
              onClick={() => setActiveRecruiter(recruiter.name)}
              className="block w-full text-left"
            >
              <div className="mb-2 flex items-center justify-between gap-3">
                <span
                  className={cn("text-sm font-semibold", isActive ? "text-white" : "text-white/65")}
                >
                  {recruiter.name}
                </span>
                <span className="text-xs text-white/45">
                  <AnimatedNumber value={recruiter.inPipeline} /> pipeline /{" "}
                  <AnimatedNumber value={recruiter.joined} /> joined
                </span>
              </div>
              <div className="h-9 overflow-hidden rounded-lg bg-white/10">
                <motion.div
                  initial={{ width: 0 }}
                  animate={{ width: isInView ? `${width}%` : "0%" }}
                  transition={{ duration: 0.9, delay: index * 0.08, ease: "easeOut" }}
                  className={cn(
                    "flex h-full items-center justify-end rounded-lg px-3 text-xs font-bold transition-colors",
                    isActive ? "bg-yellow text-navy" : "bg-white/35 text-white",
                  )}
                >
                  <AnimatedNumber value={recruiter.openSeats} /> seats
                </motion.div>
              </div>
            </button>
          );
        })}
      </div>
    </motion.section>
  );
}
