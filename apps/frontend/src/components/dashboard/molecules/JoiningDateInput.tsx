"use client";

import { useState } from "react";
import { IconCalendarEvent } from "@tabler/icons-react";
import { apiErrorMessage } from "@/lib/api";
import { clientMarkNotJoined, clientSetJoiningDate } from "@/lib/api/pipeline-actions.client";
import { useToast } from "@/components/ui/Toast";

interface JoiningDateInputProps {
  mappingId: string;
  /** Present once a joining date has already been set (offer_accepted stage). */
  joiningDate: string | null;
  onUpdated: () => void;
}

export default function JoiningDateInput({
  mappingId,
  joiningDate,
  onUpdated,
}: JoiningDateInputProps) {
  const [value, setValue] = useState(joiningDate ? joiningDate.slice(0, 10) : "");
  const [isSaving, setIsSaving] = useState(false);
  const toast = useToast();

  async function handleSetDate() {
    if (!value) return;
    setIsSaving(true);
    try {
      await clientSetJoiningDate(mappingId, value);
      toast("Joining date set.", "success");
      onUpdated();
    } catch (err) {
      toast(apiErrorMessage(err, "Could not set the joining date."), "error");
    } finally {
      setIsSaving(false);
    }
  }

  async function handleMarkNotJoined() {
    setIsSaving(true);
    try {
      await clientMarkNotJoined(mappingId);
      toast("Marked as not joined.", "info");
      onUpdated();
    } catch (err) {
      toast(apiErrorMessage(err, "Could not update this candidate."), "error");
    } finally {
      setIsSaving(false);
    }
  }

  if (joiningDate) {
    return (
      <div className="flex items-center gap-3">
        <span className="flex items-center gap-1.5 text-xs text-text-secondary">
          <IconCalendarEvent className="size-3.5" />
          Joining {new Date(joiningDate).toLocaleDateString("en-GB")}
        </span>
        <button
          type="button"
          onClick={handleMarkNotJoined}
          disabled={isSaving}
          className="text-xs font-medium text-red-500 underline decoration-dotted hover:opacity-80 disabled:opacity-50"
        >
          Didn&apos;t join
        </button>
      </div>
    );
  }

  return (
    <div className="flex items-center gap-2">
      <input
        type="date"
        value={value}
        onChange={(e) => setValue(e.target.value)}
        className="rounded-lg border px-2 py-1.5 text-xs"
        style={{
          borderColor: "var(--color-border-val)",
          background: "var(--color-canvas-val)",
          color: "var(--color-text-primary)",
        }}
      />
      <button
        type="button"
        onClick={handleSetDate}
        disabled={isSaving || !value}
        className="rounded-lg px-3 py-1.5 text-xs font-bold text-navy transition-opacity hover:opacity-90 disabled:opacity-50"
        style={{ background: "var(--color-yellow)" }}
      >
        {isSaving ? "Saving…" : "Set date"}
      </button>
    </div>
  );
}
