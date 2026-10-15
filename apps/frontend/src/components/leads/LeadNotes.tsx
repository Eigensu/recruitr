"use client";

import { useState } from "react";
import { IconLoader2, IconNote } from "@tabler/icons-react";
import { apiErrorMessage, useApiFetch } from "@/lib/api";
import { useToast } from "@/components/ui/Toast";
import {
  addLeadNote,
  fetchLeadNotes,
  type IntakeNote,
  type IntakeNoteStage,
} from "@/lib/api/intake";
import { cn } from "@/lib/utils";

const STAGE_LABELS: Record<IntakeNoteStage, string> = {
  telecaller: "Telecaller",
  review: "Review",
  recruiter: "Recruiter",
};

const STAGE_STYLES: Record<IntakeNoteStage, string> = {
  telecaller: "border-sky-500/20 bg-sky-500/10 text-sky-500",
  review: "border-amber-500/20 bg-amber-500/10 text-amber-500",
  recruiter: "border-emerald-500/20 bg-emerald-500/10 text-emerald-500",
};

function stamp(iso: string): string {
  return new Date(iso).toLocaleString("en-IN", {
    day: "numeric",
    month: "short",
    hour: "numeric",
    minute: "2-digit",
  });
}

/**
 * The notes, oldest first, each with who wrote it, at which stage and when.
 * Read-only: the log is append-only, so there is nothing here to edit or remove.
 */
export function ScreeningNoteList({ notes }: Readonly<{ notes: IntakeNote[] }>) {
  return (
    <ol className="space-y-1.5">
      {notes.map((note) => (
        <li
          key={note.id}
          className="rounded-lg border border-border bg-canvas px-2.5 py-1.5 text-xs text-text-secondary"
        >
          <div className="flex flex-wrap items-center gap-x-2 gap-y-1">
            <span
              className={cn(
                "rounded-full border px-1.5 py-0.5 text-[10px] font-semibold",
                STAGE_STYLES[note.stage],
              )}
            >
              {STAGE_LABELS[note.stage]}
            </span>
            <span className="font-semibold text-text-primary">{note.author_name ?? "Someone"}</span>
            <span className="text-text-muted">{stamp(note.created_at)}</span>
          </div>
          <p className="mt-1 whitespace-pre-wrap break-words">{note.body}</p>
        </li>
      ))}
    </ol>
  );
}

/**
 * A lead's screening notes, with a box to add one.
 *
 * Collapsed until opened, and fetched then rather than for every card in a list.
 * A note is saved with who wrote it and the stage the lead is at; the server
 * decides both, and decides who may write (`canWrite` only hides the box from
 * people it would refuse).
 */
export default function LeadNotes({
  leadId,
  canWrite = true,
}: Readonly<{ leadId: string; canWrite?: boolean }>) {
  const apiFetch = useApiFetch();
  const toast = useToast();
  const [open, setOpen] = useState(false);
  const [notes, setNotes] = useState<IntakeNote[] | null>(null);
  const [draft, setDraft] = useState("");
  const [saving, setSaving] = useState(false);

  async function load() {
    try {
      setNotes(await fetchLeadNotes(apiFetch, leadId));
    } catch (err) {
      toast(apiErrorMessage(err, "Could not load the notes."), "error");
    }
  }

  function toggle() {
    const next = !open;
    setOpen(next);
    if (next && notes === null) void load();
  }

  async function save() {
    const body = draft.trim();
    if (!body) return;
    setSaving(true);
    try {
      const saved = await addLeadNote(apiFetch, leadId, body);
      // Appended to what is on screen, not refetched: the log is append-only, so
      // the new note is the last one, and a refetch could race a second save.
      setNotes((prev) => [...(prev ?? []), saved]);
      setDraft("");
    } catch (err) {
      // The draft stays in the box.
      toast(apiErrorMessage(err, "Could not save that note."), "error");
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="mt-2">
      <button
        type="button"
        onClick={toggle}
        className="inline-flex items-center gap-1 text-xs font-medium text-text-muted underline-offset-2 hover:text-text-secondary hover:underline"
      >
        <IconNote className="size-3.5" />
        {open ? "Hide screening notes" : "Screening notes"}
        {!open && notes !== null && notes.length > 0 && ` (${notes.length})`}
      </button>
      {open && (
        <div className="mt-1.5 space-y-2">
          {notes === null && <p className="text-xs text-text-muted">Loading…</p>}
          {notes !== null && notes.length === 0 && (
            <p className="text-xs text-text-muted">No notes yet.</p>
          )}
          {notes !== null && notes.length > 0 && <ScreeningNoteList notes={notes} />}
          {canWrite && (
            <div>
              <textarea
                value={draft}
                onChange={(e) => setDraft(e.target.value)}
                rows={2}
                maxLength={2000}
                placeholder="Add a note for whoever speaks to them next…"
                aria-label="Screening note"
                className="w-full resize-none rounded-lg border border-border bg-canvas p-2.5 text-sm text-text-primary placeholder:text-text-muted focus:border-navy/40 focus:outline-none dark:focus:border-yellow/40"
              />
              <div className="mt-1.5 flex justify-end">
                <button
                  type="button"
                  disabled={saving || !draft.trim()}
                  onClick={save}
                  className="inline-flex items-center gap-1.5 rounded-lg bg-navy px-3 py-1.5 text-xs font-semibold text-white transition-opacity hover:opacity-90 disabled:opacity-50 dark:bg-yellow dark:text-navy"
                >
                  {saving && <IconLoader2 className="size-3.5 animate-spin" />}
                  Save note
                </button>
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
