"use client";
import React, { useState } from "react";
import { useApiFetch } from "@/lib/api";
import { useCurrentUser } from "@/hooks/useCurrentUser";
import { IconBell, IconCheck } from "@tabler/icons-react";

export default function NotificationPreferences() {
  const { user } = useCurrentUser();
  const apiFetch = useApiFetch();

  const defaultPrefs = {
    email_alerts: true,
    weekly_digest: false,
    new_candidate: true,
  };
  const [localPrefs, setLocalPrefs] = useState<{ [key: string]: boolean } | null>(null);

  const preferences = localPrefs || {
    ...defaultPrefs,
    ...(user?.notification_preferences || {}),
  };
  const [isSaving, setIsSaving] = useState(false);
  const [saved, setSaved] = useState(false);

  async function handleToggle(key: string) {
    const newPrefs = { ...preferences, [key]: !preferences[key] };
    setLocalPrefs(newPrefs);
    setSaved(false);
    setIsSaving(true);
    try {
      await apiFetch("/api/v1/auth/me", {
        method: "PATCH",
        body: JSON.stringify({ notification_preferences: newPrefs }),
      });
      setSaved(true);
      setTimeout(() => setSaved(false), 3000);
    } catch (err) {
      console.error("Failed to update preferences", err);
      // Revert on failure
      setLocalPrefs(preferences);
    } finally {
      setIsSaving(false);
    }
  }

  return (
    <div className="grid grid-cols-1 md:grid-cols-3 gap-4 md:gap-6 py-6 items-start">
      <div>
        <label className="text-sm font-medium text-text-primary flex items-center gap-1.5">
          <IconBell className="w-4 h-4 text-text-muted" />
          Notifications
        </label>
        <p className="text-sm text-text-secondary mt-1">Manage what alerts you receive.</p>
      </div>
      <div className="md:col-span-2 max-w-md flex flex-col gap-4">
        <label className="flex items-center justify-between cursor-pointer group">
          <div>
            <p className="text-sm font-medium text-text-primary">Email Alerts</p>
            <p className="text-xs text-text-muted mt-0.5">Receive general alerts to your inbox.</p>
          </div>
          <div className="relative inline-block w-10 mr-2 align-middle select-none transition duration-200 ease-in">
            <input
              type="checkbox"
              name="email_alerts"
              checked={preferences.email_alerts}
              onChange={() => handleToggle("email_alerts")}
              disabled={isSaving}
              className="toggle-checkbox absolute block w-5 h-5 rounded-full bg-white border-4 appearance-none cursor-pointer border-gray-300 dark:border-gray-600 checked:right-0 checked:border-navy dark:checked:border-yellow"
              style={{
                top: "0.125rem",
                right: preferences.email_alerts ? "0" : "1.25rem",
                transition: "right 0.2s",
              }}
            />
            <div
              className={`toggle-label block overflow-hidden h-6 rounded-full cursor-pointer transition-colors ${
                preferences.email_alerts ? "bg-navy dark:bg-yellow" : "bg-gray-300 dark:bg-gray-600"
              }`}
            ></div>
          </div>
        </label>

        <label className="flex items-center justify-between cursor-pointer group">
          <div>
            <p className="text-sm font-medium text-text-primary">New Candidate Activity</p>
            <p className="text-xs text-text-muted mt-0.5">Alerts when a candidate changes stage.</p>
          </div>
          <div className="relative inline-block w-10 mr-2 align-middle select-none transition duration-200 ease-in">
            <input
              type="checkbox"
              name="new_candidate"
              checked={preferences.new_candidate}
              onChange={() => handleToggle("new_candidate")}
              disabled={isSaving}
              className="toggle-checkbox absolute block w-5 h-5 rounded-full bg-white border-4 appearance-none cursor-pointer border-gray-300 dark:border-gray-600 checked:right-0 checked:border-navy dark:checked:border-yellow"
              style={{
                top: "0.125rem",
                right: preferences.new_candidate ? "0" : "1.25rem",
                transition: "right 0.2s",
              }}
            />
            <div
              className={`toggle-label block overflow-hidden h-6 rounded-full cursor-pointer transition-colors ${
                preferences.new_candidate
                  ? "bg-navy dark:bg-yellow"
                  : "bg-gray-300 dark:bg-gray-600"
              }`}
            ></div>
          </div>
        </label>

        <label className="flex items-center justify-between cursor-pointer group">
          <div>
            <p className="text-sm font-medium text-text-primary">Weekly Digest</p>
            <p className="text-xs text-text-muted mt-0.5">
              A summary of activity sent every Monday.
            </p>
          </div>
          <div className="relative inline-block w-10 mr-2 align-middle select-none transition duration-200 ease-in">
            <input
              type="checkbox"
              name="weekly_digest"
              checked={preferences.weekly_digest}
              onChange={() => handleToggle("weekly_digest")}
              disabled={isSaving}
              className="toggle-checkbox absolute block w-5 h-5 rounded-full bg-white border-4 appearance-none cursor-pointer border-gray-300 dark:border-gray-600 checked:right-0 checked:border-navy dark:checked:border-yellow"
              style={{
                top: "0.125rem",
                right: preferences.weekly_digest ? "0" : "1.25rem",
                transition: "right 0.2s",
              }}
            />
            <div
              className={`toggle-label block overflow-hidden h-6 rounded-full cursor-pointer transition-colors ${
                preferences.weekly_digest
                  ? "bg-navy dark:bg-yellow"
                  : "bg-gray-300 dark:bg-gray-600"
              }`}
            ></div>
          </div>
        </label>

        {saved && (
          <p className="text-xs text-green-600 dark:text-green-400 flex items-center gap-1">
            <IconCheck className="w-3 h-3" /> Preferences saved
          </p>
        )}
      </div>
    </div>
  );
}
