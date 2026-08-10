"use client";

import React, { useCallback, useEffect, useState } from "react";
import { IconCheck, IconFileText, IconTag } from "@tabler/icons-react";
import { apiErrorMessage, useApiFetch } from "@/lib/api";
import {
  getBrandSettings,
  updateBrandSettings,
  type AutomationSettings as Automation,
} from "@/lib/api/brands";

function Toggle({
  id,
  checked,
  disabled,
  onChange,
}: {
  id: string;
  checked: boolean;
  disabled: boolean;
  onChange: () => void;
}) {
  return (
    <div
      className={`relative inline-block w-10 mr-2 align-middle select-none shrink-0 ${
        disabled ? "opacity-50" : ""
      }`}
    >
      <input
        type="checkbox"
        id={id}
        checked={checked}
        onChange={onChange}
        disabled={disabled}
        className="toggle-checkbox absolute block w-5 h-5 rounded-full bg-white border-4 appearance-none cursor-pointer border-gray-300 dark:border-gray-600 checked:right-0 checked:border-navy dark:checked:border-yellow disabled:cursor-not-allowed"
        style={{ top: "0.125rem", right: checked ? "0" : "1.25rem", transition: "right 0.2s" }}
      />
      <label
        htmlFor={id}
        className={`toggle-label block overflow-hidden h-6 rounded-full transition-colors ${
          disabled ? "cursor-not-allowed" : "cursor-pointer"
        } ${checked ? "bg-navy dark:bg-yellow" : "bg-gray-300 dark:bg-gray-600"}`}
      />
    </div>
  );
}

/**
 * Workspace-wide resume automation switches. Maintainers only — the API
 * rejects a write from anyone else, so this is gated by the caller too.
 */
export default function AutomationSettingsPanel() {
  const apiFetch = useApiFetch();

  const [automation, setAutomation] = useState<Automation | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [isSaving, setIsSaving] = useState(false);
  const [saved, setSaved] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    getBrandSettings(apiFetch)
      .then((s) => {
        if (!cancelled) setAutomation(s.automation);
      })
      .catch((err) => {
        if (!cancelled) setError(apiErrorMessage(err, "Failed to load automation settings."));
      })
      .finally(() => {
        if (!cancelled) setIsLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [apiFetch]);

  const save = useCallback(
    async (changes: Partial<Automation>) => {
      if (!automation) return;
      const previous = automation;
      // Optimistic, mirroring the server rule that auto-tagging cannot stay on
      // without parsing — otherwise the nested switch flickers on save.
      const optimistic = { ...previous, ...changes };
      if (!optimistic.resume_parsing_enabled) optimistic.auto_tagging_enabled = false;
      setAutomation(optimistic);
      setError(null);
      setSaved(false);
      setIsSaving(true);
      try {
        const updated = await updateBrandSettings(apiFetch, changes);
        setAutomation(updated.automation);
        setSaved(true);
        setTimeout(() => setSaved(false), 3000);
      } catch (err) {
        setAutomation(previous);
        setError(apiErrorMessage(err, "Failed to save. Please try again."));
      } finally {
        setIsSaving(false);
      }
    },
    [apiFetch, automation],
  );

  if (isLoading) {
    return <div className="py-8 text-center text-sm text-text-muted">Loading automation…</div>;
  }

  if (!automation) {
    return (
      <div className="py-8 text-center text-sm text-red-500 dark:text-red-400">
        {error ?? "Automation settings are unavailable."}
      </div>
    );
  }

  const parsingOn = automation.resume_parsing_enabled;

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-lg font-bold text-text-primary">Automation</h2>
        <p className="text-sm text-text-secondary mt-1">
          Controls what happens automatically when a resume is added — anywhere in the workspace,
          for everyone on your team.
        </p>
      </div>

      <div className="divide-y divide-border border-y border-border">
        {/* Resume parsing */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4 md:gap-6 py-6 items-start">
          <div>
            <p className="text-sm font-medium text-text-primary flex items-center gap-1.5">
              <IconFileText className="w-4 h-4 text-text-muted" />
              Resume parsing
            </p>
            <p className="text-sm text-text-secondary mt-1">
              Read uploaded resumes to fill in candidate details.
            </p>
          </div>
          <div className="md:col-span-2 max-w-md flex flex-col gap-4">
            <div className="flex items-start justify-between gap-4">
              <div>
                <label
                  htmlFor="automation-parsing"
                  className="block text-sm font-medium text-text-primary cursor-pointer"
                >
                  Parse resumes on upload
                </label>
                <p className="text-xs text-text-muted mt-0.5">
                  Extracts skills, phone, experience, education and previous company. When off, the
                  resume is still stored and attached — it is just never read.
                </p>
              </div>
              <Toggle
                id="automation-parsing"
                checked={parsingOn}
                disabled={isSaving}
                onChange={() => save({ resume_parsing_enabled: !parsingOn })}
              />
            </div>

            {/* Auto-tagging — nested, since tags come from parsed skills */}
            <div className="flex items-start justify-between gap-4 pl-4 border-l-2 border-border">
              <div>
                <label
                  htmlFor="automation-autotag"
                  className={`block text-sm font-medium cursor-pointer ${
                    parsingOn ? "text-text-primary" : "text-text-muted"
                  }`}
                >
                  Auto-tagging
                </label>
                <p className="text-xs text-text-muted mt-0.5">
                  {parsingOn
                    ? "Adds the top skills found in the resume to the candidate as tags. Turn off to tag candidates manually."
                    : "Unavailable while resume parsing is off — tags are derived from parsed skills."}
                </p>
              </div>
              <Toggle
                id="automation-autotag"
                checked={automation.auto_tagging_enabled}
                disabled={isSaving || !parsingOn}
                onChange={() => save({ auto_tagging_enabled: !automation.auto_tagging_enabled })}
              />
            </div>

            {saved && (
              <p className="text-xs text-green-600 dark:text-green-400 flex items-center gap-1">
                <IconCheck className="w-3 h-3" /> Settings saved
              </p>
            )}
            {error && <p className="text-xs text-red-500 dark:text-red-400">{error}</p>}
          </div>
        </div>

        {/* What stays on regardless */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4 md:gap-6 py-6 items-start">
          <div>
            <p className="text-sm font-medium text-text-primary flex items-center gap-1.5">
              <IconTag className="w-4 h-4 text-text-muted" />
              Bulk upload
            </p>
            <p className="text-sm text-text-secondary mt-1">Not affected by the switches above.</p>
          </div>
          <div className="md:col-span-2 max-w-md">
            <p className="text-sm text-text-secondary">
              Bulk resume upload matches each file to a candidate by the email address inside it, so
              it keeps reading that one field even with parsing off. Nothing else is inferred.
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}
