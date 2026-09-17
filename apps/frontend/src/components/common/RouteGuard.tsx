"use client";

import { useEffect } from "react";
import { usePathname, useRouter } from "next/navigation";
import { useCurrentUser } from "@/hooks/useCurrentUser";

export default function RouteGuard({ children }: { readonly children: React.ReactNode }) {
  const { isClient, isReferee, isTelecaller, isLoading } = useCurrentUser();
  const pathname = usePathname();
  const router = useRouter();

  useEffect(() => {
    if (isLoading) return;

    if (isReferee) {
      // Referees should only access /referee and its sub-routes
      if (!pathname.startsWith("/referee")) {
        router.replace("/referee");
      }
    } else if (isTelecaller) {
      // An allow-list, not a deny-list like clients get below: the backend
      // refuses a telecaller on every staff endpoint, so any other page would
      // render as a wall of 403s. Mirrors get_tenant's default-deny.
      const allowedForTelecallers = ["/leads", "/settings"];
      if (!allowedForTelecallers.some((path) => pathname.startsWith(path))) {
        router.replace("/leads");
      }
    } else if (isClient) {
      const forbiddenForClients = [
        "/candidates",
        "/leaderboard",
        "/clients",
        "/activity",
        "/client-messaging",
        "/referee",
      ];
      if (forbiddenForClients.some((path) => pathname.startsWith(path))) {
        router.replace("/");
      }
    } else {
      const forbiddenForEmployees = ["/company", "/referee"];
      if (forbiddenForEmployees.some((path) => pathname.startsWith(path))) {
        router.replace("/");
      }
    }
  }, [isReferee, isTelecaller, isClient, isLoading, pathname, router]);

  return <>{children}</>;
}
