"use client";

import { useTheme } from "@/context/ThemeContext";
import { IconSun, IconMoon } from "@tabler/icons-react";

export function ThemeToggle() {
  const { toggleTheme, isDark } = useTheme();

  return (
    <button
      type="button"
      onClick={toggleTheme}
      aria-label={isDark ? "Switch to light mode" : "Switch to dark mode"}
      className="size-8 rounded-lg flex items-center justify-center hover:opacity-80 transition-opacity cursor-pointer"
      style={{
        background: "var(--color-toggle-bg)",
        color: "var(--color-toggle-icon)",
      }}
    >
      {isDark ? <IconSun size={16} /> : <IconMoon size={16} />}
    </button>
  );
}
