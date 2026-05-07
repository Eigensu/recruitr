"use client";

import { motion } from "motion/react";
import { IconBuildingStore } from "@tabler/icons-react";
import AnimatedNumber from "@/components/dashboard/AnimatedNumber";
import { DASHBOARD_PANEL_CLASS, DASHBOARD_TABLE_HEADER_CLASS } from "@/lib/dashboard-constants";
import { cn } from "@/lib/utils";
import type { ClientActivityRow } from "@/types/dashboard";

interface ClientActivityTableProps {
  rows: ClientActivityRow[];
}

export default function ClientActivityTable({ rows }: ClientActivityTableProps) {
  return (
    <motion.section
      initial={{ opacity: 0, y: 18 }}
      whileInView={{ opacity: 1, y: 0 }}
      viewport={{ once: true, amount: 0.12 }}
      transition={{ duration: 0.45, ease: "easeOut" }}
      className={cn(DASHBOARD_PANEL_CLASS, "overflow-hidden")}
    >
      <div className="flex flex-wrap items-start justify-between gap-3 border-b border-white/10 p-5">
        <div>
          <h2 className="font-heading text-xl text-white">Client Activity</h2>
          <p className="mt-1 text-sm text-white/50">
            Every client added to open positions appears here automatically.
          </p>
        </div>
        <div className="flex items-center gap-2 rounded-full bg-white/10 px-3 py-1 text-xs font-semibold text-white/70">
          <IconBuildingStore className="size-4 text-yellow" />
          <AnimatedNumber value={rows.length} /> clients
        </div>
      </div>

      <div className="max-h-[520px] overflow-auto">
        <table className="min-w-[760px] w-full border-collapse">
          <thead className="sticky top-0 z-10 bg-[#111827]/95 backdrop-blur">
            <tr>
              <th className={cn(DASHBOARD_TABLE_HEADER_CLASS, "px-5 py-3 text-left")}>Client</th>
              <th className={cn(DASHBOARD_TABLE_HEADER_CLASS, "px-3 py-3 text-center")}>Open</th>
              <th className={cn(DASHBOARD_TABLE_HEADER_CLASS, "px-3 py-3 text-center")}>Seats</th>
              <th className={cn(DASHBOARD_TABLE_HEADER_CLASS, "px-3 py-3 text-center")}>Filled</th>
              <th className={cn(DASHBOARD_TABLE_HEADER_CLASS, "px-3 py-3 text-center")}>
                Remaining
              </th>
              <th className={cn(DASHBOARD_TABLE_HEADER_CLASS, "px-3 py-3 text-center")}>
                Pipeline
              </th>
              <th className={cn(DASHBOARD_TABLE_HEADER_CLASS, "px-5 py-3 text-center")}>Joined</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((row, index) => (
              <motion.tr
                key={row.clientId}
                initial={{ opacity: 0 }}
                whileInView={{ opacity: 1 }}
                viewport={{ once: true, amount: 0.2 }}
                transition={{ duration: 0.2, delay: index * 0.01 }}
                className="border-t border-white/10 hover:bg-white/[0.035]"
              >
                <td className="px-5 py-3">
                  <p className="text-sm font-medium text-white">{row.clientName}</p>
                  <p className="text-xs text-white/40">{row.clientId}</p>
                </td>
                <td className="px-3 py-3 text-center text-sm text-white/75">{row.openPositions}</td>
                <td className="px-3 py-3 text-center text-sm text-white/75">{row.totalSeats}</td>
                <td className="px-3 py-3 text-center text-sm text-emerald-200">{row.filled}</td>
                <td className="px-3 py-3 text-center text-sm text-yellow">{row.remaining}</td>
                <td className="px-3 py-3 text-center text-sm text-white/75">{row.inPipeline}</td>
                <td className="px-5 py-3 text-center text-sm text-white/75">{row.joined}</td>
              </motion.tr>
            ))}
          </tbody>
        </table>
      </div>
    </motion.section>
  );
}
