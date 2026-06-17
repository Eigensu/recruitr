"use client";

import { useState, useEffect } from "react";
import { usePathname, useRouter } from "next/navigation";
import Link from "next/link";
import Image from "next/image";
import { motion } from "motion/react";
import {
  IconLayoutDashboard,
  IconBriefcase,
  IconUsers,
  IconLayoutKanban,
  IconTrophy,
  IconSettings,
  IconLayoutSidebarLeftCollapse,
  IconLayoutSidebarLeftExpand,
  IconMoon,
  IconSun,
  IconActivity,
} from "@tabler/icons-react";
import { Sidebar, SidebarBody, SidebarLink, useSidebar } from "@/components/ui/sidebar";
import { useTheme } from "@/context/ThemeContext";
import { OnboardingProgressCard } from "@/components/sidebar/OnboardingProgressCard";
import MobileBottomNav from "@/components/sidebar/MobileBottomNav";

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
    label: "Pipeline",
    href: "/pipeline",
    icon: <IconLayoutKanban className="h-5 w-5 shrink-0" />,
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

/** Logo row — single component, handles both open/collapsed states */
function LogoRow() {
  const { open, animate, pinned, setPinned } = useSidebar();
  const logoAnimation = animate ? { opacity: open ? 1 : 0, x: open ? 0 : -6 } : undefined;

  return (
    <div
      className="flex items-center px-3"
      style={{
        justifyContent: open ? "space-between" : "center",
      }}
    >
      {/* Left: logo + name */}
      <div className="flex items-center">
        <Link href="/" className="shrink-0 no-underline">
          <div className="size-8 overflow-hidden rounded-lg shadow">
            <Image
              src="/logo-yellow.jpeg"
              alt="Binge"
              width={32}
              height={32}
              className="size-full object-cover"
            />
          </div>
        </Link>

        <motion.span
          animate={logoAnimation}
          transition={{ type: "tween", duration: 0.12, ease: "easeOut" }}
          className="font-heading text-base font-bold tracking-tight text-white whitespace-nowrap ml-2.5"
          style={{ display: open ? "block" : "none" }}
        >
          binge <span className="text-yellow font-normal">ai</span>
        </motion.span>
      </div>

      {/* Pin button — only visible when sidebar is open */}
      <motion.button
        type="button"
        aria-label={pinned ? "Unpin sidebar" : "Pin sidebar open"}
        onClick={() => setPinned((p) => !p)}
        animate={animate ? { opacity: open ? 1 : 0 } : undefined}
        transition={{ type: "tween", duration: 0.12, ease: "easeOut" }}
        style={{ display: open ? "flex" : "none" }}
        className="shrink-0 flex items-center justify-center rounded-md p-1 text-white/40 hover:text-white hover:bg-white/10 transition-colors cursor-pointer"
      >
        {pinned ? (
          <IconLayoutSidebarLeftExpand className="size-5" />
        ) : (
          <IconLayoutSidebarLeftCollapse className="size-5" />
        )}
      </motion.button>
    </div>
  );
}

function useThemeToggle() {
  const { theme, toggleTheme } = useTheme();
  const [mounted, setMounted] = useState(false);
  // eslint-disable-next-line react-hooks/set-state-in-effect
  useEffect(() => setMounted(true), []);
  const isLight = mounted && theme === "light";
  return { theme, toggleTheme, mounted, isLight };
}

/** Theme toggle row — compact when closed, expanded when open */
function ThemeToggleRow() {
  const { theme, toggleTheme, isLight } = useThemeToggle();
  const { open } = useSidebar();

  if (!open) {
    return (
      <div className="flex items-center justify-center px-3 py-1.5 w-full">
        <motion.button
          type="button"
          onClick={toggleTheme}
          whileHover={{ scale: 1.1 }}
          whileTap={{ scale: 0.95 }}
          className="size-8 flex shrink-0 items-center justify-center rounded-full transition-colors cursor-pointer bg-white/10 hover:bg-white/20 text-white"
          aria-label={isLight ? "Switch to dark mode" : "Switch to light mode"}
          title={isLight ? "Dark Mode" : "Light Mode"}
        >
          {isLight ? <IconMoon size={18} stroke={2} /> : <IconSun size={18} stroke={2} />}
        </motion.button>
      </div>
    );
  }

  return (
    <div className="flex items-center justify-between px-3 py-1.5 w-full">
      <span className="text-sm font-medium text-white pl-1">Theme</span>
      <button
        type="button"
        className="relative flex items-center w-17 h-9 p-1 shrink-0 rounded-full cursor-pointer bg-white"
        onClick={toggleTheme}
        aria-label={isLight ? "Switch to dark mode" : "Switch to light mode"}
        title={isLight ? "Dark Mode" : "Light Mode"}
      >
        <motion.div
          className="absolute top-1 left-1 w-7 h-7 rounded-full bg-gray-800"
          layout
          transition={{ type: "spring", stiffness: 700, damping: 30 }}
          animate={{ x: theme === "dark" ? 32 : 0 }}
        />
        <div className="relative flex flex-1 justify-around items-center">
          <IconMoon
            size={16}
            className={`z-10 transition-colors ${isLight ? "text-white" : "text-gray-400"}`}
          />
          <IconSun
            size={16}
            className={`z-10 transition-colors ${isLight ? "text-gray-400" : "text-white"}`}
          />
        </div>
      </button>
    </div>
  );
}

/** Bottom user row — avatar + name, no hover popover */
function UserRow({ user }: { readonly user: { full_name: string; email: string } | null }) {
  const { open, animate } = useSidebar();
  const labelAnimation = animate ? { opacity: open ? 1 : 0, x: open ? 0 : -4 } : undefined;

  return (
    <div className="relative px-3">
      <div
        className="flex items-center gap-3 py-1.5 w-full"
        style={{ justifyContent: open ? "flex-start" : "center" }}
      >
        <div className="size-8 shrink-0 rounded-full bg-yellow flex items-center justify-center text-xs font-bold text-navy uppercase select-none shadow-sm">
          {user?.full_name?.[0] ?? "?"}
        </div>
        <motion.span
          animate={labelAnimation}
          transition={{ type: "tween", duration: 0.12, ease: "easeOut" }}
          className="text-sm font-medium text-white truncate whitespace-nowrap"
          style={{ display: open ? "block" : "none" }}
        >
          {user?.full_name ?? "Loading…"}
        </motion.span>
      </div>
    </div>
  );
}

/** The full sidebar */
export default function DashboardSidebar() {
  const pathname = usePathname();
  const router = useRouter();
  const [open, setOpen] = useState(false);
  const [user, setUser] = useState<{ full_name: string; email: string; role?: string } | null>(
    null,
  );

  useEffect(() => {
    fetch(`${API_URL}/api/v1/auth/me`, { credentials: "include" })
      .then((r) => {
        if (!r.ok) {
          router.replace("/sign-in");
          return null;
        }
        return r.json();
      })
      .then((data) => {
        if (data) setUser({ full_name: data.full_name, email: data.email, role: data.role });
      })
      .catch(() => {
        router.replace("/sign-in");
      });
  }, [router]);

  const isMaintainer = user?.role === "maintainer" || user?.role === "admin";

  const visibleLinks = [
    ...NAV_LINKS,
    ...(isMaintainer
      ? [
          {
            label: "Activity",
            href: "/activity",
            icon: <IconActivity className="h-5 w-5 shrink-0" />,
          },
        ]
      : []),
  ];

  return (
    <>
      <Sidebar open={open} setOpen={setOpen}>
        <SidebarBody className="justify-between gap-6">
          {/* Top: logo + nav */}
          <div className="flex flex-1 flex-col overflow-y-auto overflow-x-hidden">
            <div className="py-1">
              <LogoRow />
            </div>
            <nav className="mt-6 flex flex-col items-stretch gap-0.5 px-3 w-full">
              {visibleLinks.map((link) => {
                const isActive =
                  link.href === "/" ? pathname === "/" : pathname.startsWith(link.href);
                return <SidebarLink key={link.href} link={link} active={isActive} />;
              })}
            </nav>
          </div>

          {/* Bottom: onboarding + theme toggle + user */}
          <div className="flex flex-col">
            <OnboardingProgressCard progress={76} />

            <div className="mt-4 flex flex-col pt-2">
              <ThemeToggleRow />

              <div className="h-px bg-white/10 my-2 mx-4" />

              <UserRow user={user} />
            </div>
          </div>
        </SidebarBody>
      </Sidebar>
      <MobileBottomNav />
    </>
  );
}
