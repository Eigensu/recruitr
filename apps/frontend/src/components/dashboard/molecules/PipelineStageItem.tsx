"use client";

import { motion } from "motion/react";
import AnimatedNumber from "@/components/dashboard/atoms/AnimatedNumber";
import { cn } from "@/lib/utils";
import type { PipelineStageMetric } from "@/types/dashboard";

interface PipelineStageItemProps {
  stage: PipelineStageMetric;
  index: number;
}

export default function PipelineStageItem({ stage, index }: PipelineStageItemProps) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 8 }}
      whileInView={{ opacity: 1, y: 0 }}
      viewport={{ once: true, amount: 0.35 }}
      transition={{ duration: 0.28, delay: index * 0.025 }}
    >
      <div className="mb-2 flex items-center justify-between gap-4">
        <div className="min-w-0">
          <p className="truncate text-sm font-medium text-white">{stage.label}</p>
          <p className="text-xs text-white">
            <AnimatedNumber value={stage.count} /> candidates
          </p>
        </div>
        <span className="font-heading text-lg text-yellow">
          <AnimatedNumber value={stage.percent} suffix="%" />
        </span>
      </div>
      <div className="h-2 overflow-hidden rounded-full bg-white/10">
        <motion.div
          initial={{ width: 0 }}
          whileInView={{ width: `${Math.min(stage.percent, 100)}%` }}
          viewport={{ once: true, amount: 0.45 }}
          transition={{ duration: 0.7, delay: 0.12 + index * 0.035, ease: "easeOut" }}
          className="h-full rounded-full bg-yellow"
        />
      </div>
    </motion.div>
  );
}
