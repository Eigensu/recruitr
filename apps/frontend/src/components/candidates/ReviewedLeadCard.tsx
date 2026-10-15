"use client";

import {
  IconBriefcase,
  IconCircleCheck,
  IconMapPin,
  IconNote,
  IconPhone,
  IconSchool,
  IconUser,
} from "@tabler/icons-react";
import LeadCvLink from "@/components/leads/LeadCvLink";
import type { IntakeLead } from "@/lib/api/intake";

interface Props {
  lead: IntakeLead;
  /** Show whose lead this is — on for maintainers, who see every recruiter's. */
  showRecruiter: boolean;
  onViewProfile: () => void;
}

function Meta({
  icon: Icon,
  children,
}: Readonly<{ icon: typeof IconMapPin; children: React.ReactNode }>) {
  if (!children) return null;
  return (
    <span className="inline-flex items-center gap-1.5 text-xs text-text-secondary">
      <Icon className="size-3.5 shrink-0 text-text-muted" />
      {children}
    </span>
  );
}

function acceptedOn(iso: string | null): string | null {
  if (!iso) return null;
  return new Date(iso).toLocaleDateString(undefined, {
    day: "numeric",
    month: "short",
    year: "numeric",
  });
}

/**
 * One lead in the Candidates page's REVIEWED tab: a recruiter accepted them from
 * the Review tab. Read-only — the decision is made, so there is nothing to act on
 * here; the name opens the candidate's profile.
 */
export default function ReviewedLeadCard({ lead, showRecruiter, onViewProfile }: Readonly<Props>) {
  const accepted = acceptedOn(lead.recruiter_accepted_at);
  // One string, so Meta's emptiness check sees an empty row as empty.
  const work = [lead.current_role, lead.experience_years > 0 && `${lead.experience_years} yrs`]
    .filter(Boolean)
    .join(" · ");

  return (
    <article className="flex flex-col rounded-xl border border-border bg-surface p-4 shadow-sm">
      <header className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <button
            type="button"
            onClick={onViewProfile}
            className="block max-w-full truncate text-left font-heading text-lg font-bold text-text-primary hover:underline"
          >
            {lead.full_name}
          </button>
          {lead.role_interest && (
            <p className="mt-0.5 truncate text-sm text-text-secondary">
              Interested in {lead.role_interest}
            </p>
          )}
        </div>
        <span className="inline-flex shrink-0 items-center gap-1 rounded-full border border-emerald-500/20 bg-emerald-500/10 px-2 py-1 text-[11px] font-semibold text-emerald-500">
          <IconCircleCheck className="size-3" />
          {accepted ? `Reviewed ${accepted}` : "Reviewed"}
        </span>
      </header>

      <div className="mt-3 flex flex-wrap gap-x-4 gap-y-1.5">
        {lead.phone && (
          <a
            href={`tel:${lead.phone}`}
            className="inline-flex items-center gap-1.5 text-xs font-semibold text-text-primary hover:underline"
          >
            <IconPhone className="size-3.5 shrink-0 text-text-muted" />
            {lead.phone}
          </a>
        )}
        <LeadCvLink lead={lead} />
        <Meta icon={IconMapPin}>{lead.city}</Meta>
        <Meta icon={IconBriefcase}>{work}</Meta>
        <Meta icon={IconSchool}>{lead.education}</Meta>
        {showRecruiter && <Meta icon={IconUser}>{lead.recruiter_name ?? "—"}</Meta>}
      </div>

      {lead.telecaller_notes && (
        <p className="mt-3 rounded-lg border border-border bg-canvas p-2.5 text-xs text-text-secondary">
          <IconNote className="mr-1 inline size-3.5 text-text-muted" />
          <span className="font-semibold">
            {lead.telecaller_name ? `${lead.telecaller_name}: ` : "Telecaller: "}
          </span>
          {lead.telecaller_notes}
        </p>
      )}
    </article>
  );
}
