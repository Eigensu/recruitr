import type { ComponentType, SVGAttributes } from "react";
import {
  IconActivity,
  IconBriefcase,
  IconLayoutDashboard,
  IconLayoutKanban,
  IconSettings,
  IconTrophy,
  IconUsers,
  IconBuildingStore,
  IconBuilding,
  IconMessage,
} from "@tabler/icons-react";

export interface NavItemConfig {
  href: string;
  label: string;
  icon: ComponentType<SVGAttributes<SVGElement> & { className?: string }>;
  exact?: boolean;
  maintainerOnly?: boolean;
  hideForClient?: boolean;
  clientOnly?: boolean;
}

export const NAV_CONFIG: NavItemConfig[] = [
  { href: "/", label: "Dashboard", icon: IconLayoutDashboard, exact: true },
  { href: "/positions", label: "Positions", icon: IconBriefcase },
  { href: "/company", label: "Company Profile", icon: IconBuilding, clientOnly: true },
  { href: "/candidates", label: "Candidates", icon: IconUsers, hideForClient: true },
  { href: "/pipeline", label: "Pipeline", icon: IconLayoutKanban },
  { href: "/leaderboard", label: "Leaderboard", icon: IconTrophy, hideForClient: true },
  {
    href: "/clients",
    label: "Clients",
    icon: IconBuildingStore,
    maintainerOnly: true,
    hideForClient: true,
  },
  {
    href: "/client-messaging",
    label: "Client Messaging",
    icon: IconMessage,
    hideForClient: true,
  },
  { href: "/settings", label: "Settings", icon: IconSettings },
  {
    href: "/activity",
    label: "Activity",
    icon: IconActivity,
    maintainerOnly: true,
    hideForClient: true,
  },
];

export function isNavItemActive(pathname: string, href: string, exact?: boolean): boolean {
  if (exact) return pathname === href;
  return pathname === href || pathname.startsWith(href + "/");
}
