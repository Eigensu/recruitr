"use client";

import { useEffect, useId, useRef, useState, type ReactNode } from "react";
import { IconAlertTriangle, IconLoader2 } from "@tabler/icons-react";
import { apiErrorMessage } from "@/lib/api";
import { cn } from "@/lib/utils";

export interface ConfirmDialogProps {
  readonly open: boolean;
  readonly title: string;
  readonly description?: ReactNode;
  readonly confirmLabel?: string;
  readonly cancelLabel?: string;
  /** Red confirm button, for actions that remove or revoke something. */
  readonly destructive?: boolean;
  /**
   * May return a promise. The dialog stays open and busy until it settles,
   * closes when it resolves, and shows the error in place when it rejects —
   * so the caller has no failure path of its own to wire up.
   */
  readonly onConfirm: () => void | Promise<void>;
  readonly onClose: () => void;
}

/**
 * Ask before doing something, in place of window.confirm.
 *
 * Built on the native <dialog> opened with showModal(), which supplies the
 * focus trap, the Escape key and the inert page behind it. It deliberately
 * does not close on a backdrop click: a confirmation wants an explicit answer,
 * and a stray click outside is not one.
 */
export default function ConfirmDialog({
  open,
  title,
  description,
  confirmLabel = "Confirm",
  cancelLabel = "Cancel",
  destructive = false,
  onConfirm,
  onClose,
}: ConfirmDialogProps) {
  const ref = useRef<HTMLDialogElement>(null);
  const titleId = useId();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const dialog = ref.current;
    if (!dialog) return;
    if (open && !dialog.open) dialog.showModal();
    else if (!open && dialog.open) dialog.close();
  }, [open]);

  function close() {
    if (busy) return;
    setError(null);
    onClose();
  }

  async function confirm() {
    setBusy(true);
    setError(null);
    try {
      await onConfirm();
      onClose();
    } catch (err) {
      setError(apiErrorMessage(err, "Something went wrong. Please try again."));
    } finally {
      setBusy(false);
    }
  }

  return (
    <dialog
      ref={ref}
      aria-labelledby={titleId}
      // Escape fires `cancel` and would close the element behind React's back,
      // leaving `open` stale; route it through onClose so the parent decides.
      onCancel={(e) => {
        e.preventDefault();
        close();
      }}
      // Preflight zeroes every margin, which strips the UA's centring.
      className="m-auto w-[calc(100%-2rem)] max-w-sm rounded-xl border border-border bg-surface p-5 text-text-primary shadow-2xl backdrop:bg-black/60"
    >
      <div className="flex items-start gap-3">
        {destructive && (
          <span className="flex size-9 shrink-0 items-center justify-center rounded-full bg-red-500/10">
            <IconAlertTriangle className="size-4.5 text-red-500" />
          </span>
        )}
        <div className="min-w-0">
          <h2 id={titleId} className="font-heading text-base font-bold">
            {title}
          </h2>
          {description && <div className="mt-1 text-sm text-text-secondary">{description}</div>}
        </div>
      </div>

      {error && (
        <p
          role="alert"
          className="mt-4 rounded-lg border border-red-500/20 bg-red-500/10 px-3 py-2 text-sm text-red-500"
        >
          {error}
        </p>
      )}

      <div className="mt-5 flex justify-end gap-2">
        {/* First in the DOM, so showModal() focuses it: Enter on a freshly
            opened dialog should not be the destructive choice. */}
        <button
          type="button"
          onClick={close}
          disabled={busy}
          className="rounded-lg px-4 py-2 text-sm font-medium text-text-secondary transition-colors hover:text-text-primary disabled:opacity-50 cursor-pointer"
        >
          {cancelLabel}
        </button>
        <button
          type="button"
          onClick={confirm}
          disabled={busy}
          className={cn(
            "flex items-center gap-2 rounded-lg px-4 py-2 text-sm font-medium transition-opacity hover:opacity-90 disabled:opacity-50 cursor-pointer",
            destructive
              ? "bg-red-500 text-white"
              : "bg-navy text-white dark:bg-yellow dark:text-navy",
          )}
        >
          {busy && <IconLoader2 className="size-4 animate-spin" />}
          {confirmLabel}
        </button>
      </div>
    </dialog>
  );
}
