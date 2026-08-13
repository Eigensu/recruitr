"use client";

import React, { useState } from "react";
import { IconUser, IconMail, IconCheck, IconX, IconPencil, IconLogout } from "@tabler/icons-react";
import PasswordChange from "@/components/settings/PasswordChange";
import { useCurrentUser } from "@/hooks/useCurrentUser";
import { useApiFetch } from "@/lib/api";

export default function RefereeSettingsPage() {
  const { user, isLoading: userLoading } = useCurrentUser();
  const apiFetch = useApiFetch();

  // Name editing state
  const [isEditingName, setIsEditingName] = useState(false);
  const [editNameValue, setEditNameValue] = useState("");
  const [nameSaving, setNameSaving] = useState(false);
  const [nameError, setNameError] = useState<string | null>(null);

  const displayName = user?.full_name?.trim() ? user.full_name : null;

  function startEditName() {
    setEditNameValue(displayName ?? "");
    setIsEditingName(true);
    setNameError(null);
  }

  function cancelEditName() {
    setIsEditingName(false);
    setEditNameValue("");
    setNameError(null);
  }

  async function saveEditName() {
    const val = editNameValue.trim();
    if (!val) {
      setNameError("Name cannot be empty");
      return;
    }
    if (val === displayName) {
      cancelEditName();
      return;
    }
    setNameSaving(true);
    setNameError(null);
    try {
      await apiFetch("/api/v1/auth/me", {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ full_name: val }),
      });
      setIsEditingName(false);
      window.location.reload();
    } catch (err: unknown) {
      if (err instanceof Error) {
        setNameError(err.message || "Failed to update name");
      } else {
        setNameError("Failed to update name");
      }
    } finally {
      setNameSaving(false);
    }
  }

  async function handleLogout() {
    try {
      await apiFetch("/api/v1/auth/logout", {
        method: "POST",
      });
    } catch (err) {
      console.error("Logout failed:", err);
    } finally {
      window.location.href = "/sign-in";
    }
  }

  return (
    <div className="flex-1 overflow-y-auto p-4 sm:p-6 lg:p-8">
      <div className="mx-auto max-w-4xl space-y-8">
        <div>
          <h1 className="text-3xl font-heading font-bold text-text-primary">Settings</h1>
          <p className="text-sm text-text-secondary mt-1">Manage your account and preferences.</p>
        </div>

        <div className="bg-surface-card theme-transition rounded-2xl border border-border shadow-sm p-6">
          <div className="space-y-6">
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
              <div>
                <h2 className="text-lg font-bold text-text-primary">My Account</h2>
                <p className="text-sm text-text-secondary mt-1">
                  View and update your personal details.
                </p>
              </div>
            </div>

            {userLoading ? (
              <div className="py-8 text-center text-sm text-text-muted">Loading account info…</div>
            ) : (
              <div className="divide-y divide-border border-y border-border">
                {/* Name row */}
                <div className="grid grid-cols-1 md:grid-cols-3 gap-4 md:gap-6 py-6 items-start md:items-center">
                  <label className="text-sm font-medium text-text-primary flex items-center gap-1.5">
                    <IconUser className="w-4 h-4 text-text-muted" />
                    Full Name
                  </label>
                  <div className="md:col-span-2 max-w-md">
                    {isEditingName ? (
                      <div className="flex flex-col gap-2">
                        <div className="flex items-center gap-2">
                          <input
                            autoFocus
                            type="text"
                            value={editNameValue}
                            onChange={(e) => setEditNameValue(e.target.value)}
                            onKeyDown={(e) => {
                              if (e.key === "Enter") saveEditName();
                              if (e.key === "Escape") cancelEditName();
                            }}
                            placeholder="Your full name"
                            className="flex-1 px-3 py-2 rounded-lg border border-border bg-surface text-text-primary focus:outline-none focus:ring-2 focus:ring-navy dark:focus:ring-yellow transition-shadow text-sm"
                          />
                          <button
                            type="button"
                            onClick={saveEditName}
                            disabled={nameSaving}
                            className="p-2 rounded-lg text-green-600 hover:bg-surface-2 disabled:opacity-40 cursor-pointer transition-colors"
                            aria-label="Save name"
                          >
                            <IconCheck className="w-4 h-4" />
                          </button>
                          <button
                            type="button"
                            onClick={cancelEditName}
                            disabled={nameSaving}
                            className="p-2 rounded-lg text-text-muted hover:bg-surface-2 cursor-pointer transition-colors"
                            aria-label="Cancel"
                          >
                            <IconX className="w-4 h-4" />
                          </button>
                        </div>
                        {nameError && (
                          <p className="text-xs text-red-500 dark:text-red-400">{nameError}</p>
                        )}
                      </div>
                    ) : (
                      <div className="flex items-center gap-3">
                        <span className="text-sm text-text-primary">
                          {displayName ?? (
                            <span className="text-text-muted italic">No name set</span>
                          )}
                        </span>
                        <button
                          type="button"
                          onClick={startEditName}
                          className="p-1.5 rounded-lg text-text-muted hover:bg-surface-2 hover:text-text-primary cursor-pointer transition-colors"
                          aria-label="Edit name"
                        >
                          <IconPencil className="w-4 h-4" />
                        </button>
                      </div>
                    )}
                  </div>
                </div>

                {/* Email row */}
                <div className="grid grid-cols-1 md:grid-cols-3 gap-4 md:gap-6 py-6 items-start md:items-center">
                  <label className="text-sm font-medium text-text-primary flex items-center gap-1.5">
                    <IconMail className="w-4 h-4 text-text-muted" />
                    Email Address
                  </label>
                  <div className="md:col-span-2 max-w-md">
                    <p className="text-sm text-text-primary">{user?.email ?? "—"}</p>
                    <p className="text-xs text-text-muted mt-0.5">Email cannot be changed here.</p>
                  </div>
                </div>

                {/* Role row */}
                <div className="grid grid-cols-1 md:grid-cols-3 gap-4 md:gap-6 py-6 items-start md:items-center">
                  <label className="text-sm font-medium text-text-primary">Role</label>
                  <div className="md:col-span-2 max-w-md">
                    <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-semibold capitalize border border-border bg-surface-2 text-text-primary">
                      {user?.role ?? "—"}
                    </span>
                  </div>
                </div>

                {/* Session row */}
                <div className="grid grid-cols-1 md:grid-cols-3 gap-4 md:gap-6 py-6 items-start md:items-center">
                  <label className="text-sm font-medium text-text-primary">Session</label>
                  <div className="md:col-span-2 max-w-md">
                    <button
                      onClick={handleLogout}
                      className="flex items-center gap-2 px-4 py-2 text-sm font-medium rounded-lg border border-red-200 text-red-600 bg-red-50 hover:bg-red-100 dark:border-red-900/50 dark:bg-red-900/20 dark:text-red-400 dark:hover:bg-red-900/40 transition-colors cursor-pointer"
                    >
                      <IconLogout className="w-4 h-4" />
                      Log out
                    </button>
                  </div>
                </div>

                <PasswordChange />
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
