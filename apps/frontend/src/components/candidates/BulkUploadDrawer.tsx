"use client";

import { useRef, useState } from "react";
import { clientBulkUpload } from "@/lib/api/candidates.client";
import type { BulkUploadResult } from "@/types";

interface Props {
  onComplete: (result: BulkUploadResult) => void;
  onClose: () => void;
}

type FileStatus = "pending" | "uploading" | "done" | "failed";

interface FileEntry {
  file: File;
  status: FileStatus;
  error?: string;
}

const STATUS_COLOR: Record<FileStatus, string> = {
  pending: "var(--color-text-secondary)",
  uploading: "#F7C948",
  done: "#3DDC97",
  failed: "#FF5A5F",
};

export default function BulkUploadDrawer({ onComplete, onClose }: Props) {
  const inputRef = useRef<HTMLInputElement>(null);
  const [entries, setEntries] = useState<FileEntry[]>([]);
  const [uploading, setUploading] = useState(false);
  const [result, setResult] = useState<BulkUploadResult | null>(null);

  function handleFileSelect(files: FileList | null) {
    if (!files) return;
    const pdfs = Array.from(files).filter(
      (f) => f.type === "application/pdf" || f.name.toLowerCase().endsWith(".pdf"),
    );
    if (pdfs.length + entries.length > 50) {
      alert("Maximum 50 files per upload.");
      return;
    }
    setEntries((prev) => [
      ...prev,
      ...pdfs.map((f) => ({ file: f, status: "pending" as FileStatus })),
    ]);
  }

  function removeFile(idx: number) {
    setEntries((prev) => prev.filter((_, i) => i !== idx));
  }

  async function handleUpload() {
    if (entries.length === 0 || uploading) return;
    setUploading(true);
    setEntries((prev) => prev.map((e) => ({ ...e, status: "uploading" as FileStatus })));

    try {
      const res = await clientBulkUpload(entries.map((e) => e.file));
      const failedMap = new Map(res.failed.map((f) => [f.filename, f.reason]));
      setEntries((prev) =>
        prev.map((e) => ({
          ...e,
          status: failedMap.has(e.file.name) ? "failed" : "done",
          error: failedMap.get(e.file.name),
        })),
      );
      setResult(res);
      onComplete(res);
    } catch {
      setEntries((prev) => prev.map((e) => ({ ...e, status: "failed", error: "Upload failed" })));
    } finally {
      setUploading(false);
    }
  }

  return (
    <div className="flex flex-col gap-4 p-4">
      <div className="flex items-center justify-between">
        <h2 className="text-lg font-semibold" style={{ color: "var(--color-text-primary)" }}>
          Bulk Resume Upload
        </h2>
        <button
          type="button"
          onClick={onClose}
          className="text-sm opacity-60 hover:opacity-100"
          style={{ color: "var(--color-text-secondary)" }}
        >
          Close
        </button>
      </div>

      <div
        className="cursor-pointer rounded-lg border-2 border-dashed p-6 text-center"
        style={{ borderColor: "var(--color-border-val)" }}
        onClick={() => inputRef.current?.click()}
        onDragOver={(e) => e.preventDefault()}
        onDrop={(e) => {
          e.preventDefault();
          handleFileSelect(e.dataTransfer.files);
        }}
      >
        <p className="text-sm" style={{ color: "var(--color-text-secondary)" }}>
          Drop PDF files here or click to browse (max 50)
        </p>
        <input
          ref={inputRef}
          type="file"
          accept=".pdf,application/pdf"
          multiple
          className="hidden"
          onChange={(e) => handleFileSelect(e.target.files)}
        />
      </div>

      {entries.length > 0 && (
        <div className="flex max-h-48 flex-col gap-1 overflow-y-auto">
          {entries.map((entry, idx) => (
            <div
              key={`${entry.file.name}-${idx}`}
              className="flex items-center justify-between rounded-lg px-2 py-1 text-sm"
              style={{ background: "var(--color-canvas-val)" }}
            >
              <span className="flex-1 truncate" style={{ color: "var(--color-text-primary)" }}>
                {entry.file.name}
              </span>
              <span
                className="ml-2 shrink-0 text-xs font-medium"
                style={{ color: STATUS_COLOR[entry.status] }}
              >
                {entry.status === "failed" ? `✗ ${entry.error ?? "failed"}` : entry.status}
              </span>
              {entry.status === "pending" && (
                <button
                  type="button"
                  onClick={() => removeFile(idx)}
                  className="ml-2 text-xs opacity-50 hover:opacity-100"
                >
                  ×
                </button>
              )}
            </div>
          ))}
        </div>
      )}

      {result && (
        <div className="rounded-lg p-3 text-sm" style={{ background: "var(--color-canvas-val)" }}>
          <p style={{ color: "#3DDC97" }}>Created: {result.created}</p>
          <p style={{ color: "var(--color-text-primary)" }}>Updated: {result.updated}</p>
          {result.failed.length > 0 && (
            <p style={{ color: "#FF5A5F" }}>Failed: {result.failed.length}</p>
          )}
        </div>
      )}

      {!result && (
        <button
          type="button"
          disabled={entries.length === 0 || uploading}
          onClick={handleUpload}
          className="rounded-lg py-2 text-sm font-semibold disabled:opacity-50"
          style={{ background: "var(--color-yellow)", color: "#002348" }}
        >
          {uploading
            ? "Uploading…"
            : `Upload ${entries.length} file${entries.length !== 1 ? "s" : ""}`}
        </button>
      )}
    </div>
  );
}
