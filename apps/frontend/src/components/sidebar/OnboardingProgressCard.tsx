"use client";
import Link from "next/link";
import { motion } from "motion/react";
import { useSidebar } from "@/components/ui/sidebar";

interface OnboardingProgressCardProps {
  readonly progress?: number; // 0-100
  readonly totalSteps?: number;
  readonly completedSteps?: number;
}

export function OnboardingProgressCard({
  progress = 76,
  totalSteps = 9,
  completedSteps = 5,
}: OnboardingProgressCardProps) {
  const { open } = useSidebar();
  const safeTotal = Math.max(totalSteps, 0);
  const safeCompleted = Math.max(completedSteps, 0);
  const computedProgress =
    safeTotal > 0 ? Math.round((Math.min(safeCompleted, safeTotal) / safeTotal) * 100) : 0;
  const displayProgress = safeTotal > 0 ? computedProgress : Math.max(0, Math.min(progress, 100));
  const remaining = Math.max(0, safeTotal - safeCompleted);

  // Closed state: show only percentage badge (compact)
  if (!open) {
    return (
      <div className="flex items-center justify-center px-3 py-1.5">
        <motion.div
          initial={{ scale: 0.95, opacity: 0 }}
          animate={{ scale: 1, opacity: 1 }}
          transition={{ duration: 0.18 }}
          className="size-8 flex shrink-0 items-center justify-center rounded-full font-bold text-[10px] tracking-tighter"
          style={{
            background: "var(--color-surface-2-val)",
            color: "var(--color-text-primary)",
            border: "1px solid rgba(255,255,255,0.08)",
          }}
        >
          {displayProgress}%
        </motion.div>
      </div>
    );
  }

  // Open state: full card (no inner divider lines)
  return (
    <motion.div
      initial={{ opacity: 0, y: 6 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.28, ease: "easeOut" }}
      className="px-3 py-2"
    >
      <Link href="/onboarding" className="no-underline block">
        <div
          className="rounded-2xl p-4 cursor-pointer overflow-hidden"
          style={{
            background: "var(--color-surface-2-val)",
            color: "var(--color-text-primary)",
          }}
        >
          <div className="flex flex-col">
            <span className="text-sm font-semibold" style={{ color: "var(--color-text-primary)" }}>
              Setup checklist
            </span>
            <div
              className="mt-3 relative w-full h-2 rounded-full overflow-hidden"
              style={{ background: "var(--color-surface-val)" }}
            >
              <motion.div
                initial={{ width: 0 }}
                animate={{ width: `${displayProgress}%` }}
                transition={{ duration: 0.8, ease: "easeOut" }}
                className="h-full rounded-full"
                style={{
                  background: "linear-gradient(90deg, #F3FF54 0%, #F97316 100%)",
                }}
              />
            </div>
            <span className="mt-2 text-xs" style={{ color: "var(--color-text-secondary)" }}>
              {remaining} of {totalSteps} steps remaining
            </span>
          </div>
        </div>
      </Link>
    </motion.div>
  );
}
