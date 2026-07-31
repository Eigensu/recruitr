"use client";

import React, { useMemo, useState } from "react";
import { AnimatePresence, motion } from "motion/react";
import { IconX, IconBriefcase, IconPlus, IconCheck } from "@tabler/icons-react";
import { apiErrorMessage, useApiFetch } from "@/lib/api";
import {
  createPosition,
  updatePosition,
  type PositionCreatePayload,
  type PositionUpdatePayload,
} from "@/lib/api/positions";
import { createClient } from "@/lib/api/clients";
import type { ApiClientOption, ApiPosition, ApiPositionFilters } from "@/types";

interface Props {
  isOpen: boolean;
  onClose: () => void;
  filters: ApiPositionFilters | null;
  onCreated: (position: ApiPosition) => void;
  /** When provided the modal operates in edit mode */
  position?: ApiPosition;
  onUpdated?: (position: ApiPosition) => void;
  /** Lets the parent fold a newly added client into its cached filter options */
  onClientCreated?: (client: ApiClientOption) => void;
}

const INPUT_CLS =
  "w-full px-3 py-2 text-sm rounded-lg bg-(--color-surface) border border-border" +
  " text-white placeholder-gray-500 focus:outline-none focus:border-yellow transition-all";
const LABEL_BASE = "block text-xs font-semibold text-gray-400 uppercase tracking-wider";
const LABEL_CLS = `${LABEL_BASE} mb-1.5`;

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

function positionToForm(p: ApiPosition) {
  return {
    clientId: p.client_id,
    role: p.role,
    department: p.department ?? "",
    city: p.city ?? "",
    seniority: p.seniority,
    requirements: (p.requirements ?? []).join(", "),
    totalSeats: String(p.total_seats),
    notes: p.notes ?? "",
  };
}

export default function AddPositionModal({
  isOpen,
  onClose,
  filters,
  onCreated,
  position,
  onUpdated,
  onClientCreated,
}: Readonly<Props>) {
  const apiFetch = useApiFetch();
  const isEditing = Boolean(position);

  const [form, setForm] = useState(position ? positionToForm(position) : EMPTY_FORM);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Clients added from inside this modal. Kept separate from `filters` so the
  // new option survives even if the parent hasn't refreshed its filter cache.
  const [newClients, setNewClients] = useState<ApiClientOption[]>([]);
  const [showClientForm, setShowClientForm] = useState(false);
  const [clientForm, setClientForm] = useState({ name: "", city: "" });
  const [creatingClient, setCreatingClient] = useState(false);
  const [clientError, setClientError] = useState<string | null>(null);

  const clientOptions = useMemo(() => {
    const known = filters?.clients ?? [];
    const knownIds = new Set(known.map((c) => c.id));
    return [...known, ...newClients.filter((c) => !knownIds.has(c.id))].sort((a, b) =>
      a.name.localeCompare(b.name),
    );
  }, [filters, newClients]);

  function handleClose() {
    if (submitting || creatingClient) return;
    setError(null);
    closeClientForm();
    onClose();
  }

  function closeClientForm() {
    setShowClientForm(false);
    setClientForm({ name: "", city: "" });
    setClientError(null);
  }

  async function handleCreateClient() {
    const name = clientForm.name.trim();
    if (!name) {
      setClientError("Client name is required.");
      return;
    }
    setCreatingClient(true);
    setClientError(null);
    try {
      const created = await createClient(apiFetch, {
        name,
        city: clientForm.city.trim() || undefined,
      });
      const option: ApiClientOption = { id: created.id, code: created.code, name: created.name };
      setNewClients((prev) => [...prev, option]);
      setForm((prev) => ({ ...prev, clientId: option.id }));
      onClientCreated?.(option);
      closeClientForm();
    } catch (err) {
      setClientError(apiErrorMessage(err, "Failed to add client."));
    } finally {
      setCreatingClient(false);
    }
  }

  async function handleSubmit(e: React.SyntheticEvent<HTMLFormElement>) {
    e.preventDefault();
    setSubmitting(true);
    setError(null);

    const requirements = form.requirements
      .split(",")
      .map((s) => s.trim())
      .filter(Boolean);
    const total_seats = Math.max(0, Number(form.totalSeats) || 0);

    try {
      if (isEditing && position) {
        const payload: PositionUpdatePayload = {
          role: form.role.trim(),
          department: form.department.trim() || undefined,
          city: form.city.trim() || undefined,
          seniority: form.seniority,
          requirements,
          total_seats,
          notes: form.notes.trim() || undefined,
        };
        const updated = await updatePosition(apiFetch, position.id, payload);
        onUpdated?.(updated);
        onClose();
      } else {
        const payload: PositionCreatePayload = {
          client_id: form.clientId,
          role: form.role.trim(),
          department: form.department.trim() || undefined,
          city: form.city.trim() || undefined,
          seniority: form.seniority,
          requirements,
          total_seats,
          notes: form.notes.trim() || undefined,
        };
        const created = await createPosition(apiFetch, payload);
        onCreated(created);
        setForm(EMPTY_FORM);
        onClose();
      }
    } catch (err) {
      setError(apiErrorMessage(err, "Failed to save position."));
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
                {isEditing ? "Edit Position" : "New Position"}
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
                  <div className="flex items-center justify-between mb-1.5">
                    <label htmlFor="pos-client" className={LABEL_BASE}>
                      Client *
                    </label>
                    {!isEditing && !showClientForm && (
                      <button
                        type="button"
                        onClick={() => {
                          setShowClientForm(true);
                          setClientError(null);
                        }}
                        className="flex items-center gap-1 text-xs font-semibold text-yellow hover:text-yellow-dark transition-colors cursor-pointer"
                      >
                        <IconPlus className="size-3.5" /> New client
                      </button>
                    )}
                  </div>

                  {isEditing ? (
                    <div className="px-3 py-2 text-sm rounded-lg bg-(--color-surface) border border-border text-gray-400">
                      {position?.client_name}
                    </div>
                  ) : (
                    <select
                      id="pos-client"
                      required
                      value={form.clientId}
                      onChange={(e) => setForm({ ...form, clientId: e.target.value })}
                      className={INPUT_CLS}
                    >
                      <option value="">Select client…</option>
                      {clientOptions.map((c) => (
                        <option key={c.id} value={c.id}>
                          {c.name}
                        </option>
                      ))}
                    </select>
                  )}

                  {/* Inline client creation — the new client is saved to the brand's
                      list, so it stays in this dropdown for everyone afterwards. */}
                  {!isEditing && showClientForm && (
                    <div className="mt-2 p-3 rounded-lg bg-(--color-surface) border border-border space-y-2">
                      <p className="text-xs text-gray-400">
                        Adds a client to your brand&apos;s list permanently.
                      </p>
                      <div className="grid grid-cols-2 gap-2">
                        <input
                          autoFocus
                          type="text"
                          aria-label="New client name"
                          placeholder="Client name *"
                          value={clientForm.name}
                          onChange={(e) => setClientForm({ ...clientForm, name: e.target.value })}
                          onKeyDown={(e) => {
                            if (e.key === "Enter") {
                              // The wrapping <form> submits the position, not this.
                              e.preventDefault();
                              void handleCreateClient();
                            }
                            if (e.key === "Escape") closeClientForm();
                          }}
                          className={INPUT_CLS}
                        />
                        <input
                          type="text"
                          aria-label="New client city"
                          placeholder="City (optional)"
                          value={clientForm.city}
                          onChange={(e) => setClientForm({ ...clientForm, city: e.target.value })}
                          onKeyDown={(e) => {
                            if (e.key === "Enter") {
                              e.preventDefault();
                              void handleCreateClient();
                            }
                            if (e.key === "Escape") closeClientForm();
                          }}
                          className={INPUT_CLS}
                        />
                      </div>
                      {clientError && <p className="text-xs text-red-400">{clientError}</p>}
                      <div className="flex justify-end gap-2">
                        <button
                          type="button"
                          onClick={closeClientForm}
                          disabled={creatingClient}
                          className="px-3 py-1.5 rounded-lg text-xs font-semibold text-gray-400 hover:text-white transition-colors disabled:opacity-50 cursor-pointer"
                        >
                          Cancel
                        </button>
                        <button
                          type="button"
                          onClick={handleCreateClient}
                          disabled={creatingClient || !clientForm.name.trim()}
                          className="flex items-center gap-1 px-3 py-1.5 rounded-lg bg-yellow text-navy hover:bg-yellow-dark text-xs font-bold transition-all disabled:opacity-60 cursor-pointer"
                        >
                          <IconCheck className="size-3.5" />
                          {creatingClient ? "Adding…" : "Add client"}
                        </button>
                      </div>
                    </div>
                  )}
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
                {submitting
                  ? isEditing
                    ? "Saving…"
                    : "Creating…"
                  : isEditing
                    ? "Save Changes"
                    : "Create Position"}
              </button>
            </div>
          </motion.div>
        </motion.div>
      )}
    </AnimatePresence>
  );
}
