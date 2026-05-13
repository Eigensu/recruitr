"use client";

import type { CSSProperties } from "react";
import { motion } from "motion/react";
import { cn } from "@/lib/utils";

interface RecruiterAvatarProps {
  initials: string;
  color: string;
  size?: "sm" | "md" | "lg" | "xl";
  ring?: boolean;
  pulse?: boolean;
}

const sizeClasses = {
  sm: "size-8 text-xs",
  md: "size-10 text-sm",
  lg: "size-14 text-base",
  xl: "size-20 text-2xl",
};

export function RecruiterAvatar({
  initials,
  color,
  size = "md",
  ring = false,
  pulse = false,
}: RecruiterAvatarProps) {
  return (
    <div className="relative shrink-0">
      <motion.div
        whileHover={{ scale: 1.08 }}
        transition={{ type: "spring", stiffness: 300 }}
        className={cn(
          "flex items-center justify-center rounded-full font-bold select-none",
          sizeClasses[size],
          ring && "ring-2 ring-offset-2 ring-offset-[#0f1629]",
        )}
        style={{
          background: `${color}22`,
          color,
          border: `2px solid ${color}55`,
          ...(ring ? ({ ["--tw-ring-color"]: color } as CSSProperties) : {}),
        }}
      >
        {initials}
      </motion.div>
      {pulse && (
        <span
          className="absolute -top-0.5 -right-0.5 size-3 rounded-full bg-emerald-400 border-2 border-[#0f1629] animate-pulse"
          aria-hidden="true"
        />
      )}
    </div>
  );
}
