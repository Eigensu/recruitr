"use client";

import { useRef, useState } from "react";
import {
  IconAlertCircle,
  IconCloudUpload,
  IconFileTypeDocx,
  IconFileTypePdf,
  IconX,
} from "@tabler/icons-react";

const MAX_BYTES = 10 * 1024 * 1024;
const ACCEPT =
  ".pdf,.docx,application/pdf,application/vnd.openxmlformats-officedocument.wordprocessingml.document";

interface ResumeDropzoneProps {
  file: File | null;
  onChange: (file: File | null) => void;
  disabled?: boolean;
}

function formatBytes(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${Math.round(bytes / 1024)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

/** Mirrors the server's checks so applicants learn before they submit, not after. */
function validate(file: File): string | null {
  const name = file.name.toLowerCase();
  if (!name.endsWith(".pdf") && !name.endsWith(".docx")) {
    return "That file type isn't supported. Upload a PDF or DOCX.";
  }
  if (file.size > MAX_BYTES) {
    return `That file is ${formatBytes(file.size)}. The limit is 10 MB.`;
  }
  return null;
}

export default function ResumeDropzone({
  file,
  onChange,
  disabled = false,
}: Readonly<ResumeDropzoneProps>) {
  const inputRef = useRef<HTMLInputElement>(null);
  // dragenter/dragleave also fire when crossing child elements, so depth-count
  // them rather than toggling a boolean that flickers as the pointer moves.
  const dragDepth = useRef(0);
  const [dragging, setDragging] = useState(false);
  const [error, setError] = useState<string | null>(null);

  function accept(selected: File | undefined) {
    if (!selected) return;
    const problem = validate(selected);
    setError(problem);
    onChange(problem ? null : selected);
  }

  function clear() {
    setError(null);
    onChange(null);
    if (inputRef.current) inputRef.current.value = "";
  }

  function handleDrop(e: React.DragEvent) {
    e.preventDefault();
    dragDepth.current = 0;
    setDragging(false);
    if (disabled) return;
    accept(e.dataTransfer.files?.[0]);
  }

  // Without an onDragOver preventDefault the browser navigates to the dropped
  // file, discarding everything already typed into the form.
  const dragProps = {
    onDragEnter: (e: React.DragEvent) => {
      e.preventDefault();
      dragDepth.current += 1;
      if (!disabled) setDragging(true);
    },
    onDragOver: (e: React.DragEvent) => e.preventDefault(),
    onDragLeave: (e: React.DragEvent) => {
      e.preventDefault();
      dragDepth.current -= 1;
      if (dragDepth.current <= 0) setDragging(false);
    },
    onDrop: handleDrop,
  };

  const FileIcon = file?.name.toLowerCase().endsWith(".docx")
    ? IconFileTypeDocx
    : IconFileTypePdf;

  return (
    <div>
      <input
        ref={inputRef}
        id="resume"
        type="file"
        accept={ACCEPT}
        className="sr-only"
        disabled={disabled}
        onChange={(e) => accept(e.target.files?.[0])}
      />

      {file ? (
        <div
          {...dragProps}
          className="flex items-center gap-3 rounded-xl border border-border bg-canvas p-3 sm:p-4"
        >
          <div className="flex size-10 shrink-0 items-center justify-center rounded-lg bg-navy/10 text-navy dark:bg-yellow/10 dark:text-yellow">
            <FileIcon className="size-5" />
          </div>
          <div className="min-w-0 flex-1">
            <p className="truncate text-sm font-medium text-text-primary">{file.name}</p>
            <p className="mt-0.5 text-xs text-text-muted">{formatBytes(file.size)} · Attached</p>
          </div>
          <button
            type="button"
            onClick={() => inputRef.current?.click()}
            disabled={disabled}
            className="shrink-0 rounded-lg px-2.5 py-1.5 text-xs font-semibold text-text-secondary transition-colors hover:bg-surface-2 hover:text-text-primary disabled:opacity-50"
          >
            Replace
          </button>
          <button
            type="button"
            onClick={clear}
            disabled={disabled}
            aria-label={`Remove ${file.name}`}
            className="shrink-0 rounded-lg p-1.5 text-text-muted transition-colors hover:bg-surface-2 hover:text-text-primary disabled:opacity-50"
          >
            <IconX className="size-4" />
          </button>
        </div>
      ) : (
        <button
          type="button"
          {...dragProps}
          onClick={() => inputRef.current?.click()}
          disabled={disabled}
          className={`flex w-full flex-col items-center justify-center gap-2 rounded-xl border-2 border-dashed px-6 py-8 text-center transition-colors sm:py-10 ${
            dragging
              ? "border-navy bg-navy/5 dark:border-yellow dark:bg-yellow/5"
              : "border-border bg-canvas/30 hover:border-navy/50 hover:bg-canvas/60 dark:hover:border-yellow/50"
          } ${disabled ? "cursor-not-allowed opacity-60" : "cursor-pointer"}`}
        >
          <IconCloudUpload
            className={`size-8 transition-colors ${dragging ? "text-navy dark:text-yellow" : "text-text-muted"}`}
          />
          <span className="text-sm text-text-secondary">
            <span className="font-semibold text-navy dark:text-yellow">Choose a file</span> or drag it here
          </span>
          <span className="text-xs text-text-muted">PDF or DOCX, up to 10 MB</span>
        </button>
      )}

      {error && (
        <p className="mt-2 flex items-start gap-1.5 text-xs font-medium text-red-500">
          <IconAlertCircle className="mt-px size-3.5 shrink-0" />
          {error}
        </p>
      )}
    </div>
  );
}
