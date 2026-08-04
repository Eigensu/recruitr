"use client";

import { useEffect, useState } from "react";
import { IconCheck, IconCopy, IconExternalLink } from "@tabler/icons-react";

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

/**
 * Shows the public application link for the signed-in user's agency, so it can
 * be copied and shared without anyone having to remember the domain or
 * hand-assemble the URL.
 */
export default function ShareApplicationLink() {
  const [link, setLink] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);

  useEffect(() => {
    let cancelled = false;
    fetch(`${API_URL}/api/v1/brands/me`, { credentials: "include" })
      .then(async (res) => {
        if (!res.ok) throw new Error(String(res.status));
        return res.json();
      })
      .then((brand: { domain?: string }) => {
        if (cancelled) return;
        if (!brand.domain) {
          setError("Your workspace has no domain set, so the link can't be built yet.");
          return;
        }
        setLink(`${window.location.origin}/form/${encodeURIComponent(brand.domain)}`);
      })
      .catch(() => {
        if (!cancelled) setError("Couldn't load your application link. Try reloading.");
      });
    return () => {
      cancelled = true;
    };
  }, []);

  async function copy() {
    if (!link) return;
    try {
      await navigator.clipboard.writeText(link);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch {
      setError("Couldn't copy automatically — select the link and copy it manually.");
    }
  }

  return (
    <div className="rounded-xl border border-border bg-surface p-5">
      <h3 className="text-sm font-bold text-text-primary">Application link</h3>
      <p className="mt-1 text-xs text-text-secondary">
        Share this with candidates. Anyone who opens it can apply without signing in, and their
        application arrives in Candidates as Pending.
      </p>

      {error && <p className="mt-3 text-xs font-medium text-red-500">{error}</p>}

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

      {!link && !error && <p className="mt-4 text-xs text-text-muted">Loading…</p>}
    </div>
  );
}
