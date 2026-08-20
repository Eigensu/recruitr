"use client";

import { useRef, useState } from "react";
import { IconCheck, IconFileCheck, IconLoader2, IconUpload, IconX } from "@tabler/icons-react";
import { moveOwnReferral, uploadOwnReferralOffer, type RefereeStageMove } from "@/lib/api/referee";
import { useToast } from "@/components/ui/Toast";
import type { RefereeReferral } from "@/types";

/**
 * The forward move a referee may make, keyed by the referral's internal stage.
 *
 * Mirrors _ALLOWED_TRANSITIONS in app/modules/dashboard/referee_router.py. The
 * backend refuses anything outside that pair, so a stage missing here renders
 * no buttons at all rather than a button that 403s on click.
 */
const ADVANCE_BY_STAGE: Record<string, { to: RefereeStageMove; label: string; hint: string }> = {
  sent_to_client: {
    to: "interview",
    label: "Select",
    hint: "Move this candidate forward to the interview stage",
  },
  interview: {
    to: "selected",
    label: "Select",
    hint: "Mark this candidate as selected",
  },
};

const BTN =
  "rounded-lg border px-3 py-1.5 text-xs font-semibold transition-all flex items-center " +
  "justify-center gap-1 disabled:opacity-50 disabled:cursor-not-allowed";

interface ReferralActionsProps {
  readonly referral: RefereeReferral;
  readonly onDone: () => void;
}

export default function ReferralActions({ referral, onDone }: ReferralActionsProps) {
  const toast = useToast();
  const fileRef = useRef<HTMLInputElement>(null);
  const [busy, setBusy] = useState(false);
  // Reject costs the referee their incentive and cannot be undone from this
  // portal, so it arms on the first click and only fires on the second.
  const [confirmingReject, setConfirmingReject] = useState(false);

  const { mapping_id: mappingId, pipeline_stage: stage } = referral;
  if (!mappingId || !stage) return null;

  const advance = ADVANCE_BY_STAGE[stage];
  const canUploadOffer = stage === "selected";
  if (!advance && !canUploadOffer) return null;

  async function run(action: () => Promise<void>, success: string) {
    setBusy(true);
    try {
      await action();
      toast(success, "success");
      onDone();
    } catch (err) {
      toast(err instanceof Error ? err.message : "Something went wrong.", "error");
    } finally {
      setBusy(false);
      setConfirmingReject(false);
    }
  }

  function onPickOffer(event: React.ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0];
    // Clear the input first so picking the same file twice still fires onChange.
    event.target.value = "";
    // Re-read through a local: the early return above narrows mappingId for the
    // component body, but not inside a function declaration hoisted past it.
    const id = mappingId;
    if (!file || !id) return;
    void run(() => uploadOwnReferralOffer(id, file), "Offer letter uploaded.");
  }

  return (
    <div
      className="mt-4 flex flex-wrap items-center justify-end gap-2 border-t pt-3"
      style={{ borderColor: "var(--color-border-val)" }}
    >
      {busy && <IconLoader2 className="size-4 animate-spin text-text-muted" aria-hidden />}

      {advance && (
        <>
          <button
            type="button"
            title={advance.hint}
            disabled={busy}
            onClick={() =>
              run(() => moveOwnReferral(mappingId, advance.to), `Moved to ${advance.to}.`)
            }
            className={`${BTN} border-emerald-500/20 bg-emerald-500/10 text-emerald-600 hover:bg-emerald-500/20 dark:text-emerald-400`}
          >
            <IconCheck className="size-3.5" stroke={3} /> {advance.label}
          </button>

          <button
            type="button"
            title="Reject this candidate. This cannot be undone from the portal."
            disabled={busy}
            onClick={() => {
              if (!confirmingReject) {
                setConfirmingReject(true);
                return;
              }
              void run(() => moveOwnReferral(mappingId, "rejected"), "Candidate rejected.");
            }}
            onBlur={() => setConfirmingReject(false)}
            className={`${BTN} border-red-500/20 bg-red-500/10 text-red-600 hover:bg-red-500/20 dark:text-red-400`}
          >
            <IconX className="size-3.5" stroke={3} />{" "}
            {confirmingReject ? "Confirm reject?" : "Reject"}
          </button>
        </>
      )}

      {canUploadOffer &&
        (referral.offer_letter_url ? (
          <a
            href={referral.offer_letter_url}
            target="_blank"
            rel="noopener noreferrer"
            className={`${BTN} border-emerald-500/20 bg-emerald-500/10 text-emerald-600 hover:bg-emerald-500/20 dark:text-emerald-400`}
          >
            <IconFileCheck className="size-3.5" /> View offer letter
          </a>
        ) : (
          <>
            <input
              ref={fileRef}
              type="file"
              accept="application/pdf,.pdf"
              className="hidden"
              onChange={onPickOffer}
            />
            <button
              type="button"
              disabled={busy}
              onClick={() => fileRef.current?.click()}
              className={`${BTN} border-yellow/30 bg-yellow/10 text-amber-800 hover:bg-yellow/20 dark:text-yellow`}
            >
              <IconUpload className="size-3.5" /> Upload offer letter
            </button>
          </>
        ))}
    </div>
  );
}
