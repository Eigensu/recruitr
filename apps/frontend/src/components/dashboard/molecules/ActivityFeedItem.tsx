"use client";

import { motion } from "motion/react";
import {
  TONE_STYLES,
  DASHBOARD_WIDGET_CLASS,
} from "@/components/common/constants/dashboard-constants";
import { cn } from "@/lib/utils";
import type { DashboardActivityItem } from "@/types/dashboard";

interface ActivityFeedItemProps {
  item: DashboardActivityItem;
  index: number;
}

export default function ActivityFeedItem({ item, index }: ActivityFeedItemProps) {
  const tone = TONE_STYLES[item.tone];

  return (
    <motion.div
      initial={{ opacity: 0, y: 8 }}
      whileInView={{ opacity: 1, y: 0 }}
      viewport={{ once: true, amount: 0.35 }}
      transition={{ duration: 0.25, delay: index * 0.045 }}
      className={cn(DASHBOARD_WIDGET_CLASS, "relative")}
      style={{ background: tone.cardBg, color: tone.cardText }}
    >
      {/* Accent bar — uses chip background as the accent colour */}
      <span
        className="absolute left-0 top-4 h-8 w-1 rounded-r-full"
        style={{ background: tone.chipBg }}
      />
      <p className="pl-3 text-sm font-semibold">{item.title}</p>
      <p className="pl-3 mt-1 text-sm" style={{ opacity: 0.7 }}>
        {item.detail}
      </p>
      <p className="pl-3 mt-3 text-xs" style={{ opacity: 0.5 }}>
        {item.timestamp}
      </p>
    </motion.div>
  );
}
