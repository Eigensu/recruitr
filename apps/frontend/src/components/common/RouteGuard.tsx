"use client";

import { useEffect } from "react";
import { usePathname, useRouter } from "next/navigation";
import { useCurrentUser } from "@/hooks/useCurrentUser";

export default function RouteGuard({ children }: { readonly children: React.ReactNode }) {
  const { isClient, isReferee, isLoading } = useCurrentUser();
  const pathname = usePathname();
  const router = useRouter();

  useEffect(() => {
    if (isLoading) return;

    if (isReferee) {
      // Referees should only access /referee and its sub-routes
      if (!pathname.startsWith("/referee")) {
        router.replace("/referee");
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
  }, [isReferee, isClient, isLoading, pathname, router]);

  return <>{children}</>;
}
