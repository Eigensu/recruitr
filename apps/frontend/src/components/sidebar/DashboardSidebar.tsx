"use client";

import { useState, useEffect } from "react";
import { usePathname } from "next/navigation";
import Link from "next/link";
import Image from "next/image";
import { motion, AnimatePresence } from "motion/react";
import {
  IconLayoutDashboard,
  IconBriefcase,
  IconUsers,
  IconTrophy,
  IconSettings,
  IconLayoutSidebarLeftCollapse,
  IconLayoutSidebarLeftExpand,
  IconMoon,
  IconSun,
} from "@tabler/icons-react";
import { Sidebar, SidebarBody, SidebarLink, useSidebar } from "@/components/ui/sidebar";
import { useTheme } from "@/context/ThemeContext";
import SignOutButton from "@/components/sidebar/SignOutButton";
import { OnboardingProgressCard } from "@/components/sidebar/OnboardingProgressCard";

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

/** Theme toggle row — compact when closed, expanded when open */
function ThemeToggleRow() {
  const { theme, toggleTheme } = useTheme();
  const { open } = useSidebar();

  if (!open) {
    // Closed state: single button with current theme icon
    return (
      <div className="flex items-center justify-center px-3 py-2">
        <motion.button
          type="button"
          onClick={toggleTheme}
          whileHover={{ scale: 1.1 }}
          whileTap={{ scale: 0.95 }}
          className="flex items-center justify-center p-1.5 rounded-full transition-colors cursor-pointer bg-white"
          style={{
            color: "var(--color-text-primary)",
          }}
          aria-label={theme === "dark" ? "Switch to light mode" : "Switch to dark mode"}
          title={theme === "dark" ? "Light Mode" : "Dark Mode"}
        >
          {theme === "dark" ? <IconSun size={16} /> : <IconMoon size={16} />}
        </motion.button>
      </div>
    );
  }

  // Open state: pill-shaped toggle
  return (
    <div className="flex items-center justify-start px-4 py-2">
      <button
        type="button"
        className="relative flex items-center w-17 h-9 p-1 rounded-full cursor-pointer bg-white"
        onClick={toggleTheme}
        aria-label={theme === "dark" ? "Switch to light mode" : "Switch to dark mode"}
        title={theme === "dark" ? "Light Mode" : "Dark Mode"}
      >
        {/* Sliding indicator */}
        <motion.div
          className="absolute top-1 left-1 w-7 h-7 rounded-full bg-gray-800"
          layout
          transition={{ type: "spring", stiffness: 700, damping: 30 }}
          animate={{ x: theme === "dark" ? 32 : 0 }}
        />
        {/* Icons */}
        <div className="relative flex flex-1 justify-around items-center">
          <IconMoon
            size={16}
            className={`z-10 transition-colors ${theme === "light" ? "text-white" : "text-gray-400"}`}
          />
          <IconSun
            size={16}
            className={`z-10 transition-colors ${theme === "dark" ? "text-white" : "text-gray-400"}`}
          />
        </div>
      </button>
    </div>
  );
}

function UserPopover({ user }: { readonly user: { full_name: string; email: string } | null }) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 6 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0, y: 6 }}
      transition={{ type: "tween", duration: 0.15, ease: "easeOut" }}
      className="absolute bottom-full left-0 right-0 mb-2 rounded-xl bg-surface-2 border border-white/10 shadow-xl p-3 z-50"
    >
      <div className="flex items-center gap-3">
        <div className="size-9 shrink-0 rounded-full bg-yellow flex items-center justify-center text-sm font-bold text-navy uppercase select-none shadow-sm">
          {user?.full_name?.[0] ?? "?"}
        </div>
        <div className="flex flex-col min-w-0 flex-1">
          <span className="text-sm font-semibold text-white truncate leading-tight">
            {user?.full_name ?? "Loading…"}
          </span>
          <span className="text-xs text-white/45 truncate leading-tight mt-0.5">
            {user?.email ?? ""}
          </span>
        </div>
        <div className="shrink-0">
          <SignOutButton />
        </div>
      </div>
    </motion.div>
  );
}

function UserTrigger({
  user,
  open,
  animate,
  setHovered,
}: Readonly<{
  user: { full_name: string; email: string } | null;
  open: boolean;
  animate: boolean;
  setHovered: React.Dispatch<React.SetStateAction<boolean>>;
}>) {
  const labelAnimation = animate ? { opacity: open ? 1 : 0, x: open ? 0 : -4 } : undefined;

  return (
    <button
      type="button"
      className="flex items-center gap-2.5 pt-3 mt-1"
      style={{ justifyContent: open ? "flex-start" : "center" }}
      onMouseEnter={() => setHovered(true)}
      onMouseLeave={() => setHovered(false)}
      onFocus={() => setHovered(true)}
      onBlur={() => setHovered(false)}
      aria-label={user ? `${user.full_name} account menu` : "Account menu"}
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
    </button>
  );
}

/** Bottom user row — avatar + name only, hover reveals popover with email + sign out */
function UserRow({ user }: { readonly user: { full_name: string; email: string } | null }) {
  const { open, animate } = useSidebar();
  const [hovered, setHovered] = useState(false);

  return (
    <div className="relative px-3">
      <AnimatePresence>{hovered && <UserPopover user={user} />}</AnimatePresence>
      <UserTrigger user={user} open={open} animate={animate} setHovered={setHovered} />
    </div>
  );
}

/** The full sidebar */
export default function DashboardSidebar() {
  const pathname = usePathname();
  const [open, setOpen] = useState(false);
  const [user, setUser] = useState<{ full_name: string; email: string } | null>(null);

  useEffect(() => {
    fetch(`${API_URL}/api/v1/auth/me`, { credentials: "include" })
      .then((r) => {
        if (!r.ok) {
          console.error(`Auth check failed: ${r.status}`);
          return null;
        }
        return r.json();
      })
      .then((data) => {
        if (data) setUser({ full_name: data.full_name, email: data.email });
      })
      .catch((err) => {
        console.error("Error fetching user session:", err);
      });
  }, []);

  return (
    <Sidebar open={open} setOpen={setOpen}>
      <SidebarBody className="justify-between gap-6">
        {/* Top: logo + nav */}
        <div className="flex flex-1 flex-col overflow-y-auto overflow-x-hidden">
          <div className="py-1">
            <LogoRow />
          </div>
          <nav className="mt-6 flex flex-col items-stretch gap-0.5 px-3 w-full">
            {NAV_LINKS.map((link) => {
              const isActive =
                link.href === "/" ? pathname === "/" : pathname.startsWith(link.href);
              return <SidebarLink key={link.href} link={link} active={isActive} />;
            })}
          </nav>
        </div>

        {/* Bottom: onboarding + theme toggle + user */}
        <div className="flex flex-col gap-2">
          <OnboardingProgressCard progress={76} />
          <div className="flex flex-col gap-3">
            <ThemeToggleRow />
            <UserRow user={user} />
          </div>
        </div>
      </SidebarBody>
    </Sidebar>
  );
}
