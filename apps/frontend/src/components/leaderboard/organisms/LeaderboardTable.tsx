"use client";

import { useState, useMemo } from "react";
import { motion } from "motion/react";
import { LeaderboardTableRow } from "@/components/leaderboard/molecules/LeaderboardTableRow";
import {
  DASHBOARD_PANEL_CLASS,
  DASHBOARD_TABLE_HEADER_CLASS,
} from "@/components/common/constants/dashboard-constants";
import { cn } from "@/lib/utils";
import type { LeaderboardRecruiter } from "@/lib/leaderboard-data";

type SortKey =
  | "rank"
  | "name"
  | "totalMappings"
  | "offersReceived"
  | "joined"
  | "rejected"
  | "successRate"
  | "monthlyGrowth";

interface LeaderboardTableProps {
  recruiters: LeaderboardRecruiter[];
}

const COLUMNS: { key: SortKey; label: string; className: string }[] = [
  { key: "rank", label: "Rank", className: "w-14 px-4 py-3 text-left" },
  { key: "name", label: "Recruiter", className: "px-4 py-3 text-left" },
  {
    key: "totalMappings",
    label: "Mappings",
    className: "px-4 py-3 text-center hidden sm:table-cell",
  },
  {
    key: "offersReceived",
    label: "Offers",
    className: "px-4 py-3 text-center hidden md:table-cell",
  },
  { key: "joined", label: "Joined", className: "px-4 py-3 text-center hidden lg:table-cell" },
  { key: "rejected", label: "Rejected", className: "px-4 py-3 text-center hidden xl:table-cell" },
  {
    key: "successRate",
    label: "Success %",
    className: "px-4 py-3 text-center w-32 hidden xl:table-cell",
  },
  {
    key: "monthlyGrowth",
    label: "Growth",
    className: "px-4 py-3 text-center hidden 2xl:table-cell",
  },
  { key: "rank", label: "Badge", className: "px-4 py-3 text-center" },
];

export function LeaderboardTable({ recruiters }: LeaderboardTableProps) {
  const [sortKey, setSortKey] = useState<SortKey>("rank");
  const [sortDir, setSortDir] = useState<"asc" | "desc">("asc");

  const sorted = useMemo(() => {
    return [...recruiters].sort((a, b) => {
      const left = a[sortKey];
      const right = b[sortKey];

      if (typeof left === "string" && typeof right === "string") {
        return sortDir === "asc" ? left.localeCompare(right) : right.localeCompare(left);
      }

      const diff = Number(left) - Number(right);
      return sortDir === "asc" ? diff : -diff;
    });
  }, [recruiters, sortKey, sortDir]);

  function handleSort(key: SortKey) {
    if (key === sortKey) {
      setSortDir((d) => (d === "asc" ? "desc" : "asc"));
    } else {
      setSortKey(key);
      setSortDir("asc");
    }
  }

  return (
    <motion.section
      initial={{ opacity: 0, y: 18 }}
      whileInView={{ opacity: 1, y: 0 }}
      viewport={{ once: true, amount: 0.08 }}
      transition={{ duration: 0.45, ease: "easeOut" }}
      className={cn(DASHBOARD_PANEL_CLASS, "overflow-hidden")}
    >
      {/* Header */}
      <div className="flex flex-wrap items-start justify-between gap-3 border-b border-white/10 px-5 py-4">
        <div>
          <h2 className="font-heading text-xl text-white">Recruiter Leaderboard</h2>
          <p className="mt-1 text-sm text-white/50">
            Click any row to expand stats · Click columns to sort
          </p>
        </div>
        <span className="rounded-full bg-yellow/15 border border-yellow/30 px-3 py-1 text-xs font-bold text-yellow">
          {recruiters.length} Active
        </span>
      </div>

      <div className="overflow-x-auto dashboard-scrollbar">
        <table className="min-w-full border-collapse">
          <thead className="sticky top-0 z-10 bg-[#0b1220]/95 backdrop-blur">
            <tr>
              {COLUMNS.map((col, i) => (
                <th
                  key={i}
                  aria-sort={
                    sortKey !== col.key ? "none" : sortDir === "asc" ? "ascending" : "descending"
                  }
                  className={cn(DASHBOARD_TABLE_HEADER_CLASS, col.className, "select-none")}
                >
                  <button
                    type="button"
                    onClick={() => handleSort(col.key)}
                    className={cn(
                      "flex items-center gap-1 rounded-sm cursor-pointer hover:text-white/70 transition-colors focus:outline-none focus-visible:ring-2 focus-visible:ring-yellow focus-visible:ring-offset-2 focus-visible:ring-offset-[#0b1220]",
                      col.className,
                    )}
                  >
                    <span>{col.label}</span>
                    {sortKey === col.key && (
                      <span className="text-yellow">{sortDir === "asc" ? "↑" : "↓"}</span>
                    )}
                  </button>
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {sorted.map((recruiter, index) => (
              <LeaderboardTableRow key={recruiter.id} recruiter={recruiter} index={index} />
            ))}
          </tbody>
        </table>
      </div>
    </motion.section>
  );
}
