import { IconBuildingStore } from "@tabler/icons-react";
import {
  DASHBOARD_PANEL_CLASS,
  DASHBOARD_TABLE_HEADER_CLASS,
} from "@/components/common/constants/dashboard-constants";
import { cn } from "@/lib/utils";
import type { ClientProfileRow, ClientProfileStatus } from "@/types/dashboard";

interface Props {
  rows: ClientProfileRow[];
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
    <section
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
          {rows.length} clients
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
                  "w-[26%] px-4 py-3 text-left text-base",
                )}
              >
                Client
              </th>
              <th
                className={cn(
                  DASHBOARD_TABLE_HEADER_CLASS,
                  "w-[14%] px-2 py-3 text-center text-base",
                )}
              >
                Open Positions
              </th>
              <th
                className={cn(
                  DASHBOARD_TABLE_HEADER_CLASS,
                  "w-[12%] px-2 py-3 text-center text-base",
                )}
              >
                Candidates
              </th>
              <th
                className={cn(
                  DASHBOARD_TABLE_HEADER_CLASS,
                  "w-[16%] px-2 py-3 text-center text-base",
                )}
              >
                Active Recruiters
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
                  "w-[16%] px-4 py-3 text-center text-base",
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
              rows.map((row) => {
                const st = STATUS_STYLES[row.status] ?? STATUS_STYLES.closed;
                return (
                  <tr
                    key={row.client_name}
                    className="border-t"
                    style={{ borderColor: "var(--color-border-val)" }}
                  >
                    <td className="px-4 py-3 text-left font-semibold">{row.client_name}</td>
                    <td className="px-2 py-3 text-center tabular-nums">
                      {row.total_open_positions}
                    </td>
                    <td className="px-2 py-3 text-center tabular-nums">{row.total_candidates}</td>
                    <td className="px-2 py-3 text-center tabular-nums">{row.active_recruiters}</td>
                    <td
                      className="px-2 py-3 text-center"
                      style={{ color: "var(--color-text-secondary)" }}
                    >
                      {formatTimeAgo(row.last_activity)}
                    </td>
                    <td className="px-4 py-3 text-center">
                      <span
                        className="inline-block rounded-full px-2.5 py-0.5 text-xs font-medium"
                        style={{ background: st.bg, color: st.color }}
                      >
                        {st.label}
                      </span>
                    </td>
                  </tr>
                );
              })
            )}
          </tbody>
        </table>
      </div>
    </section>
  );
}
