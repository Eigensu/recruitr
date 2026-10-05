"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { IconLoader2 } from "@tabler/icons-react";
import { useCurrentUser } from "@/hooks/useCurrentUser";
import TelecallerQueue from "@/components/leads/TelecallerQueue";
import AdminLeadList from "@/components/leads/AdminLeadList";
import RecruiterLeads from "@/components/leads/RecruiterLeads";

/**
 * One route, three screens.
 *
 * A telecaller sees only their own queue — this is where sign-in, OAuth and
 * RouteGuard all send the role, because every other staff page is built on
 * endpoints it is refused. A maintainer sees every lead. A recruiter imports
 * leads and follows the ones they put in, and nothing else: the queue and the
 * all-leads list stay closed to them on the server. Clients and referees have
 * no business here, so they are sent home rather than shown a page of 403s.
 */
export default function LeadsPage() {
  const router = useRouter();
  const { isTelecaller, isMaintainer, isAdmin, isClient, isReferee, isLoading } = useCurrentUser();
  const isOutsider = isClient || isReferee;

  useEffect(() => {
    if (isLoading) return;
    if (isOutsider) router.replace("/");
  }, [isLoading, isOutsider, router]);

  if (isLoading || isOutsider) {
    return (
      <div className="flex h-64 items-center justify-center">
        <IconLoader2 className="size-6 animate-spin text-text-muted" />
      </div>
    );
  }

  if (isTelecaller) return <TelecallerQueue />;
  if (isMaintainer) return <AdminLeadList isAdmin={isAdmin} />;
  return <RecruiterLeads />;
}
