"use client";

import React, { useEffect, useState, useMemo } from "react";
import Link from "next/link";
import { IconPlus, IconSearch, IconX, IconUsers, IconBuildingStore } from "@tabler/icons-react";
import { apiErrorMessage, useApiFetch } from "@/lib/api";
import { useToast } from "@/components/ui/Toast";
import { listClients, createClient, type Client } from "@/lib/api/clients";
import { Skeleton } from "@/components/common/skeletons/Skeleton";
import { ESTABLISHMENT_TAG_OPTIONS } from "@/lib/constants/candidate";

// Fixed identities for the loading placeholders. Using the map index as a key
// makes React tie each element to a position rather than to a thing.
const SKELETON_KEYS = ["a", "b", "c", "d", "e", "f"];

export default function ClientsPage() {
  const apiFetch = useApiFetch();
  const toast = useToast();

  const [clients, setClients] = useState<Client[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [loadError, setLoadError] = useState<string | null>(null);

  const [search, setSearch] = useState("");
  const [statusFilter, setStatusFilter] = useState<"all" | "active" | "inactive">("all");
  const [userFilter, setUserFilter] = useState<"all" | "has_users" | "no_users">("all");

  const [isCreateModalOpen, setIsCreateModalOpen] = useState(false);
  const [newClient, setNewClient] = useState({ name: "", city: "", establishment_tag: "" });
  const [creating, setCreating] = useState(false);

  useEffect(() => {
    let cancelled = false;
    async function load() {
      setIsLoading(true);
      setLoadError(null);
      try {
        const data = await listClients(apiFetch, true); // fetch all including archived
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
  }, [apiFetch]);

  async function handleCreate(e: React.FormEvent) {
    e.preventDefault();
    const name = newClient.name.trim();
    if (!name) return;
    setCreating(true);
    try {
      const created = await createClient(apiFetch, {
        name,
        city: newClient.city.trim() || undefined,
        establishment_tag: newClient.establishment_tag || undefined,
      });
      setClients((prev) =>
        [...prev.filter((c) => c.id !== created.id), created].sort((a, b) =>
          a.name.localeCompare(b.name),
        ),
      );
      setNewClient({ name: "", city: "", establishment_tag: "" });
      setIsCreateModalOpen(false);
      toast(`Client "${created.name}" created`, "success");
      // Optional: router.push(`/clients/${created.id}`)
    } catch (err) {
      toast(apiErrorMessage(err, "Failed to create client."), "error");
    } finally {
      setCreating(false);
    }
  }

  const filteredClients = useMemo(() => {
    return clients.filter((c) => {
      const q = search.toLowerCase();
      if (q) {
        const matches = [
          c.name,
          c.code,
          c.city,
          c.industry,
          c.establishment_tag,
          c.website,
          c.contact_person,
          c.contact_email,
          ...(c.allowed_domains || []),
          ...(c.allowed_emails || []),
        ]
          .filter(Boolean)
          .some((v) => v?.toLowerCase().includes(q));
        if (!matches) return false;
      }
      if (statusFilter === "active" && !c.is_active) return false;
      if (statusFilter === "inactive" && c.is_active) return false;
      if (userFilter === "has_users" && (c.user_count || 0) === 0) return false;
      if (userFilter === "no_users" && (c.user_count || 0) > 0) return false;
      return true;
    });
  }, [clients, search, statusFilter, userFilter]);

  // Split out of a four-way nested ternary: the branches are mutually
  // exclusive states, and early returns say that far more plainly.
  function renderClientList() {
    if (isLoading) {
      return (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {SKELETON_KEYS.map((key) => (
            <div
              key={key}
              className="p-5 rounded-xl border border-border bg-surface flex flex-col min-h-[140px]"
            >
              <Skeleton className="h-6 w-3/4 mb-3" />
              <div className="flex gap-2 mb-auto">
                <Skeleton className="h-4 w-16" />
                <Skeleton className="h-4 w-24" />
              </div>
              <div className="flex gap-4 mt-4 pt-4 border-t border-border">
                <Skeleton className="h-4 w-12" />
                <Skeleton className="h-4 w-12" />
                <Skeleton className="h-4 w-12" />
              </div>
            </div>
          ))}
        </div>
      );
    }
    if (loadError) {
      return (
        <div className="p-6 bg-red-500/10 border border-red-500/20 rounded-xl text-center text-red-500">
          {loadError}
        </div>
      );
    }
    if (filteredClients.length === 0) {
      return (
        <div className="py-20 flex flex-col items-center justify-center border border-dashed border-border rounded-xl text-center">
          <IconBuildingStore className="size-12 text-border mb-4" />
          <h3 className="text-lg font-medium text-text-primary">No clients found</h3>
          <p className="text-sm text-text-secondary mt-1 max-w-sm">
            {search || statusFilter !== "all"
              ? "Try adjusting your search or filters to find what you're looking for."
              : "Create your first client to start assigning positions to them."}
          </p>
        </div>
      );
    }
    return (
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
        {filteredClients.map((client) => (
          // A real anchor rather than a div with onClick: navigation should be
          // reachable by keyboard, announced as a link, and open in a new tab
          // on middle-click — none of which a click handler gives you.
          <Link
            key={client.id}
            href={`/clients/${client.id}`}
            className={`p-5 rounded-xl border border-border bg-surface hover:shadow-md transition-all cursor-pointer group flex flex-col focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-navy dark:focus-visible:outline-yellow ${
              !client.is_active ? "opacity-60" : ""
            }`}
          >
            <div className="flex justify-between items-start mb-3">
              <div className="flex-1 min-w-0 pr-3">
                <h3 className="text-lg font-bold text-text-primary truncate group-hover:text-navy dark:group-hover:text-yellow transition-colors">
                  {client.name}
                </h3>
                <div className="flex items-center gap-2 mt-1">
                  <span className="text-xs font-mono text-text-muted bg-surface-2 px-1.5 py-0.5 rounded">
                    {client.code}
                  </span>
                  {client.city && (
                    <span className="text-xs text-text-secondary truncate">{client.city}</span>
                  )}
                </div>
              </div>
              {!client.is_active && (
                <span className="px-2 py-0.5 text-[10px] font-bold tracking-wider text-red-600 bg-red-100 rounded-full shrink-0">
                  ARCHIVED
                </span>
              )}
            </div>
            <div className="mt-auto pt-4 flex gap-4 text-sm text-text-secondary border-t border-border">
              <div>
                <span className="font-semibold text-text-primary">{client.position_count}</span> Pos
              </div>
              <div>
                <span className="font-semibold text-text-primary">{client.candidate_count}</span>{" "}
                Cand
              </div>
              <div className="flex items-center gap-1">
                <IconUsers className="size-4" />
                <span className="font-semibold text-text-primary">{client.user_count}</span>
              </div>
            </div>
          </Link>
        ))}
      </div>
    );
  }

  return (
    <main className="mx-auto w-full max-w-7xl p-4 sm:p-6 lg:p-8 animate-in fade-in duration-300">
      <header className="mb-8 flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-text-primary tracking-tight">Clients</h1>
          <p className="text-sm text-text-secondary mt-1">
            Manage organizations, authorized domains, and client users.
          </p>
        </div>
        <button
          type="button"
          onClick={() => setIsCreateModalOpen(true)}
          className="flex items-center justify-center gap-2 px-4 py-2 bg-navy dark:bg-yellow dark:text-navy text-white rounded-lg hover:opacity-90 transition-opacity font-medium text-sm shadow-sm"
        >
          <IconPlus className="size-4" /> Create Company
        </button>
      </header>

      <div className="mb-6 flex flex-col md:flex-row gap-4 items-center bg-surface p-4 rounded-xl border border-border shadow-sm">
        <div className="relative flex-1 w-full">
          <IconSearch className="absolute left-3 top-1/2 -translate-y-1/2 size-4 text-text-muted" />
          <input
            type="text"
            placeholder="Search by company, code, city, industry..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="w-full pl-9 pr-4 py-2 bg-surface-2 border border-border rounded-lg text-sm text-text-primary focus:outline-none focus:ring-2 focus:ring-navy dark:focus:ring-yellow transition-shadow"
          />
        </div>
        <div className="flex gap-2 w-full md:w-auto overflow-x-auto pb-2 md:pb-0 hide-scrollbar">
          <select
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value as "all" | "active" | "inactive")}
            className="px-3 py-2 bg-surface-2 border border-border rounded-lg text-sm text-text-primary focus:outline-none focus:ring-2 focus:ring-navy dark:focus:ring-yellow cursor-pointer"
          >
            <option value="all">All Status</option>
            <option value="active">Active</option>
            <option value="inactive">Archived</option>
          </select>
          <select
            value={userFilter}
            onChange={(e) => setUserFilter(e.target.value as "all" | "has_users" | "no_users")}
            className="px-3 py-2 bg-surface-2 border border-border rounded-lg text-sm text-text-primary focus:outline-none focus:ring-2 focus:ring-navy dark:focus:ring-yellow cursor-pointer"
          >
            <option value="all">All Users</option>
            <option value="has_users">Has Users</option>
            <option value="no_users">No Users</option>
          </select>
        </div>
      </div>

      {renderClientList()}

      {isCreateModalOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 backdrop-blur-sm p-4 animate-in fade-in duration-200">
          <div className="bg-surface border border-border rounded-xl shadow-2xl w-full max-w-md overflow-hidden flex flex-col">
            <div className="flex items-center justify-between p-4 border-b border-border bg-surface-2">
              <h3 className="font-bold text-text-primary">Create Company</h3>
              <button
                type="button"
                onClick={() => setIsCreateModalOpen(false)}
                className="text-text-muted hover:text-text-primary cursor-pointer p-1"
              >
                <IconX className="size-5" />
              </button>
            </div>
            <form onSubmit={handleCreate} className="p-4 flex flex-col gap-4">
              <div>
                <label
                  htmlFor="new-client-name"
                  className="block text-sm font-medium text-text-primary mb-1"
                >
                  Company Name
                </label>
                <input
                  id="new-client-name"
                  autoFocus
                  type="text"
                  required
                  value={newClient.name}
                  onChange={(e) => setNewClient({ ...newClient, name: e.target.value })}
                  className="w-full px-3 py-2 bg-surface border border-border rounded-lg text-sm text-text-primary focus:ring-2 focus:ring-navy dark:focus:ring-yellow focus:outline-none"
                  placeholder="e.g. Acme Corp"
                />
              </div>
              <div>
                <label
                  htmlFor="new-client-city"
                  className="block text-sm font-medium text-text-primary mb-1"
                >
                  City (Optional)
                </label>
                <input
                  id="new-client-city"
                  type="text"
                  value={newClient.city}
                  onChange={(e) => setNewClient({ ...newClient, city: e.target.value })}
                  className="w-full px-3 py-2 bg-surface border border-border rounded-lg text-sm text-text-primary focus:ring-2 focus:ring-navy dark:focus:ring-yellow focus:outline-none"
                  placeholder="e.g. New York"
                />
              </div>
              <div>
                <label
                  htmlFor="new-client-establishment-tag"
                  className="block text-sm font-medium text-text-primary mb-1"
                >
                  Establishment Tag (Optional)
                </label>
                <select
                  id="new-client-establishment-tag"
                  value={newClient.establishment_tag}
                  onChange={(e) =>
                    setNewClient({ ...newClient, establishment_tag: e.target.value })
                  }
                  className="w-full px-3 py-2 bg-surface border border-border rounded-lg text-sm text-text-primary focus:ring-2 focus:ring-navy dark:focus:ring-yellow focus:outline-none cursor-pointer"
                >
                  <option value="">Select...</option>
                  {ESTABLISHMENT_TAG_OPTIONS.map((o) => (
                    <option key={o.value} value={o.value}>
                      {o.label}
                    </option>
                  ))}
                </select>
              </div>
              <div className="mt-2 flex justify-end gap-2">
                <button
                  type="button"
                  onClick={() => setIsCreateModalOpen(false)}
                  className="px-4 py-2 text-sm font-medium text-text-secondary hover:bg-surface-2 rounded-lg cursor-pointer"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={creating || !newClient.name.trim()}
                  className="px-4 py-2 bg-navy dark:bg-yellow dark:text-navy text-white rounded-lg text-sm font-medium hover:opacity-90 disabled:opacity-50 cursor-pointer"
                >
                  {creating ? "Creating..." : "Create"}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </main>
  );
}
