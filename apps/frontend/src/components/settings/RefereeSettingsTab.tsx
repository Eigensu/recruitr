"use client";

import React, { useEffect, useState } from "react";
import { IconPlus, IconTrash } from "@tabler/icons-react";
import { useApiFetch, apiErrorMessage } from "@/lib/api";
import { listReferees, inviteReferee, removeReferee, type RefereeUser } from "@/lib/api/referees";

const USER_STATUS_STYLES: Record<string, string> = {
  Active: "bg-green-100 text-green-700",
  Inactive: "bg-red-100 text-red-700",
  Pending: "bg-yellow-100 text-yellow-800",
};

export default function RefereeSettingsTab() {
  const apiFetch = useApiFetch();
  const [users, setUsers] = useState<RefereeUser[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [isInviting, setIsInviting] = useState(false);
  const [inviteName, setInviteName] = useState("");
  const [inviteEmail, setInviteEmail] = useState("");
  const [inviteError, setInviteError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  useEffect(() => {
    async function loadUsers() {
      setIsLoading(true);
      setError(null);
      try {
        const data = await listReferees(apiFetch);
        setUsers(data);
      } catch (err) {
        setError(apiErrorMessage(err, "Failed to load referees"));
      } finally {
        setIsLoading(false);
      }
    }
    loadUsers();
  }, [apiFetch]);

  async function handleInvite(e: React.FormEvent) {
    e.preventDefault();
    setInviteError(null);
    setIsSubmitting(true);

    try {
      const newUser = await inviteReferee(apiFetch, {
        name: inviteName.trim() || null,
        email: inviteEmail.trim(),
        role: "referee",
      });
      setUsers((prev) => {
        const existingIdx = prev.findIndex((u) => u.email === newUser.email);
        if (existingIdx >= 0) {
          const copy = [...prev];
          copy[existingIdx] = newUser;
          return copy.sort((a, b) => a.email.localeCompare(b.email));
        }
        return [...prev, newUser].sort((a, b) => a.email.localeCompare(b.email));
      });
      setIsInviting(false);
      setInviteName("");
      setInviteEmail("");
    } catch (err) {
      setInviteError(apiErrorMessage(err, "Failed to provision referee"));
    } finally {
      setIsSubmitting(false);
    }
  }

  async function handleRemove(userId: string) {
    if (!window.confirm("Are you sure you want to deactivate this referee's access?")) {
      return;
    }
    try {
      await removeReferee(apiFetch, userId);
      setUsers((prev) => prev.map((u) => (u.id === userId ? { ...u, is_active: false } : u)));
    } catch (err) {
      alert(apiErrorMessage(err, "Failed to remove referee access"));
    }
  }

  if (isLoading) {
    return <div className="py-12 flex justify-center text-text-muted">Loading referees...</div>;
  }

  if (error) {
    return <div className="py-12 flex justify-center text-red-500">{error}</div>;
  }

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-lg font-bold text-text-primary">Referees</h2>
        <p className="text-sm text-text-secondary mt-1">
          Manage authorized referees who can refer candidates to your brand.
        </p>
      </div>

      <div className="border border-border rounded-xl bg-surface overflow-hidden shadow-sm">
        <div className="flex items-center justify-between p-4 border-b border-border bg-surface-2">
          <h3 className="font-bold text-text-primary">Authorized Referees</h3>
          <button
            type="button"
            onClick={() => setIsInviting(true)}
            className="flex items-center gap-2 px-3 py-1.5 bg-navy dark:bg-yellow dark:text-navy text-white rounded-lg text-sm font-medium hover:opacity-90 transition-opacity cursor-pointer shadow-sm"
          >
            <IconPlus className="size-4" /> Add Referee
          </button>
        </div>

        {isInviting && (
          <div className="p-4 border-b border-border bg-canvas/50">
            <form onSubmit={handleInvite} className="space-y-4">
              <h4 className="text-sm font-bold text-text-primary">Provision New Referee</h4>
              {inviteError && (
                <div className="p-3 bg-red-50 text-red-600 text-sm rounded-lg border border-red-100">
                  {inviteError}
                </div>
              )}
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                <div>
                  <label className="block text-xs font-medium text-text-secondary mb-1">
                    Name (Optional)
                  </label>
                  <input
                    type="text"
                    value={inviteName}
                    onChange={(e) => setInviteName(e.target.value)}
                    placeholder="Jane Doe"
                    className="w-full px-3 py-2 bg-surface border border-border rounded-lg text-sm focus:ring-2 focus:ring-navy outline-none text-text-primary"
                    disabled={isSubmitting}
                  />
                </div>
                <div>
                  <label className="block text-xs font-medium text-text-secondary mb-1">
                    Email Address (Optional)
                  </label>
                  <input
                    type="email"
                    value={inviteEmail}
                    onChange={(e) => setInviteEmail(e.target.value)}
                    placeholder="jane@example.com"
                    className="w-full px-3 py-2 bg-surface border border-border rounded-lg text-sm focus:ring-2 focus:ring-navy outline-none text-text-primary"
                    disabled={isSubmitting}
                  />
                </div>
              </div>
              <div className="flex justify-end gap-3 pt-2">
                <button
                  type="button"
                  onClick={() => setIsInviting(false)}
                  className="px-4 py-2 text-sm font-medium text-text-secondary hover:text-text-primary transition-colors cursor-pointer"
                  disabled={isSubmitting}
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={isSubmitting}
                  className="px-4 py-2 bg-navy dark:bg-yellow dark:text-navy text-white text-sm font-medium rounded-lg hover:opacity-90 transition-opacity disabled:opacity-50 cursor-pointer"
                >
                  {isSubmitting ? "Provisioning..." : "Provision Referee"}
                </button>
              </div>
            </form>
          </div>
        )}

        <div className="overflow-x-auto">
          <table className="w-full text-sm text-left">
            <thead className="bg-surface-2 border-b border-border text-xs uppercase text-text-secondary font-semibold">
              <tr>
                <th className="px-4 py-3">Name</th>
                <th className="px-4 py-3">Email</th>
                <th className="px-4 py-3">Status</th>
                <th className="px-4 py-3">Last Login</th>
                <th className="px-4 py-3 text-right">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border">
              {users.map((u) => {
                const status = u.is_active ? (u.last_login ? "Active" : "Pending") : "Inactive";
                return (
                  <tr key={u.id} className="hover:bg-surface-2/50 transition-colors">
                    <td className="px-4 py-3 font-medium text-text-primary">
                      {u.name || <span className="text-text-muted italic">Unknown</span>}
                    </td>
                    <td className="px-4 py-3 text-text-secondary">{u.email}</td>
                    <td className="px-4 py-3">
                      <span
                        className={`px-2 py-1 rounded-full text-[10px] font-bold tracking-wider uppercase ${USER_STATUS_STYLES[status] ?? USER_STATUS_STYLES.Pending}`}
                      >
                        {status}
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
                      {u.is_active && (
                        <button
                          type="button"
                          onClick={() => handleRemove(u.id)}
                          className="p-1.5 text-text-muted hover:text-red-500 hover:bg-red-50 rounded-md transition-colors cursor-pointer"
                          title="Revoke Access"
                        >
                          <IconTrash className="size-4" />
                        </button>
                      )}
                    </td>
                  </tr>
                );
              })}
              {users.length === 0 && !isInviting && (
                <tr>
                  <td colSpan={5} className="px-4 py-12 text-center text-text-muted">
                    No referees provisioned yet.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
