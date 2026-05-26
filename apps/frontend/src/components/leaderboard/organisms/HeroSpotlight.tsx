"use client";

import { useRef } from "react";
import { motion, useInView } from "motion/react";
import { RecruiterAvatar } from "@/components/leaderboard/atoms/RecruiterAvatar";
import { AchievementBadge } from "@/components/leaderboard/molecules/AchievementBadge";
import { AnimatedProgressBar } from "@/components/leaderboard/atoms/AnimatedProgressBar";
import AnimatedNumber from "@/components/dashboard/atoms/AnimatedNumber";
import { DASHBOARD_PANEL_CLASS } from "@/components/common/constants/dashboard-constants";
import { cn } from "@/lib/utils";
import type { LeaderboardRecruiter } from "@/lib/leaderboard-data";

interface HeroSpotlightProps {
  readonly recruiter: LeaderboardRecruiter;
}

export function HeroSpotlight(props: HeroSpotlightProps) {
  const { recruiter } = props;
  const ref = useRef<HTMLDivElement>(null);
  const isInView = useInView(ref, { once: true, amount: 0.3 });

  const xpPercent = Math.min((recruiter.xp / 10000) * 100, 100);

  return (
    <motion.div
      ref={ref}
      initial={{ opacity: 0, scale: 0.97 }}
      animate={isInView ? { opacity: 1, scale: 1 } : {}}
      transition={{ duration: 0.55, ease: "easeOut" }}
      className={cn(DASHBOARD_PANEL_CLASS, "relative overflow-hidden p-6")}
    >
      {/* Glow background */}
      <div
        className="pointer-events-none absolute -top-16 -left-16 size-64 rounded-full opacity-20 blur-3xl"
        style={{ background: "#F3FF54" }}
        aria-hidden="true"
      />

      {/* Animated glow pulse — replaces border pulse */}
      <motion.div
        animate={{ opacity: [0.15, 0.4, 0.15] }}
        transition={{ duration: 2.5, repeat: Infinity, ease: "easeInOut" }}
        className="pointer-events-none absolute inset-0 rounded-lg shadow-[inset_0_0_40px_rgba(243,255,84,0.12)]"
        aria-hidden="true"
      />

      <div className="relative z-10 flex flex-col sm:flex-row items-start sm:items-center gap-6">
        {/* Avatar */}
        <div className="shrink-0">
          <RecruiterAvatar
            initials={recruiter.initials}
            color={recruiter.avatarColor}
            size="xl"
            ring
            pulse
          />
        </div>

        {/* Info */}
        <div className="flex-1 min-w-0">
          <div className="flex flex-wrap items-center gap-2 mb-1">
            <span className="text-xs font-bold uppercase tracking-widest text-yellow/70">
              🏆 #1 Recruiter
            </span>
            <span className="rounded-full bg-yellow/15 px-2 py-0.5 text-[10px] font-bold text-yellow">
              Level {recruiter.level}
            </span>
          </div>

          <h2 className="font-heading text-3xl text-(--color-text-primary) leading-tight">
            {recruiter.name}
          </h2>

          <div className="mt-3 flex flex-wrap gap-4">
            <Stat
              label="Mappings"
              value={recruiter.totalMappings}
              color="text-(--color-text-primary)"
            />
            <Stat label="Offers" value={recruiter.offersReceived} color="text-yellow" />
            <Stat label="Joined" value={recruiter.joined} color="text-emerald-400" />
            <Stat
              label="Growth"
              value={recruiter.monthlyGrowth}
              suffix="%"
              color="text-emerald-300"
            />
          </div>

          {/* XP Bar */}
          <div className="mt-4">
            <div className="flex items-center justify-between mb-1">
              <span className="text-[10px] font-semibold uppercase tracking-wider text-(--color-text-secondary)">
                XP Progress
              </span>
              <span className="text-xs font-bold text-yellow">
                <AnimatedNumber value={recruiter.xp} /> / 10,000
              </span>
            </div>
            <AnimatedProgressBar value={xpPercent} color="#F3FF54" height="md" />
          </div>
        </div>

        {/* Badge */}
        <div className="shrink-0 flex flex-col items-center gap-2">
          <AchievementBadge badgeKey={recruiter.badge} size="lg" />
          <p className="text-[10px] text-(--color-text-secondary) text-center">Top Badge</p>
        </div>
      </div>
    </motion.div>
  );
}

function Stat({
  label,
  value,
  suffix = "",
  color,
}: Readonly<{
  label: string;
  value: number;
  suffix?: string;
  color: string;
}>) {
  return (
    <div>
      <p className="text-[10px] text-(--color-text-secondary) uppercase tracking-wider">{label}</p>
      <p className={cn("font-heading text-xl", color)}>
        <AnimatedNumber value={value} suffix={suffix} />
      </p>
    </div>
  );
}
