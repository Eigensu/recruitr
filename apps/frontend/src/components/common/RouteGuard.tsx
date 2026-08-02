"use client";

import { useEffect } from "react";
import { usePathname, useRouter } from "next/navigation";
import { useCurrentUser } from "@/hooks/useCurrentUser";

export default function RouteGuard({ children }: { readonly children: React.ReactNode }) {
  const { isClient, isLoading } = useCurrentUser();
  const pathname = usePathname();
  const router = useRouter();

  useEffect(() => {
    if (isLoading) return;

    if (isClient) {
      const forbiddenForClients = ["/candidates", "/leaderboard", "/clients", "/activity"];
      if (forbiddenForClients.some((path) => pathname.startsWith(path))) {
        router.replace("/");
      }
    } else {
      const forbiddenForEmployees = ["/company"];
      if (forbiddenForEmployees.some((path) => pathname.startsWith(path))) {
        router.replace("/");
      }
    }
  }, [isClient, isLoading, pathname, router]);

  return <>{children}</>;
}
