"use client";

import React, { useState } from "react";
import {
  IconSearch,
  IconMail,
  IconChevronDown,
  IconLogout,
  IconPencil,
  IconCheck,
  IconX,
  IconUser,
  IconSun,
  IconMoon,
  IconCopy,
  IconLink,
} from "@tabler/icons-react";
import ShareApplicationLink from "@/components/settings/ShareApplicationLink";
import PasswordChange from "@/components/settings/PasswordChange";
import { useCurrentUser } from "@/hooks/useCurrentUser";
import { useApiFetch } from "@/lib/api";
import { useTheme } from "@/context/ThemeContext";

export default function RefereeSettingsPage() {
  const apiFetch = useApiFetch();
  const { theme, toggleTheme } = useTheme();

  const { user, isLoading: userLoading } = useCurrentUser();

  const [language, setLanguage] = React.useState<string>(() => {
    try {
      return globalThis.localStorage?.getItem("binge-language") ?? "en";
    } catch {
      return "en";
    }
  });

  function handleLanguageChange(lang: string) {
    setLanguage(lang);
    try {
      globalThis.localStorage?.setItem("binge-language", lang);
    } catch {
      // ignore
    }
  }

  // Name editing state
  const [isEditingName, setIsEditingName] = useState(false);
  const [editNameValue, setEditNameValue] = useState("");
  const [nameSaving, setNameSaving] = useState(false);
  const [nameError, setNameError] = useState<string | null>(null);

  const [connectCodeCopied, setConnectCodeCopied] = useState(false);

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

  const TABS = ["Preferences", "Account"];
  const [activeTab, setActiveTab] = useState("Preferences");

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

  return (
    <div className="p-6 md:p-10 max-w-6xl mx-auto w-full animate-in fade-in duration-300">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 mb-8">
        <h1 className="text-3xl font-heading font-bold text-text-primary">Settings</h1>
        <div className="relative w-full sm:w-auto">
          <IconSearch className="absolute left-3 top-1/2 -translate-y-1/2 text-text-muted w-5 h-5" />
          <input
            type="text"
            placeholder="Search"
            className="w-full sm:w-64 pl-10 pr-12 py-2 rounded-lg border border-border bg-surface text-text-primary focus:outline-none focus:ring-2 focus:ring-navy dark:focus:ring-yellow transition-shadow"
          />
          <span className="absolute right-3 top-1/2 -translate-y-1/2 text-xs text-text-muted bg-canvas px-1.5 py-0.5 rounded border border-border">
            ⌘K
          </span>
        </div>
      </div>

      {/* Tabs */}
      <div className="flex space-x-1 border-b border-border overflow-x-auto scrollbar-none mb-8 pb-[1px]">
        {TABS.map((tab) => (
          <button
            key={tab}
            onClick={() => setActiveTab(tab)}
            className={`px-4 py-2 text-sm font-medium whitespace-nowrap transition-colors ${
              activeTab === tab
                ? "text-text-primary border-b-2 border-text-primary"
                : "text-text-secondary hover:text-text-primary hover:bg-surface-2 rounded-t-lg"
            }`}
          >
            {tab}
          </button>
        ))}
      </div>

      {/* Main Section */}
      <div>
        {activeTab === "Preferences" && (
          <div className="space-y-6">
            <div>
              <h2 className="text-lg font-bold text-text-primary">Preferences</h2>
              <p className="text-sm text-text-secondary mt-1">
                Customize how the app looks and feels for you.
              </p>
            </div>

            <ShareApplicationLink />

            <div className="divide-y divide-border border-y border-border">
              {/* Appearance */}
              <div className="grid grid-cols-1 md:grid-cols-3 gap-4 md:gap-6 py-6 items-start">
                <div>
                  <p className="text-sm font-medium text-text-primary">Appearance</p>
                  <p className="text-sm text-text-secondary mt-1">Choose your colour scheme.</p>
                </div>
                <div className="md:col-span-2 flex gap-3">
                  <button
                    type="button"
                    onClick={() => theme === "dark" && toggleTheme()}
                    className={`flex items-center gap-2 px-4 py-2.5 rounded-lg border text-sm font-medium transition-colors cursor-pointer ${
                      theme === "light"
                        ? "border-navy dark:border-yellow bg-navy/5 dark:bg-yellow/10 text-navy dark:text-yellow"
                        : "border-border bg-surface text-text-secondary hover:bg-surface-2"
                    }`}
                  >
                    <IconSun className="w-4 h-4" /> Light
                  </button>
                  <button
                    type="button"
                    onClick={() => theme === "light" && toggleTheme()}
                    className={`flex items-center gap-2 px-4 py-2.5 rounded-lg border text-sm font-medium transition-colors cursor-pointer ${
                      theme === "dark"
                        ? "border-navy dark:border-yellow bg-navy/5 dark:bg-yellow/10 text-navy dark:text-yellow"
                        : "border-border bg-surface text-text-secondary hover:bg-surface-2"
                    }`}
                  >
                    <IconMoon className="w-4 h-4" /> Dark
                  </button>
                </div>
              </div>

              {/* Language */}
              <div className="grid grid-cols-1 md:grid-cols-3 gap-4 md:gap-6 py-6 items-start md:items-center">
                <div>
                  <label htmlFor="language" className="text-sm font-medium text-text-primary">
                    Language
                  </label>
                  <p className="text-sm text-text-secondary mt-1">
                    Sets your display language preference.
                  </p>
                </div>
                <div className="md:col-span-2 max-w-xs">
                  <div className="relative">
                    <select
                      id="language"
                      value={language}
                      onChange={(e) => handleLanguageChange(e.target.value)}
                      className="w-full px-3 pr-10 py-2 rounded-lg border border-border bg-surface text-text-primary appearance-none focus:outline-none focus:ring-2 focus:ring-navy dark:focus:ring-yellow transition-shadow text-sm"
                    >
                      <option value="en">English</option>
                      <option value="ja">Japanese (日本語)</option>
                      <option value="zh">Chinese (中文)</option>
                      <option value="hi">Hindi (हिन्दी)</option>
                      <option value="ar">Arabic (العربية)</option>
                    </select>
                    <IconChevronDown className="absolute right-3 top-1/2 -translate-y-1/2 text-text-muted w-4 h-4 pointer-events-none" />
                  </div>
                </div>
              </div>
            </div>
          </div>
        )}

        {activeTab === "Account" && (
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

                {/* Connect Code row */}
                {user?.role === "referee" && (
                  <div className="grid grid-cols-1 md:grid-cols-3 gap-4 md:gap-6 py-6 items-start md:items-center">
                    <label className="text-sm font-medium text-text-primary flex items-center gap-1.5">
                      <IconLink className="w-4 h-4 text-text-muted" />
                      Connect Code
                    </label>
                    <div className="md:col-span-2 max-w-md">
                      <div className="flex items-center gap-3">
                        <span className="font-mono text-sm text-text-primary bg-surface-2 px-2 py-1 rounded">
                          {user?.connect_code ?? "—"}
                        </span>
                        {user?.connect_code && (
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
                      <p className="text-xs text-text-muted mt-1">
                        Unique code to track your candidates.
                      </p>
                    </div>
                  </div>
                )}

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
        )}
      </div>
    </div>
  );
}
