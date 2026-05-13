"use client";

import { motion } from "motion/react";
import { IconBuildingStore } from "@tabler/icons-react";
import ClientActivityTableRow from "@/components/dashboard/molecules/ClientActivityTableRow";
import AnimatedNumber from "@/components/dashboard/atoms/AnimatedNumber";
import {
  DASHBOARD_PANEL_CLASS,
  DASHBOARD_TABLE_HEADER_CLASS,
} from "@/components/common/constants/dashboard-constants";
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
          <p className="mt-1 text-sm text-white">
            Every client added to open positions appears here automatically.
          </p>
        </div>
        <div className="flex items-center gap-2 rounded-full bg-white/10 px-3 py-1 text-xs font-semibold text-white">
          <IconBuildingStore className="size-4 text-yellow" />
          <AnimatedNumber value={rows.length} /> clients
        </div>
      </div>

      <div className="max-h-130 overflow-auto dashboard-scrollbar">
        <table className="min-w-170 w-full table-fixed border-collapse">
          <thead className="sticky top-0 z-10 bg-[#111827]/95 backdrop-blur">
            <tr>
              <th
                className={cn(
                  DASHBOARD_TABLE_HEADER_CLASS,
                  "w-[32%] px-4 py-3 text-left text-base",
                )}
              >
                Client
              </th>
              <th
                className={cn(
                  DASHBOARD_TABLE_HEADER_CLASS,
                  "w-[10%] px-2 py-3 text-center text-base",
                )}
              >
                Open
              </th>
              <th
                className={cn(
                  DASHBOARD_TABLE_HEADER_CLASS,
                  "w-[10%] px-2 py-3 text-center text-base",
                )}
              >
                Seats
              </th>
              <th
                className={cn(
                  DASHBOARD_TABLE_HEADER_CLASS,
                  "w-[10%] px-2 py-3 text-center text-base",
                )}
              >
                Filled
              </th>
              <th
                className={cn(
                  DASHBOARD_TABLE_HEADER_CLASS,
                  "w-[12%] px-2 py-3 text-center text-base",
                )}
              >
                Remaining
              </th>
              <th
                className={cn(
                  DASHBOARD_TABLE_HEADER_CLASS,
                  "w-[12%] px-2 py-3 text-center text-base",
                )}
              >
                Pipeline
              </th>
              <th
                className={cn(
                  DASHBOARD_TABLE_HEADER_CLASS,
                  "w-[14%] px-4 py-3 text-center text-base",
                )}
              >
                Joined
              </th>
            </tr>
          </thead>
          <tbody>
            {rows.map((row, index) => (
              <ClientActivityTableRow key={row.clientId} row={row} index={index} />
            ))}
          </tbody>
        </table>
      </div>
    </motion.section>
  );
}
