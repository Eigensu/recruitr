"use client";

import { useState } from "react";
import { IconCheck, IconX } from "@tabler/icons-react";
import { apiErrorMessage } from "@/lib/api";
import { clientDecideMapping } from "@/lib/api/pipeline-actions.client";
import { useToast } from "@/components/ui/Toast";
import OfferUploadBox from "@/components/dashboard/molecules/OfferUploadBox";
import JoiningDateInput from "@/components/dashboard/molecules/JoiningDateInput";
import type { PipelineCard } from "@/types";

export type ActionGate = "decision" | "offer" | "joining-date" | "joined-pending";

/** Which of the four dashboard actions this mapping is currently waiting on, if any. */
export function actionGateFor(card: PipelineCard): ActionGate | null {
  if (
    (card.stage === "sent_to_client" || card.stage === "decision_pending") &&
    card.decision === "pending"
  ) {
    return "decision";
  }
  if (card.stage === "offer") {
    return card.offer_document_url ? "joining-date" : "offer";
  }
  if (card.stage === "offer_accepted") return "joined-pending";
  return null;
}

interface PipelineActionRowProps {
  card: PipelineCard;
  gate: ActionGate;
  onUpdated: () => void;
}

export default function PipelineActionRow({ card, gate, onUpdated }: PipelineActionRowProps) {
  const [isDeciding, setIsDeciding] = useState(false);
  const toast = useToast();

  async function decide(decision: "selected" | "rejected") {
    setIsDeciding(true);
    try {
      await clientDecideMapping(card.mapping_id, decision);
      toast(
        decision === "selected" ? "Moved to the next stage." : "Candidate rejected.",
        decision === "selected" ? "success" : "info",
      );
      onUpdated();
    } catch (err) {
      toast(apiErrorMessage(err, "Could not update this candidate."), "error");
    } finally {
      setIsDeciding(false);
    }
  }

  return (
    <div
      className="flex flex-col gap-2 rounded-lg border p-3 sm:flex-row sm:items-center sm:justify-between"
      style={{ borderColor: "var(--color-border-val)", background: "var(--color-surface-2-val)" }}
    >
      <div className="min-w-0">
        <p className="truncate text-sm font-medium text-text-primary">{card.candidate_name}</p>
        <p className="truncate text-xs text-text-secondary">{card.position_role}</p>
      </div>

      <div className="shrink-0">
        {gate === "decision" && (
          <div className="flex items-center gap-2">
            <button
              type="button"
              aria-label="Reject candidate"
              onClick={() => decide("rejected")}
              disabled={isDeciding}
              className="flex size-8 items-center justify-center rounded-full border border-red-500/30 text-red-500 transition-colors hover:bg-red-500/10 disabled:opacity-50"
            >
              <IconX className="size-4" />
            </button>
            <button
              type="button"
              aria-label="Advance candidate"
              onClick={() => decide("selected")}
              disabled={isDeciding}
              className="flex size-8 items-center justify-center rounded-full text-navy transition-opacity hover:opacity-90 disabled:opacity-50"
              style={{ background: "var(--color-yellow)" }}
            >
              <IconCheck className="size-4" />
            </button>
          </div>
        )}

        {gate === "offer" && <OfferUploadBox mappingId={card.mapping_id} onUploaded={onUpdated} />}

        {(gate === "joining-date" || gate === "joined-pending") && (
          <JoiningDateInput
            mappingId={card.mapping_id}
            joiningDate={card.joining_date}
            onUpdated={onUpdated}
          />
        )}
      </div>
    </div>
  );
}
