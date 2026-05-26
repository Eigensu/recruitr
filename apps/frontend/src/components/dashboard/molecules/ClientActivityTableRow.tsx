"use client";

import { motion } from "motion/react";
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
      className="hover:bg-white/[0.035]"
      style={{ color: "var(--color-text-primary)" }}
    >
      <td className="px-5 py-3">
        <p className="text-base font-medium">{row.clientName}</p>
        <p className="text-sm" style={{ opacity: 0.5 }}>
          {row.clientId}
        </p>
      </td>
      <td className="px-3 py-3 text-center text-base">{row.openPositions}</td>
      <td className="px-3 py-3 text-center text-base">{row.totalSeats}</td>
      <td className="px-3 py-3 text-center text-base text-emerald-400">{row.filled}</td>
      <td className="px-3 py-3 text-center text-base text-yellow">{row.remaining}</td>
      <td className="px-3 py-3 text-center text-base">{row.inPipeline}</td>
      <td className="px-5 py-3 text-center text-base">{row.joined}</td>
    </motion.tr>
  );
}
