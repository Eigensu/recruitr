"use client";

import { useTheme } from "@/context/ThemeContext";
import { IconMoon, IconSun } from "@tabler/icons-react";
import { motion } from "motion/react";

export function ThemePanel() {
  const { theme, toggleTheme } = useTheme();

  return (
    <motion.div
      initial={{ x: -100, opacity: 0 }}
      animate={{ x: 0, opacity: 1 }}
      transition={{ duration: 0.3, ease: "easeOut" }}
      className="fixed left-3 top-1/2 -translate-y-1/2 z-50 lg:flex hidden items-center justify-center"
    >
      <div
        className="rounded-full p-2 flex flex-col items-center gap-2 backdrop-blur-sm"
        style={{
          background: "var(--color-surface-val)",
          boxShadow: "0 8px 32px rgba(0, 0, 0, 0.1)",
        }}
      >
        {/* Dark Mode Button */}
        <motion.button
          onClick={toggleTheme}
          whileHover={{ scale: 1.1 }}
          whileTap={{ scale: 0.95 }}
          className={`w-12 h-12 rounded-full flex items-center justify-center transition-all duration-200 cursor-pointer ${
            theme === "dark" ? "bg-text-primary text-surface-val" : "hover:bg-surface-2-val"
          }`}
          style={
            theme === "dark"
              ? {
                  background: "var(--color-text-primary)",
                  color: "var(--color-surface-val)",
                }
              : {
                  background: "var(--color-surface-2-val)",
                  color: "var(--color-text-primary)",
                }
          }
          aria-label="Switch to dark mode"
          title="Dark Mode"
        >
          <IconMoon size={20} />
        </motion.button>

        {/* Light Mode Button */}
        <motion.button
          onClick={toggleTheme}
          whileHover={{ scale: 1.1 }}
          whileTap={{ scale: 0.95 }}
          className={`w-12 h-12 rounded-full flex items-center justify-center transition-all duration-200 cursor-pointer ${
            theme === "light" ? "bg-text-primary text-surface-val" : "hover:bg-surface-2-val"
          }`}
          style={
            theme === "light"
              ? {
                  background: "var(--color-text-primary)",
                  color: "var(--color-surface-val)",
                }
              : {
                  background: "var(--color-surface-2-val)",
                  color: "var(--color-text-primary)",
                }
          }
          aria-label="Switch to light mode"
          title="Light Mode"
        >
          <IconSun size={20} />
        </motion.button>
      </div>
    </motion.div>
  );
}
