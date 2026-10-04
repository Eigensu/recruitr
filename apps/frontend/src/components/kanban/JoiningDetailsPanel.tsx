"use client";

import { useState, type ReactNode } from "react";
import { IconCalendarEvent, IconCheck } from "@tabler/icons-react";
import { setMappingJoiningDate } from "@/lib/api/pipeline";
import type { PipelineCard } from "@/types";

const INPUT =
  "w-full rounded-lg border border-border bg-surface-2 px-3 py-2 text-sm text-text-primary focus:border-yellow focus:outline-none";

/**
 * Joining date and salary offered for one placement, at the top of the
 * candidate drawer opened from a joined card. The rest of the drawer is the
 * candidate's whole history, across every position.
 *
 * The parent keys this by mapping, so the fields start again from what is
 * saved for each card. `readOnly` (an archived card) shows what is saved
 * without the form.
 */
export default function JoiningDetailsPanel({
  card,
  onSaved,
  readOnly = false,
}: Readonly<{ card: PipelineCard; onSaved: () => void; readOnly?: boolean }>) {
  if (readOnly) return <SavedJoiningDetails card={card} />;
  return <JoiningDetailsForm card={card} onSaved={onSaved} />;
}

function PanelShell({ card, children }: Readonly<{ card: PipelineCard; children: ReactNode }>) {
  return (
    <section className="rounded-xl border border-emerald-500/20 bg-emerald-500/5 p-4">
      <div className="mb-3 flex items-center gap-2">
        <IconCalendarEvent className="size-4 shrink-0 text-emerald-400" />
        <h3 className="text-[10px] font-bold uppercase tracking-widest text-text-muted">
          Joining details
        </h3>
      </div>
      <p className="mb-3 truncate text-xs text-text-secondary">
        {card.position_role} · {card.position_client}
      </p>
      {children}
    </section>
  );
}

function SavedJoiningDetails({ card }: Readonly<{ card: PipelineCard }>) {
  return (
    <PanelShell card={card}>
      <dl className="grid grid-cols-2 gap-2 text-sm">
        <div>
          <dt className="text-[10px] font-semibold uppercase text-text-muted">Joining date</dt>
          <dd className="mt-1 text-text-primary">
            {card.joining_date ? new Date(card.joining_date).toLocaleDateString() : "—"}
          </dd>
        </div>
        <div>
          <dt className="text-[10px] font-semibold uppercase text-text-muted">Salary offered</dt>
          <dd className="mt-1 text-text-primary">
            {card.salary_offered == null ? "—" : `₹${card.salary_offered.toLocaleString()}`}
          </dd>
        </div>
      </dl>
    </PanelShell>
  );
}

function JoiningDetailsForm({
  card,
  onSaved,
}: Readonly<{ card: PipelineCard; onSaved: () => void }>) {
  const [joiningDate, setJoiningDate] = useState(card.joining_date?.slice(0, 10) ?? "");
  const [salary, setSalary] = useState(
    card.salary_offered == null ? "" : String(card.salary_offered),
  );
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const savedDate = card.joining_date?.slice(0, 10) ?? "";
  const savedSalary = card.salary_offered == null ? "" : String(card.salary_offered);
  const dirty = joiningDate !== savedDate || salary !== savedSalary;

  async function save() {
    setSaving(true);
    setError(null);
    try {
      // A blank salary sends null, which keeps what is stored rather than
      // overwriting it with 0.
      await setMappingJoiningDate(
        card.mapping_id,
        new Date(joiningDate).toISOString(),
        salary.trim() === "" ? null : Number(salary),
      );
      onSaved();
    } catch (err) {
      setError(err instanceof Error && err.message ? err.message : "Could not save.");
    } finally {
      setSaving(false);
    }
  }

  return (
    <PanelShell card={card}>
      {error && (
        <div className="mb-3 rounded-lg border border-red-500/20 bg-red-500/10 p-2.5 text-xs text-red-400">
          {error}
        </div>
      )}

      <div className="grid grid-cols-2 gap-2">
        <label className="space-y-1">
          <span className="text-[10px] font-semibold uppercase text-text-muted">Joining date</span>
          <input
            type="date"
            value={joiningDate}
            onChange={(e) => setJoiningDate(e.target.value)}
            className={INPUT}
          />
        </label>
        <label className="space-y-1">
          <span className="text-[10px] font-semibold uppercase text-text-muted">
            Salary offered (₹)
          </span>
          <input
            type="number"
            min={0}
            inputMode="numeric"
            value={salary}
            onChange={(e) => setSalary(e.target.value)}
            className={INPUT}
          />
        </label>
      </div>

      <div className="mt-3 flex items-center justify-between gap-3">
        {!dirty && card.joining_date ? (
          <span className="flex items-center gap-1.5 text-xs font-semibold text-emerald-400">
            <IconCheck className="size-3.5 shrink-0" /> Saved
          </span>
        ) : (
          <span />
        )}
        <button
          type="button"
          onClick={save}
          disabled={saving || !joiningDate || !dirty}
          className="rounded-lg border border-emerald-500/20 bg-emerald-500/10 px-4 py-2 text-xs font-semibold text-emerald-400 transition-all hover:bg-emerald-500/20 disabled:opacity-50"
        >
          {saving ? "Saving…" : "Save"}
        </button>
      </div>
    </PanelShell>
  );
}
