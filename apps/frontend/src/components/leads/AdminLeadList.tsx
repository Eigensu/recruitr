"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import {
  IconAlertTriangle,
  IconChartBar,
  IconChevronLeft,
  IconChevronRight,
  IconLoader2,
  IconRefresh,
  IconUserShare,
} from "@tabler/icons-react";
import { cn } from "@/lib/utils";
import { apiErrorMessage, useApiFetch } from "@/lib/api";
import { useToast } from "@/components/ui/Toast";
import ReassignDialog from "@/components/leads/ReassignDialog";
import {
  STATUS_LABELS,
  STATUS_STYLES,
  fetchAssignees,
  fetchLeads,
  elapsedHours,
  formatHours,
  syncNow,
  type IntakeAssignee,
  type IntakeLead,
  type IntakeLeadPage,
  type IntakeLeadStatus,
} from "@/lib/api/intake";

const STATUSES = Object.keys(STATUS_LABELS) as IntakeLeadStatus[];
const PAGE_SIZE = 25;

function waitingOn(lead: IntakeLead): { label: string; at: string | null } {
  if (lead.status === "pending_telecaller")
    return { label: lead.telecaller_name ?? "Unassigned", at: lead.telecaller_assigned_at };
  if (lead.status === "pending_recruiter")
    return { label: lead.recruiter_name ?? "Unassigned", at: lead.recruiter_assigned_at };
  return { label: lead.telecaller_name ?? "—", at: null };
}

export default function AdminLeadList({ isAdmin }: { readonly isAdmin: boolean }) {
  const apiFetch = useApiFetch();
  const toast = useToast();

  const [page, setPage] = useState(1);
  const [status, setStatus] = useState<string>("");
  const [overdue, setOverdue] = useState(false);
  const [telecallerId, setTelecallerId] = useState("");
  const [data, setData] = useState<IntakeLeadPage | null>(null);
  const [loading, setLoading] = useState(true);
  const [syncing, setSyncing] = useState(false);
  const [rosters, setRosters] = useState<{
    telecallers: IntakeAssignee[];
    recruiters: IntakeAssignee[];
  }>({ telecallers: [], recruiters: [] });
  const [reassigning, setReassigning] = useState<IntakeLead | null>(null);

  // Every filter change goes through this, which sets `loading` in the event
  // handler rather than in the effect below — setting it synchronously inside
  // an effect cascades a render, which is what react-hooks/set-state-in-effect
  // is about.
  function applyFilter(change: () => void) {
    setLoading(true);
    setPage(1);
    change();
  }

  const load = useCallback(
    (): Promise<void> =>
      fetchLeads(apiFetch, {
        page,
        limit: PAGE_SIZE,
        status: status || undefined,
        overdue: overdue || undefined,
        telecaller_id: telecallerId || undefined,
      })
        .then(setData)
        .catch((err: unknown) => {
          toast(apiErrorMessage(err, "Could not load leads."), "error");
        }),
    [apiFetch, page, status, overdue, telecallerId, toast],
  );

  useEffect(() => {
    let cancelled = false;
    load().finally(() => {
      if (!cancelled) setLoading(false);
    });
    return () => {
      cancelled = true;
    };
  }, [load]);

  useEffect(() => {
    fetchAssignees(apiFetch)
      .then(setRosters)
      .catch(() => {});
  }, [apiFetch]);

  async function handleSync() {
    setSyncing(true);
    try {
      const result = await syncNow(apiFetch);
      toast(result.detail, result.ran ? "success" : "info");
      if (result.ran) await load();
    } catch (err) {
      toast(apiErrorMessage(err, "Sync failed."), "error");
    } finally {
      setSyncing(false);
    }
  }

  const meta = data?.meta;

  return (
    <main className="mx-auto w-full max-w-7xl p-4 duration-300 animate-in fade-in sm:p-6 lg:p-8">
      <header className="mb-6 flex flex-wrap items-start justify-between gap-3">
        <div>
          <h1 className="font-heading text-2xl font-bold tracking-tight text-text-primary">
            Leads
          </h1>
          <p className="mt-1 text-sm text-text-secondary">
            {meta ? `${meta.total} inbound leads` : "Inbound candidates from lead ads"}
          </p>
        </div>
        <div className="flex items-center gap-2">
          <Link
            href="/leads/analytics"
            className="inline-flex items-center gap-1.5 rounded-lg border border-border px-3 py-2 text-sm text-text-secondary transition-colors hover:text-text-primary"
          >
            <IconChartBar className="size-4" />
            Analytics
          </Link>
          {isAdmin && (
            <button
              type="button"
              onClick={handleSync}
              disabled={syncing}
              className="inline-flex items-center gap-1.5 rounded-lg border border-border px-3 py-2 text-sm text-text-secondary transition-colors hover:text-text-primary disabled:opacity-60"
            >
              <IconRefresh className={cn("size-4", syncing && "animate-spin")} />
              Sync now
            </button>
          )}
        </div>
      </header>

      {/* Filters */}
      <div className="mb-4 flex flex-wrap items-center gap-2">
        <select
          value={status}
          onChange={(e) => applyFilter(() => setStatus(e.target.value))}
          className="rounded-lg border border-border bg-surface px-3 py-2 text-sm text-text-primary focus:outline-none"
        >
          <option value="">All statuses</option>
          {STATUSES.map((value) => (
            <option key={value} value={value}>
              {STATUS_LABELS[value]}
            </option>
          ))}
        </select>

        <select
          value={telecallerId}
          onChange={(e) => applyFilter(() => setTelecallerId(e.target.value))}
          className="rounded-lg border border-border bg-surface px-3 py-2 text-sm text-text-primary focus:outline-none"
        >
          <option value="">All telecallers</option>
          {rosters.telecallers.map((person) => (
            <option key={person.id} value={person.id}>
              {person.name}
            </option>
          ))}
        </select>

        <button
          type="button"
          onClick={() => applyFilter(() => setOverdue((v) => !v))}
          className={cn(
            "inline-flex items-center gap-1.5 rounded-lg border px-3 py-2 text-sm transition-colors",
            overdue
              ? "border-red-500/30 bg-red-500/10 text-red-400"
              : "border-border text-text-secondary hover:text-text-primary",
          )}
        >
          <IconAlertTriangle className="size-4" />
          Overdue only
        </button>
      </div>

      <div className="overflow-hidden rounded-xl border border-border bg-surface shadow-sm">
        <div className="overflow-x-auto">
          <table className="w-full min-w-[820px] text-left text-sm">
            <thead className="bg-surface text-text-secondary">
              <tr>
                <th className="border-b border-border p-3 font-semibold">Candidate</th>
                <th className="border-b border-border p-3 font-semibold">Status</th>
                <th className="border-b border-border p-3 font-semibold">With</th>
                <th className="border-b border-border p-3 font-semibold">Waiting</th>
                <th className="border-b border-border p-3 font-semibold">Campaign</th>
                <th className="border-b border-border p-3 font-semibold" />
              </tr>
            </thead>
            <tbody className="divide-y divide-border">
              {loading && (
                <tr>
                  <td colSpan={6} className="p-10 text-center">
                    <IconLoader2 className="mx-auto size-5 animate-spin text-text-muted" />
                  </td>
                </tr>
              )}
              {!loading && data?.items.length === 0 && (
                <tr>
                  <td colSpan={6} className="p-10 text-center text-text-muted">
                    No leads match these filters.
                  </td>
                </tr>
              )}
              {!loading &&
                data?.items.map((lead) => {
                  const owner = waitingOn(lead);
                  const waited = elapsedHours(owner.at);
                  const open =
                    lead.status === "pending_telecaller" ||
                    lead.status === "pending_recruiter" ||
                    lead.status === "unassigned";
                  return (
                    <tr key={lead.id} className="transition-colors hover:bg-canvas">
                      <td className="p-3">
                        <div className="font-medium text-text-primary">{lead.full_name}</div>
                        <div className="text-xs text-text-muted">
                          {lead.phone ?? "no number"}
                          {lead.city && ` · ${lead.city}`}
                        </div>
                      </td>
                      <td className="p-3">
                        <span
                          className={cn(
                            "inline-block whitespace-nowrap rounded-full border px-2 py-1 text-[11px] font-semibold",
                            STATUS_STYLES[lead.status],
                          )}
                        >
                          {STATUS_LABELS[lead.status]}
                        </span>
                      </td>
                      <td className="p-3 text-text-secondary">{owner.label}</td>
                      <td className="p-3">
                        {waited === null ? (
                          <span className="text-text-muted">—</span>
                        ) : (
                          <span
                            className={cn(
                              lead.overdue ? "font-semibold text-red-400" : "text-text-secondary",
                            )}
                          >
                            {formatHours(waited)}
                          </span>
                        )}
                      </td>
                      <td className="max-w-[200px] truncate p-3 text-text-secondary">
                        {lead.campaign_name ?? "—"}
                      </td>
                      <td className="p-3 text-right">
                        {open && (
                          <button
                            type="button"
                            onClick={() => setReassigning(lead)}
                            aria-label={`Reassign ${lead.full_name}`}
                            className="rounded-lg border border-border p-1.5 text-text-muted transition-colors hover:text-text-primary"
                          >
                            <IconUserShare className="size-4" />
                          </button>
                        )}
                      </td>
                    </tr>
                  );
                })}
            </tbody>
          </table>
        </div>
      </div>

      {meta && meta.pages > 1 && (
        <nav className="mt-4 flex items-center justify-between text-sm text-text-secondary">
          <span>
            Page {meta.page} of {meta.pages}
          </span>
          <div className="flex gap-2">
            <button
              type="button"
              disabled={!meta.has_prev}
              onClick={() => {
                setLoading(true);
                setPage((p) => p - 1);
              }}
              className="rounded-lg border border-border p-2 disabled:opacity-40"
            >
              <IconChevronLeft className="size-4" />
            </button>
            <button
              type="button"
              disabled={!meta.has_next}
              onClick={() => {
                setLoading(true);
                setPage((p) => p + 1);
              }}
              className="rounded-lg border border-border p-2 disabled:opacity-40"
            >
              <IconChevronRight className="size-4" />
            </button>
          </div>
        </nav>
      )}

      {reassigning && (
        <ReassignDialog
          lead={reassigning}
          // A lead waiting on a recruiter can only go to a recruiter: the
          // backend moves whichever leg is open, so offering the other roster
          // would silently hand it to the wrong person.
          people={
            reassigning.status === "pending_recruiter" ? rosters.recruiters : rosters.telecallers
          }
          onClose={() => setReassigning(null)}
          onDone={() => {
            setReassigning(null);
            load();
          }}
        />
      )}
    </main>
  );
}
