"use client";

import React, { useState } from "react";
import { IconMail, IconLogout, IconPencil, IconCheck, IconX, IconUser } from "@tabler/icons-react";
import PasswordChange from "@/components/settings/PasswordChange";
import { useApiFetch } from "@/lib/api";
import type { UserInfo } from "@/types";

interface AccountPanelProps {
  user: UserInfo | null;
  isLoading: boolean;
  /**
   * Logging out differs per shell — staff clear their dismissed banners and
   * route away, the referee portal hard-navigates to drop cached pages — so the
   * handler comes from the page rather than living here.
   */
  onLogout: () => void;
  /** Extra rows rendered above the session row, e.g. the referee connect code. */
  extraRows?: React.ReactNode;
}

/**
 * The Account tab: name, email, role, session and password, shared by the staff
 * and referee settings pages.
 */
export default function AccountPanel({ user, isLoading, onLogout, extraRows }: AccountPanelProps) {
  const apiFetch = useApiFetch();

  const [isEditingName, setIsEditingName] = useState(false);
  const [editNameValue, setEditNameValue] = useState("");
  // undefined = not yet overridden by user; null = user cleared it; string = user set it
  const [savedName, setSavedName] = useState<string | null | undefined>(undefined);
  const [nameSaving, setNameSaving] = useState(false);
  const [nameError, setNameError] = useState<string | null>(null);

  const displayName = savedName !== undefined ? savedName : (user?.full_name ?? null);

  function startEditName() {
    setEditNameValue(displayName ?? "");
    setNameError(null);
    setIsEditingName(true);
  }

  function cancelEditName() {
    setIsEditingName(false);
    setNameError(null);
  }

  async function saveEditName() {
    const trimmed = editNameValue.trim();
    setNameSaving(true);
    setNameError(null);
    try {
      const updated = await apiFetch<{ full_name: string | null }>("/api/v1/auth/me", {
        method: "PATCH",
        body: JSON.stringify({ full_name: trimmed }),
      });
      setSavedName(updated.full_name);
      setIsEditingName(false);
    } catch {
      setNameError("Failed to save. Please try again.");
    } finally {
      setNameSaving(false);
    }
  }

  return (
    <div className="space-y-6">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h2 className="text-lg font-bold text-text-primary">My Account</h2>
          <p className="text-sm text-text-secondary mt-1">View and update your personal details.</p>
        </div>
      </div>

      {isLoading ? (
        <div className="py-8 text-center text-sm text-text-muted">Loading account info…</div>
      ) : (
        <div className="divide-y divide-border border-y border-border">
          {/* Name row */}
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4 md:gap-6 py-6 items-start md:items-center">
            <p className="text-sm font-medium text-text-primary flex items-center gap-1.5">
              <IconUser className="w-4 h-4 text-text-muted" />
              Full Name
            </p>
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
                      aria-label="Full name"
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
                    {displayName ?? <span className="text-text-muted italic">No name set</span>}
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
            <p className="text-sm font-medium text-text-primary flex items-center gap-1.5">
              <IconMail className="w-4 h-4 text-text-muted" />
              Email Address
            </p>
            <div className="md:col-span-2 max-w-md">
              <p className="text-sm text-text-primary">{user?.email ?? "—"}</p>
              <p className="text-xs text-text-muted mt-0.5">Email cannot be changed here.</p>
            </div>
          </div>

          {/* Role row */}
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4 md:gap-6 py-6 items-start md:items-center">
            <p className="text-sm font-medium text-text-primary">Role</p>
            <div className="md:col-span-2 max-w-md">
              <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-semibold capitalize border border-border bg-surface-2 text-text-primary">
                {user?.role ?? "—"}
              </span>
            </div>
          </div>

          {extraRows}

          {/* Session row */}
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4 md:gap-6 py-6 items-start md:items-center">
            <p className="text-sm font-medium text-text-primary">Session</p>
            <div className="md:col-span-2 max-w-md">
              <button
                type="button"
                onClick={onLogout}
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
  );
}
