import DashboardSidebar from "@/components/sidebar/DashboardSidebar";

export default function DashboardLayout({ children }: { children: React.ReactNode }) {
  return (
    <div className="flex h-dvh overflow-hidden bg-canvas">
      <DashboardSidebar />
      <main className="flex-1 overflow-auto bg-canvas p-6">{children}</main>
    </div>
  );
}
