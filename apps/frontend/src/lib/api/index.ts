/**
 * Typed API fetch wrapper.
 *
 * Frontend uses credentials: "include" to send HttpOnly cookies
 * safely to the API without exposing tokens to JS.
 */
"use client";

import { useCallback } from "react";
import { useRouter } from "next/navigation";

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

/** Thrown by apiFetch when the server returns 403 Forbidden. */
export class ForbiddenError extends Error {
  constructor() {
    super("403 Forbidden");
    this.name = "ForbiddenError";
  }
}

/**
 * Human-readable message from an apiFetch rejection.
 *
 * apiFetch puts the raw response body on the Error, and FastAPI sends
 * `{"detail": "..."}` — so surfacing err.message directly would show JSON to
 * the user. Unwraps that detail when present, otherwise falls back.
 */
export function apiErrorMessage(err: unknown, fallback: string): string {
  if (err instanceof ForbiddenError) return "You don't have permission to do that.";
  const raw = err instanceof Error ? err.message : "";
  if (!raw) return fallback;
  try {
    const detail = (JSON.parse(raw) as { detail?: unknown }).detail;
    if (typeof detail === "string") return detail;
    // 422 validation errors come back as a list of {loc, msg, type}
    if (Array.isArray(detail)) {
      const msg = (detail[0] as { msg?: unknown } | undefined)?.msg;
      if (typeof msg === "string") return msg;
    }
  } catch {
    // Not JSON (e.g. "API error: 500") — use the raw text.
  }
  return raw;
}

export function useApiFetch() {
  const router = useRouter();

  const apiFetch = useCallback(
    async <T>(path: string, options?: RequestInit): Promise<T> => {
      const headers: Record<string, string> = {
        "Content-Type": "application/json",
        ...(options?.headers as Record<string, string>),
      };

      const res = await fetch(`${API_URL}${path}`, {
        ...options,
        headers,
        credentials: "include",
      });

      if (!res.ok) {
        if (res.status === 401) {
          router.replace("/sign-in");
          throw new Error("Session expired");
        }
        if (res.status === 403) throw new ForbiddenError();
        const errorText = await res.text();
        throw new Error(errorText || `API error: ${res.status}`);
      }

      // 204 No Content — return null
      if (res.status === 204) return null as T;
      return res.json() as Promise<T>;
    },
    [router],
  );

  return apiFetch;
}
