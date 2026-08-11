import DashboardSidebar from "@/components/sidebar/DashboardSidebar";
import { ToastProvider } from "@/components/ui/Toast";
import ForbiddenBoundary from "@/components/common/ForbiddenBoundary";
import RouteGuard from "@/components/common/RouteGuard";
import "./dashboard.css";

// Every route under (dashboard) is authenticated and reads the access_token
// cookie (directly via getUserServer, or indirectly via dashboardFetch)
// before rendering anything — none of them can be statically generated.
// Without this, `next build` still attempts a static pass, and the resulting
// DYNAMIC_SERVER_USAGE bailout gets caught by this codebase's own
// Promise.allSettled error handling instead of reaching Next.js's build step
// cleanly, which is what produced the noisy "X fetch failed" build log.
export const dynamic = "force-dynamic";

export default function DashboardLayout({ children }: { readonly children: React.ReactNode }) {
  return (
    <ToastProvider>
      <RouteGuard>
        <div className="flex h-dvh overflow-hidden bg-shell md:p-3 md:gap-3">
          <DashboardSidebar />
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
