"use client";

import { useState } from "react";
import { IconCopy, IconCheck, IconLink } from "@tabler/icons-react";
import { useCurrentUser } from "@/hooks/useCurrentUser";
import ApplicationForm from "@/components/public/ApplicationForm";

export default function ReferCandidatePage() {
  const { user } = useCurrentUser();
  const [copied, setCopied] = useState(false);

  const copyConnectCode = async () => {
    if (!user?.connect_code) return;
    try {
      await navigator.clipboard.writeText(user.connect_code);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch {
      // ignore
    }
  };

  return (
    <div
      className="min-h-full p-4 sm:p-6 lg:p-8 animate-in fade-in duration-300"
      style={{ background: "var(--color-canvas)", color: "var(--color-text-primary)" }}
    >
      <div className="max-w-6xl mx-auto space-y-8">
        {/* Connect Code Banner */}
        <div className="rounded-xl border border-border bg-surface p-6 shadow-sm flex flex-col sm:flex-row sm:items-center justify-between gap-4">
          <div>
            <h2 className="text-sm font-bold text-text-primary flex items-center gap-2">
              <IconLink className="w-4 h-4 text-text-muted" />
              YOUR CONNECT CODE
            </h2>
            <p className="mt-1 text-xs text-text-secondary">
              Share this code with your candidates or apply on their behalf below.
            </p>
          </div>

          <div className="flex items-center gap-3">
            <span className="font-mono text-lg font-bold tracking-wider text-text-primary bg-surface-2 px-4 py-2 rounded-lg border border-border">
              {user?.connect_code ?? "—"}
            </span>
            {user?.connect_code && (
              <button
                type="button"
                onClick={copyConnectCode}
                className="flex items-center justify-center gap-1.5 rounded-lg px-4 py-2.5 text-sm font-semibold text-navy transition-all hover:brightness-105"
                style={{ background: "var(--color-yellow)" }}
              >
                {copied ? <IconCheck className="size-4" /> : <IconCopy className="size-4" />}
                {copied ? "Copied" : "Copy"}
              </button>
            )}
          </div>
        </div>

        {/* Form Container */}
        <div className="-mx-4 sm:-mx-6">
          {user ? (
            <ApplicationForm
              brandId={user.brand_id}
              isEmbedded
              initialConnectCode={user.connect_code}
              initialSourceChannel="Connected by a Binge Partner"
            />
          ) : (
            <div className="flex justify-center py-20">
              <div className="h-8 w-8 animate-spin rounded-full border-2 border-border border-t-text-primary" />
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
