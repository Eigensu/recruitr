import { getUserServer } from "@/lib/api/auth.server";
import { ToastProvider } from "@/components/ui/Toast";
import ForbiddenBoundary from "@/components/common/ForbiddenBoundary";
import RouteGuard from "@/components/common/RouteGuard";
import { redirect } from "next/navigation";
import DashboardSidebar from "@/components/sidebar/DashboardSidebar";
import "../(dashboard)/dashboard.css"; // Reuse dashboard styles

export const dynamic = "force-dynamic";

export default async function RefereeLayout({ children }: { readonly children: React.ReactNode }) {
  const user = await getUserServer();

  if (!user || user.role !== "referee") {
    redirect("/");
  }

  return (
    <ToastProvider>
      <RouteGuard>
        <div className="flex h-dvh overflow-hidden bg-shell md:p-3 md:gap-3">
          <DashboardSidebar user={user} />
          <main className="flex-1 overflow-hidden bg-canvas md:rounded-xl md:shadow-2xl flex flex-col">
            <div className="flex-1 overflow-y-auto scrollbar-none pb-[calc(4rem+env(safe-area-inset-bottom,0px))] md:pb-0">
              <ForbiddenBoundary>{children}</ForbiddenBoundary>
            </div>
          </main>
        </div>
      </RouteGuard>
    </ToastProvider>
  );
}
