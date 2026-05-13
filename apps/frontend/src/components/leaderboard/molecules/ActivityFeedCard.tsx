"use client";

import { motion } from "motion/react";
import { cn } from "@/lib/utils";
import { AnimatedProgressBar } from "@/components/leaderboard/atoms/AnimatedProgressBar";
import type { RecentActivityItem } from "@/lib/leaderboard-data";

const toneBar: Record<RecentActivityItem["tone"], string> = {
  yellow: "#F3FF54",
  green: "#3DDC97",
  red: "#FF5A5F",
  neutral: "rgba(255,255,255,0.3)",
};

const toneText: Record<RecentActivityItem["tone"], string> = {
  yellow: "text-yellow",
  green: "text-emerald-400",
  red: "text-red-400",
  neutral: "text-white/60",
};

interface ActivityFeedCardProps {
  item: RecentActivityItem;
  index: number;
}

export function ActivityFeedCard({ item, index }: ActivityFeedCardProps) {
  return (
    <motion.div
      initial={{ opacity: 0, x: -10 }}
      whileInView={{ opacity: 1, x: 0 }}
      viewport={{ once: true, amount: 0.5 }}
      transition={{ duration: 0.35, delay: index * 0.05, ease: "easeOut" }}
      whileHover={{ x: 3 }}
      className="flex items-start gap-3 py-3 px-1 group"
    >
      {/* Colour bar */}
      <div
        className="w-0.5 self-stretch rounded-full shrink-0 mt-1"
        style={{ background: toneBar[item.tone] }}
      />

      {/* Avatar */}
      <div
        className="size-8 rounded-full flex items-center justify-center text-xs font-bold shrink-0"
        style={{
          background: `${item.avatarColor}22`,
          color: item.avatarColor,
          border: `1.5px solid ${item.avatarColor}44`,
        }}
      >
        {item.initials}
      </div>

      {/* Content */}
      <div className="min-w-0 flex-1">
        <p className="text-xs font-semibold text-white/80 truncate">
          <span className="text-white">{item.recruiter}</span>
        </p>
        <p className={cn("text-xs mt-0.5", toneText[item.tone])}>{item.action}</p>
        <p className="text-[10px] text-white/40 mt-0.5 truncate">{item.target}</p>
      </div>

      {/* Timestamp */}
      <span className="text-[10px] text-white/30 shrink-0 mt-0.5">{item.timestamp}</span>
    </motion.div>
  );
}
