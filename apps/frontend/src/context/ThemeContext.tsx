"use client";

import { createContext, useContext, useEffect, useMemo, useState } from "react";

type Theme = "dark" | "light";

interface ThemeContextValue {
  theme: Theme;
  toggleTheme: () => void;
  isDark: boolean;
}

const ThemeContext = createContext<ThemeContextValue | null>(null);

function getInitialTheme(): Theme {
  if (typeof globalThis === "undefined" || !("localStorage" in globalThis)) {
    return "dark";
  }

  const stored = globalThis.localStorage.getItem("binge-theme") as Theme | null;
  if (stored === "dark" || stored === "light") {
    return stored;
  }

  return globalThis.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
}

export function ThemeProvider({ children }: Readonly<{ children: React.ReactNode }>) {
  const [theme, setTheme] = useState<Theme>(getInitialTheme);

  // Apply [data-theme] to <html> whenever theme changes
  useEffect(() => {
    document.documentElement.dataset.theme = theme;
    globalThis.localStorage.setItem("binge-theme", theme);
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
