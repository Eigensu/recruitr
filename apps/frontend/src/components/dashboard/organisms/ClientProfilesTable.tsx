"use client";

import { motion } from "motion/react";
import { IconBuildingStore } from "@tabler/icons-react";
import AnimatedNumber from "@/components/dashboard/atoms/AnimatedNumber";
import {
  DASHBOARD_PANEL_CLASS,
  DASHBOARD_TABLE_HEADER_CLASS,
} from "@/components/common/constants/dashboard-constants";
import { cn } from "@/lib/utils";
import type { ClientProfileRow, ClientProfileStatus } from "@/types/dashboard";

interface Props {
  readonly rows: ClientProfileRow[];
}

const STATUS_STYLES: Record<ClientProfileStatus, { label: string; bg: string; color: string }> = {
  active: { label: "Active", bg: "rgba(61,220,151,0.15)", color: "#3DDC97" },
  on_hold: { label: "On Hold", bg: "rgba(247,201,72,0.15)", color: "#F7C948" },
  closed: { label: "Closed", bg: "rgba(148,163,184,0.15)", color: "var(--color-text-secondary)" },
};

function formatTimeAgo(isoDate: string | null): string {
  if (!isoDate) return "—";
  const ms = Date.now() - new Date(isoDate).getTime();
  if (!Number.isFinite(ms) || ms < 0) return "—";
  const days = Math.floor(ms / 86_400_000);
  if (days === 0) return "Today";
  if (days === 1) return "Yesterday";
  if (days < 30) return `${days} days ago`;
  const months = Math.floor(days / 30);
  return `${months} month${months > 1 ? "s" : ""} ago`;
}

export default function ClientProfilesTable({ rows }: Props) {
  return (
    <motion.section
      initial={{ opacity: 0, y: 18 }}
      whileInView={{ opacity: 1, y: 0 }}
      viewport={{ once: true, amount: 0.12 }}
      transition={{ duration: 0.45, ease: "easeOut" }}
      className={cn(DASHBOARD_PANEL_CLASS, "overflow-hidden")}
      style={{ color: "var(--color-text-primary)" }}
    >
      <div className="flex flex-wrap items-start justify-between gap-3 p-5">
        <div>
          <h2 className="font-heading text-xl">Client Profiles</h2>
          <p className="mt-1 text-sm" style={{ opacity: 0.6 }}>
            One row per client — aggregated across all of their open positions.
          </p>
        </div>
        <div
          className="flex items-center gap-2 rounded-full px-3 py-1 text-xs font-semibold"
          style={{ background: "var(--color-surface-2-val)", color: "var(--color-text-primary)" }}
        >
          <IconBuildingStore className="size-4 text-yellow" />
          <AnimatedNumber value={rows.length} /> clients
        </div>
      </div>

      <div className="max-h-130 overflow-auto dashboard-scrollbar">
        <table className="min-w-170 w-full table-fixed border-collapse">
          <thead
            className="sticky top-0 z-10 backdrop-blur"
            style={{ background: "var(--color-surface-val)" }}
          >
            <tr>
              <th
                className={cn(
                  DASHBOARD_TABLE_HEADER_CLASS,
                  "w-[28%] px-5 py-3 text-left text-base",
                )}
              >
                Client
              </th>
              <th
                className={cn(
                  DASHBOARD_TABLE_HEADER_CLASS,
                  "w-[13%] px-2 py-3 text-center text-base",
                )}
              >
                Open
              </th>
              <th
                className={cn(
                  DASHBOARD_TABLE_HEADER_CLASS,
                  "w-[13%] px-2 py-3 text-center text-base",
                )}
              >
                Candidates
              </th>
              <th
                className={cn(
                  DASHBOARD_TABLE_HEADER_CLASS,
                  "w-[15%] px-2 py-3 text-center text-base",
                )}
              >
                Recruiters
              </th>
              <th
                className={cn(
                  DASHBOARD_TABLE_HEADER_CLASS,
                  "w-[16%] px-2 py-3 text-center text-base",
                )}
              >
                Last Activity
              </th>
              <th
                className={cn(
                  DASHBOARD_TABLE_HEADER_CLASS,
                  "w-[15%] px-4 py-3 text-center text-base",
                )}
              >
                Status
              </th>
            </tr>
          </thead>
          <tbody>
            {rows.length === 0 ? (
              <tr>
                <td
                  colSpan={6}
                  className="px-4 py-8 text-center text-sm"
                  style={{ color: "var(--color-text-secondary)" }}
                >
                  No client data available.
                </td>
              </tr>
            ) : (
              rows.map((row, index) => {
                const st = STATUS_STYLES[row.status] ?? STATUS_STYLES.closed;
                return (
                  <motion.tr
                    key={row.client_name}
                    initial={{ opacity: 0 }}
                    whileInView={{ opacity: 1 }}
                    viewport={{ once: true, amount: 0.2 }}
                    transition={{ duration: 0.2, delay: index * 0.01 }}
                    className="hover:bg-white/[0.035]"
                    style={{ color: "var(--color-text-primary)" }}
                  >
                    {/* Client name */}
                    <td className="px-5 py-3">
                      <p className="text-base font-medium">{row.client_name}</p>
                    </td>

                    {/* Open positions — yellow: outstanding work */}
                    <td className="px-3 py-3 text-center text-base text-yellow">
                      <AnimatedNumber value={row.total_open_positions} />
                    </td>

                    {/* Candidates — neutral */}
                    <td className="px-3 py-3 text-center text-base">
                      <AnimatedNumber value={row.total_candidates} />
                    </td>

                    {/* Active recruiters — green: people doing work */}
                    <td className="px-3 py-3 text-center text-base text-emerald-400">
                      <AnimatedNumber value={row.active_recruiters} />
                    </td>

                    {/* Last activity — muted */}
                    <td className="px-3 py-3 text-center text-base" style={{ opacity: 0.55 }}>
                      {formatTimeAgo(row.last_activity)}
                    </td>

                    {/* Status badge */}
                    <td className="px-5 py-3 text-center">
                      <span
                        className="inline-block rounded-full px-2.5 py-0.5 text-xs font-medium"
                        style={{ background: st.bg, color: st.color }}
                      >
                        {st.label}
                      </span>
                    </td>
                  </motion.tr>
                );
              })
            )}
          </tbody>
        </table>
      </div>
    </motion.section>
  );
}
