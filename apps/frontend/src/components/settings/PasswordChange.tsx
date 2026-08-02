"use client";
import React, { useState } from "react";
import { useApiFetch } from "@/lib/api";
import { IconLock } from "@tabler/icons-react";

export default function PasswordChange() {
  const apiFetch = useApiFetch();
  const [isEditing, setIsEditing] = useState(false);
  const [currentPassword, setCurrentPassword] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [isSaving, setIsSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState(false);

  async function handleSave(e: React.FormEvent) {
    e.preventDefault();
    if (newPassword.length < 8) {
      setError("New password must be at least 8 characters");
      return;
    }
    setIsSaving(true);
    setError(null);
    setSuccess(false);
    try {
      await apiFetch("/api/v1/auth/change-password", {
        method: "POST",
        body: JSON.stringify({ current_password: currentPassword, new_password: newPassword }),
      });
      setSuccess(true);
      setIsEditing(false);
      setCurrentPassword("");
      setNewPassword("");
    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : "Failed to change password. Please check your current password.",
      );
    } finally {
      setIsSaving(false);
    }
  }

  return (
    <div className="grid grid-cols-1 md:grid-cols-3 gap-4 md:gap-6 py-6 items-start md:items-center border-t border-border">
      <label className="text-sm font-medium text-text-primary flex items-center gap-1.5">
        <IconLock className="w-4 h-4 text-text-muted" />
        Password
      </label>
      <div className="md:col-span-2 max-w-md">
        {isEditing ? (
          <form onSubmit={handleSave} className="flex flex-col gap-3">
            <input
              type="password"
              placeholder="Current password"
              value={currentPassword}
              onChange={(e) => setCurrentPassword(e.target.value)}
              className="px-3 py-2 rounded-lg border border-border bg-surface text-text-primary focus:outline-none focus:ring-2 focus:ring-navy dark:focus:ring-yellow text-sm"
              required
            />
            <input
              type="password"
              placeholder="New password (min 8 characters)"
              value={newPassword}
              onChange={(e) => setNewPassword(e.target.value)}
              className="px-3 py-2 rounded-lg border border-border bg-surface text-text-primary focus:outline-none focus:ring-2 focus:ring-navy dark:focus:ring-yellow text-sm"
              required
              minLength={8}
            />
            {error && <p className="text-xs text-red-500">{error}</p>}
            <div className="flex items-center gap-2 mt-1">
              <button
                type="submit"
                disabled={isSaving}
                className="px-3 py-1.5 rounded-lg bg-navy dark:bg-yellow text-white dark:text-navy text-xs font-medium hover:opacity-90 disabled:opacity-50"
              >
                {isSaving ? "Saving..." : "Change Password"}
              </button>
              <button
                type="button"
                onClick={() => {
                  setIsEditing(false);
                  setError(null);
                }}
                disabled={isSaving}
                className="px-3 py-1.5 rounded-lg bg-surface-2 text-text-secondary text-xs font-medium hover:bg-surface-3 disabled:opacity-50"
              >
                Cancel
              </button>
            </div>
          </form>
        ) : (
          <div className="flex flex-col gap-2">
            <div className="flex items-center gap-3">
              <span className="text-sm text-text-primary">••••••••</span>
              <button
                type="button"
                onClick={() => {
                  setIsEditing(true);
                  setSuccess(false);
                }}
                className="text-sm font-medium text-navy dark:text-yellow hover:underline cursor-pointer"
              >
                Change password
              </button>
            </div>
            {success && (
              <p className="text-xs text-green-600 dark:text-green-400">
                Password updated successfully.
              </p>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
