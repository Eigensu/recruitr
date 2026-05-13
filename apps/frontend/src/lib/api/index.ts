/**
 * Typed API fetch wrapper.
 *
 * Frontend uses credentials: "include" to send HttpOnly cookies
 * safely to the API without exposing tokens to JS.
 */
"use client";

import { useCallback } from "react";

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

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
      const errorText = await res.text();
      throw new Error(errorText || `API error: ${res.status}`);
    }

    // 204 No Content — return null
    if (res.status === 204) return null as T;
    return res.json() as Promise<T>;
  }, []);

  return apiFetch;
}
