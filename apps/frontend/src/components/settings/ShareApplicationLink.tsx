"use client";

import { useState } from "react";
import { IconCheck, IconCopy, IconExternalLink } from "@tabler/icons-react";
import { useCurrentUser } from "@/hooks/useCurrentUser";

/**
 * Shows the public application link for the signed-in user's agency, so it can
 * be copied and shared without anyone having to remember the domain or
 * hand-assemble the URL.
 *
 * The domain rides along on /auth/me, which is already fetched on every page
 * load — no extra request, and no brands endpoint to keep alive for it.
 */
export default function ShareApplicationLink() {
  const { user, isLoading } = useCurrentUser();
  const [copied, setCopied] = useState(false);
  const [copyError, setCopyError] = useState<string | null>(null);

  const domain = user?.brand_domain;
  // window is unavailable during SSR; this component only renders client-side
  // content once the user has loaded, so guard rather than assume.
  const link =
    domain && typeof window !== "undefined"
      ? `${window.location.origin}/form/${encodeURIComponent(domain)}`
      : null;

  async function copy() {
    if (!link) return;
    try {
      await navigator.clipboard.writeText(link);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch {
      setCopyError("Couldn't copy automatically — select the link and copy it manually.");
    }
  }

  return (
    <div className="rounded-xl border border-border bg-surface p-5">
      <h3 className="text-sm font-bold text-text-primary">Application link</h3>
      <p className="mt-1 text-xs text-text-secondary">
        Share this with candidates. Anyone who opens it can apply without signing in, and their
        application arrives in Candidates as Pending.
      </p>

      {isLoading && <p className="mt-4 text-xs text-text-muted">Loading…</p>}

      {!isLoading && !domain && (
        <p className="mt-3 text-xs font-medium text-red-500">
          Your workspace has no domain set, so the link can&apos;t be built yet.
        </p>
      )}

      {copyError && <p className="mt-3 text-xs font-medium text-red-500">{copyError}</p>}

      {link && (
        <div className="mt-4 flex flex-col gap-2 sm:flex-row">
          <input
            readOnly
            value={link}
            aria-label="Public application link"
            onFocus={(e) => e.currentTarget.select()}
            className="w-full flex-1 rounded-lg border border-border bg-canvas px-3 py-2 text-sm text-text-primary outline-none"
          />
          <div className="flex gap-2">
            <button
              type="button"
              onClick={copy}
              className="flex items-center justify-center gap-1.5 rounded-lg px-3 py-2 text-sm font-semibold text-navy transition-all hover:brightness-105"
              style={{ background: "var(--color-yellow)" }}
            >
              {copied ? <IconCheck className="size-4" /> : <IconCopy className="size-4" />}
              {copied ? "Copied" : "Copy"}
            </button>
            <a
              href={link}
              target="_blank"
              rel="noreferrer noopener"
              className="flex items-center justify-center gap-1.5 rounded-lg border border-border px-3 py-2 text-sm font-medium text-text-secondary transition-colors hover:text-text-primary"
            >
              <IconExternalLink className="size-4" />
              Open
            </a>
          </div>
        </div>
      )}
    </div>
  );
}
