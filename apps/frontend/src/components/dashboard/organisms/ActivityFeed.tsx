"use client";

import { motion } from "motion/react";
import { IconActivityHeartbeat } from "@tabler/icons-react";
import ActivityFeedItem from "@/components/dashboard/molecules/ActivityFeedItem";
import { DASHBOARD_PANEL_CLASS } from "@/components/common/constants/dashboard-constants";
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
      style={{ color: "var(--color-text-primary)" }}
    >
      <div className="flex items-start justify-between gap-3">
        <div>
          <h2 className="font-heading text-xl">Activity Feed</h2>
          <p className="mt-1 text-sm" style={{ opacity: 0.6 }}>
            Latest operational signals
          </p>
        </div>
        <IconActivityHeartbeat className="size-6 text-yellow" />
      </div>

      <div className="mt-6 space-y-4">
        {items.length === 0 ? (
          <p className="text-sm text-text-muted text-center py-4">No recent activity.</p>
        ) : (
          items.map((item, index) => <ActivityFeedItem key={item.id} item={item} index={index} />)
        )}
      </div>
    </motion.aside>
  );
}
