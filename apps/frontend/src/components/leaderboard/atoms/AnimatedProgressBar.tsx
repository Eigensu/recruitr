"use client";

import { motion } from "motion/react";
import { cn } from "@/lib/utils";

interface AnimatedProgressBarProps {
  value: number; // 0–100
  color?: string;
  className?: string;
  height?: "xs" | "sm" | "md";
  delay?: number;
  showLabel?: boolean;
}

const heightClasses = {
  xs: "h-1",
  sm: "h-1.5",
  md: "h-2",
};

export function AnimatedProgressBar({
  value,
  color = "#F3FF54",
  className,
  height = "sm",
  delay = 0,
  showLabel = false,
}: AnimatedProgressBarProps) {
  const clamped = Math.min(Math.max(value, 0), 100);

  return (
    <div className={cn("w-full", className)}>
      <div className={cn("w-full rounded-full bg-white/10 overflow-hidden", heightClasses[height])}>
        <motion.div
          initial={{ width: "0%" }}
          whileInView={{ width: `${clamped}%` }}
          viewport={{ once: true, amount: 0.5 }}
          transition={{ duration: 0.8, delay, ease: "easeOut" }}
          className="h-full rounded-full"
          style={{ background: color }}
        />
      </div>
      {showLabel && <p className="mt-1 text-[10px] text-white/50 tabular-nums">{clamped}%</p>}
    </div>
  );
}
