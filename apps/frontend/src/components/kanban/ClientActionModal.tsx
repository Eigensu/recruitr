"use client";

import React, { useState } from "react";
import { AnimatePresence, motion } from "motion/react";
import { IconX, IconCheck, IconFileText } from "@tabler/icons-react";
import type { PipelineCard, KanbanStage } from "@/types";
import { isAbsoluteUrl } from "@/lib/api/candidates";
import {
  setMappingInterviewDate,
  uploadMappingOffer,
  setMappingJoiningDate,
  setMappingDropped,
} from "@/lib/api/pipeline";

interface Props {
  isOpen: boolean;
  onClose: () => void;
  card: PipelineCard | null;
  onStageChange: (newStage: KanbanStage) => void | Promise<void>;
  onActionComplete: () => void;
}

export default function ClientActionModal({
  isOpen,
  onClose,
  card,
  onStageChange,
  onActionComplete,
}: Props) {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // States for different actions. The joining fields start from what is saved,
  // so reopening a card shows the stored details instead of a blank form that
  // reads as though the last save never happened. Parents key this modal by
  // mapping, so these initialisers run again for each card.
  const [interviewDate, setInterviewDate] = useState("");
  const [joiningDate, setJoiningDate] = useState(card?.joining_date?.slice(0, 10) ?? "");
  const [salaryOffered, setSalaryOffered] = useState(
    card?.salary_offered == null ? "" : String(card.salary_offered),
  );
  const [offerFile, setOfferFile] = useState<File | null>(null);
  const [droppedNotes, setDroppedNotes] = useState("");

  if (!card) return null;

  const offerLetterHref =
    card.offer_letter_url && isAbsoluteUrl(card.offer_letter_url) ? card.offer_letter_url : null;

  async function handleAction(action: () => Promise<void>, { close = true } = {}) {
    setLoading(true);
    setError(null);
    try {
      await action();
      onActionComplete();
      if (close) onClose();
    } catch (err: unknown) {
      setError((err as Error).message || "Action failed");
    } finally {
      setLoading(false);
    }
  }

  async function handleOfferFileChange(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    // Clear the input's value so picking the same file again after a failure
    // still fires onChange.
    e.target.value = "";
    if (!file || !card) return;

    setOfferFile(file);
    await handleAction(() => uploadMappingOffer(card.mapping_id, file), { close: false });
    setOfferFile(null);
  }

  return (
    <AnimatePresence>
      {isOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 sm:p-6">
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            onClick={onClose}
            className="absolute inset-0 bg-black/60 backdrop-blur-sm"
          />
          <motion.div
            initial={{ opacity: 0, scale: 0.95, y: 10 }}
            animate={{ opacity: 1, scale: 1, y: 0 }}
            exit={{ opacity: 0, scale: 0.95, y: 10 }}
            className="relative w-full max-w-md overflow-hidden rounded-2xl border border-border bg-surface-panel shadow-2xl"
          >
            <div className="flex items-center justify-between border-b border-border p-4">
              <h2 className="text-lg font-bold text-text-primary">
                Review Action: {card.candidate_name}
              </h2>
              <button
                type="button"
                onClick={onClose}
                className="rounded-lg p-1.5 text-text-muted hover:bg-surface-2 hover:text-text-primary transition-colors"
              >
                <IconX className="size-5" />
              </button>
            </div>

            <div className="p-5 space-y-4">
              {error && (
                <div className="rounded-lg bg-red-500/10 p-3 text-sm text-red-400 border border-red-500/20">
                  {error}
                </div>
              )}

              <div className="text-sm text-text-secondary mb-4">
                Current Stage:{" "}
                <span className="font-semibold text-text-primary">
                  {card.stage.replace(/_/g, " ")}
                </span>
              </div>

              {/* Above the per-stage actions rather than inside `selected`, so
                  the letter stays one click away after the candidate joins —
                  which is when anyone is most likely to go looking for it. */}
              {card.offer_letter_url && (
                <div className="flex items-center justify-between gap-2 text-sm text-emerald-400 font-semibold bg-emerald-500/10 border border-emerald-500/20 px-3 py-2 rounded-lg">
                  <span className="flex items-center gap-2">
                    <IconCheck className="size-4 shrink-0" /> Offer Uploaded
                  </span>
                  {offerLetterHref && (
                    <a
                      href={offerLetterHref}
                      target="_blank"
                      rel="noreferrer noopener"
                      className="flex items-center gap-1 text-xs hover:underline"
                    >
                      <IconFileText className="size-3.5 shrink-0" />
                      View offer letter
                    </a>
                  )}
                </div>
              )}

              {/* SOURCED -> present to the client.
                  This used to share the `sent_to_client` branch below, so a
                  sourced candidate offered "Approve for Interview" — a decision
                  that is the client's to make and only after they have been
                  shown the candidate. Taking it also jumped straight to
                  `interview`, skipping `sent_to_client`, so the candidate was
                  never recorded as having been presented at all. */}
              {card.stage === "sourced" && (
                <div className="flex gap-3">
                  <button
                    type="button"
                    onClick={() =>
                      handleAction(async () => {
                        await onStageChange("sent_to_client");
                      })
                    }
                    disabled={loading}
                    className="flex-1 flex items-center justify-center gap-2 rounded-lg bg-blue-500/10 border border-blue-500/20 px-4 py-2.5 text-sm font-semibold text-blue-400 hover:bg-blue-500/20 transition-all disabled:opacity-50"
                  >
                    <IconCheck className="size-4" /> Send to Client
                  </button>
                  <button
                    type="button"
                    onClick={() =>
                      handleAction(async () => {
                        await onStageChange("rejected");
                      })
                    }
                    disabled={loading}
                    className="flex-1 flex items-center justify-center gap-2 rounded-lg bg-red-500/10 border border-red-500/20 px-4 py-2.5 text-sm font-semibold text-red-400 hover:bg-red-500/20 transition-all disabled:opacity-50"
                  >
                    <IconX className="size-4" /> Reject
                  </button>
                </div>
              )}

              {/* SENT TO CLIENT -> Approve/Reject */}
              {card.stage === "sent_to_client" && (
                <div className="flex gap-3">
                  <button
                    type="button"
                    onClick={() =>
                      handleAction(async () => {
                        await onStageChange("interview");
                      })
                    }
                    disabled={loading}
                    className="flex-1 flex items-center justify-center gap-2 rounded-lg bg-emerald-500/10 border border-emerald-500/20 px-4 py-2.5 text-sm font-semibold text-emerald-400 hover:bg-emerald-500/20 transition-all disabled:opacity-50"
                  >
                    <IconCheck className="size-4" /> Approve for Interview
                  </button>
                  <button
                    type="button"
                    onClick={() =>
                      handleAction(async () => {
                        await onStageChange("rejected");
                      })
                    }
                    disabled={loading}
                    className="flex-1 flex items-center justify-center gap-2 rounded-lg bg-red-500/10 border border-red-500/20 px-4 py-2.5 text-sm font-semibold text-red-400 hover:bg-red-500/20 transition-all disabled:opacity-50"
                  >
                    <IconX className="size-4" /> Reject
                  </button>
                </div>
              )}

              {/* INTERVIEW -> Set Date, Selected, Rejected */}
              {card.stage === "interview" && (
                <div className="space-y-4">
                  <div className="space-y-2">
                    <label className="text-xs font-semibold text-text-muted uppercase">
                      Set Interview Date
                    </label>
                    <div className="flex gap-2">
                      <input
                        type="datetime-local"
                        value={interviewDate}
                        onChange={(e) => setInterviewDate(e.target.value)}
                        className="flex-1 rounded-lg bg-surface-2 border border-border px-3 py-2 text-sm text-text-primary focus:border-yellow focus:outline-none"
                      />
                      <button
                        type="button"
                        onClick={() =>
                          handleAction(() =>
                            setMappingInterviewDate(
                              card.mapping_id,
                              new Date(interviewDate).toISOString(),
                            ),
                          )
                        }
                        disabled={loading || !interviewDate}
                        className="rounded-lg bg-yellow/10 border border-yellow/20 px-4 py-2 text-sm font-semibold text-yellow hover:bg-yellow/20 disabled:opacity-50"
                      >
                        Save
                      </button>
                    </div>
                  </div>

                  <div className="border-t border-border pt-4 flex gap-3">
                    <button
                      type="button"
                      onClick={() =>
                        handleAction(async () => {
                          await onStageChange("selected");
                        })
                      }
                      disabled={loading}
                      className="flex-1 flex items-center justify-center gap-2 rounded-lg bg-indigo-500/10 border border-indigo-500/20 px-4 py-2 text-sm font-semibold text-indigo-400 hover:bg-indigo-500/20 transition-all disabled:opacity-50"
                    >
                      <IconCheck className="size-4" /> Mark Selected
                    </button>
                    <button
                      type="button"
                      onClick={() =>
                        handleAction(async () => {
                          await onStageChange("rejected");
                        })
                      }
                      disabled={loading}
                      className="flex-1 flex items-center justify-center gap-2 rounded-lg bg-red-500/10 border border-red-500/20 px-4 py-2 text-sm font-semibold text-red-400 hover:bg-red-500/20 transition-all disabled:opacity-50"
                    >
                      <IconX className="size-4" /> Mark Rejected
                    </button>
                  </div>
                </div>
              )}

              {/* SELECTED -> Upload Offer, Set Joining, Drop */}
              {card.stage === "selected" && (
                <div className="space-y-4">
                  <div className="space-y-2">
                    <label
                      htmlFor="offer-letter-input"
                      className="text-xs font-semibold text-text-muted uppercase"
                    >
                      {card.offer_letter_url ? "Replace Offer Letter" : "Upload Offer Letter"}
                    </label>
                    <div className="flex flex-col gap-2">
                      {/* Choosing the file uploads it. This used to only set
                          state, with a separate Upload button — disabled until
                          a file was picked — actually sending the request. A
                          disabled button does nothing and says nothing, so
                          picking a file and closing the dialog sent no request
                          at all: the server logs show board fetches and stage
                          moves in the same session and not one offer-letter
                          call. "I uploaded it" meant "I chose the file". */}
                      <input
                        id="offer-letter-input"
                        type="file"
                        accept="application/pdf,.pdf"
                        disabled={loading}
                        onChange={handleOfferFileChange}
                        className="w-full rounded-lg bg-surface-2 border border-border px-3 py-1.5 text-sm text-text-primary file:mr-3 file:py-1 file:px-3 file:rounded-md file:border-0 file:bg-surface-panel file:text-text-primary file:text-xs disabled:opacity-50"
                      />
                      {loading && offerFile && (
                        <p className="text-xs text-text-muted">Uploading {offerFile.name}…</p>
                      )}
                    </div>
                  </div>

                  {card.offer_letter_url && (
                    <div className="border-t border-border pt-4 space-y-2">
                      <label className="text-xs font-semibold text-text-muted uppercase">
                        Set Joining Details
                      </label>
                      {(card.joining_date || card.salary_offered != null) && (
                        <div className="flex items-center gap-2 text-sm text-emerald-400 font-semibold bg-emerald-500/10 border border-emerald-500/20 px-3 py-2 rounded-lg">
                          <IconCheck className="size-4 shrink-0" />
                          <span>
                            Saved
                            {card.joining_date &&
                              ` · Joining ${new Date(card.joining_date).toLocaleDateString()}`}
                            {card.salary_offered != null &&
                              ` · ₹${card.salary_offered.toLocaleString()}`}
                          </span>
                        </div>
                      )}
                      <div className="grid grid-cols-2 gap-2">
                        <input
                          type="date"
                          value={joiningDate}
                          onChange={(e) => setJoiningDate(e.target.value)}
                          className="rounded-lg bg-surface-2 border border-border px-3 py-2 text-sm text-text-primary focus:border-yellow focus:outline-none"
                        />
                        <input
                          type="number"
                          placeholder="Salary Offered"
                          value={salaryOffered}
                          onChange={(e) => setSalaryOffered(e.target.value)}
                          className="rounded-lg bg-surface-2 border border-border px-3 py-2 text-sm text-text-primary focus:border-yellow focus:outline-none"
                        />
                      </div>
                      <button
                        type="button"
                        onClick={() =>
                          handleAction(async () => {
                            await setMappingJoiningDate(
                              card.mapping_id,
                              new Date(joiningDate).toISOString(),
                              Number(salaryOffered),
                            );
                            /* Stage transitions via background task */
                          })
                        }
                        disabled={loading || !joiningDate || !salaryOffered}
                        className="w-full mt-2 rounded-lg bg-emerald-500/10 border border-emerald-500/20 px-4 py-2 text-sm font-semibold text-emerald-400 hover:bg-emerald-500/20 transition-all disabled:opacity-50"
                      >
                        {card.joining_date ? "Update Details" : "Save Details"}
                      </button>
                    </div>
                  )}

                  <div className="border-t border-border pt-4 space-y-2">
                    <label className="text-xs font-semibold text-text-muted uppercase">
                      Candidate Dropped
                    </label>
                    <textarea
                      placeholder="Reason for dropping..."
                      value={droppedNotes}
                      onChange={(e) => setDroppedNotes(e.target.value)}
                      className="w-full rounded-lg bg-surface-2 border border-border px-3 py-2 text-sm text-text-primary focus:border-yellow focus:outline-none min-h-20"
                    />
                    <button
                      type="button"
                      onClick={() =>
                        handleAction(async () => {
                          await setMappingDropped(card.mapping_id, droppedNotes);
                        })
                      }
                      disabled={loading || !droppedNotes}
                      className="w-full rounded-lg bg-red-500/10 border border-red-500/20 px-4 py-2 text-sm font-semibold text-red-400 hover:bg-red-500/20 transition-all disabled:opacity-50"
                    >
                      Mark Dropped
                    </button>
                  </div>
                </div>
              )}

              {/* JOINED / DROPPED -> No further actions usually, but we show current info */}
              {(card.stage === "joined" ||
                card.stage === "candidate_dropped" ||
                card.stage === "rejected") && (
                <div className="text-sm text-text-muted text-center py-4">
                  No further actions available for this stage.
                </div>
              )}
            </div>
          </motion.div>
        </div>
      )}
    </AnimatePresence>
  );
}
