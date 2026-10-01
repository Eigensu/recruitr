"use client";

import { useRef, useState } from "react";
import { motion } from "motion/react";
import {
  IconAlertTriangle,
  IconFileSpreadsheet,
  IconLoader2,
  IconUpload,
  IconX,
} from "@tabler/icons-react";
import { cn, formatMonthlySalary } from "@/lib/utils";
import { apiErrorMessage } from "@/lib/api";
import {
  importNaukri,
  NAUKRI_OUTCOME_LABELS,
  previewNaukriImport,
  type NaukriImportResult,
  type NaukriPreview,
  type NaukriRowOutcome,
} from "@/lib/api/intake";

const OUTCOME_STYLES: Record<NaukriRowOutcome, string> = {
  new: "bg-emerald-500/10 text-emerald-400 border-emerald-500/20",
  matched_existing: "bg-surface-panel text-text-muted border-border",
  already_ingested: "bg-surface-panel text-text-muted border-border",
  duplicate_in_sheet: "bg-surface-panel text-text-muted border-border",
};

type Step =
  | { name: "pick" }
  | { name: "preview"; file: File; preview: NaukriPreview }
  | { name: "done"; result: NaukriImportResult };

/**
 * Upload a Naukri export, see what it would do, then import it.
 *
 * The preview is the point: it is worked out by the same checks the import
 * runs, so "3 new leads" here is the 3 the telecallers will get — and a row
 * whose salary looks mis-keyed is flagged before anyone is asked to call it.
 */
export default function NaukriImportDialog({
  onClose,
  onImported,
}: {
  readonly onClose: () => void;
  readonly onImported: () => void;
}) {
  const inputRef = useRef<HTMLInputElement>(null);
  const [step, setStep] = useState<Step>({ name: "pick" });
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function choose(file: File | undefined) {
    if (!file) return;
    setBusy(true);
    setError(null);
    try {
      setStep({ name: "preview", file, preview: await previewNaukriImport(file) });
    } catch (err) {
      setError(apiErrorMessage(err, "Could not read that file."));
    } finally {
      setBusy(false);
      if (inputRef.current) inputRef.current.value = "";
    }
  }

  async function runImport() {
    if (step.name !== "preview") return;
    setBusy(true);
    setError(null);
    try {
      const result = await importNaukri(step.file);
      setStep({ name: "done", result });
      onImported();
    } catch (err) {
      setError(apiErrorMessage(err, "The import failed. Nothing was saved."));
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-end justify-center bg-black/60 p-4 sm:items-center">
      <button
        type="button"
        aria-label="Close"
        tabIndex={-1}
        onClick={busy ? undefined : onClose}
        className="absolute inset-0 cursor-default"
      />
      <motion.div
        initial={{ opacity: 0, y: 12 }}
        animate={{ opacity: 1, y: 0 }}
        role="dialog"
        aria-modal="true"
        aria-label="Import a Naukri export"
        className="relative flex max-h-[90vh] w-full max-w-4xl flex-col rounded-xl border border-border bg-surface p-5 shadow-2xl"
      >
        <header className="mb-4 flex items-start justify-between gap-3">
          <div>
            <h2 className="font-heading text-lg font-bold text-text-primary">
              Import a Naukri export
            </h2>
            <p className="mt-0.5 text-sm text-text-secondary">
              New people become leads in the telecaller queue. Salaries are converted from yearly to
              per month.
            </p>
          </div>
          <button
            type="button"
            onClick={onClose}
            disabled={busy}
            aria-label="Close"
            className="rounded-lg p-1 text-text-muted hover:text-text-primary disabled:opacity-40"
          >
            <IconX className="size-4" />
          </button>
        </header>

        {error && (
          <p
            role="alert"
            className="mb-3 rounded-lg border border-red-500/20 bg-red-500/10 px-3 py-2 text-sm text-red-400"
          >
            {error}
          </p>
        )}

        {step.name === "pick" && (
          <label
            htmlFor="naukri-file"
            className={cn(
              "flex cursor-pointer flex-col items-center gap-2 rounded-xl border border-dashed border-border px-6 py-10 text-center transition-colors hover:border-yellow/40",
              busy && "pointer-events-none opacity-60",
            )}
          >
            {busy ? (
              <IconLoader2 className="size-6 animate-spin text-text-muted" />
            ) : (
              <IconFileSpreadsheet className="size-6 text-text-muted" />
            )}
            <span className="text-sm font-medium text-text-primary">
              {busy ? "Reading the file…" : "Choose the .xlsx Naukri exported"}
            </span>
            <span className="text-xs text-text-muted">
              Up to 5 MB. Nothing is saved until you confirm.
            </span>
            <input
              ref={inputRef}
              id="naukri-file"
              type="file"
              accept=".xlsx,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
              className="sr-only"
              onChange={(e) => choose(e.target.files?.[0])}
            />
          </label>
        )}

        {step.name === "preview" && (
          <>
            <div className="mb-3 flex flex-wrap gap-2 text-xs">
              <Count n={step.preview.new} label="new leads" strong />
              <Count n={step.preview.matched_existing} label="already in the pool" />
              <Count n={step.preview.already_ingested} label="imported before" />
              <Count n={step.preview.duplicate_in_sheet} label="repeated in the file" />
              <Count n={step.preview.skipped.length} label="unusable rows" />
              <span className="ml-auto self-center text-text-muted">{step.file.name}</span>
            </div>

            <div className="min-h-0 flex-1 overflow-auto rounded-lg border border-border">
              <table className="w-full text-left text-sm">
                <thead className="sticky top-0 bg-surface-2 text-xs text-text-muted">
                  <tr>
                    <th className="px-3 py-2 font-medium">Row</th>
                    <th className="px-3 py-2 font-medium">Name</th>
                    <th className="px-3 py-2 font-medium">Phone</th>
                    <th className="px-3 py-2 font-medium">Current role</th>
                    <th className="px-3 py-2 font-medium">Salary</th>
                    <th className="px-3 py-2 font-medium">Result</th>
                  </tr>
                </thead>
                <tbody>
                  {step.preview.rows.map((row) => (
                    <tr key={row.row_number} className="border-t border-border align-top">
                      <td className="px-3 py-2 text-text-muted tabular-nums">{row.row_number}</td>
                      <td className="px-3 py-2 text-text-primary">{row.full_name}</td>
                      <td className="px-3 py-2 text-text-secondary tabular-nums">{row.phone}</td>
                      <td className="px-3 py-2 text-text-secondary">
                        {[row.designation, row.current_company].filter(Boolean).join(" @ ") || "—"}
                      </td>
                      <td className="px-3 py-2 text-text-secondary tabular-nums">
                        {row.salary == null ? "—" : formatMonthlySalary(row.salary)}
                        {row.warnings.map((w) => (
                          <span
                            key={w}
                            className="mt-1 flex items-start gap-1 text-xs text-orange-500"
                          >
                            <IconAlertTriangle className="mt-px size-3 shrink-0" />
                            {w}
                          </span>
                        ))}
                      </td>
                      <td className="px-3 py-2">
                        <span
                          className={cn(
                            "inline-block whitespace-nowrap rounded-full border px-2 py-0.5 text-xs",
                            OUTCOME_STYLES[row.outcome],
                          )}
                        >
                          {NAUKRI_OUTCOME_LABELS[row.outcome]}
                        </span>
                      </td>
                    </tr>
                  ))}
                  {step.preview.skipped.map((row) => (
                    <tr key={`skip-${row.row_number}`} className="border-t border-border">
                      <td className="px-3 py-2 text-text-muted tabular-nums">{row.row_number}</td>
                      <td colSpan={4} className="px-3 py-2 text-text-muted">
                        Skipped — {row.reason}
                      </td>
                      <td className="px-3 py-2">
                        <span className="inline-block rounded-full border border-red-500/20 bg-red-500/10 px-2 py-0.5 text-xs text-red-400">
                          Unusable
                        </span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            <footer className="mt-4 flex items-center justify-between gap-3">
              <button
                type="button"
                disabled={busy}
                onClick={() => setStep({ name: "pick" })}
                className="rounded-lg px-3 py-2 text-sm text-text-secondary hover:text-text-primary disabled:opacity-40"
              >
                Choose another file
              </button>
              <button
                type="button"
                disabled={busy || step.preview.new === 0}
                onClick={runImport}
                className="inline-flex items-center gap-1.5 rounded-lg bg-yellow px-4 py-2 text-sm font-semibold text-navy disabled:opacity-50"
              >
                {busy ? (
                  <IconLoader2 className="size-4 animate-spin" />
                ) : (
                  <IconUpload className="size-4" />
                )}
                {step.preview.new === 0
                  ? "Nothing new to import"
                  : `Import ${step.preview.new} lead${step.preview.new === 1 ? "" : "s"}`}
              </button>
            </footer>
          </>
        )}

        {step.name === "done" && (
          <div className="flex flex-col gap-4">
            <div className="rounded-lg border border-emerald-500/20 bg-emerald-500/10 px-4 py-3 text-sm text-emerald-300">
              {step.result.created} new lead{step.result.created === 1 ? "" : "s"} created
              {step.result.assigned > 0 && ` and handed to telecallers (${step.result.assigned})`}.
              {step.result.unassigned > 0 &&
                ` ${step.result.unassigned} are waiting because no telecaller is active.`}
            </div>
            <ul className="grid grid-cols-2 gap-2 text-sm text-text-secondary sm:grid-cols-4">
              <li>Already in the pool: {step.result.matched_existing}</li>
              <li>Imported before: {step.result.already_ingested}</li>
              <li>Repeated in the file: {step.result.repeated_in_file}</li>
              <li>Unusable rows: {step.result.unusable}</li>
            </ul>
            {step.result.errors.length > 0 && (
              <ul className="list-inside list-disc text-xs text-red-400">
                {step.result.errors.map((e) => (
                  <li key={e}>{e}</li>
                ))}
              </ul>
            )}
            <div className="flex justify-end">
              <button
                type="button"
                onClick={onClose}
                className="rounded-lg bg-yellow px-4 py-2 text-sm font-semibold text-navy"
              >
                Done
              </button>
            </div>
          </div>
        )}
      </motion.div>
    </div>
  );
}

function Count({
  n,
  label,
  strong = false,
}: Readonly<{ n: number; label: string; strong?: boolean }>) {
  return (
    <span
      className={cn(
        "rounded-full border px-2.5 py-1",
        strong && n > 0
          ? "border-emerald-500/20 bg-emerald-500/10 text-emerald-300"
          : "border-border text-text-secondary",
      )}
    >
      <span className="font-semibold tabular-nums">{n}</span> {label}
    </span>
  );
}
