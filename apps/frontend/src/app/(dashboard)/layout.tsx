import DashboardSidebar from "@/components/sidebar/DashboardSidebar";
import { ToastProvider } from "@/components/ui/Toast";
import ForbiddenBoundary from "@/components/common/ForbiddenBoundary";
import "./dashboard.css";

export default function DashboardLayout({ children }: { readonly children: React.ReactNode }) {
  return (
    <ToastProvider>
      <div className="flex h-dvh overflow-hidden bg-shell md:p-3 md:gap-3">
        <DashboardSidebar />
        <main className="flex-1 overflow-hidden bg-canvas md:rounded-xl md:shadow-2xl flex flex-col">
          {/* Inner scroll container — main itself never scrolls so rounded corners stay intact */}
          <div className="flex-1 overflow-y-auto scrollbar-none">
            <ForbiddenBoundary>{children}</ForbiddenBoundary>
          </div>
        </main>
      </div>
    </ToastProvider>
  );
}
