"use client";

import { motion } from "motion/react";
import { IconActivityHeartbeat } from "@tabler/icons-react";
import { DASHBOARD_PANEL_CLASS, TONE_CLASSES } from "@/lib/dashboard-constants";
import { cn } from "@/lib/utils";
import type { DashboardActivityItem } from "@/types/dashboard";

interface ActivityFeedProps {
  items: DashboardActivityItem[];
}

export default function ActivityFeed({ items }: ActivityFeedProps) {
  return (
    <motion.aside
      initial={{ opacity: 0, y: 18 }}
      whileInView={{ opacity: 1, y: 0 }}
      viewport={{ once: true, amount: 0.2 }}
      transition={{ duration: 0.45, ease: "easeOut" }}
      className={cn(DASHBOARD_PANEL_CLASS, "p-5")}
    >
      <div className="flex items-start justify-between gap-3">
        <div>
          <h2 className="font-heading text-xl text-white">Activity Feed</h2>
          <p className="mt-1 text-sm text-white/50">Latest operational signals</p>
        </div>
        <IconActivityHeartbeat className="size-6 text-yellow" />
      </div>

      <div className="mt-6 space-y-4">
        {items.map((item, index) => {
          const tone = TONE_CLASSES[item.tone];

          return (
            <motion.div
              key={item.id}
              initial={{ opacity: 0, y: 8 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true, amount: 0.35 }}
              transition={{ duration: 0.25, delay: index * 0.045 }}
              className="relative rounded-lg border border-white/10 bg-white/[0.035] p-4"
            >
              <span className={cn("absolute left-0 top-4 h-8 w-1 rounded-r-full", tone.accent)} />
              <p className="pl-3 text-sm font-semibold text-white">{item.title}</p>
              <p className="mt-1 pl-3 text-sm text-white/55">{item.detail}</p>
              <p className="mt-3 pl-3 text-xs text-white/35">{item.timestamp}</p>
            </motion.div>
          );
        })}
      </div>
    </motion.aside>
  );
}
