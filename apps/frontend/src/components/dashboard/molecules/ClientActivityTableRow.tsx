"use client";

import { motion } from "motion/react";
import AnimatedNumber from "@/components/dashboard/atoms/AnimatedNumber";
import { cn } from "@/lib/utils";
import type { ClientActivityRow } from "@/types/dashboard";

interface ClientActivityTableRowProps {
  row: ClientActivityRow;
  index: number;
}

export default function ClientActivityTableRow({ row, index }: ClientActivityTableRowProps) {
  return (
    <motion.tr
      initial={{ opacity: 0 }}
      whileInView={{ opacity: 1 }}
      viewport={{ once: true, amount: 0.2 }}
      transition={{ duration: 0.2, delay: index * 0.01 }}
      className="border-t border-white/10 hover:bg-white/[0.035]"
    >
      <td className="px-5 py-3">
        <p className="text-base font-medium text-white">{row.clientName}</p>
        <p className="text-sm text-white">{row.clientId}</p>
      </td>
      <td className="px-3 py-3 text-center text-base text-white">{row.openPositions}</td>
      <td className="px-3 py-3 text-center text-base text-white">{row.totalSeats}</td>
      <td className="px-3 py-3 text-center text-base text-emerald-200">{row.filled}</td>
      <td className="px-3 py-3 text-center text-base text-yellow">{row.remaining}</td>
      <td className="px-3 py-3 text-center text-base text-white">{row.inPipeline}</td>
      <td className="px-5 py-3 text-center text-base text-white">{row.joined}</td>
    </motion.tr>
  );
}
