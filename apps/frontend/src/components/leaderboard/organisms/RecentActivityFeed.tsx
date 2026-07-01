"use client";

import { motion } from "motion/react";
import { ActivityFeedCard } from "@/components/leaderboard/molecules/ActivityFeedCard";
import { DASHBOARD_PANEL_CLASS } from "@/components/common/constants/dashboard-constants";
import { cn } from "@/lib/utils";
import type { RecentActivityItem } from "@/lib/leaderboard-data";

interface RecentActivityFeedProps {
  readonly items: RecentActivityItem[];
}

export function RecentActivityFeed(props: RecentActivityFeedProps) {
  const { items } = props;
  return (
    <motion.section
      initial={{ opacity: 0, y: 18 }}
      whileInView={{ opacity: 1, y: 0 }}
      viewport={{ once: true, amount: 0.12 }}
      transition={{ duration: 0.45, ease: "easeOut" }}
      className={cn(DASHBOARD_PANEL_CLASS, "p-5")}
    >
      <div className="flex items-start justify-between gap-3 mb-4">
        <div>
          <h2 className="font-heading text-xl text-(--color-text-primary)">Recent Activity</h2>
          <p className="mt-1 text-sm text-(--color-text-secondary)">Live recruiter actions</p>
        </div>
        <span className="flex items-center gap-1.5 rounded-full bg-emerald-400/15 px-3 py-1 text-xs font-semibold text-emerald-300">
          <span className="size-1.5 rounded-full bg-emerald-400 animate-pulse inline-block" />
          <span>Live</span>
        </span>
      </div>

      <div className="divide-y divide-border">
        {items.slice(0, 5).map((item, index) => (
          <ActivityFeedCard key={item.id} item={item} index={index} />
        ))}
      </div>
    </motion.section>
  );
}
