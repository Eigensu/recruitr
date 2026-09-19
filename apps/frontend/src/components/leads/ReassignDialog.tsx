"use client";

import { useState } from "react";
import { motion } from "motion/react";
import { IconLoader2, IconX } from "@tabler/icons-react";
import { cn } from "@/lib/utils";
import { apiErrorMessage, useApiFetch } from "@/lib/api";
import { useToast } from "@/components/ui/Toast";
import { reassignLead, type IntakeAssignee, type IntakeLead } from "@/lib/api/intake";

/**
 * Hand a waiting lead to somebody else.
 *
 * The open-lead count next to each name is the point of the dialog: the reason
 * a lead is stuck is usually that its owner is buried, so moving it to whoever
 * is already busiest is the one choice guaranteed not to help.
 */
export default function ReassignDialog({
  lead,
  people,
  onClose,
  onDone,
}: {
  readonly lead: IntakeLead;
  readonly people: IntakeAssignee[];
  readonly onClose: () => void;
  readonly onDone: () => void;
}) {
  const apiFetch = useApiFetch();
  const toast = useToast();
  const [busy, setBusy] = useState(false);

  const currentId = lead.status === "pending_recruiter" ? lead.recruiter_id : lead.telecaller_id;

  async function choose(person: IntakeAssignee) {
    setBusy(true);
    try {
      await reassignLead(apiFetch, lead.id, person.id);
      toast(`${lead.full_name} moved to ${person.name}.`, "success");
      onDone();
    } catch (err) {
      toast(apiErrorMessage(err, "Could not reassign that lead."), "error");
      setBusy(false);
    }
  }

  return (
    <div
      className="fixed inset-0 z-50 flex items-end justify-center bg-black/60 p-4 sm:items-center"
      onClick={onClose}
      role="presentation"
    >
      <motion.div
        initial={{ opacity: 0, y: 12 }}
        animate={{ opacity: 1, y: 0 }}
        onClick={(e) => e.stopPropagation()}
        role="dialog"
        aria-modal="true"
        aria-label={`Reassign ${lead.full_name}`}
        className="w-full max-w-md rounded-xl border border-border bg-surface p-5 shadow-2xl"
      >
        <header className="mb-4 flex items-start justify-between gap-3">
          <div>
            <h2 className="font-heading text-lg font-bold text-text-primary">Reassign lead</h2>
            <p className="mt-0.5 text-sm text-text-secondary">
              {lead.full_name} — the clock restarts for whoever takes it.
            </p>
          </div>
          <button
            type="button"
            onClick={onClose}
            aria-label="Close"
            className="rounded-lg p-1 text-text-muted hover:text-text-primary"
          >
            <IconX className="size-4" />
          </button>
        </header>

        {people.length === 0 ? (
          <p className="py-6 text-center text-sm text-text-muted">
            Nobody is available to take this on.
          </p>
        ) : (
          <ul className="flex max-h-72 flex-col gap-1.5 overflow-y-auto">
            {people.map((person) => (
              <li key={person.id}>
                <button
                  type="button"
                  disabled={busy || person.id === currentId}
                  onClick={() => choose(person)}
                  className={cn(
                    "flex w-full items-center justify-between gap-3 rounded-lg border border-border px-3 py-2.5 text-left transition-colors",
                    person.id === currentId
                      ? "opacity-40"
                      : "hover:border-yellow/30 hover:bg-yellow/5",
                  )}
                >
                  <span className="min-w-0">
                    <span className="block truncate text-sm font-medium text-text-primary">
                      {person.name}
                      {person.id === currentId && " (current)"}
                    </span>
                    {person.email && (
                      <span className="block truncate text-xs text-text-muted">{person.email}</span>
                    )}
                  </span>
                  <span className="shrink-0 rounded-full border border-border px-2 py-1 text-[11px] text-text-secondary">
                    {person.open_leads} open
                  </span>
                </button>
              </li>
            ))}
          </ul>
        )}

        {busy && (
          <div className="mt-3 flex justify-center">
            <IconLoader2 className="size-4 animate-spin text-text-muted" />
          </div>
        )}
      </motion.div>
    </div>
  );
}
