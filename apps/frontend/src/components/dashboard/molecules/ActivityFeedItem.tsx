"use client";

import { motion } from "motion/react";
import {
  TONE_CLASSES,
  DASHBOARD_WIDGET_CLASS,
} from "@/components/common/constants/dashboard-constants";
import { cn } from "@/lib/utils";
import type { DashboardActivityItem } from "@/types/dashboard";

interface ActivityFeedItemProps {
  item: DashboardActivityItem;
  index: number;
}

export default function ActivityFeedItem({ item, index }: ActivityFeedItemProps) {
  const tone = TONE_CLASSES[item.tone];

  return (
    <motion.div
      initial={{ opacity: 0, y: 8 }}
      whileInView={{ opacity: 1, y: 0 }}
      viewport={{ once: true, amount: 0.35 }}
      transition={{ duration: 0.25, delay: index * 0.045 }}
      className={cn(DASHBOARD_WIDGET_CLASS, "relative")}
    >
      <span className={cn("absolute left-0 top-4 h-8 w-1 rounded-r-full", tone.accent)} />
      <p className="pl-3 text-sm font-semibold text-white">{item.title}</p>
      <p className="mt-1 pl-3 text-sm text-white">{item.detail}</p>
      <p className="mt-3 pl-3 text-xs text-white">{item.timestamp}</p>
    </motion.div>
  );
}
