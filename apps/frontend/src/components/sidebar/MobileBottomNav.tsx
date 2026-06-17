"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  IconLayoutDashboard,
  IconBriefcase,
  IconUsers,
  IconLayoutKanban,
  IconTrophy,
} from "@tabler/icons-react";

const NAV_ITEMS = [
  { href: "/", label: "Home", icon: IconLayoutDashboard, exact: true },
  { href: "/positions", label: "Positions", icon: IconBriefcase, exact: false },
  { href: "/candidates", label: "Candidates", icon: IconUsers, exact: false },
  { href: "/pipeline", label: "Pipeline", icon: IconLayoutKanban, exact: false },
  { href: "/leaderboard", label: "Leaderboard", icon: IconTrophy, exact: false },
];

export default function MobileBottomNav() {
  const pathname = usePathname();

  return (
    <nav
      className="fixed bottom-0 left-0 right-0 z-50 flex md:hidden"
      style={{ background: "var(--color-sidebar)", borderTop: "1px solid rgba(255,255,255,0.08)" }}
    >
      {NAV_ITEMS.map(({ href, label, icon: Icon, exact }) => {
        const isActive = exact ? pathname === href : pathname.startsWith(href);
        return (
          <Link
            key={href}
            href={href}
            className="flex flex-1 flex-col items-center justify-center gap-0.5 py-2.5 transition-colors"
            style={{ color: isActive ? "#f5c518" : "rgba(255,255,255,0.4)" }}
            aria-label={label}
          >
            <Icon className="size-5 shrink-0" />
            <span className="text-[10px] font-medium leading-none">{label}</span>
          </Link>
        );
      })}
    </nav>
  );
}
