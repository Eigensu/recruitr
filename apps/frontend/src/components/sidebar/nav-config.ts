import type { ComponentType, SVGAttributes } from "react";
import {
  IconActivity,
  IconBriefcase,
  IconLayoutDashboard,
  IconLayoutKanban,
  IconSettings,
  IconTrophy,
  IconUsers,
} from "@tabler/icons-react";

export interface NavItemConfig {
  href: string;
  label: string;
  icon: ComponentType<SVGAttributes<SVGElement> & { className?: string }>;
  exact?: boolean;
  maintainerOnly?: boolean;
}

export const NAV_CONFIG: NavItemConfig[] = [
  { href: "/", label: "Dashboard", icon: IconLayoutDashboard, exact: true },
  { href: "/positions", label: "Positions", icon: IconBriefcase },
  { href: "/candidates", label: "Candidates", icon: IconUsers },
  { href: "/pipeline", label: "Pipeline", icon: IconLayoutKanban },
  { href: "/leaderboard", label: "Leaderboard", icon: IconTrophy },
  { href: "/settings", label: "Settings", icon: IconSettings },
  { href: "/activity", label: "Activity", icon: IconActivity, maintainerOnly: true },
];

export function isNavItemActive(pathname: string, href: string, exact?: boolean): boolean {
  if (exact) return pathname === href;
  return pathname === href || pathname.startsWith(href + "/");
}
