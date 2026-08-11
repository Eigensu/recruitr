"use client";

import Link from "next/link";
import { motion } from "motion/react";
import { IconArrowRight, IconBriefcase, IconMapPin } from "@tabler/icons-react";
import { DASHBOARD_PANEL_CLASS } from "@/components/common/constants/dashboard-constants";
import { cn } from "@/lib/utils";
import type { ApiPosition } from "@/types";

interface ClientPositionsSnapshotProps {
  positions: ApiPosition[];
  totalOpen: number;
}

export default function ClientPositionsSnapshot({
  positions,
  totalOpen,
}: ClientPositionsSnapshotProps) {
  return (
    <motion.section
      initial={{ opacity: 0, y: 18 }}
      whileInView={{ opacity: 1, y: 0 }}
      viewport={{ once: true, amount: 0.18 }}
      transition={{ duration: 0.45, ease: "easeOut" }}
      className={cn(DASHBOARD_PANEL_CLASS, "flex h-full flex-col p-5")}
      style={{ color: "var(--color-text-primary)" }}
    >
      <div className="flex items-start justify-between gap-3">
        <div>
          <h2 className="font-heading text-xl">Your Open Positions</h2>
          <p className="mt-1 text-sm" style={{ opacity: 0.6 }}>
            {totalOpen > 0
              ? `${totalOpen} role${totalOpen === 1 ? "" : "s"} currently open with Binge`
              : "No open roles right now"}
          </p>
        </div>
        <Link
          href="/positions"
          className="flex shrink-0 items-center gap-1 text-xs font-bold text-yellow transition-opacity hover:opacity-80"
        >
          View all <IconArrowRight className="size-3.5" />
        </Link>
      </div>

      {positions.length === 0 ? (
        <div
          className="flex flex-1 flex-col items-center justify-center gap-2 py-10 text-center"
          style={{ opacity: 0.5 }}
        >
          <IconBriefcase className="size-8" style={{ opacity: 0.4 }} />
          <p className="max-w-60 text-sm">
            Nothing open at the moment — reach out to your Binge contact to start a new mandate.
          </p>
        </div>
      ) : (
        <div className="mt-4 flex-1 space-y-2.5 overflow-y-auto dashboard-scrollbar">
          {positions.map((position) => {
            const progress =
              position.total_seats > 0
                ? Math.min((position.filled_seats / position.total_seats) * 100, 100)
                : 0;

            return (
              <div
                key={position.id}
                className="rounded-lg border p-3"
                style={{
                  borderColor: "var(--color-border-val)",
                  background: "var(--color-surface-2-val)",
                }}
              >
                <div className="flex items-start justify-between gap-3">
                  <div className="min-w-0">
                    <p className="truncate text-sm font-semibold">{position.role}</p>
                    <p
                      className="mt-0.5 flex items-center gap-1 truncate text-xs"
                      style={{ opacity: 0.6 }}
                    >
                      {position.city && (
                        <>
                          <IconMapPin className="size-3 shrink-0" />
                          {position.city}
                          {position.seniority ? " · " : ""}
                        </>
                      )}
                      {position.seniority}
                    </p>
                  </div>
                  <span className="shrink-0 text-xs font-bold" style={{ opacity: 0.7 }}>
                    {position.filled_seats}/{position.total_seats} seats
                  </span>
                </div>
                <div
                  className="mt-2.5 h-1.5 overflow-hidden rounded-full"
                  style={{ background: "var(--color-border-val)" }}
                >
                  <div
                    className={cn(
                      "h-full rounded-full",
                      progress >= 100 ? "bg-emerald-500" : "bg-yellow",
                    )}
                    style={{ width: `${progress}%` }}
                  />
                </div>
              </div>
            );
          })}
        </div>
      )}
    </motion.section>
  );
}
