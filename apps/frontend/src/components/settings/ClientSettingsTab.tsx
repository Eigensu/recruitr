"use client";

import React, { useEffect, useState } from "react";
import {
  IconPlus,
  IconPencil,
  IconCheck,
  IconX,
  IconArchive,
  IconArchiveOff,
} from "@tabler/icons-react";
import { apiErrorMessage, useApiFetch } from "@/lib/api";
import { useToast } from "@/components/ui/Toast";
import {
  listClients,
  createClient,
  updateClient,
  archiveClient,
  type Client,
} from "@/lib/api/clients";

const INPUT_CLS =
  "w-full px-3 py-2 rounded-lg border border-border bg-surface text-text-primary text-sm" +
  " focus:outline-none focus:ring-2 focus:ring-navy dark:focus:ring-yellow transition-shadow";

/**
 * Admin-only client list management.
 *
 * The Settings page decides who sees this tab; the backend independently gates
 * every write behind require_admin.
 */
export default function ClientSettingsTab() {
  const apiFetch = useApiFetch();
  const toast = useToast();

  const [clients, setClients] = useState<Client[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [showArchived, setShowArchived] = useState(false);

  const [newClient, setNewClient] = useState({ name: "", city: "" });
  const [creating, setCreating] = useState(false);

  const [editingId, setEditingId] = useState<string | null>(null);
  const [editForm, setEditForm] = useState({ name: "", city: "" });
  const [savingId, setSavingId] = useState<string | null>(null);

  // Bumped by the Retry button to re-run the load effect.
  const [reloadNonce, setReloadNonce] = useState(0);

  useEffect(() => {
    let cancelled = false;
    async function load() {
      setIsLoading(true);
      setLoadError(null);
      try {
        // Archived clients are always fetched — the toggle only filters the
        // render, so flipping it doesn't cost a round trip.
        const data = await listClients(apiFetch, true);
        if (!cancelled) setClients(data);
      } catch (err) {
        if (!cancelled) setLoadError(apiErrorMessage(err, "Failed to load clients."));
      } finally {
        if (!cancelled) setIsLoading(false);
      }
    }
    void load();
    return () => {
      cancelled = true;
    };
  }, [apiFetch, reloadNonce]);

  async function handleCreate(e: React.FormEvent) {
    e.preventDefault();
    const name = newClient.name.trim();
    if (!name) return;
    setCreating(true);
    try {
      const created = await createClient(apiFetch, {
        name,
        city: newClient.city.trim() || undefined,
      });
      setClients((prev) =>
        [...prev.filter((c) => c.id !== created.id), created].sort((a, b) =>
          a.name.localeCompare(b.name),
        ),
      );
      setNewClient({ name: "", city: "" });
      toast(`Client "${created.name}" added`, "success");
    } catch (err) {
      toast(apiErrorMessage(err, "Failed to add client."), "error");
    } finally {
      setCreating(false);
    }
  }

  function startEdit(client: Client) {
    setEditingId(client.id);
    setEditForm({ name: client.name, city: client.city ?? "" });
  }

  function cancelEdit() {
    setEditingId(null);
    setEditForm({ name: "", city: "" });
  }

  async function handleSaveEdit(client: Client) {
    const name = editForm.name.trim();
    if (!name) return;
    setSavingId(client.id);
    try {
      const updated = await updateClient(apiFetch, client.id, {
        name,
        city: editForm.city.trim(),
      });
      setClients((prev) =>
        prev
          .map((c) => (c.id === client.id ? updated : c))
          .sort((a, b) => a.name.localeCompare(b.name)),
      );
      cancelEdit();
      toast("Client updated", "success");
    } catch (err) {
      toast(apiErrorMessage(err, "Failed to update client."), "error");
    } finally {
      setSavingId(null);
    }
  }

  async function handleArchive(client: Client) {
    setSavingId(client.id);
    try {
      await archiveClient(apiFetch, client.id);
      setClients((prev) => prev.map((c) => (c.id === client.id ? { ...c, is_active: false } : c)));
      toast(`"${client.name}" archived`, "success");
    } catch (err) {
      toast(apiErrorMessage(err, "Failed to archive client."), "error");
    } finally {
      setSavingId(null);
    }
  }

  async function handleRestore(client: Client) {
    setSavingId(client.id);
    try {
      const updated = await updateClient(apiFetch, client.id, { is_active: true });
      setClients((prev) => prev.map((c) => (c.id === client.id ? updated : c)));
      toast(`"${client.name}" restored`, "success");
    } catch (err) {
      toast(apiErrorMessage(err, "Failed to restore client."), "error");
    } finally {
      setSavingId(null);
    }
  }

  const archivedCount = clients.filter((c) => !c.is_active).length;
  const visible = showArchived ? clients : clients.filter((c) => c.is_active);

  return (
    <div className="space-y-6 animate-in fade-in duration-300">
      <div className="flex flex-col sm:flex-row sm:items-start justify-between gap-4">
        <div>
          <h2 className="text-lg font-bold text-text-primary">Client Management</h2>
          <p className="text-sm text-text-secondary mt-1">
            The list every recruiter picks from when creating a position. Renaming a client updates
            it on all of its positions.
          </p>
        </div>
        {archivedCount > 0 && (
          <label className="flex items-center gap-2 text-sm text-text-secondary cursor-pointer select-none whitespace-nowrap">
            <input
              type="checkbox"
              checked={showArchived}
              onChange={(e) => setShowArchived(e.target.checked)}
              className="rounded border-border text-navy focus:ring-navy w-4 h-4"
            />
            Show archived ({archivedCount})
          </label>
        )}
      </div>

      {/* Add client */}
      <form
        onSubmit={handleCreate}
        className="flex flex-col sm:flex-row gap-3 p-4 border border-border rounded-lg bg-surface"
      >
        <div className="flex-1">
          <label htmlFor="new-client-name" className="sr-only">
            Client name
          </label>
          <input
            id="new-client-name"
            type="text"
            placeholder="Client name"
            value={newClient.name}
            onChange={(e) => setNewClient({ ...newClient, name: e.target.value })}
            className={INPUT_CLS}
          />
        </div>
        <div className="flex-1">
          <label htmlFor="new-client-city" className="sr-only">
            City
          </label>
          <input
            id="new-client-city"
            type="text"
            placeholder="City (optional)"
            value={newClient.city}
            onChange={(e) => setNewClient({ ...newClient, city: e.target.value })}
            className={INPUT_CLS}
          />
        </div>
        <button
          type="submit"
          disabled={creating || !newClient.name.trim()}
          className="flex items-center justify-center gap-2 px-4 py-2 rounded-lg bg-navy dark:bg-yellow dark:text-navy text-white hover:opacity-90 disabled:opacity-50 transition-colors font-medium text-sm cursor-pointer whitespace-nowrap"
        >
          <IconPlus className="w-4 h-4" /> {creating ? "Adding…" : "Add Client"}
        </button>
      </form>

      {/* List */}
      {isLoading ? (
        <div className="py-12 text-center text-sm text-text-muted">Loading clients…</div>
      ) : loadError ? (
        <div className="py-8 px-4 text-center border border-border rounded-lg bg-surface">
          <p className="text-sm text-red-500 dark:text-red-400">{loadError}</p>
          <button
            type="button"
            onClick={() => setReloadNonce((n) => n + 1)}
            className="mt-3 px-4 py-2 rounded-lg border border-border text-sm font-medium text-text-primary hover:bg-surface-2 cursor-pointer"
          >
            Retry
          </button>
        </div>
      ) : visible.length === 0 ? (
        <div className="py-12 text-center border border-dashed border-border rounded-lg text-sm text-text-muted">
          {clients.length === 0
            ? "No clients yet. Add the first one above."
            : "Every client is archived. Tick “Show archived” to restore one."}
        </div>
      ) : (
        <div className="border border-border rounded-lg bg-surface overflow-hidden">
          <div className="hidden sm:grid grid-cols-[1fr_1fr_auto_auto] gap-3 px-4 py-3 bg-surface-2 border-b border-border text-xs font-semibold text-text-secondary uppercase tracking-wider">
            <span>Name</span>
            <span>City</span>
            <span className="text-right">Positions</span>
            <span className="sr-only">Actions</span>
          </div>
          <div className="divide-y divide-border">
            {visible.map((client) => {
              const busy = savingId === client.id;
              const isEditing = editingId === client.id;
              return (
                <div
                  key={client.id}
                  className={`grid grid-cols-1 sm:grid-cols-[1fr_1fr_auto_auto] gap-2 sm:gap-3 items-center px-4 py-3 ${
                    client.is_active ? "" : "opacity-60"
                  }`}
                >
                  {isEditing ? (
                    <>
                      <input
                        autoFocus
                        type="text"
                        aria-label="Client name"
                        value={editForm.name}
                        onChange={(e) => setEditForm({ ...editForm, name: e.target.value })}
                        onKeyDown={(e) => {
                          if (e.key === "Enter") void handleSaveEdit(client);
                          if (e.key === "Escape") cancelEdit();
                        }}
                        className={INPUT_CLS}
                      />
                      <input
                        type="text"
                        aria-label="Client city"
                        placeholder="City"
                        value={editForm.city}
                        onChange={(e) => setEditForm({ ...editForm, city: e.target.value })}
                        onKeyDown={(e) => {
                          if (e.key === "Enter") void handleSaveEdit(client);
                          if (e.key === "Escape") cancelEdit();
                        }}
                        className={INPUT_CLS}
                      />
                      <span className="text-sm text-text-secondary sm:text-right">
                        {client.position_count}
                      </span>
                      <div className="flex items-center gap-1 sm:justify-end">
                        <button
                          type="button"
                          onClick={() => void handleSaveEdit(client)}
                          disabled={busy || !editForm.name.trim()}
                          className="p-1.5 rounded-lg text-green-600 hover:bg-surface-2 disabled:opacity-40 cursor-pointer"
                          aria-label="Save client"
                        >
                          <IconCheck className="w-4 h-4" />
                        </button>
                        <button
                          type="button"
                          onClick={cancelEdit}
                          disabled={busy}
                          className="p-1.5 rounded-lg text-text-muted hover:bg-surface-2 cursor-pointer"
                          aria-label="Cancel edit"
                        >
                          <IconX className="w-4 h-4" />
                        </button>
                      </div>
                    </>
                  ) : (
                    <>
                      <div className="min-w-0">
                        <p className="text-sm font-medium text-text-primary truncate">
                          {client.name}
                        </p>
                        <p className="text-xs text-text-muted">{client.code}</p>
                      </div>
                      <span className="text-sm text-text-secondary truncate">
                        {client.city ?? <span className="text-text-muted">—</span>}
                      </span>
                      <span className="text-sm text-text-secondary sm:text-right">
                        {client.position_count}
                      </span>
                      <div className="flex items-center gap-1 sm:justify-end">
                        {client.is_active ? (
                          <>
                            <button
                              type="button"
                              onClick={() => startEdit(client)}
                              className="p-1.5 rounded-lg text-text-muted hover:bg-surface-2 hover:text-text-primary cursor-pointer"
                              aria-label={`Edit ${client.name}`}
                            >
                              <IconPencil className="w-4 h-4" />
                            </button>
                            <button
                              type="button"
                              onClick={() => void handleArchive(client)}
                              disabled={busy}
                              title={
                                client.position_count > 0
                                  ? "Delete this client's positions first"
                                  : "Archive client"
                              }
                              className="p-1.5 rounded-lg text-text-muted hover:bg-surface-2 hover:text-red-500 disabled:opacity-40 cursor-pointer"
                              aria-label={`Archive ${client.name}`}
                            >
                              <IconArchive className="w-4 h-4" />
                            </button>
                          </>
                        ) : (
                          <button
                            type="button"
                            onClick={() => void handleRestore(client)}
                            disabled={busy}
                            className="flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg border border-border text-xs font-medium text-text-secondary hover:bg-surface-2 hover:text-text-primary disabled:opacity-40 cursor-pointer"
                          >
                            <IconArchiveOff className="w-3.5 h-3.5" /> Restore
                          </button>
                        )}
                      </div>
                    </>
                  )}
                </div>
              );
            })}
          </div>
        </div>
      )}
    </div>
  );
}
