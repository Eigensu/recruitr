"use client";

import { createContext, useContext, useEffect, useMemo, useState } from "react";

type Theme = "dark" | "light";

interface ThemeContextValue {
  theme: Theme;
  toggleTheme: () => void;
  isDark: boolean;
}

const ThemeContext = createContext<ThemeContextValue | null>(null);

function resolveTheme(): Theme {
  try {
    if (typeof document !== "undefined") {
      const domTheme = document.documentElement.dataset.theme as Theme | undefined;
      if (domTheme === "dark" || domTheme === "light") {
        return domTheme;
      }
    }

    if (typeof globalThis !== "undefined" && "localStorage" in globalThis) {
      const stored = globalThis.localStorage.getItem("binge-theme") as Theme | null;
      if (stored === "dark" || stored === "light") {
        return stored;
      }
    }

    if (typeof window !== "undefined" && typeof window.matchMedia === "function") {
      return window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
    }

    return "dark";
  } catch {
    return "dark";
  }
}

export function ThemeProvider({ children }: Readonly<{ children: React.ReactNode }>) {
  const [theme, setTheme] = useState<Theme>(() => resolveTheme());

  // Apply [data-theme] to <html> whenever theme changes
  useEffect(() => {
    document.documentElement.dataset.theme = theme;
    try {
      if (typeof globalThis !== "undefined" && "localStorage" in globalThis) {
        globalThis.localStorage.setItem("binge-theme", theme);
      }
    } catch {
      return;
    }
  }, [theme]);

  const toggleTheme = () => setTheme((t) => (t === "dark" ? "light" : "dark"));
  const contextValue = useMemo(() => ({ theme, toggleTheme, isDark: theme === "dark" }), [theme]);

  return <ThemeContext.Provider value={contextValue}>{children}</ThemeContext.Provider>;
}

export function useTheme() {
  const ctx = useContext(ThemeContext);
  if (!ctx) throw new Error("useTheme must be used inside ThemeProvider");
  return ctx;
}
