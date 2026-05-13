"use client";

import React, { useState, useEffect } from "react";
import { usePathname } from "next/navigation";
import Link from "next/link";
import Image from "next/image";
import { motion } from "motion/react";
import {
  IconLayoutDashboard,
  IconBriefcase,
  IconUsers,
  IconTrophy,
  IconSettings,
} from "@tabler/icons-react";
import { Sidebar, SidebarBody, SidebarLink, useSidebar } from "@/components/ui/sidebar";
import SignOutButton from "@/components/sidebar/SignOutButton";

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

const NAV_LINKS = [
  {
    label: "Dashboard",
    href: "/",
    icon: <IconLayoutDashboard className="h-5 w-5 shrink-0" />,
  },
  {
    label: "Positions",
    href: "/positions",
    icon: <IconBriefcase className="h-5 w-5 shrink-0" />,
  },
  {
    label: "Candidates",
    href: "/candidates",
    icon: <IconUsers className="h-5 w-5 shrink-0" />,
  },
  {
    label: "Leaderboard",
    href: "/leaderboard",
    icon: <IconTrophy className="h-5 w-5 shrink-0" />,
  },
  {
    label: "Settings",
    href: "/settings",
    icon: <IconSettings className="h-5 w-5 shrink-0" />,
  },
];

/** Animated logo — full version when sidebar is open */
const BingeLogo = () => (
  <Link href="/" className="relative z-20 flex items-center gap-3 py-1 no-underline">
    <div className="size-8 shrink-0 overflow-hidden rounded-lg shadow">
      <Image
        src="/logo-yellow.jpeg"
        alt="Binge"
        width={32}
        height={32}
        className="size-full object-cover"
      />
    </div>
    <motion.span
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      className="font-heading text-base font-bold tracking-tight text-white whitespace-pre"
    >
      binge <span className="text-yellow-300">ai</span>
    </motion.span>
  </Link>
);

/** Icon-only logo when sidebar is collapsed */
const BingeLogoIcon = () => (
  <Link href="/" className="relative z-20 flex items-center py-1 no-underline">
    <div className="size-8 shrink-0 overflow-hidden rounded-lg shadow">
      <Image
        src="/logo-yellow.jpeg"
        alt="Binge"
        width={32}
        height={32}
        className="size-full object-cover"
      />
    </div>
  </Link>
);

/** Bottom user row — shows avatar + name/email when expanded */
function UserRow({ user }: { user: { full_name: string; email: string } | null }) {
  const { open, animate } = useSidebar();

  return (
    <div className="flex items-center gap-3 px-2 py-2">
      {/* Avatar */}
      <div className="size-8 shrink-0 rounded-full bg-gray-700 flex items-center justify-center text-xs font-bold text-white uppercase select-none">
        {user?.full_name?.[0] ?? "?"}
      </div>

      {/* Name + sign out */}
      <motion.div
        animate={{
          display: animate ? (open ? "flex" : "none") : "flex",
          opacity: animate ? (open ? 1 : 0) : 1,
        }}
        className="flex flex-col min-w-0 flex-1"
      >
        <span className="text-sm font-medium text-white truncate leading-tight">
          {user?.full_name ?? "Loading…"}
        </span>
        <span className="text-xs text-white truncate leading-tight">{user?.email ?? ""}</span>
      </motion.div>

      {/* Sign out — only shows when open */}
      <motion.div
        animate={{
          display: animate ? (open ? "flex" : "none") : "flex",
          opacity: animate ? (open ? 1 : 0) : 1,
        }}
        className="shrink-0"
      >
        <SignOutButton />
      </motion.div>
    </div>
  );
}

/** The full sidebar — drop this into your layout */
export default function DashboardSidebar() {
  const pathname = usePathname();
  const [open, setOpen] = useState(false);
  const [user, setUser] = useState<{ full_name: string; email: string } | null>(null);

  useEffect(() => {
    fetch(`${API_URL}/api/v1/auth/me`, { credentials: "include" })
      .then((r) => (r.ok ? r.json() : null))
      .then((data) => {
        if (data) setUser({ full_name: data.full_name, email: data.email });
      })
      .catch(() => null);
  }, []);

  return (
    <Sidebar open={open} setOpen={setOpen}>
      <SidebarBody className="justify-between gap-6">
        {/* Top: logo + nav */}
        <div className="flex flex-1 flex-col overflow-x-hidden overflow-y-auto">
          {open ? <BingeLogo /> : <BingeLogoIcon />}

          <nav className="mt-8 flex flex-col gap-1">
            {NAV_LINKS.map((link) => {
              const isActive =
                link.href === "/" ? pathname === "/" : pathname.startsWith(link.href);
              return <SidebarLink key={link.href} link={link} active={isActive} />;
            })}
          </nav>
        </div>

        {/* Bottom: user + sign-out */}
        <div className="border-t border-gray-800 pt-4">
          <UserRow user={user} />
        </div>
      </SidebarBody>
    </Sidebar>
  );
}
