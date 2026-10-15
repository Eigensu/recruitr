"use client";

import { useEffect, useState } from "react";
import { IconNote } from "@tabler/icons-react";
import { useApiFetch } from "@/lib/api";
import { getScreeningNotes } from "@/lib/api/candidates";
import type { IntakeNote } from "@/lib/api/intake";
import { ScreeningNoteList } from "@/components/leads/LeadNotes";

/**
 * Everything the people who screened this candidate wrote, telecaller to
 * recruiter, for whoever is about to speak to them. Read-only, and quiet when
 * there is nothing: most candidates were added by hand and have no notes.
 *
 * Keyed by candidate where it is used, so switching candidates remounts it
 * rather than showing the last one's notes under the new name.
 */
export default function ScreeningNotes({ candidateId }: Readonly<{ candidateId: string }>) {
  const apiFetch = useApiFetch();
  const [notes, setNotes] = useState<IntakeNote[] | null>(null);

  useEffect(() => {
    let cancelled = false;
    getScreeningNotes(apiFetch, candidateId)
      .then((data) => {
        if (!cancelled) setNotes(data);
      })
      .catch(() => {
        // A section that cannot load is left out; the rest of the drawer is fine.
        if (!cancelled) setNotes([]);
      });
    return () => {
      cancelled = true;
    };
  }, [apiFetch, candidateId]);

  if (!notes || notes.length === 0) return null;
  return (
    <>
      <div className="h-px bg-border/50" />
      <section>
        <div className="mb-3 flex items-center gap-1.5">
          <IconNote className="size-3.5 text-text-muted opacity-60" />
          <h3 className="text-[10px] font-bold uppercase tracking-widest text-text-muted">
            Screening notes
          </h3>
        </div>
        <ScreeningNoteList notes={notes} />
      </section>
    </>
  );
}
