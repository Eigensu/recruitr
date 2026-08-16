"use client";

import React from "react";
import { IconSearch } from "@tabler/icons-react";

interface SettingsShellProps {
  tabs: readonly string[];
  activeTab: string;
  onTabChange: (tab: string) => void;
  children: React.ReactNode;
}

/**
 * Page chrome for a settings screen: the title, the search box and the tab bar.
 *
 * Shared by the staff and referee settings pages, which differ only in which
 * tabs they list and what those tabs render.
 */
export default function SettingsShell({
  tabs,
  activeTab,
  onTabChange,
  children,
}: SettingsShellProps) {
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
        {tabs.map((tab) => (
          <button
            key={tab}
            type="button"
            onClick={() => onTabChange(tab)}
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
      <div>{children}</div>
    </div>
  );
}
