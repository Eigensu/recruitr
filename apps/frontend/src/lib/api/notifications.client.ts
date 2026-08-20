"use client";

import type { PipelineNotification } from "@/types";

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

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
