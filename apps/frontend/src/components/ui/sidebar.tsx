"use client";
import { cn } from "@/lib/utils";
import React, { useState, createContext, useContext } from "react";
import { AnimatePresence, motion } from "motion/react";
import { IconMenu2, IconX } from "@tabler/icons-react";
import Link from "next/link";

interface Links {
  label: string;
  href: string;
  icon: React.JSX.Element | React.ReactNode;
}

interface SidebarContextProps {
  open: boolean;
  setOpen: React.Dispatch<React.SetStateAction<boolean>>;
  animate: boolean;
  pinned: boolean;
  setPinned: React.Dispatch<React.SetStateAction<boolean>>;
}

const SidebarContext = createContext<SidebarContextProps | undefined>(undefined);

export const useSidebar = () => {
  const context = useContext(SidebarContext);
  if (!context) {
    throw new Error("useSidebar must be used within a SidebarProvider");
  }
  return context;
};

export const SidebarProvider = ({
  children,
  open: openProp,
  setOpen: setOpenProp,
  animate = true,
}: {
  children: React.ReactNode;
  open?: boolean;
  setOpen?: React.Dispatch<React.SetStateAction<boolean>>;
  animate?: boolean;
}) => {
  const [openState, setOpenState] = useState(false);
  const [pinned, setPinned] = useState(false);

  const open = pinned ? true : (openProp ?? openState);
  const setOpen = setOpenProp ?? setOpenState;

  return (
    <SidebarContext.Provider value={{ open, setOpen, animate, pinned, setPinned }}>
      {children}
    </SidebarContext.Provider>
  );
};

export const Sidebar = ({
  children,
  open,
  setOpen,
  animate,
}: {
  children: React.ReactNode;
  open?: boolean;
  setOpen?: React.Dispatch<React.SetStateAction<boolean>>;
  animate?: boolean;
}) => {
  return (
    <SidebarProvider open={open} setOpen={setOpen} animate={animate}>
      {children}
    </SidebarProvider>
  );
};

export const SidebarBody = (props: React.ComponentProps<typeof motion.div>) => {
  /* eslint-disable @typescript-eslint/no-unused-vars */
  const {
    animate: _animate,
    initial: _initial,
    exit: _exit,
    transition: _transition,
    variants: _variants,
    style: _style,
    layout: _layout,
    layoutId: _layoutId,
    ...mobileProps
  } = props;
  /* eslint-enable @typescript-eslint/no-unused-vars */
  return (
    <>
      <DesktopSidebar {...props} />
      <MobileSidebar {...(mobileProps as React.ComponentProps<"div">)} />
    </>
  );
};

export const DesktopSidebar = ({
  className,
  children,
  ...props
}: React.ComponentProps<typeof motion.div>) => {
  const { open, setOpen, animate, pinned } = useSidebar();
  return (
    <motion.div
      className={cn(
        "h-full py-4 hidden md:flex md:flex-col bg-sidebar rounded-xl shadow-2xl shrink-0 overflow-hidden relative",
        className,
      )}
      animate={{
        width: animate ? (open ? "200px" : "64px") : "200px",
      }}
      transition={{
        type: "tween",
        duration: 0.2,
        ease: [0.25, 0.46, 0.45, 0.94],
      }}
      onMouseEnter={() => {
        if (!pinned) setOpen(true);
      }}
      onMouseLeave={() => {
        if (!pinned) setOpen(false);
      }}
      {...props}
    >
      {children}
    </motion.div>
  );
};

export const MobileSidebar = ({ className, children, ...props }: React.ComponentProps<"div">) => {
  const { open, setOpen } = useSidebar();
  return (
    <div
      className={cn(
        "h-12 px-4 flex flex-row md:hidden items-center justify-between bg-sidebar border-b border-border w-full",
      )}
      {...props}
    >
      <div className="flex justify-end z-20 w-full">
        <button
          type="button"
          aria-label="Toggle menu"
          className="text-white/50 cursor-pointer hover:text-white transition-colors"
          onClick={() => setOpen(!open)}
        >
          <IconMenu2 />
        </button>
      </div>
      <AnimatePresence>
        {open && (
          <motion.div
            initial={{ x: "-100%", opacity: 0 }}
            animate={{ x: 0, opacity: 1 }}
            exit={{ x: "-100%", opacity: 0 }}
            transition={{ duration: 0.25, ease: "easeInOut" }}
            className={cn(
              "fixed h-full w-full inset-0 bg-sidebar p-8 z-100 flex flex-col justify-between",
              className,
            )}
          >
            <button
              type="button"
              aria-label="Close menu"
              className="absolute right-8 top-8 z-50 text-white/50 cursor-pointer hover:text-white transition-colors"
              onClick={() => setOpen(!open)}
            >
              <IconX />
            </button>
            {children}
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
};

export const SidebarLink = ({
  link,
  className,
  active,
  ...props
}: {
  link: Links;
  className?: string;
  active?: boolean;
} & Omit<React.ComponentProps<typeof Link>, "href">) => {
  const { open, animate } = useSidebar();
  return (
    <Link
      href={link.href}
      aria-label={!open ? link.label : undefined}
      className={cn(
        "flex w-full items-center group/sidebar rounded-lg transition-all duration-150 sidebar-nav-link",
        !active && "hover:bg-white/5",
        className,
      )}
      style={{
        padding: open ? "8px 12px" : "8px 0",
        justifyContent: open ? "flex-start" : "center",
        background: active ? "rgba(255, 255, 255, 0.12)" : undefined,
        color: active ? "#ffffff" : "#94a3b8",
      }}
      {...props}
    >
      {/* Icon — always rendered, never hidden */}
      <span className="shrink-0 flex items-center justify-center w-5 h-5">{link.icon}</span>

      {/* Label — fade + slide in, no width animation to avoid layout lag */}
      <motion.span
        aria-hidden={!open ? "true" : undefined}
        animate={{
          opacity: animate ? (open ? 1 : 0) : 1,
          x: animate ? (open ? 0 : -4) : 0,
        }}
        transition={{ type: "tween", duration: 0.12, ease: "easeOut" }}
        className={cn(
          "text-sm font-medium whitespace-nowrap overflow-hidden ml-2.5",
          !open && "absolute w-0 h-0 opacity-0 overflow-hidden",
        )}
      >
        {link.label}
      </motion.span>
    </Link>
  );
};
