"use client";

import { useRef, useState } from "react";
import { IconUpload } from "@tabler/icons-react";
import { apiErrorMessage } from "@/lib/api";
import { clientUploadOffer } from "@/lib/api/pipeline-actions.client";
import { useToast } from "@/components/ui/Toast";

interface OfferUploadBoxProps {
  mappingId: string;
  onUploaded: () => void;
}

export default function OfferUploadBox({ mappingId, onUploaded }: OfferUploadBoxProps) {
  const inputRef = useRef<HTMLInputElement>(null);
  const [isUploading, setIsUploading] = useState(false);
  const toast = useToast();

  async function handleChange(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (!file) return;
    setIsUploading(true);
    try {
      await clientUploadOffer(mappingId, file);
      toast("Offer letter uploaded.", "success");
      onUploaded();
    } catch (err) {
      toast(apiErrorMessage(err, "Could not upload the offer letter."), "error");
    } finally {
      setIsUploading(false);
      if (inputRef.current) inputRef.current.value = "";
    }
  }

  return (
    <div className="flex items-center gap-2">
      <input
        ref={inputRef}
        type="file"
        accept=".pdf,.doc,.docx"
        className="hidden"
        onChange={handleChange}
        disabled={isUploading}
      />
      <button
        type="button"
        onClick={() => inputRef.current?.click()}
        disabled={isUploading}
        className="flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-xs font-bold text-navy transition-opacity hover:opacity-90 disabled:opacity-50"
        style={{ background: "var(--color-yellow)" }}
      >
        <IconUpload className="size-3.5" />
        {isUploading ? "Uploading…" : "Upload offer"}
      </button>
    </div>
  );
}
