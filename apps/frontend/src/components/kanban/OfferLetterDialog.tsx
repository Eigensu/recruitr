"use client";

import React, { useState } from "react";
import { AnimatePresence, motion } from "motion/react";
import { IconCheck, IconFileText, IconX } from "@tabler/icons-react";
import { isAbsoluteUrl } from "@/lib/api/candidates";
import { uploadMappingOffer } from "@/lib/api/pipeline";
import type { PipelineCard } from "@/types";

interface Props {
  /** The board's current row for this card, so an upload shows up here as
   *  soon as the board is re-read. Null closes the dialog. */
  card: PipelineCard | null;
  onClose: () => void;
  onUploaded: () => void;
}

/**
 * The Offer letter button on a joined card: view the letter on file, or upload
 * one (replacing it if there is one already). Staff board only.
 */
export default function OfferLetterDialog({ card, onClose, onUploaded }: Readonly<Props>) {
  const [uploading, setUploading] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const href =
    card?.offer_letter_url && isAbsoluteUrl(card.offer_letter_url) ? card.offer_letter_url : null;

  async function handleFile(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    // Cleared so picking the same file again after a failure still fires.
    e.target.value = "";
    if (!file || !card) return;
    setUploading(file.name);
    setError(null);
    try {
      // Choosing the file uploads it — no second button to forget, see the
      // note on the same input in ClientActionModal.
      await uploadMappingOffer(card.mapping_id, file);
      onUploaded();
    } catch (err) {
      setError(err instanceof Error && err.message ? err.message : "Upload failed.");
    } finally {
      setUploading(null);
    }
  }

  return (
    <AnimatePresence>
      {card && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 sm:p-6">
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            onClick={onClose}
            className="absolute inset-0 bg-black/60 backdrop-blur-sm"
          />
          <motion.div
            role="dialog"
            aria-modal="true"
            aria-labelledby="offerLetterDialogTitle"
            initial={{ opacity: 0, scale: 0.95, y: 10 }}
            animate={{ opacity: 1, scale: 1, y: 0 }}
            exit={{ opacity: 0, scale: 0.95, y: 10 }}
            className="relative w-full max-w-md overflow-hidden rounded-2xl border border-border bg-surface-panel shadow-2xl"
          >
            <div className="flex items-center justify-between border-b border-border p-4">
              <div className="min-w-0">
                <h2 id="offerLetterDialogTitle" className="text-lg font-bold text-text-primary">
                  Offer letter
                </h2>
                <p className="truncate text-xs text-text-muted">
                  {card.candidate_name} · {card.position_role}, {card.position_client}
                </p>
              </div>
              <button
                type="button"
                onClick={onClose}
                aria-label="Close"
                className="rounded-lg p-1.5 text-text-muted hover:bg-surface-2 hover:text-text-primary transition-colors"
              >
                <IconX className="size-5" />
              </button>
            </div>

            <div className="space-y-4 p-5">
              {error && (
                <div className="rounded-lg border border-red-500/20 bg-red-500/10 p-3 text-sm text-red-400">
                  {error}
                </div>
              )}

              {card.offer_letter_url ? (
                <div className="flex items-center justify-between gap-2 rounded-lg border border-emerald-500/20 bg-emerald-500/10 px-3 py-2 text-sm font-semibold text-emerald-400">
                  <span className="flex items-center gap-2">
                    <IconCheck className="size-4 shrink-0" /> Offer letter on file
                  </span>
                  {href && (
                    <a
                      href={href}
                      target="_blank"
                      rel="noreferrer noopener"
                      className="flex items-center gap-1 text-xs hover:underline"
                    >
                      <IconFileText className="size-3.5 shrink-0" />
                      View
                    </a>
                  )}
                </div>
              ) : (
                <p className="text-sm text-text-secondary">No offer letter uploaded yet.</p>
              )}

              <div className="space-y-2">
                <label
                  htmlFor="joined-offer-letter-input"
                  className="text-xs font-semibold uppercase text-text-muted"
                >
                  {card.offer_letter_url ? "Replace with a new PDF" : "Upload a PDF"}
                </label>
                <input
                  id="joined-offer-letter-input"
                  type="file"
                  accept="application/pdf,.pdf"
                  disabled={uploading !== null}
                  onChange={handleFile}
                  className="w-full rounded-lg border border-border bg-surface-2 px-3 py-1.5 text-sm text-text-primary file:mr-3 file:rounded-md file:border-0 file:bg-surface-panel file:px-3 file:py-1 file:text-xs file:text-text-primary disabled:opacity-50"
                />
                {uploading && <p className="text-xs text-text-muted">Uploading {uploading}…</p>}
              </div>
            </div>
          </motion.div>
        </div>
      )}
    </AnimatePresence>
  );
}
