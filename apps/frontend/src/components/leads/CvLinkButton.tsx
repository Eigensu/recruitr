"use client";

import { useRef, useState } from "react";
import { IconBrandWhatsapp, IconCheck, IconCopy, IconLink, IconLoader2 } from "@tabler/icons-react";
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
 * The number as wa.me wants it: international, digits only. A bare 10-digit
 * number is read as Indian, as the backend's normalize_phone reads one. Null
 * when there is no usable number, which opens WhatsApp's contact picker.
 */
function whatsAppNumber(phone: string | null): string | null {
  const digits = (phone ?? "").replaceAll(/\D/g, "");
  if (digits.length === 10) return `91${digits}`;
  if (digits.length === 11 && digits.startsWith("0")) return `91${digits.slice(1)}`;
  if (digits.length > 10) return digits;
  return null;
}

function whatsAppHref(phone: string | null, message: string): string {
  return `https://wa.me/${whatsAppNumber(phone) ?? ""}?text=${encodeURIComponent(message)}`;
}

const smallButton =
  "inline-flex items-center gap-1.5 rounded-lg border border-border px-2.5 py-1 text-xs font-medium text-text-secondary transition-colors hover:bg-surface-panel hover:text-text-primary disabled:opacity-60";

/**
 * Makes a link the lead's candidate can upload their CV through, for whoever
 * holds the lead to send them. The app sends nothing itself: the link is shown
 * with a Copy button, and a WhatsApp button that opens a chat with the
 * candidate, message and link already written.
 *
 * Only the token's hash is stored, so a link can be shown only in the session
 * that made it. After that the card says one was sent and until when; making
 * a new one cancels it.
 */
export default function CvLinkButton({
  lead,
}: Readonly<{ lead: Pick<IntakeLead, "id" | "full_name" | "phone" | "cv_link_expires_at"> }>) {
  const apiFetch = useApiFetch();
  const toast = useToast();
  const inputRef = useRef<HTMLInputElement>(null);
  const [busy, setBusy] = useState(false);
  const [expiresAt, setExpiresAt] = useState(lead.cv_link_expires_at);
  const [url, setUrl] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);
  // Read once: a link running out while the card is open is not worth a timer.
  const [now] = useState(() => Date.now());
  const live = expiresAt !== null && new Date(expiresAt).getTime() > now;
  const firstName = lead.full_name.split(" ")[0];

  async function copy(text: string): Promise<boolean> {
    try {
      await navigator.clipboard.writeText(text);
      setCopied(true);
      return true;
    } catch {
      setCopied(false);
      return false;
    }
  }

  async function handleMake() {
    setBusy(true);
    try {
      const link = await createCvLink(apiFetch, lead.id);
      const made = cvUploadPageUrl(link.token);
      setExpiresAt(link.expires_at);
      setUrl(made);
      await copy(made);
    } catch (err) {
      toast(apiErrorMessage(err, "Could not make a CV link."), "error");
    } finally {
      setBusy(false);
    }
  }

  async function handleCopy() {
    if (!url) return;
    if (!(await copy(url))) {
      // An http page or an old browser: leave it selected for Ctrl/⌘+C.
      inputRef.current?.select();
      toast("Couldn't copy it automatically. The link is selected; copy it with Ctrl+C.", "error");
    }
  }

  if (url && expiresAt) {
    const until = untilLabel(expiresAt);
    const message =
      `Hi ${firstName}, please upload your CV here so we can match you to the right roles: ` +
      `${url}\nThe link works until ${until}.`;
    return (
      <div className="flex flex-col gap-1.5 rounded-lg border border-border bg-canvas p-2.5">
        <p className="flex items-center gap-1 text-[11px] font-semibold text-text-secondary">
          <IconLink className="size-3" />
          CV upload link for {firstName} · works until {until}
        </p>
        <input
          ref={inputRef}
          readOnly
          value={url}
          onFocus={(e) => e.currentTarget.select()}
          aria-label={`CV upload link for ${firstName}`}
          className="w-full min-w-0 rounded-md border border-border bg-surface px-2 py-1.5 text-xs text-text-primary"
        />
        <div className="flex flex-wrap gap-2">
          <button type="button" onClick={handleCopy} className={smallButton}>
            {copied ? <IconCheck className="size-3.5" /> : <IconCopy className="size-3.5" />}
            {copied ? "Copied" : "Copy"}
          </button>
          <a
            href={whatsAppHref(lead.phone, message)}
            target="_blank"
            rel="noreferrer noopener"
            className={smallButton}
          >
            <IconBrandWhatsapp className="size-3.5" />
            Send on WhatsApp
          </a>
        </div>
      </div>
    );
  }

  return (
    <div className="flex flex-wrap items-center gap-2">
      <button
        type="button"
        disabled={busy}
        onClick={handleMake}
        title={live ? "The link already sent stops working." : undefined}
        className={smallButton}
      >
        {busy ? (
          <IconLoader2 className="size-3.5 animate-spin" />
        ) : (
          <IconLink className="size-3.5" />
        )}
        {live ? "Make a new CV link" : "Get CV upload link"}
      </button>
      {live && expiresAt && (
        <span className="text-[11px] text-text-muted">
          Link sent, works until {untilLabel(expiresAt)}
        </span>
      )}
    </div>
  );
}
