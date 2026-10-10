"use client";

import { useState } from "react";
import Image from "next/image";
import { IconAlertCircle, IconCheck, IconLinkOff } from "@tabler/icons-react";
import ResumeDropzone from "@/components/public/ResumeDropzone";
import { ThemeToggle } from "@/components/ui/ThemeToggle";
import { uploadCvThroughLink, type CvUploadLinkInfo } from "@/lib/api/public";

/**
 * Pinned to one locale and zone: this renders on the server (UTC, whatever its
 * locale) and again in the candidate's browser, and the two have to agree or
 * React throws the page away and re-renders it.
 */
function dateLabel(iso: string): string {
  return new Date(iso).toLocaleDateString("en-IN", {
    day: "numeric",
    month: "long",
    timeZone: "Asia/Kolkata",
  });
}

function Shell({
  info,
  children,
}: Readonly<{ info: CvUploadLinkInfo | null; children: React.ReactNode }>) {
  return (
    <main className="min-h-dvh bg-shell font-sans text-text-primary theme-transition">
      <header className="flex items-center justify-between gap-3 px-5 py-5 sm:px-8">
        {/* min-w-0 so a long agency name truncates instead of pushing the
            theme toggle off a phone screen. */}
        <div className="flex min-w-0 items-center gap-2.5">
          <Image
            src={info?.brand_logo_url || "/logo-yellow.jpeg"}
            alt=""
            width={32}
            height={32}
            className="size-8 rounded-lg object-cover"
            unoptimized={!!info?.brand_logo_url}
          />
          <span className="truncate font-heading text-lg font-bold tracking-tight">
            {info?.brand_name || "Binge"}
          </span>
        </div>
        <ThemeToggle size="lg" />
      </header>
      <div className="flex justify-center px-4 pb-16 pt-4 sm:pt-10">
        <div className="w-full max-w-md rounded-2xl border border-border bg-surface-panel p-6 sm:p-8">
          {children}
        </div>
      </div>
    </main>
  );
}

/**
 * The page a CV upload link opens: the candidate sends their CV with no
 * account. Someone at the agency made the link for them and sent it on
 * WhatsApp or similar, so the page greets them by first name and asks for
 * nothing but the file.
 *
 * The link stays usable until it expires, and a second upload replaces the
 * first — so someone who picked the wrong file can simply send the right one.
 */
export default function CvUploadForm({
  token,
  info,
}: Readonly<{ token: string; info: CvUploadLinkInfo | null }>) {
  const [file, setFile] = useState<File | null>(null);
  const [sending, setSending] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [sent, setSent] = useState(false);
  const [sentBefore, setSentBefore] = useState(info?.uploaded ?? false);

  if (!info) {
    return (
      <Shell info={null}>
        <div className="text-center">
          <div className="mx-auto mb-5 flex size-12 items-center justify-center rounded-full bg-red-500/10 text-red-500">
            <IconLinkOff className="size-6" />
          </div>
          <h1 className="font-heading text-2xl font-bold tracking-tight">
            This link no longer works
          </h1>
          <p className="mt-3 text-sm text-text-secondary">
            It has expired or been replaced by a newer one. Ask whoever sent it to you for a new
            link.
          </p>
        </div>
      </Shell>
    );
  }

  const until = dateLabel(info.expires_at);

  if (sent) {
    return (
      <Shell info={info}>
        <div className="text-center">
          <div className="mx-auto mb-5 flex size-12 items-center justify-center rounded-full bg-yellow/10 text-yellow">
            <IconCheck className="size-6" />
          </div>
          <h1 className="font-heading text-2xl font-bold tracking-tight">
            Thanks, {info.first_name}
          </h1>
          <p className="mt-3 text-sm text-text-secondary">{info.brand_name} has your CV.</p>
          <p className="mt-4 text-xs text-text-muted">
            Sent the wrong file? You can send a different one from this link until {until}.
          </p>
          <button
            type="button"
            onClick={() => setSent(false)}
            className="mt-3 text-xs font-semibold text-text-primary underline underline-offset-2"
          >
            Send a different file
          </button>
        </div>
      </Shell>
    );
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!file) {
      setError("Choose your CV first.");
      return;
    }
    setSending(true);
    setError(null);
    try {
      await uploadCvThroughLink(token, file);
      setFile(null);
      setSentBefore(true);
      setSent(true);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not upload your CV. Try again.");
    } finally {
      setSending(false);
    }
  }

  return (
    <Shell info={info}>
      <h1 className="font-heading text-2xl font-bold tracking-tight">
        Hi {info.first_name}, send us your CV
      </h1>
      <p className="mt-2 text-sm text-text-secondary">
        {info.brand_name} asked for your CV. A PDF or Word (.docx) file, up to 10 MB.
      </p>
      {sentBefore && (
        <p className="mt-3 rounded-lg border border-border bg-surface p-2.5 text-xs text-text-secondary">
          You&apos;ve already sent one. Sending another replaces it.
        </p>
      )}

      <form onSubmit={handleSubmit} className="mt-5 flex flex-col gap-4">
        <ResumeDropzone
          file={file}
          onChange={(next) => {
            setFile(next);
            setError(null);
          }}
          disabled={sending}
        />
        {error && (
          <div
            role="alert"
            className="flex items-start gap-2.5 rounded-xl border border-red-500/20 bg-red-500/10 p-3"
          >
            <IconAlertCircle className="mt-px size-4 shrink-0 text-red-500" />
            <p className="text-sm font-medium text-red-500">{error}</p>
          </div>
        )}
        <button
          type="submit"
          disabled={sending}
          className="w-full rounded-lg bg-yellow px-4 py-3 text-sm font-bold text-navy transition-all hover:brightness-105 disabled:opacity-50"
        >
          {sending ? "Sending…" : "Send CV"}
        </button>
      </form>

      <p className="mt-4 text-center text-xs text-text-muted">
        Shared only with {info.brand_name}. This link works until {until}.
      </p>
    </Shell>
  );
}
