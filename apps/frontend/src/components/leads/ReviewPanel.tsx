"use client";

import { useCallback, useEffect, useState } from "react";
import {
  IconBriefcase,
  IconLoader2,
  IconMapPin,
  IconNote,
  IconRefresh,
  IconUsersGroup,
} from "@tabler/icons-react";
import { cn } from "@/lib/utils";
import { apiErrorMessage, useApiFetch } from "@/lib/api";
import { useToast } from "@/components/ui/Toast";
import {
  assignLeadsToTeam,
  elapsedHours,
  fetchLeads,
  fetchReviewTeams,
  formatHours,
  type IntakeLead,
  type IntakeTeamOption,
} from "@/lib/api/intake";

// The backend accepts up to 100 leads per assignment, so one page is one batch.
const PAGE_SIZE = 100;

function teamLabel(team: IntakeTeamOption): string {
  if (team.recruiters === 0) return `${team.name} — no recruiters`;
  const people = team.recruiters === 1 ? "recruiter" : "recruiters";
  return `${team.name} — ${team.recruiters} ${people}, ${team.open_leads} open`;
}

/**
 * Leads a telecaller has accepted, waiting for someone to pick a team.
 *
 * The reviewer chooses the team; the team's own round-robin chooses the
 * recruiter. That split is deliberate — the reviewer knows which desk suits
 * the candidate, and the rotation keeps work even inside it without anyone
 * having to track who had the last one.
 */
export default function ReviewPanel({
  onChanged,
  onOpen,
  opening,
}: {
  readonly onChanged?: () => void;
  /** Show the lead's full candidate profile. The parent owns the drawer. */
  readonly onOpen?: (lead: IntakeLead) => void;
  /** candidate_id of the profile being fetched, for a spinner on that row. */
  readonly opening?: string | null;
}) {
  const apiFetch = useApiFetch();
  const toast = useToast();

  const [leads, setLeads] = useState<IntakeLead[]>([]);
  const [total, setTotal] = useState(0);
  const [teams, setTeams] = useState<IntakeTeamOption[]>([]);
  const [loading, setLoading] = useState(true);
  const [loadFailed, setLoadFailed] = useState(false);
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [teamId, setTeamId] = useState("");
  const [assigning, setAssigning] = useState(false);

  const load = useCallback(
    (): Promise<void> =>
      Promise.all([
        fetchLeads(apiFetch, { status: "pending_review", limit: PAGE_SIZE }),
        fetchReviewTeams(apiFetch),
      ])
        .then(([page, options]) => {
          setLoadFailed(false);
          setLeads(page.items);
          setTotal(page.meta.total);
          setTeams(options);
          // Drop anything someone else assigned since it was ticked.
          setSelected((prev) => new Set(page.items.map((l) => l.id).filter((id) => prev.has(id))));
        })
        .catch((err: unknown) => {
          setLoadFailed(true);
          toast(apiErrorMessage(err, "Could not load the review list."), "error");
        }),
    [apiFetch, toast],
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

  function toggle(id: string) {
    setSelected((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }

  const allSelected = leads.length > 0 && selected.size === leads.length;
  const team = teams.find((t) => t.id === teamId);

  async function assign() {
    if (!team || selected.size === 0) return;
    setAssigning(true);
    try {
      const result = await assignLeadsToTeam(apiFetch, [...selected], team.id);
      const moved = result.assigned.length;
      const skipped = result.skipped.length;
      toast(
        skipped
          ? `${moved} assigned to ${team.name}. ${skipped} had already been assigned.`
          : `${moved} assigned to ${team.name}.`,
        "success",
      );
      setSelected(new Set());
      await load();
      onChanged?.();
    } catch (err) {
      toast(apiErrorMessage(err, "Could not assign those leads."), "error");
    } finally {
      setAssigning(false);
    }
  }

  if (loading) {
    return (
      <div className="flex h-48 items-center justify-center">
        <IconLoader2 className="size-5 animate-spin text-text-muted" />
      </div>
    );
  }

  return (
    <section className="flex flex-col gap-3">
      <div className="flex flex-wrap items-center gap-2 rounded-xl border border-border bg-surface p-3">
        <label className="flex items-center gap-2 text-sm text-text-secondary">
          <input
            type="checkbox"
            checked={allSelected}
            disabled={leads.length === 0}
            onChange={() =>
              setSelected(allSelected ? new Set() : new Set(leads.map((lead) => lead.id)))
            }
            className="size-4 accent-current"
          />
          {selected.size > 0 ? `${selected.size} selected` : "Select all"}
        </label>

        <div className="ml-auto flex flex-wrap items-center gap-2">
          <select
            value={teamId}
            onChange={(e) => setTeamId(e.target.value)}
            aria-label="Team"
            className="rounded-lg border border-border bg-surface px-3 py-2 text-sm text-text-primary focus:outline-none"
          >
            <option value="">Choose a team…</option>
            {teams.map((option) => (
              <option key={option.id} value={option.id} disabled={option.recruiters === 0}>
                {teamLabel(option)}
              </option>
            ))}
          </select>
          <button
            type="button"
            onClick={assign}
            disabled={!team || selected.size === 0 || assigning}
            className="inline-flex items-center gap-1.5 rounded-lg bg-navy px-3 py-2 text-sm font-semibold text-white transition-colors hover:bg-navy/90 disabled:opacity-50 dark:bg-yellow dark:text-navy dark:hover:bg-yellow/90"
          >
            {assigning ? (
              <IconLoader2 className="size-4 animate-spin" />
            ) : (
              <IconUsersGroup className="size-4" />
            )}
            Assign{selected.size > 0 ? ` ${selected.size}` : ""}
          </button>
          <button
            type="button"
            onClick={() => load()}
            aria-label="Refresh"
            className="rounded-lg border border-border p-2 text-text-muted transition-colors hover:text-text-primary"
          >
            <IconRefresh className="size-4" />
          </button>
        </div>
      </div>

      {teams.length === 0 && !loadFailed && !loading && (
        <p className="rounded-lg border border-orange-500/20 bg-orange-500/10 px-3 py-2 text-sm text-orange-400">
          There are no active teams yet. Create one and add recruiters to it under Settings → Team.
        </p>
      )}

      {loadFailed && leads.length === 0 ? (
        <div className="flex flex-col items-center justify-center gap-2 rounded-xl border border-dashed border-red-500/30 py-16 text-center">
          <p className="text-sm text-red-400">
            Could not load the review list. Use Refresh to try again.
          </p>
        </div>
      ) : leads.length === 0 ? (
        <div className="flex flex-col items-center justify-center gap-2 rounded-xl border border-dashed border-border py-16 text-center">
          <IconUsersGroup className="size-8 text-text-secondary" />
          <p className="text-sm text-text-secondary">
            Nothing waiting for review. Leads appear here once a telecaller accepts them.
          </p>
        </div>
      ) : (
        <ul className="flex flex-col gap-2">
          {leads.map((lead) => {
            const waited = elapsedHours(lead.telecaller_actioned_at);
            const checked = selected.has(lead.id);
            return (
              <li key={lead.id}>
                <label
                  className={cn(
                    "flex cursor-pointer items-start gap-3 rounded-xl border bg-surface p-3 transition-colors",
                    checked ? "border-navy/40 dark:border-yellow/40" : "border-border",
                  )}
                >
                  <input
                    type="checkbox"
                    checked={checked}
                    onChange={() => toggle(lead.id)}
                    className="mt-1 size-4 shrink-0 accent-current"
                  />
                  <div className="min-w-0 flex-1">
                    <div className="flex flex-wrap items-baseline justify-between gap-x-3 gap-y-1">
                      {onOpen ? (
                        // The row is a <label> for the checkbox; preventDefault
                        // keeps opening the profile from also selecting the lead.
                        <button
                          type="button"
                          onClick={(e) => {
                            e.preventDefault();
                            onOpen(lead);
                          }}
                          className="inline-flex items-center gap-1.5 text-left font-medium text-text-primary underline-offset-2 hover:underline focus:outline-none focus-visible:underline"
                        >
                          {lead.full_name}
                          {opening === lead.candidate_id && (
                            <IconLoader2 className="size-3.5 animate-spin text-text-muted" />
                          )}
                        </button>
                      ) : (
                        <span className="font-medium text-text-primary">{lead.full_name}</span>
                      )}
                      <span className="text-xs text-text-muted">
                        {lead.telecaller_name ? `Screened by ${lead.telecaller_name}` : "Screened"}
                        {waited !== null && ` · ${formatHours(waited)} ago`}
                      </span>
                    </div>
                    <div className="mt-1 flex flex-wrap gap-x-4 gap-y-1 text-xs text-text-secondary">
                      {lead.phone && <span>{lead.phone}</span>}
                      {lead.city && (
                        <span className="inline-flex items-center gap-1">
                          <IconMapPin className="size-3.5 text-text-muted" />
                          {lead.city}
                        </span>
                      )}
                      {lead.current_role && (
                        <span className="inline-flex items-center gap-1">
                          <IconBriefcase className="size-3.5 text-text-muted" />
                          {lead.current_role}
                          {lead.experience_years > 0 && ` · ${lead.experience_years} yrs`}
                        </span>
                      )}
                      {/* role_interest is the candidate's specialization, which the
                          telecaller set on the accept form — not the ad's free text. */}
                      {lead.role_interest && <span>Specialization: {lead.role_interest}</span>}
                      <span className="text-text-muted">
                        {lead.source === "public_form"
                          ? "Application"
                          : (lead.source_channel ?? "Lead ad")}
                      </span>
                    </div>
                    {lead.telecaller_notes && (
                      <p className="mt-1.5 flex gap-1.5 text-xs text-text-secondary">
                        <IconNote className="mt-px size-3.5 shrink-0 text-text-muted" />
                        <span className="line-clamp-2">{lead.telecaller_notes}</span>
                      </p>
                    )}
                  </div>
                </label>
              </li>
            );
          })}
        </ul>
      )}

      {total > leads.length && (
        <p className="text-center text-xs text-text-muted">
          Showing the {leads.length} most recent of {total}. Assign these to see the rest.
        </p>
      )}
    </section>
  );
}
