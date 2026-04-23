import Link from "next/link";

export default function DashboardLayout({ children }: { children: React.ReactNode }) {
  return (
    <div className="flex min-h-screen bg-gray-950">
      {/* Sidebar */}
      <aside className="w-64 bg-gray-900 border-r border-gray-800 flex flex-col">
        {/* Logo */}
        <div className="p-6 border-b border-gray-800">
          <span className="text-xl font-bold bg-gradient-to-r from-violet-400 to-indigo-400 bg-clip-text text-transparent">
            Eigensu
          </span>
        </div>

        {/* Nav links */}
        <nav className="flex-1 p-4 space-y-1">
          {[
            { href: "/", label: "Dashboard", icon: "▣" },
            { href: "/positions", label: "Positions", icon: "◈" },
            { href: "/candidates", label: "Candidates", icon: "◉" },
            { href: "/leaderboard", label: "Leaderboard", icon: "◆" },
            { href: "/settings", label: "Settings", icon: "◎" },
          ].map(({ href, label, icon }) => (
            <Link
              key={href}
              href={href}
              className="flex items-center gap-3 px-3 py-2 rounded-lg text-gray-400 hover:text-gray-50 hover:bg-gray-800 transition-colors text-sm font-medium"
            >
              <span>{icon}</span>
              {label}
            </Link>
          ))}
        </nav>

        {/* User profile */}
        <div className="p-4 border-t border-gray-800 flex items-center gap-3">
          <Link
            href="/sign-in"
            className="text-sm font-medium text-gray-400 hover:text-white transition-colors"
            onClick={async () => {
              // In a real implementation this would call an API route to clear the cookie
              await fetch("/api/v1/auth/logout", { method: "POST" });
              document.cookie = "access_token=; expires=Thu, 01 Jan 1970 00:00:00 UTC; path=/;";
            }}
          >
            Sign Out
          </Link>
        </div>
      </aside>

      {/* Main content */}
      <main className="flex-1 overflow-auto">{children}</main>
    </div>
  );
}
