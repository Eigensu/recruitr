"use client";

import { useState } from "react";
import { IconLoader2 } from "@tabler/icons-react";
import { apiErrorMessage, useApiFetch } from "@/lib/api";
import { useToast } from "@/components/ui/Toast";
import { saveTelecallerTarget, type TelecallerTarget } from "@/lib/api/intake";

/** "" is no target; anything else must be a whole number of calls, 0 or more. */
function parseTarget(text: string): number | null | "invalid" {
  const trimmed = text.trim();
  if (trimmed === "") return null;
  const n = Number(trimmed);
  return Number.isInteger(n) && n >= 0 ? n : "invalid";
}

function TargetRow({
  target,
  onSaved,
}: Readonly<{ target: TelecallerTarget; onSaved: (saved: TelecallerTarget) => void }>) {
  const apiFetch = useApiFetch();
  const toast = useToast();
  const [daily, setDaily] = useState(target.daily_calls?.toString() ?? "");
  const [weekly, setWeekly] = useState(target.weekly_calls?.toString() ?? "");
  const [saving, setSaving] = useState(false);

  const dailyValue = parseTarget(daily);
  const weeklyValue = parseTarget(weekly);
  const invalid = dailyValue === "invalid" || weeklyValue === "invalid";
  const dirty =
    daily !== (target.daily_calls?.toString() ?? "") ||
    weekly !== (target.weekly_calls?.toString() ?? "");

  async function save() {
    if (dailyValue === "invalid" || weeklyValue === "invalid") return;
    setSaving(true);
    try {
      const saved = await saveTelecallerTarget(apiFetch, target.telecaller_id, {
        daily_calls: dailyValue,
        weekly_calls: weeklyValue,
      });
      onSaved(saved);
      toast(`Targets saved for ${target.telecaller_name}.`, "success");
    } catch (err) {
      toast(apiErrorMessage(err, "Could not save those targets."), "error");
    } finally {
      setSaving(false);
    }
  }

  const input =
    "w-24 rounded-lg border bg-canvas px-2.5 py-1.5 text-right text-sm tabular-nums text-text-primary focus:outline-none focus-visible:ring-2 focus-visible:ring-yellow";

  return (
    <tr className="border-b border-border/60">
      <td className="px-3 py-2 font-medium text-text-primary">
        {target.telecaller_name}
        {!target.active && (
          <span className="ml-1 text-xs font-normal text-text-muted">(paused)</span>
        )}
      </td>
      <td className="px-3 py-2 text-right">
        <input
          inputMode="numeric"
          value={daily}
          onChange={(e) => setDaily(e.target.value)}
          placeholder="—"
          aria-label={`Daily calls target for ${target.telecaller_name}`}
          aria-invalid={dailyValue === "invalid"}
          className={`${input} ${dailyValue === "invalid" ? "border-red-500/60" : "border-border"}`}
        />
      </td>
      <td className="px-3 py-2 text-right">
        <input
          inputMode="numeric"
          value={weekly}
          onChange={(e) => setWeekly(e.target.value)}
          placeholder="—"
          aria-label={`Weekly calls target for ${target.telecaller_name}`}
          aria-invalid={weeklyValue === "invalid"}
          className={`${input} ${weeklyValue === "invalid" ? "border-red-500/60" : "border-border"}`}
        />
      </td>
      <td className="px-3 py-2 text-right">
        <button
          type="button"
          onClick={save}
          disabled={saving || invalid || !dirty}
          className="inline-flex items-center gap-1.5 rounded-lg bg-navy px-3 py-1.5 text-xs font-semibold text-white transition-opacity hover:opacity-90 disabled:opacity-40 dark:bg-yellow dark:text-navy"
        >
          {saving && <IconLoader2 className="size-3.5 animate-spin" />}
          Save
        </button>
      </td>
    </tr>
  );
}

/**
 * Calls per day and per week, per telecaller. A yardstick for the report, not a
 * rule: nothing is blocked when someone is under it. Blank means no target.
 */
export default function TelecallerTargets({
  targets,
  onSaved,
}: Readonly<{ targets: TelecallerTarget[]; onSaved: (saved: TelecallerTarget) => void }>) {
  if (targets.length === 0) {
    return (
      <p className="rounded-xl border border-dashed border-border py-12 text-center text-sm text-text-secondary">
        No telecallers yet. Add them under Settings → Telecallers.
      </p>
    );
  }
  return (
    <div className="overflow-x-auto rounded-xl border border-border bg-surface">
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b border-border text-left text-xs uppercase tracking-wide text-text-muted">
            <th className="px-3 py-2 font-semibold">Telecaller</th>
            <th className="px-3 py-2 text-right font-semibold">Calls per day</th>
            <th className="px-3 py-2 text-right font-semibold">Calls per week</th>
            <th className="px-3 py-2" />
          </tr>
        </thead>
        <tbody>
          {targets.map((target) => (
            // Keyed on what is saved, so a saved row remounts with its stored values.
            <TargetRow
              key={`${target.telecaller_id}:${target.daily_calls}:${target.weekly_calls}`}
              target={target}
              onSaved={onSaved}
            />
          ))}
        </tbody>
      </table>
    </div>
  );
}
