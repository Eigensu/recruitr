"use client";

import { useEffect, useState } from "react";
import type { UserInfo, UserRole } from "@/types";

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

interface CurrentUserState {
  user: UserInfo | null;
  isLoading: boolean;
  /** True for maintainers and admins (admin ⊇ maintainer). */
  isMaintainer: boolean;
  isAdmin: boolean;
  isClient: boolean;
  isReferee: boolean;
}

/**
 * Fetch the authenticated user (incl. role) from /auth/me.
 *
 * Role is resolved server-side and not stored in the JWT, so it must come
 * from this endpoint rather than the cookie. Used to gate management UI;
 * the backend still enforces every role check independently.
 */
export function useCurrentUser(): CurrentUserState {
  const [user, setUser] = useState<UserInfo | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    fetch(`${API_URL}/api/v1/auth/me`, { credentials: "include" })
      .then((r) => (r.ok ? r.json() : null))
      .then((data: UserInfo | null) => {
        if (!cancelled) setUser(data);
      })
      .catch(() => {
        if (!cancelled) setUser(null);
      })
      .finally(() => {
        if (!cancelled) setIsLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  const role: UserRole | undefined = user?.role;
  return {
    user,
    isLoading,
    isMaintainer: role === "maintainer" || role === "admin",
    isAdmin: role === "admin",
    isClient: role === "client",
    isReferee: role === "referee",
  };
}
