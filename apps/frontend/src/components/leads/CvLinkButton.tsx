"use client";

import { useState } from "react";
import { IconCopy, IconLink, IconLoader2 } from "@tabler/icons-react";
import { useApiFetch, apiErrorMessage } from "@/lib/api";
import { createCvLink, cvUploadPageUrl, type IntakeLead } from "@/lib/api/intake";
import { useToast } from "@/components/ui/Toast";

function untilLabel(iso: string): string {
  return new Date(iso).toLocaleDateString("en-IN", { day: "numeric", month: "short" });
}

/** Whether a lead has no CV anyone could open — the case a CV link is for. */
export function needsCv(lead: Pick<IntakeLead, "cv_link" | "resume_url" | "cv_locked">): boolean {
  return !lead.cv_link && !lead.resume_url && !lead.cv_locked;
}

/**
 * Makes a link the lead's candidate can upload their CV through, and copies
 * it, for whoever holds the lead to send on WhatsApp or however they reach
 * them. The app sends nothing itself. A new link cancels the previous one.
 *
 * Where the clipboard is refused (an http page, an old browser) the link is
 * shown instead, ready to select.
 */
export default function CvLinkButton({
  lead,
}: Readonly<{ lead: Pick<IntakeLead, "id" | "full_name" | "cv_link_expires_at"> }>) {
  const apiFetch = useApiFetch();
  const toast = useToast();
  const [busy, setBusy] = useState(false);
  const [expiresAt, setExpiresAt] = useState(lead.cv_link_expires_at);
  const [shown, setShown] = useState<string | null>(null);
  // Read once: a link running out while the card is open is not worth a timer.
  const [now] = useState(() => Date.now());
  const live = expiresAt !== null && new Date(expiresAt).getTime() > now;
  const firstName = lead.full_name.split(" ")[0];

  async function handleClick() {
    setBusy(true);
    try {
      const link = await createCvLink(apiFetch, lead.id);
      const url = cvUploadPageUrl(link.token);
      setExpiresAt(link.expires_at);
      try {
        await navigator.clipboard.writeText(url);
        setShown(null);
        toast(`Link copied. Send it to ${firstName}; it works for 7 days.`, "success");
      } catch {
        setShown(url);
        toast(`Copy the link below and send it to ${firstName}.`, "success");
      }
    } catch (err) {
      toast(apiErrorMessage(err, "Could not make a CV link."), "error");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="flex flex-col gap-1.5">
      <div className="flex flex-wrap items-center gap-2">
        <button
          type="button"
          disabled={busy}
          onClick={handleClick}
          title={live ? "Makes a fresh link. The one already sent stops working." : undefined}
          className="inline-flex items-center gap-1.5 rounded-lg border border-border px-2.5 py-1 text-xs font-medium text-text-secondary transition-colors hover:bg-surface-panel hover:text-text-primary disabled:opacity-60"
        >
          {busy ? (
            <IconLoader2 className="size-3.5 animate-spin" />
          ) : (
            <IconCopy className="size-3.5" />
          )}
          {live ? "Copy a new CV link" : "Get CV upload link"}
        </button>
        {live && expiresAt && (
          <span className="inline-flex items-center gap-1 text-[11px] text-text-muted">
            <IconLink className="size-3" />
            Link sent, works until {untilLabel(expiresAt)}
          </span>
        )}
      </div>
      {shown && (
        <input
          readOnly
          value={shown}
          onFocus={(e) => e.currentTarget.select()}
          aria-label={`CV upload link for ${firstName}`}
          className="w-full rounded-lg border border-border bg-canvas px-2.5 py-1.5 text-xs text-text-primary"
        />
      )}
    </div>
  );
}
