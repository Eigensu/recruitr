/**
 * Typed API fetch wrapper.
 *
 * Frontend uses credentials: "include" to send HttpOnly cookies
 * safely to the API without exposing tokens to JS.
 */
"use client";

import { useCallback } from "react";

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

/** Thrown by apiFetch when the server returns 403 Forbidden. */
export class ForbiddenError extends Error {
  constructor() {
    super("403 Forbidden");
    this.name = "ForbiddenError";
  }
}

export function useApiFetch() {
  const apiFetch = useCallback(async <T>(path: string, options?: RequestInit): Promise<T> => {
    const headers: Record<string, string> = {
      "Content-Type": "application/json",
      ...(options?.headers as Record<string, string>),
    };

    const res = await fetch(`${API_URL}${path}`, {
      ...options,
      headers,
      credentials: "include", // Ensure cookies are passed
    });

    if (!res.ok) {
      if (res.status === 403) throw new ForbiddenError();
      const errorText = await res.text();
      throw new Error(errorText || `API error: ${res.status}`);
    }

    // 204 No Content — return null
    if (res.status === 204) return null as T;
    return res.json() as Promise<T>;
  }, []);

  return apiFetch;
}
