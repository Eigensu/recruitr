"use client";

import React, { useState } from "react";
import { IconChevronDown, IconSun, IconMoon } from "@tabler/icons-react";
import ShareApplicationLink from "@/components/settings/ShareApplicationLink";
import { useTheme } from "@/context/ThemeContext";

const LANGUAGE_KEY = "binge-language";

const LANGUAGES = [
  { value: "en", label: "English" },
  { value: "ja", label: "Japanese (日本語)" },
  { value: "zh", label: "Chinese (中文)" },
  { value: "hi", label: "Hindi (हिन्दी)" },
  { value: "ar", label: "Arabic (العربية)" },
] as const;

interface PreferencesPanelProps {
  /** Extra rows appended inside the bordered list, e.g. the staff "My Team" block. */
  extraRows?: React.ReactNode;
  /** Rendered below the list, e.g. staff notification preferences. */
  children?: React.ReactNode;
}

/**
 * The Preferences tab: appearance and language, shared by staff and referees.
 *
 * Language lives in localStorage rather than on the user record, so reads are
 * wrapped — Safari in private mode throws on access rather than returning null.
 */
export default function PreferencesPanel({ extraRows, children }: PreferencesPanelProps) {
  const { theme, toggleTheme } = useTheme();

  const [language, setLanguage] = useState<string>(() => {
    try {
      return globalThis.localStorage?.getItem(LANGUAGE_KEY) ?? "en";
    } catch {
      return "en";
    }
  });

  function handleLanguageChange(lang: string) {
    setLanguage(lang);
    try {
      globalThis.localStorage?.setItem(LANGUAGE_KEY, lang);
    } catch {
      // ignore
    }
  }

  const themeButtonCls = (selected: boolean) =>
    `flex items-center gap-2 px-4 py-2.5 rounded-lg border text-sm font-medium transition-colors cursor-pointer ${
      selected
        ? "border-navy dark:border-yellow bg-navy/5 dark:bg-yellow/10 text-navy dark:text-yellow"
        : "border-border bg-surface text-text-secondary hover:bg-surface-2"
    }`;

  return (
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
              className={themeButtonCls(theme === "light")}
            >
              <IconSun className="w-4 h-4" /> Light
            </button>
            <button
              type="button"
              onClick={() => theme === "light" && toggleTheme()}
              className={themeButtonCls(theme === "dark")}
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
                {LANGUAGES.map((lang) => (
                  <option key={lang.value} value={lang.value}>
                    {lang.label}
                  </option>
                ))}
              </select>
              <IconChevronDown className="absolute right-3 top-1/2 -translate-y-1/2 text-text-muted w-4 h-4 pointer-events-none" />
            </div>
          </div>
        </div>

        {extraRows}
      </div>

      {children}
    </div>
  );
}
