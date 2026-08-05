"use client";

import React, { useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import {
  IconArrowLeft,
  IconPencil,
  IconX,
  IconArchive,
  IconArchiveOff,
  IconTrash,
  IconPlus,
} from "@tabler/icons-react";
import { apiErrorMessage, useApiFetch } from "@/lib/api";
import { Skeleton } from "@/components/common/skeletons/Skeleton";
import { useCurrentUser } from "@/hooks/useCurrentUser";
import { useToast } from "@/components/ui/Toast";
import {
  getClient,
  updateClient,
  archiveClient,
  listClientUsers,
  inviteClientUser,
  removeClientUser,
  type Client,
  type ClientUser,
} from "@/lib/api/clients";

// Chip colours per authorization state. A lookup beats a nested ternary:
// adding a state is one line and cannot reorder the existing branches.
const USER_STATUS_STYLES: Record<string, string> = {
  Active: "bg-green-100 text-green-700",
  Inactive: "bg-red-100 text-red-700",
  Pending: "bg-yellow-100 text-yellow-800",
};

/** The Authorized Users tab.
 *
 * Split out of ClientDetailsPage purely to keep that component's cognitive
 * complexity in range — the page already branched on loading, load failure,
 * edit mode, active tab and maintainer rights before reaching this table.
 */
function AuthorizedUsersPanel({
  users,
  isMaintainer,
  onInvite,
  onRemove,
}: Readonly<{
  users: ClientUser[];
  isMaintainer: boolean;
  onInvite: () => void;
  onRemove: (userId: string) => void;
}>) {
  return (
    <div>
      <div className="flex items-center justify-between p-4 border-b border-border bg-surface-2">
        <h3 className="font-bold text-text-primary">Authorized Users</h3>
        {isMaintainer && (
          <button
            type="button"
            onClick={() => onInvite()}
            className="flex items-center gap-2 px-3 py-1.5 bg-navy dark:bg-yellow dark:text-navy text-white rounded-lg text-sm font-medium hover:opacity-90 transition-opacity cursor-pointer shadow-sm"
          >
            <IconPlus className="size-4" /> Invite User
          </button>
        )}
      </div>

      <div className="overflow-x-auto">
        <table className="w-full text-sm text-left">
          <thead className="bg-surface-2 border-b border-border text-xs uppercase text-text-secondary font-semibold">
            <tr>
              <th className="px-4 py-3">Name</th>
              <th className="px-4 py-3">Email</th>
              <th className="px-4 py-3">Role</th>
              <th className="px-4 py-3">Status</th>
              <th className="px-4 py-3">Last Login</th>
              <th className="px-4 py-3 text-right">Actions</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-border">
            {users.map((u) => (
              <tr key={u.id} className="hover:bg-surface-2/50 transition-colors">
                <td className="px-4 py-3 font-medium text-text-primary">
                  {u.name || <span className="text-text-muted italic">Pending</span>}
                </td>
                <td className="px-4 py-3 text-text-secondary">{u.email}</td>
                <td className="px-4 py-3">
                  <span className="px-2 py-0.5 bg-surface-3 rounded text-xs font-mono">
                    {u.role}
                  </span>
                </td>
                <td className="px-4 py-3">
                  <span
                    className={`px-2 py-1 rounded-full text-[10px] font-bold tracking-wider uppercase ${USER_STATUS_STYLES[u.status] ?? USER_STATUS_STYLES.Pending}`}
                  >
                    {u.status}
                  </span>
                </td>
                <td className="px-4 py-3 text-text-muted text-xs">
                  {u.last_login
                    ? new Date(u.last_login).toLocaleString("en-US", {
                        month: "short",
                        day: "numeric",
                        year: "numeric",
                        hour: "2-digit",
                        minute: "2-digit",
                        hour12: false,
                      })
                    : "—"}
                </td>
                <td className="px-4 py-3 text-right">
                  {u.status !== "Inactive" && isMaintainer && (
                    <button
                      type="button"
                      onClick={() => onRemove(u.id)}
                      className="p-1.5 text-text-muted hover:text-red-500 hover:bg-red-50 rounded-md transition-colors cursor-pointer"
                      title="Remove Access"
                    >
                      <IconTrash className="size-4" />
                    </button>
                  )}
                </td>
              </tr>
            ))}
            {users.length === 0 && (
              <tr>
                <td colSpan={6} className="px-4 py-12 text-center text-text-muted">
                  No users authorized for this client yet.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}

/** The Company Info tab: the detail grid, its edit form and the rollup stats.
 *
 * Split out of ClientDetailsPage to bring that component's cognitive
 * complexity back in range — eight `isEditing ? input : text` branches lived
 * here, on top of the page's own branching for loading, load failure, active
 * tab and maintainer rights.
 */
function CompanyInfoPanel({
  client,
  isEditing,
  editForm,
  setEditForm,
  saving,
  onCancel,
  onSave,
  userCount,
}: Readonly<{
  client: Client;
  isEditing: boolean;
  editForm: Partial<Client>;
  setEditForm: React.Dispatch<React.SetStateAction<Partial<Client>>>;
  saving: boolean;
  onCancel: () => void;
  onSave: () => void;
  userCount: number;
}>) {
  return (
    <div className="p-6">
      <h3 className="text-lg font-bold text-text-primary mb-4">Company Details</h3>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-x-8 gap-y-6">
        {/* Field pairs */}
        <div className="space-y-1">
          <label htmlFor="client-name" className="text-sm font-medium text-text-secondary">
            Company Name
          </label>
          {isEditing ? (
            <input
              id="client-name"
              type="text"
              value={editForm.name}
              onChange={(e) => setEditForm({ ...editForm, name: e.target.value })}
              className="w-full px-3 py-1.5 border border-border rounded-md bg-surface text-sm"
            />
          ) : (
            <p className="text-text-primary font-medium">{client.name}</p>
          )}
        </div>

        <div className="space-y-1">
          <label htmlFor="client-city" className="text-sm font-medium text-text-secondary">
            City
          </label>
          {isEditing ? (
            <input
              id="client-city"
              type="text"
              value={editForm.city ?? ""}
              onChange={(e) => setEditForm({ ...editForm, city: e.target.value })}
              className="w-full px-3 py-1.5 border border-border rounded-md bg-surface text-sm"
            />
          ) : (
            <p className="text-text-primary">{client.city || "—"}</p>
          )}
        </div>

        <div className="space-y-1">
          <label htmlFor="client-industry" className="text-sm font-medium text-text-secondary">
            Industry
          </label>
          {isEditing ? (
            <input
              id="client-industry"
              type="text"
              value={editForm.industry ?? ""}
              onChange={(e) => setEditForm({ ...editForm, industry: e.target.value })}
              className="w-full px-3 py-1.5 border border-border rounded-md bg-surface text-sm"
            />
          ) : (
            <p className="text-text-primary">{client.industry || "—"}</p>
          )}
        </div>

        <div className="space-y-1">
          <label htmlFor="client-website" className="text-sm font-medium text-text-secondary">
            Website
          </label>
          {isEditing ? (
            <input
              id="client-website"
              type="text"
              value={editForm.website ?? ""}
              onChange={(e) => setEditForm({ ...editForm, website: e.target.value })}
              className="w-full px-3 py-1.5 border border-border rounded-md bg-surface text-sm"
            />
          ) : (
            <p className="text-text-primary">{client.website || "—"}</p>
          )}
        </div>

        <div className="space-y-1">
          <label
            htmlFor="client-contact_person"
            className="text-sm font-medium text-text-secondary"
          >
            Contact Person
          </label>
          {isEditing ? (
            <input
              id="client-contact_person"
              type="text"
              value={editForm.contact_person ?? ""}
              onChange={(e) => setEditForm({ ...editForm, contact_person: e.target.value })}
              className="w-full px-3 py-1.5 border border-border rounded-md bg-surface text-sm"
            />
          ) : (
            <p className="text-text-primary">{client.contact_person || "—"}</p>
          )}
        </div>

        <div className="space-y-1">
          <label htmlFor="client-contact_email" className="text-sm font-medium text-text-secondary">
            Contact Email
          </label>
          {isEditing ? (
            <input
              id="client-contact_email"
              type="email"
              value={editForm.contact_email ?? ""}
              onChange={(e) => setEditForm({ ...editForm, contact_email: e.target.value })}
              className="w-full px-3 py-1.5 border border-border rounded-md bg-surface text-sm"
            />
          ) : (
            <p className="text-text-primary">{client.contact_email || "—"}</p>
          )}
        </div>

        <div className="space-y-1 md:col-span-2">
          <label
            htmlFor="client-allowed_domains"
            className="text-sm font-medium text-text-secondary"
          >
            Authorized Domains
          </label>
          {isEditing ? (
            <input
              id="client-allowed_domains"
              type="text"
              value={editForm.allowed_domains?.join(", ") || ""}
              onChange={(e) =>
                setEditForm({
                  ...editForm,
                  allowed_domains: e.target.value
                    .split(",")
                    .map((s) => s.trim())
                    .filter(Boolean),
                })
              }
              placeholder="@company.com, @subsidiary.com"
              className="w-full px-3 py-1.5 border border-border rounded-md bg-surface text-sm"
            />
          ) : (
            <p className="text-text-primary">
              {client.allowed_domains?.length ? client.allowed_domains.join(", ") : "—"}
            </p>
          )}
        </div>

        <div className="space-y-1 md:col-span-2">
          <label
            htmlFor="client-allowed_emails"
            className="text-sm font-medium text-text-secondary"
          >
            Authorized Emails
          </label>
          {isEditing ? (
            <input
              id="client-allowed_emails"
              type="text"
              value={editForm.allowed_emails?.join(", ") || ""}
              onChange={(e) =>
                setEditForm({
                  ...editForm,
                  allowed_emails: e.target.value
                    .split(",")
                    .map((s) => s.trim())
                    .filter(Boolean),
                })
              }
              placeholder="ceo@other.com, hr@company.com"
              className="w-full px-3 py-1.5 border border-border rounded-md bg-surface text-sm"
            />
          ) : (
            <p className="text-text-primary">
              {client.allowed_emails?.length ? client.allowed_emails.join(", ") : "—"}
            </p>
          )}
        </div>
      </div>

      {isEditing && (
        <div className="mt-8 flex justify-end gap-3 pt-6 border-t border-border">
          <button
            type="button"
            onClick={() => onCancel()}
            className="px-4 py-2 border border-border rounded-lg text-sm font-medium hover:bg-surface-2 cursor-pointer"
          >
            Cancel
          </button>
          <button
            type="button"
            onClick={onSave}
            disabled={saving}
            className="px-4 py-2 bg-navy dark:bg-yellow dark:text-navy text-white rounded-lg text-sm font-medium hover:opacity-90 disabled:opacity-50 cursor-pointer"
          >
            {saving ? "Saving..." : "Save Changes"}
          </button>
        </div>
      )}

      {!isEditing && (
        <div className="mt-8 pt-6 border-t border-border grid grid-cols-2 md:grid-cols-4 gap-4 text-center">
          <div>
            <p className="text-2xl font-bold text-navy dark:text-yellow">{client.position_count}</p>
            <p className="text-xs text-text-secondary uppercase tracking-wider font-semibold">
              Positions
            </p>
          </div>
          <div>
            <p className="text-2xl font-bold text-navy dark:text-yellow">
              {client.candidate_count}
            </p>
            <p className="text-xs text-text-secondary uppercase tracking-wider font-semibold">
              Candidates
            </p>
          </div>
          <div>
            <p className="text-2xl font-bold text-navy dark:text-yellow">{userCount}</p>
            <p className="text-xs text-text-secondary uppercase tracking-wider font-semibold">
              Users
            </p>
          </div>
          <div className="text-left flex flex-col justify-center">
            <p className="text-xs text-text-muted">
              Created:{" "}
              {client.created_at
                ? new Date(client.created_at).toLocaleDateString("en-US", {
                    month: "short",
                    day: "numeric",
                    year: "numeric",
                  })
                : "—"}
            </p>
            {client.created_by_id && (
              <p className="text-[10px] text-text-muted mt-0.5 truncate max-w-[150px]">
                By: {client.created_by_id}
              </p>
            )}
            <p className="text-xs text-text-muted mt-2">
              Updated:{" "}
              {client.updated_at
                ? new Date(client.updated_at).toLocaleDateString("en-US", {
                    month: "short",
                    day: "numeric",
                    year: "numeric",
                  })
                : "—"}
            </p>
            {client.updated_by_id && (
              <p className="text-[10px] text-text-muted mt-0.5 truncate max-w-[150px]">
                By: {client.updated_by_id}
              </p>
            )}
          </div>
        </div>
      )}
    </div>
  );
}

/** All data loading and mutations for the client detail page.
 *
 * Separated from the component because six async handlers, each with its own
 * guard clauses and try/catch, counted toward the component's cognitive
 * complexity on top of its rendering branches. Keeping fetch-and-mutate here
 * leaves the page to decide what to draw.
 */
function useClientDetails(id: string) {
  const apiFetch = useApiFetch();
  const toast = useToast();

  const [client, setClient] = useState<Client | null>(null);
  const [users, setUsers] = useState<ClientUser[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [loadError, setLoadError] = useState<string | null>(null);

  // Editing state for Company Info
  const [isEditing, setIsEditing] = useState(false);
  const [editForm, setEditForm] = useState<Partial<Client>>({});
  const [saving, setSaving] = useState(false);

  // Users Tab state
  const [isInviteModalOpen, setIsInviteModalOpen] = useState(false);
  const [inviteEmail, setInviteEmail] = useState("");
  const [inviteRole, setInviteRole] = useState("client");
  const [inviting, setInviting] = useState(false);

  useEffect(() => {
    let cancelled = false;
    async function load() {
      setIsLoading(true);
      try {
        const [clientData, usersData] = await Promise.all([
          getClient(apiFetch, id),
          listClientUsers(apiFetch, id),
        ]);
        if (!cancelled) {
          setClient(clientData);
          setUsers(usersData);
        }
      } catch (err) {
        if (!cancelled) setLoadError(apiErrorMessage(err, "Failed to load client details."));
      } finally {
        if (!cancelled) setIsLoading(false);
      }
    }
    void load();
    return () => {
      cancelled = true;
    };
  }, [apiFetch, id]);

  function startEdit() {
    if (!client) return;
    setEditForm({
      name: client.name,
      city: client.city || "",
      industry: client.industry || "",
      website: client.website || "",
      contact_person: client.contact_person || "",
      contact_email: client.contact_email || "",
      contact_phone: client.contact_phone || "",
      allowed_domains: client.allowed_domains || [],
      allowed_emails: client.allowed_emails || [],
    });
    setIsEditing(true);
  }

  async function saveEdit() {
    if (!client) return;
    setSaving(true);
    try {
      const updated = await updateClient(apiFetch, client.id, {
        name: editForm.name,
        city: editForm.city ?? undefined,
        industry: editForm.industry ?? undefined,
        website: editForm.website ?? undefined,
        contact_person: editForm.contact_person ?? undefined,
        contact_email: editForm.contact_email ?? undefined,
        contact_phone: editForm.contact_phone ?? undefined,
        allowed_domains: editForm.allowed_domains,
        allowed_emails: editForm.allowed_emails,
      });
      setClient(updated);
      setIsEditing(false);
      toast("Company updated", "success");
    } catch (err) {
      toast(apiErrorMessage(err, "Failed to update company."), "error");
    } finally {
      setSaving(false);
    }
  }

  async function handleArchiveToggle() {
    if (!client) return;
    setSaving(true);
    try {
      if (client.is_active) {
        await archiveClient(apiFetch, client.id);
        setClient({ ...client, is_active: false });
        toast("Company archived", "success");
      } else {
        const updated = await updateClient(apiFetch, client.id, { is_active: true });
        setClient(updated);
        toast("Company restored", "success");
      }
    } catch (err) {
      toast(apiErrorMessage(err, "Failed to archive/restore."), "error");
    } finally {
      setSaving(false);
    }
  }

  async function handleInviteUser(e: React.FormEvent) {
    e.preventDefault();
    setInviting(true);
    try {
      const newUser = await inviteClientUser(apiFetch, id, {
        email: inviteEmail,
        role: inviteRole,
      });
      setUsers((prev) => [...prev, newUser].sort((a, b) => a.email.localeCompare(b.email)));
      setInviteEmail("");
      setIsInviteModalOpen(false);
      toast("User invited successfully", "success");
    } catch (err) {
      toast(apiErrorMessage(err, "Failed to invite user."), "error");
    } finally {
      setInviting(false);
    }
  }

  async function handleRemoveUser(userId: string) {
    if (!confirm("Are you sure you want to remove access for this user?")) return;
    try {
      await removeClientUser(apiFetch, id, userId);
      setUsers((prev) => prev.map((u) => (u.id === userId ? { ...u, status: "Inactive" } : u)));
      toast("User access removed", "success");
    } catch (err) {
      toast(apiErrorMessage(err, "Failed to remove user access."), "error");
    }
  }

  return {
    client,
    users,
    isLoading,
    loadError,
    isEditing,
    setIsEditing,
    editForm,
    setEditForm,
    saving,
    isInviteModalOpen,
    setIsInviteModalOpen,
    inviteEmail,
    setInviteEmail,
    inviteRole,
    setInviteRole,
    inviting,
    startEdit,
    saveEdit,
    handleArchiveToggle,
    handleInviteUser,
    handleRemoveUser,
  };
}

export default function ClientDetailsPage() {
  const { id } = useParams() as { id: string };
  const router = useRouter();
  const { isMaintainer } = useCurrentUser();
  const [activeTab, setActiveTab] = useState<"info" | "users">("info");
  const {
    client,
    users,
    isLoading,
    loadError,
    isEditing,
    setIsEditing,
    editForm,
    setEditForm,
    saving,
    isInviteModalOpen,
    setIsInviteModalOpen,
    inviteEmail,
    setInviteEmail,
    inviteRole,
    setInviteRole,
    inviting,
    startEdit,
    saveEdit,
    handleArchiveToggle,
    handleInviteUser,
    handleRemoveUser,
  } = useClientDetails(id);

  if (isLoading) {
    return (
      <main className="mx-auto w-full max-w-5xl p-4 sm:p-6 lg:p-8 animate-in fade-in">
        <div className="mb-6 flex flex-col sm:flex-row sm:items-center justify-between gap-4">
          <Skeleton className="h-8 w-64" />
          <Skeleton className="h-10 w-32" />
        </div>
        <Skeleton className="h-[400px] w-full rounded-xl" />
      </main>
    );
  }
  if (loadError || !client) {
    return <div className="p-8 text-center text-red-500">{loadError || "Client not found"}</div>;
  }

  return (
    <main className="mx-auto w-full max-w-5xl p-4 sm:p-6 lg:p-8 animate-in fade-in duration-300">
      {/* Header */}
      <div className="mb-6 flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div className="flex items-center gap-4">
          <button
            type="button"
            onClick={() => router.push("/clients")}
            className="p-2 rounded-full hover:bg-surface-2 text-text-secondary hover:text-text-primary transition-colors cursor-pointer"
          >
            <IconArrowLeft className="size-5" />
          </button>
          <div>
            <div className="flex items-center gap-3">
              <h1 className="text-2xl font-bold text-text-primary tracking-tight">{client.name}</h1>
              {!client.is_active && (
                <span className="px-2 py-0.5 text-xs font-bold tracking-wider text-red-600 bg-red-100 rounded-full">
                  ARCHIVED
                </span>
              )}
            </div>
            <p className="text-sm text-text-secondary mt-1 font-mono">{client.code}</p>
          </div>
        </div>
        <div className="flex items-center gap-2">
          {!isEditing && client.is_active && isMaintainer && (
            <button
              type="button"
              onClick={startEdit}
              className="flex items-center gap-2 px-4 py-2 bg-surface-2 border border-border text-text-primary rounded-lg hover:bg-surface-3 transition-colors text-sm font-medium cursor-pointer"
            >
              <IconPencil className="size-4" /> Edit
            </button>
          )}
          {isMaintainer && (
            <button
              type="button"
              onClick={handleArchiveToggle}
              disabled={saving}
              className={`flex items-center gap-2 px-4 py-2 border rounded-lg text-sm font-medium transition-colors cursor-pointer disabled:opacity-50 ${
                client.is_active
                  ? "border-red-200 text-red-600 hover:bg-red-50"
                  : "border-border text-text-primary bg-surface hover:bg-surface-2"
              }`}
            >
              {client.is_active ? (
                <IconArchive className="size-4" />
              ) : (
                <IconArchiveOff className="size-4" />
              )}
              {client.is_active ? "Archive" : "Restore"}
            </button>
          )}
        </div>
      </div>

      {/* Tabs */}
      <div className="flex gap-6 border-b border-border mb-6">
        <button
          type="button"
          onClick={() => setActiveTab("info")}
          className={`pb-3 text-sm font-medium transition-colors border-b-2 cursor-pointer ${
            activeTab === "info"
              ? "border-navy dark:border-yellow text-navy dark:text-yellow"
              : "border-transparent text-text-secondary hover:text-text-primary"
          }`}
        >
          Company Info
        </button>
        <button
          type="button"
          onClick={() => setActiveTab("users")}
          className={`pb-3 text-sm font-medium transition-colors border-b-2 cursor-pointer ${
            activeTab === "users"
              ? "border-navy dark:border-yellow text-navy dark:text-yellow"
              : "border-transparent text-text-secondary hover:text-text-primary"
          }`}
        >
          Authorized Users
        </button>
      </div>

      {/* Tab Content */}
      <div className="bg-surface border border-border rounded-xl shadow-sm overflow-hidden">
        {activeTab === "info" && (
          <CompanyInfoPanel
            client={client}
            isEditing={isEditing}
            editForm={editForm}
            setEditForm={setEditForm}
            saving={saving}
            onCancel={() => setIsEditing(false)}
            onSave={saveEdit}
            userCount={users.length}
          />
        )}

        {activeTab === "users" && (
          <AuthorizedUsersPanel
            users={users}
            isMaintainer={isMaintainer}
            onInvite={() => setIsInviteModalOpen(true)}
            onRemove={handleRemoveUser}
          />
        )}
      </div>

      {isInviteModalOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 backdrop-blur-sm p-4 animate-in fade-in duration-200">
          <div className="bg-surface border border-border rounded-xl shadow-2xl w-full max-w-sm overflow-hidden flex flex-col">
            <div className="flex items-center justify-between p-4 border-b border-border bg-surface-2">
              <h3 className="font-bold text-text-primary">Invite User</h3>
              <button
                type="button"
                onClick={() => setIsInviteModalOpen(false)}
                className="text-text-muted hover:text-text-primary cursor-pointer p-1"
              >
                <IconX className="size-5" />
              </button>
            </div>
            <form onSubmit={handleInviteUser} className="p-4 flex flex-col gap-4">
              <div>
                <label
                  htmlFor="invite-email"
                  className="block text-sm font-medium text-text-primary mb-1"
                >
                  User Email
                </label>
                <input
                  id="invite-email"
                  autoFocus
                  type="email"
                  required
                  value={inviteEmail}
                  onChange={(e) => setInviteEmail(e.target.value)}
                  className="w-full px-3 py-2 bg-surface border border-border rounded-lg text-sm text-text-primary focus:ring-2 focus:ring-navy dark:focus:ring-yellow focus:outline-none"
                  placeholder="e.g. employee@client.com"
                />
                <p className="text-xs text-text-muted mt-1">
                  Must match an authorized domain or email.
                </p>
              </div>
              <div>
                <label
                  htmlFor="invite-role"
                  className="block text-sm font-medium text-text-primary mb-1"
                >
                  Role
                </label>
                <select
                  id="invite-role"
                  value={inviteRole}
                  onChange={(e) => setInviteRole(e.target.value)}
                  className="w-full px-3 py-2 bg-surface border border-border rounded-lg text-sm text-text-primary focus:ring-2 focus:ring-navy dark:focus:ring-yellow focus:outline-none"
                >
                  <option value="client">Client</option>
                  {/* Future roles can be added here */}
                </select>
              </div>
              <div className="mt-2 flex justify-end gap-2">
                <button
                  type="button"
                  onClick={() => setIsInviteModalOpen(false)}
                  className="px-4 py-2 text-sm font-medium text-text-secondary hover:bg-surface-2 rounded-lg cursor-pointer"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={inviting || !inviteEmail.trim()}
                  className="px-4 py-2 bg-navy dark:bg-yellow dark:text-navy text-white rounded-lg text-sm font-medium hover:opacity-90 disabled:opacity-50 cursor-pointer"
                >
                  {inviting ? "Inviting..." : "Invite"}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </main>
  );
}
