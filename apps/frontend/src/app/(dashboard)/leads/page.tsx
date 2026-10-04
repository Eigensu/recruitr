"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { IconLoader2 } from "@tabler/icons-react";
import { useCurrentUser } from "@/hooks/useCurrentUser";
import TelecallerQueue from "@/components/leads/TelecallerQueue";
import AdminLeadList from "@/components/leads/AdminLeadList";

/**
 * One route, two screens.
 *
 * A telecaller sees only their own queue — this is where sign-in, OAuth and
 * RouteGuard all send the role, because every other staff page is built on
 * endpoints it is refused. A maintainer sees every lead. A recruiter has no
 * business here at all: the backend refuses them, so sending them home is
 * kinder than rendering a page of 403s.
 */
export default function LeadsPage() {
  const router = useRouter();
  const { isTelecaller, isMaintainer, isAdmin, isLoading } = useCurrentUser();

  useEffect(() => {
    if (isLoading) return;
    if (!isTelecaller && !isMaintainer) router.replace("/");
  }, [isLoading, isTelecaller, isMaintainer, router]);

  if (isLoading || (!isTelecaller && !isMaintainer)) {
    return (
      <div className="flex h-64 items-center justify-center">
        <IconLoader2 className="size-6 animate-spin text-text-muted" />
      </div>
    );
  }

  if (isTelecaller) return <TelecallerQueue />;
  return <AdminLeadList isAdmin={isAdmin} />;
}
