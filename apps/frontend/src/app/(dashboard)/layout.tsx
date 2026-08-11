import DashboardSidebar from "@/components/sidebar/DashboardSidebar";
import { ToastProvider } from "@/components/ui/Toast";
import ForbiddenBoundary from "@/components/common/ForbiddenBoundary";
import RouteGuard from "@/components/common/RouteGuard";
import { getUserServer } from "@/lib/api/auth.server";
import "./dashboard.css";

// Every route under (dashboard) is authenticated and reads the access_token
// cookie (directly via getUserServer, or indirectly via dashboardFetch)
// before rendering anything — none of them can be statically generated.
// Without this, `next build` still attempts a static pass, and the resulting
// DYNAMIC_SERVER_USAGE bailout gets caught by this codebase's own
// Promise.allSettled error handling instead of reaching Next.js's build step
// cleanly, which is what produced the noisy "X fetch failed" build log.
export const dynamic = "force-dynamic";

export default async function DashboardLayout({
  children,
}: {
  readonly children: React.ReactNode;
}) {
  // Resolved once, server-side, and passed down instead of letting the
  // sidebar re-fetch /auth/me client-side on mount — that duplicate fetch
  // started from role=unknown on every load, so the nav briefly rendered
  // every role's items (including staff-only ones like Candidates) before
  // correcting itself once the response came back.
  const user = await getUserServer();

  return (
    <ToastProvider>
      <RouteGuard>
        <div className="flex h-dvh overflow-hidden bg-shell md:p-3 md:gap-3">
          <DashboardSidebar user={user} />
          <main className="flex-1 overflow-hidden bg-canvas md:rounded-xl md:shadow-2xl flex flex-col">
            {/* Inner scroll container — main itself never scrolls so rounded corners stay intact */}
            <div className="flex-1 overflow-y-auto scrollbar-none pb-[calc(4rem+env(safe-area-inset-bottom,0px))] md:pb-0">
              <ForbiddenBoundary>{children}</ForbiddenBoundary>
            </div>
          </main>
        </div>
      </RouteGuard>
    </ToastProvider>
  );
}
