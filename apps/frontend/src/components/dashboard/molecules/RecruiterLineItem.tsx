"use client";

import { motion } from "motion/react";
import AnimatedNumber from "@/components/dashboard/atoms/AnimatedNumber";
import { cn } from "@/lib/utils";
import type { RecruiterDashboardStat } from "@/types/dashboard";

interface RecruiterLineItemProps {
  recruiter: RecruiterDashboardStat;
  index: number;
  isInView: boolean;
  isActive: boolean;
  maxPipeline: number;
  onHover: () => void;
  onFocus: () => void;
  onClick: () => void;
}

export default function RecruiterLineItem({
  recruiter,
  index,
  isInView,
  isActive,
  maxPipeline,
  onHover,
  onFocus,
  onClick,
}: RecruiterLineItemProps) {
  const width = Math.max((recruiter.inPipeline / maxPipeline) * 100, 4);

  return (
    <button
      key={recruiter.name}
      type="button"
      onMouseEnter={onHover}
      onFocus={onFocus}
      onClick={onClick}
      className="block w-full text-left"
    >
      <div className="mb-2 flex items-center justify-between gap-3">
        <span className={cn("text-sm font-semibold", isActive ? "text-white" : "text-white")}>
          {recruiter.name}
        </span>
        <span className="text-xs text-white">
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
}
