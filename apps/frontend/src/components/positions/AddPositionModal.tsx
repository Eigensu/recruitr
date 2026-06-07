"use client";

import React, { useState } from "react";
import { AnimatePresence, motion } from "motion/react";
import { IconX, IconBriefcase } from "@tabler/icons-react";
import { useApiFetch } from "@/lib/api";
import { createPosition, type PositionCreatePayload } from "@/lib/api/positions";
import type { ApiPosition, ApiPositionFilters } from "@/types";

interface Props {
  isOpen: boolean;
  onClose: () => void;
  filters: ApiPositionFilters | null;
  onCreated: (position: ApiPosition) => void;
}

const INPUT_CLS =
  "w-full px-3 py-2 text-sm rounded-lg bg-(--color-surface) border border-border" +
  " text-white placeholder-gray-500 focus:outline-none focus:border-yellow transition-all";
const LABEL_CLS = "block text-xs font-semibold text-gray-400 mb-1.5 uppercase tracking-wider";

const EMPTY_FORM = {
  clientId: "",
  role: "",
  department: "",
  city: "",
  seniority: "Mid",
  requirements: "",
  totalSeats: "1",
  notes: "",
};

export default function AddPositionModal({ isOpen, onClose, filters, onCreated }: Readonly<Props>) {
  const apiFetch = useApiFetch();
  const [form, setForm] = useState(EMPTY_FORM);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  function handleClose() {
    if (submitting) return;
    setForm(EMPTY_FORM);
    setError(null);
    onClose();
  }

  async function handleSubmit(e: React.SyntheticEvent<HTMLFormElement>) {
    e.preventDefault();
    setSubmitting(true);
    setError(null);

    const payload: PositionCreatePayload = {
      client_id: form.clientId,
      role: form.role.trim(),
      department: form.department.trim() || undefined,
      city: form.city.trim() || undefined,
      seniority: form.seniority,
      requirements: form.requirements
        .split(",")
        .map((s) => s.trim())
        .filter(Boolean),
      total_seats: Math.max(0, Number(form.totalSeats) || 0),
      notes: form.notes.trim() || undefined,
    };

    try {
      const created = await createPosition(apiFetch, payload);
      onCreated(created);
      setForm(EMPTY_FORM);
      onClose();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to create position.");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <AnimatePresence>
      {isOpen && (
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          onClick={handleClose}
          className="fixed inset-0 bg-black/60 backdrop-blur-sm z-50 flex items-center justify-center p-4"
        >
          <motion.div
            role="dialog"
            aria-modal="true"
            aria-labelledby="add-position-title"
            initial={{ opacity: 0, scale: 0.95, y: 20 }}
            animate={{ opacity: 1, scale: 1, y: 0 }}
            exit={{ opacity: 0, scale: 0.95, y: 20 }}
            onClick={(e) => e.stopPropagation()}
            className="bg-(--color-surface) border border-border shadow-2xl rounded-2xl w-full max-w-lg overflow-hidden flex flex-col max-h-[90vh]"
          >
            {/* Header */}
            <div className="p-5 border-b border-border flex items-center justify-between bg-(--color-surface)">
              <h2
                id="add-position-title"
                className="text-lg font-bold font-heading text-white flex items-center gap-2"
              >
                <IconBriefcase className="size-5 text-yellow" />
                New Position
              </h2>
              <button
                type="button"
                onClick={handleClose}
                disabled={submitting}
                aria-label="Close"
                className="p-1.5 rounded-lg bg-(--color-canvas) border border-border text-gray-400 hover:text-white transition-colors disabled:opacity-50"
              >
                <IconX className="size-4" />
              </button>
            </div>

            {/* Body */}
            <div className="p-5 overflow-y-auto dashboard-scrollbar bg-(--color-canvas)">
              {error && (
                <div className="mb-4 px-3 py-2 rounded-lg bg-red-500/10 border border-red-500/20 text-red-400 text-sm">
                  {error}
                </div>
              )}

              <form id="add-position-form" onSubmit={handleSubmit} className="space-y-4">
                <div>
                  <label htmlFor="pos-client" className={LABEL_CLS}>
                    Client *
                  </label>
                  <select
                    id="pos-client"
                    required
                    value={form.clientId}
                    onChange={(e) => setForm({ ...form, clientId: e.target.value })}
                    className={INPUT_CLS}
                  >
                    <option value="">Select client…</option>
                    {filters?.clients.map((c) => (
                      <option key={c.id} value={c.id}>
                        {c.name}
                      </option>
                    ))}
                  </select>
                </div>

                <div>
                  <label htmlFor="pos-role" className={LABEL_CLS}>
                    Role *
                  </label>
                  <input
                    id="pos-role"
                    required
                    type="text"
                    placeholder="e.g. Sous Chef"
                    value={form.role}
                    onChange={(e) => setForm({ ...form, role: e.target.value })}
                    className={INPUT_CLS}
                  />
                </div>

                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <label htmlFor="pos-dept" className={LABEL_CLS}>
                      Department
                    </label>
                    <input
                      id="pos-dept"
                      type="text"
                      placeholder="e.g. Kitchen"
                      value={form.department}
                      onChange={(e) => setForm({ ...form, department: e.target.value })}
                      className={INPUT_CLS}
                    />
                  </div>
                  <div>
                    <label htmlFor="pos-city" className={LABEL_CLS}>
                      City
                    </label>
                    <input
                      id="pos-city"
                      type="text"
                      placeholder="e.g. Mumbai"
                      value={form.city}
                      onChange={(e) => setForm({ ...form, city: e.target.value })}
                      className={INPUT_CLS}
                    />
                  </div>
                </div>

                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <label htmlFor="pos-seniority" className={LABEL_CLS}>
                      Seniority
                    </label>
                    <select
                      id="pos-seniority"
                      value={form.seniority}
                      onChange={(e) => setForm({ ...form, seniority: e.target.value })}
                      className={INPUT_CLS}
                    >
                      <option value="Junior">Junior</option>
                      <option value="Mid">Mid</option>
                      <option value="Senior">Senior</option>
                    </select>
                  </div>
                  <div>
                    <label htmlFor="pos-seats" className={LABEL_CLS}>
                      Total Seats
                    </label>
                    <input
                      id="pos-seats"
                      type="number"
                      min="0"
                      placeholder="1"
                      value={form.totalSeats}
                      onChange={(e) => setForm({ ...form, totalSeats: e.target.value })}
                      className={INPUT_CLS}
                    />
                  </div>
                </div>

                <div>
                  <label htmlFor="pos-req" className={LABEL_CLS}>
                    Requirements (comma-separated)
                  </label>
                  <input
                    id="pos-req"
                    type="text"
                    placeholder="e.g. Knife Skills, Kitchen Ops, Food Safety"
                    value={form.requirements}
                    onChange={(e) => setForm({ ...form, requirements: e.target.value })}
                    className={INPUT_CLS}
                  />
                </div>

                <div>
                  <label htmlFor="pos-notes" className={LABEL_CLS}>
                    Notes
                  </label>
                  <textarea
                    id="pos-notes"
                    rows={2}
                    placeholder="Any additional context…"
                    value={form.notes}
                    onChange={(e) => setForm({ ...form, notes: e.target.value })}
                    className={`${INPUT_CLS} resize-none`}
                  />
                </div>
              </form>
            </div>

            {/* Footer */}
            <div className="p-5 border-t border-border bg-(--color-surface) flex justify-end gap-3">
              <button
                type="button"
                onClick={handleClose}
                disabled={submitting}
                className="px-4 py-2 rounded-lg text-sm font-semibold text-gray-400 hover:text-white transition-colors disabled:opacity-50"
              >
                Cancel
              </button>
              <button
                type="submit"
                form="add-position-form"
                disabled={submitting}
                className="px-4 py-2 rounded-lg bg-yellow text-navy hover:bg-yellow-dark text-sm font-bold transition-all shadow-lg shadow-yellow/10 disabled:opacity-60"
              >
                {submitting ? "Creating…" : "Create Position"}
              </button>
            </div>
          </motion.div>
        </motion.div>
      )}
    </AnimatePresence>
  );
}
