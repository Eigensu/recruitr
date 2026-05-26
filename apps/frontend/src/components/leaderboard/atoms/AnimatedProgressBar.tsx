"use client";

import { motion } from "motion/react";
import { cn } from "@/lib/utils";

interface AnimatedProgressBarProps {
  readonly value: number; // 0–100
  readonly color?: string;
  readonly className?: string;
  readonly height?: "xs" | "sm" | "md";
  readonly delay?: number;
  readonly showLabel?: boolean;
}

const heightClasses = {
  xs: "h-1",
  sm: "h-1.5",
  md: "h-2",
};

export function AnimatedProgressBar(props: AnimatedProgressBarProps) {
  const {
    value,
    color = "#F3FF54",
    className,
    height = "sm",
    delay = 0,
    showLabel = false,
  } = props;
  const clamped = Math.min(Math.max(value, 0), 100);

  return (
    <div className={cn("w-full", className)}>
      <div
        className={cn(
          "w-full rounded-full bg-(--color-chart-track) overflow-hidden",
          heightClasses[height],
        )}
      >
        <motion.div
          initial={{ width: "0%" }}
          whileInView={{ width: `${clamped}%` }}
          viewport={{ once: true, amount: 0.5 }}
          transition={{ duration: 0.8, delay, ease: "easeOut" }}
          className="h-full rounded-full"
          style={{ background: color }}
        />
      </div>
      {showLabel && (
        <p className="mt-1 text-[10px] text-(--color-text-secondary) tabular-nums">{clamped}%</p>
      )}
    </div>
  );
}
