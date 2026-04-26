import DashboardSidebar from "@/components/sidebar/DashboardSidebar";

export default function DashboardLayout({ children }: { children: React.ReactNode }) {
  return (
    <div className="flex h-screen overflow-hidden bg-gray-950">
      <DashboardSidebar />
      <main className="flex-1 overflow-auto">{children}</main>
    </div>
  );
}
