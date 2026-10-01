"use client";

import { useCallback, useEffect, useState } from "react";
import { IconFileSpreadsheet, IconLoader2 } from "@tabler/icons-react";
import { cn } from "@/lib/utils";
import { apiErrorMessage, useApiFetch } from "@/lib/api";
import { useToast } from "@/components/ui/Toast";
import {
  listSubmittedLeads,
  STATUS_LABELS,
  STATUS_STYLES,
  type IntakeLead,
} from "@/lib/api/intake";
import NaukriImportDialog from "@/components/leads/NaukriImportDialog";

/**
 * The Leads page for a recruiter: put people in, and see where they went.
 *
 * Recruiters don't work the queue or see everyone's leads — that is the
 * telecallers' and maintainers' — so this shows only what they submitted, each
 * with its current step (awaiting a call, in review, with a recruiter, …).
 */
export default function RecruiterLeads() {
  const apiFetch = useApiFetch();
  const toast = useToast();
  const [leads, setLeads] = useState<IntakeLead[] | null>(null);
  const [importing, setImporting] = useState(false);

  const load = useCallback(
    () =>
      listSubmittedLeads(apiFetch)
        .then(setLeads)
        .catch((err: unknown) => {
          setLeads([]);
          toast(apiErrorMessage(err, "Could not load your leads."), "error");
        }),
    [apiFetch, toast],
  );

  useEffect(() => {
    load();
  }, [load]);

  return (
    <div className="mx-auto w-full max-w-7xl p-4 duration-300 animate-in fade-in sm:p-6 lg:p-8">
      <header className="mb-6 flex flex-wrap items-start justify-between gap-3">
        <div>
          <h1 className="font-heading text-2xl font-bold tracking-tight text-text-primary">
            Leads
          </h1>
          <p className="mt-1 text-sm text-text-secondary">
            People you&apos;ve put in. Telecallers call each one before a recruiter is assigned.
          </p>
        </div>
        <button
          type="button"
          onClick={() => setImporting(true)}
          className="inline-flex items-center gap-1.5 rounded-lg bg-yellow px-3 py-2 text-sm font-semibold text-navy"
        >
          <IconFileSpreadsheet className="size-4" />
          Import Naukri file
        </button>
      </header>

      <section aria-labelledby="my-leads-heading">
        <h2
          id="my-leads-heading"
          className="mb-3 text-xs font-semibold uppercase tracking-wider text-text-muted"
        >
          My submitted leads {leads && leads.length > 0 && `(${leads.length})`}
        </h2>

        {leads === null ? (
          <div className="flex h-40 items-center justify-center">
            <IconLoader2 className="size-5 animate-spin text-text-muted" />
          </div>
        ) : leads.length === 0 ? (
          <p className="rounded-xl border border-dashed border-border px-6 py-10 text-center text-sm text-text-muted">
            Nothing yet. Import a Naukri export to add people as leads.
          </p>
        ) : (
          <div className="overflow-x-auto rounded-xl border border-border">
            <table className="w-full text-left text-sm">
              <thead className="bg-surface-2 text-xs text-text-muted">
                <tr>
                  <th className="px-4 py-2.5 font-medium">Name</th>
                  <th className="px-4 py-2.5 font-medium">Phone</th>
                  <th className="px-4 py-2.5 font-medium">Current role</th>
                  <th className="px-4 py-2.5 font-medium">Source</th>
                  <th className="px-4 py-2.5 font-medium">Status</th>
                  <th className="px-4 py-2.5 font-medium">With</th>
                  <th className="px-4 py-2.5 font-medium">Added</th>
                </tr>
              </thead>
              <tbody>
                {leads.map((lead) => (
                  <tr key={lead.id} className="border-t border-border">
                    <td className="px-4 py-2.5 text-text-primary">{lead.full_name}</td>
                    <td className="px-4 py-2.5 text-text-secondary tabular-nums">
                      {lead.phone ?? "—"}
                    </td>
                    <td className="px-4 py-2.5 text-text-secondary">{lead.current_role ?? "—"}</td>
                    <td className="px-4 py-2.5 text-text-secondary">
                      {lead.source_channel ?? "—"}
                    </td>
                    <td className="px-4 py-2.5">
                      <span
                        className={cn(
                          "inline-block whitespace-nowrap rounded-full border px-2 py-0.5 text-xs",
                          STATUS_STYLES[lead.status],
                        )}
                      >
                        {STATUS_LABELS[lead.status]}
                      </span>
                    </td>
                    <td className="px-4 py-2.5 text-text-secondary">
                      {lead.recruiter_name ?? lead.team_name ?? lead.telecaller_name ?? "—"}
                    </td>
                    <td className="px-4 py-2.5 text-text-muted tabular-nums">
                      {new Date(lead.ingested_at).toLocaleDateString("en-IN")}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>

      {importing && (
        <NaukriImportDialog onClose={() => setImporting(false)} onImported={() => load()} />
      )}
    </div>
  );
}
