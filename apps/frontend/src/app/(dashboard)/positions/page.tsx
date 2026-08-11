import { Suspense } from "react";
import { getUserServer } from "@/lib/api/auth.server";
import PositionsPageClient from "@/components/positions/PositionsPageClient";

export default async function PositionsPage() {
  // Resolved once, server-side, and passed down instead of letting the
  // client component re-fetch /auth/me on mount — that duplicate fetch
  // started from role=unknown on every load, so staff-only affordances
  // (client filter, "+ New Position", drag hints) briefly rendered for
  // every visitor, including clients, before the response came back.
  const user = await getUserServer();
  const isClient = user?.role === "client";
  const isMaintainer = user?.role === "maintainer" || user?.role === "admin";

  return (
    <Suspense fallback={<div className="h-full bg-canvas" />}>
      <PositionsPageClient isClient={isClient} isMaintainer={isMaintainer} />
    </Suspense>
  );
}
