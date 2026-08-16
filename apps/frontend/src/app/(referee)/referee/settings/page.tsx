"use client";

import React, { useState } from "react";
import { IconCheck, IconCopy, IconLink } from "@tabler/icons-react";
import SettingsShell from "@/components/settings/SettingsShell";
import PreferencesPanel from "@/components/settings/PreferencesPanel";
import AccountPanel from "@/components/settings/AccountPanel";
import { useCurrentUser } from "@/hooks/useCurrentUser";
import { useApiFetch } from "@/lib/api";

const TABS = ["Preferences", "Account"] as const;

export default function RefereeSettingsPage() {
  const apiFetch = useApiFetch();
  const { user, isLoading: userLoading } = useCurrentUser();

  const [activeTab, setActiveTab] = useState<string>(TABS[0]);
  const [connectCodeCopied, setConnectCodeCopied] = useState(false);

  async function handleLogout() {
    try {
      await apiFetch("/api/v1/auth/logout", { method: "POST" });
    } catch (err) {
      console.error("Logout failed:", err);
    } finally {
      // Hard navigation, not router.push: it drops the Next.js client cache so
      // the next account cannot see the previous one's rendered pages.
      window.location.href = "/sign-in";
    }
  }

  const copyConnectCode = async () => {
    if (!user?.connect_code) return;
    try {
      await navigator.clipboard.writeText(user.connect_code);
      setConnectCodeCopied(true);
      setTimeout(() => setConnectCodeCopied(false), 2000);
    } catch {
      // ignore error
    }
  };

  const connectCodeRow = user?.role === "referee" && (
    <div className="grid grid-cols-1 md:grid-cols-3 gap-4 md:gap-6 py-6 items-start md:items-center">
      <p className="text-sm font-medium text-text-primary flex items-center gap-1.5">
        <IconLink className="w-4 h-4 text-text-muted" />
        Connect Code
      </p>
      <div className="md:col-span-2 max-w-md">
        <div className="flex items-center gap-3">
          <span className="font-mono text-sm text-text-primary bg-surface-2 px-2 py-1 rounded">
            {user.connect_code ?? "—"}
          </span>
          {user.connect_code && (
            <button
              type="button"
              onClick={copyConnectCode}
              className="p-1.5 rounded-lg text-text-muted hover:bg-surface-2 hover:text-text-primary cursor-pointer transition-colors"
              aria-label="Copy connect code"
            >
              {connectCodeCopied ? (
                <IconCheck className="w-4 h-4 text-green-600" />
              ) : (
                <IconCopy className="w-4 h-4" />
              )}
            </button>
          )}
        </div>
        <p className="text-xs text-text-muted mt-1">Unique code to track your candidates.</p>
      </div>
    </div>
  );

  return (
    <SettingsShell tabs={TABS} activeTab={activeTab} onTabChange={setActiveTab}>
      {activeTab === "Preferences" && <PreferencesPanel />}
      {activeTab === "Account" && (
        <AccountPanel
          user={user}
          isLoading={userLoading}
          onLogout={handleLogout}
          extraRows={connectCodeRow}
        />
      )}
    </SettingsShell>
  );
}
