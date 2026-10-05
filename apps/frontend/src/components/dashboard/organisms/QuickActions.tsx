"use client";

import { useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import {
  IconBriefcase,
  IconChevronRight,
  IconLayoutKanban,
  IconTrophy,
  IconUserPlus,
  IconUsers,
} from "@tabler/icons-react";
import { DASHBOARD_PANEL_CLASS } from "@/components/common/constants/dashboard-constants";
import AddLeadDialog from "@/components/leads/AddLeadDialog";
import AddPositionModal from "@/components/positions/AddPositionModal";
import { apiErrorMessage, useApiFetch } from "@/lib/api";
import { getPositionFilters } from "@/lib/api/positions";
import { useToast } from "@/components/ui/Toast";
import { cn } from "@/lib/utils";
import type { ApiPositionFilters } from "@/types";

const ITEM =
  "group flex w-full items-center gap-3 rounded-lg border border-border px-4 py-3 text-left transition-colors hover:border-yellow/40 hover:bg-yellow/5";

function Item({
  icon: Icon,
  label,
  hint,
}: Readonly<{ icon: typeof IconUsers; label: string; hint: string }>) {
  return (
    <>
      <span className="flex size-9 shrink-0 items-center justify-center rounded-lg bg-yellow/10 text-yellow">
        <Icon className="size-4.5" />
      </span>
      <span className="min-w-0 flex-1">
        <span className="block text-sm font-semibold text-text-primary">{label}</span>
        <span className="block truncate text-xs text-text-secondary">{hint}</span>
      </span>
      <IconChevronRight className="size-4 shrink-0 text-text-muted transition-transform group-hover:translate-x-0.5" />
    </>
  );
}

/**
 * A recruiter's shortcuts, where the team-wide line graph sits for managers.
 *
 * The add actions open the same dialogs as their own pages; when one saves,
 * the dashboard re-reads its (recruiter-scoped) numbers.
 */
export default function QuickActions() {
  const router = useRouter();
  const apiFetch = useApiFetch();
  const toast = useToast();
  const [addingLead, setAddingLead] = useState(false);
  const [positionFilters, setPositionFilters] = useState<ApiPositionFilters | null>(null);
  const [addingPosition, setAddingPosition] = useState(false);

  async function openAddPosition() {
    setAddingPosition(true);
    if (positionFilters) return;
    try {
      setPositionFilters(await getPositionFilters(apiFetch));
    } catch (err) {
      toast(apiErrorMessage(err, "Couldn't load clients for the position form."), "error");
    }
  }

  return (
    <section
      aria-labelledby="quick-actions-heading"
      className={cn(DASHBOARD_PANEL_CLASS, "flex h-full flex-col p-5")}
    >
      <h2 id="quick-actions-heading" className="font-heading text-xl text-text-primary">
        Quick actions
      </h2>
      <p className="mt-1 text-sm text-text-secondary">The things you do most, one click away.</p>

      <div className="mt-4 grid flex-1 grid-cols-1 content-start gap-2.5 sm:grid-cols-2">
        <button type="button" className={ITEM} onClick={() => setAddingLead(true)}>
          <Item icon={IconUserPlus} label="Add lead" hint="From resumes or by hand" />
        </button>
        <button type="button" className={ITEM} onClick={openAddPosition}>
          <Item icon={IconBriefcase} label="Add position" hint="Open a role for a client" />
        </button>
        <Link href="/candidates?add=1" className={ITEM}>
          <Item icon={IconUsers} label="Add candidate" hint="Straight into the talent pool" />
        </Link>
        <Link href="/pipeline" className={ITEM}>
          <Item icon={IconLayoutKanban} label="Go to pipeline" hint="Move your candidates on" />
        </Link>
        <Link href="/leaderboard" className={ITEM}>
          <Item icon={IconTrophy} label="Check leaderboard" hint="See where you stand" />
        </Link>
      </div>

      {addingLead && (
        <AddLeadDialog onClose={() => setAddingLead(false)} onAdded={() => router.refresh()} />
      )}
      <AddPositionModal
        isOpen={addingPosition}
        onClose={() => setAddingPosition(false)}
        filters={positionFilters}
        onCreated={(position) => {
          toast(`Position "${position.role}" created`, "success");
          router.refresh();
        }}
      />
    </section>
  );
}
