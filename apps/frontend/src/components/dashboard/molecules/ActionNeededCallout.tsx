"use client";

import Link from "next/link";
import { motion } from "motion/react";
import { IconAlertTriangle, IconArrowRight } from "@tabler/icons-react";

interface ActionNeededCalloutProps {
  count: number;
}

export default function ActionNeededCallout({ count }: ActionNeededCalloutProps) {
  if (count <= 0) return null;

  return (
    <motion.div
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.35, ease: "easeOut" }}
      className="flex items-center justify-between gap-4 rounded-lg border border-red-500/20 bg-red-500/10 p-4 shadow-sm"
    >
      <div className="flex items-start gap-3">
        <span className="mt-0.5 flex size-8 shrink-0 items-center justify-center rounded-full bg-red-500/15 text-red-500">
          <IconAlertTriangle className="size-4.5" />
        </span>
        <div>
          <h3 className="text-sm font-semibold text-red-500">Action needed</h3>
          <p className="mt-0.5 text-sm text-red-500/80">
            {count} {count === 1 ? "candidate is" : "candidates are"} waiting on your decision or
            offer response.
          </p>
        </div>
      </div>
      <Link
        href="/pipeline"
        className="flex shrink-0 items-center gap-1.5 rounded-lg bg-red-500/15 px-3 py-2 text-sm font-bold text-red-500 transition-colors hover:bg-red-500/25"
      >
        Review now <IconArrowRight className="size-4" />
      </Link>
    </motion.div>
  );
}
