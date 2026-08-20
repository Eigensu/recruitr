"use client";

import type { PipelineBoardData, PipelineNotification } from "@/types";

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

/** Full Kanban board state — used by the dashboard action widget to find
 * mappings awaiting a client/staff action (see PipelineActionRow's actionGateFor). */
export async function clientFetchPipelineBoard(): Promise<PipelineBoardData> {
  const res = await fetch(`${API_URL}/api/v1/pipeline/board`, { credentials: "include" });
  if (!res.ok) throw new Error(`Board fetch failed: ${res.status}`);
  return res.json();
}

interface MappingActionResult {
  mapping_id: string;
  stage: string;
  decision: string;
  offer_document_url: string | null;
  joining_date: string | null;
}

/** Tick ("selected") or cross ("rejected") a mapping awaiting a decision. */
export async function clientDecideMapping(
  mappingId: string,
  decision: "selected" | "rejected",
): Promise<MappingActionResult> {
  const res = await fetch(`${API_URL}/api/v1/pipeline/mappings/${mappingId}/decision`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    credentials: "include",
    body: JSON.stringify({ decision }),
  });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

/** Upload the offer letter for a selected candidate. */
export async function clientUploadOffer(
  mappingId: string,
  file: File,
): Promise<MappingActionResult> {
  const formData = new FormData();
  formData.append("file", file);
  const res = await fetch(`${API_URL}/api/v1/pipeline/mappings/${mappingId}/offer`, {
    method: "POST",
    credentials: "include",
    body: formData,
  });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

/** Set the candidate's joining date once an offer has been uploaded. */
export async function clientSetJoiningDate(
  mappingId: string,
  joiningDate: string,
): Promise<MappingActionResult> {
  const res = await fetch(`${API_URL}/api/v1/pipeline/mappings/${mappingId}/joining-date`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    credentials: "include",
    body: JSON.stringify({ joining_date: joiningDate }),
  });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

/** Manual override: the candidate didn't show up on their joining date. */
export async function clientMarkNotJoined(mappingId: string): Promise<MappingActionResult> {
  const res = await fetch(`${API_URL}/api/v1/pipeline/mappings/${mappingId}/mark-not-joined`, {
    method: "POST",
    credentials: "include",
  });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

export async function clientFetchNotifications(
  unreadOnly = false,
): Promise<PipelineNotification[]> {
  const qs = unreadOnly ? "?unread_only=true" : "";
  const res = await fetch(`${API_URL}/api/v1/notifications${qs}`, {
    credentials: "include",
  });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

export async function clientMarkNotificationRead(id: string): Promise<PipelineNotification> {
  const res = await fetch(`${API_URL}/api/v1/notifications/${id}/read`, {
    method: "POST",
    credentials: "include",
  });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}
