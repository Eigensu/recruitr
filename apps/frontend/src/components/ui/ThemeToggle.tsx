"use client";

import { useTheme } from "@/context/ThemeContext";
import { IconSun, IconMoon } from "@tabler/icons-react";

/** `lg` meets the 44px minimum touch target — use it on surfaces people reach
 *  on a phone. `sm` is the compact dashboard chrome, where a pointer is the
 *  norm and the button sits among other 32px controls. */
const SIZES = {
  sm: { button: "size-8", icon: 16 },
  lg: { button: "size-11", icon: 20 },
} as const;

export function ThemeToggle({ size = "sm" }: Readonly<{ size?: keyof typeof SIZES }>) {
  const { toggleTheme, isDark } = useTheme();
  const { button, icon } = SIZES[size];
  const label = isDark ? "Switch to light mode" : "Switch to dark mode";

  return (
    <button
      type="button"
      onClick={toggleTheme}
      aria-label={label}
      title={label}
      className={`${button} shrink-0 rounded-lg flex items-center justify-center hover:opacity-80 transition-opacity cursor-pointer`}
      style={{
        background: "var(--color-toggle-bg)",
        color: "var(--color-toggle-icon)",
      }}
    >
      {isDark ? <IconSun size={icon} /> : <IconMoon size={icon} />}
    </button>
  );
}
