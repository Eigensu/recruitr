# Light Mode Implementation Spec

> Binge AI · Recruitment Dashboard · Full ThemeContext system

---

## Design Decision: "Fixed Sidebar" Model

The **sidebar stays navy (#002348) in both modes.** It's a branded element, not a chrome element.
Only the shell and main content panel flip. This is intentional — it keeps the brand strong in
light mode and avoids the washed-out "everything goes grey" problem.

```
DARK MODE:  shell=#002348  sidebar=#002348  main=dark navy
LIGHT MODE: shell=#F9F7F8  sidebar=#002348  main=#FFFFFF
```

---

## 1. ThemeContext — `context/ThemeContext.tsx`

Create this file from scratch:

```tsx
"use client";

import { createContext, useContext, useEffect, useState } from "react";

type Theme = "dark" | "light";

interface ThemeContextValue {
  theme: Theme;
  toggleTheme: () => void;
  isDark: boolean;
}

const ThemeContext = createContext<ThemeContextValue | null>(null);

export function ThemeProvider({ children }: { children: React.ReactNode }) {
  const [theme, setTheme] = useState<Theme>("dark"); // dark is default

  // On mount: read from localStorage or system preference
  useEffect(() => {
    const stored = localStorage.getItem("binge-theme") as Theme | null;
    if (stored) {
      setTheme(stored);
    } else {
      const prefersDark = window.matchMedia(
        "(prefers-color-scheme: dark)",
      ).matches;
      setTheme(prefersDark ? "dark" : "light");
    }
  }, []);

  // Apply [data-theme] to <html> whenever theme changes
  useEffect(() => {
    document.documentElement.setAttribute("data-theme", theme);
    localStorage.setItem("binge-theme", theme);
  }, [theme]);

  const toggleTheme = () => setTheme((t) => (t === "dark" ? "light" : "dark"));

  return (
    <ThemeContext.Provider
      value={{ theme, toggleTheme, isDark: theme === "dark" }}
    >
      {children}
    </ThemeContext.Provider>
  );
}

export function useTheme() {
  const ctx = useContext(ThemeContext);
  if (!ctx) throw new Error("useTheme must be used inside ThemeProvider");
  return ctx;
}
```

---

## 2. Wrap the App — `layout.tsx`

```tsx
import { ThemeProvider } from "@/context/ThemeContext";

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en" suppressHydrationWarning>
      {/* suppressHydrationWarning prevents SSR mismatch on data-theme */}
      <body>
        <ThemeProvider>
          <div className="shell p-3 gap-3 h-dvh flex overflow-hidden">
            <DashboardSidebar />
            <main className="main-panel rounded-xl flex-1 overflow-hidden flex flex-col">
              <div className="flex-1 overflow-y-auto">{children}</div>
            </main>
          </div>
        </ThemeProvider>
      </body>
    </html>
  );
}
```

---

## 3. CSS Variables — `globals.css`

All theming lives here. Components use variable names only — never hardcoded hex.

```css
/* ============================================================
   DARK MODE (default)
   ============================================================ */
:root,
[data-theme="dark"] {
  /* Layout */
  --color-shell: #040c15;
  --color-sidebar: #002348;
  --color-canvas: #0a1628; /* main panel background */
  --color-surface: #0f1f35; /* widget/card default background */
  --color-surface-raised: #162741; /* slightly elevated card */

  /* Typography */
  --color-text-primary: #ffffff;
  --color-text-secondary: #94a3b8;
  --color-text-muted: #64748b;

  /* Borders */
  --color-border: rgba(255, 255, 255, 0.08);
  --color-border-strong: rgba(255, 255, 255, 0.15);

  /* Brand accent (same in both modes — only on navy bg) */
  --color-accent: #f3ff54;
  --color-accent-text: #002348; /* text ON accent bg */

  /* Semantic card backgrounds */
  --color-card-featured: #f3ff54; /* Open Positions, Sent to Client */
  --color-card-featured-text: #002348;

  --color-card-positive: #052e16; /* Seats Filled, Offers Accepted, Joined */
  --color-card-positive-text: #ffffff;
  --color-card-positive-badge: #065f46;

  --color-card-negative: #2d0a0a; /* Candidate Dropped */
  --color-card-negative-text: #ffffff;
  --color-card-negative-badge: #7f1d1d;

  --color-card-info: #002348; /* Total Seats Open, Total in Pipeline */
  --color-card-info-text: #ffffff;

  /* Sidebar active state */
  --color-nav-active-bg: rgba(255, 255, 255, 0.1);
  --color-nav-active-text: #ffffff;
  --color-nav-active-bar: #f3ff54;
  --color-nav-text: #94a3b8;
  --color-nav-hover: rgba(255, 255, 255, 0.06);

  /* Toggle button */
  --color-toggle-bg: rgba(255, 255, 255, 0.1);
  --color-toggle-icon: #ffffff;
}

/* ============================================================
   LIGHT MODE
   ============================================================ */
[data-theme="light"] {
  /* Layout */
  --color-shell: #f9f7f8; /* warm off-white frame */
  --color-sidebar: #002348; /* UNCHANGED — sidebar is always brand navy */
  --color-canvas: #ffffff; /* main panel */
  --color-surface: #f9f7f8; /* widget/card default */
  --color-surface-raised: #ffffff;

  /* Typography */
  --color-text-primary: #262626;
  --color-text-secondary: #4b5563;
  --color-text-muted: #9ca3af;

  /* Borders */
  --color-border: rgba(0, 0, 0, 0.08);
  --color-border-strong: rgba(0, 0, 0, 0.15);

  /* Brand accent — unchanged */
  --color-accent: #f3ff54;
  --color-accent-text: #002348;

  /* Semantic cards — light versions */
  --color-card-featured: #f3ff54; /* stays yellow — perfect contrast ✅ */
  --color-card-featured-text: #002348;

  --color-card-positive: #ecfdf5; /* light mint */
  --color-card-positive-text: #065f46;
  --color-card-positive-badge: #d1fae5;

  --color-card-negative: #fff1f2; /* light rose */
  --color-card-negative-text: #9f1239;
  --color-card-negative-badge: #ffe4e6;

  --color-card-info: #eff6ff; /* light blue */
  --color-card-info-text: #002348;

  /* Sidebar nav — UNCHANGED (sidebar is always dark) */
  --color-nav-active-bg: rgba(255, 255, 255, 0.1);
  --color-nav-active-text: #ffffff;
  --color-nav-active-bar: #f3ff54;
  --color-nav-text: #94a3b8;
  --color-nav-hover: rgba(255, 255, 255, 0.06);

  /* Toggle button */
  --color-toggle-bg: #002348;
  --color-toggle-icon: #f3ff54;
}

/* ============================================================
   TRANSITIONS — smooth theme switching
   ============================================================ */
*,
*::before,
*::after {
  transition:
    background-color 200ms ease,
    border-color 200ms ease,
    color 200ms ease,
    box-shadow 200ms ease;
}

/* Exception: don't animate transforms/layout properties */
[class*="translate"],
[class*="scale"],
[class*="rotate"] {
  transition: transform 200ms ease;
}
```

---

## 4. Tailwind Utility Classes (if using Tailwind)

Add these to your `tailwind.config.ts` so you can use them as class names:

```ts
theme: {
  extend: {
    colors: {
      shell:    "var(--color-shell)",
      sidebar:  "var(--color-sidebar)",
      canvas:   "var(--color-canvas)",
      surface:  "var(--color-surface)",
      accent:   "var(--color-accent)",
    },
    backgroundColor: {
      "card-featured": "var(--color-card-featured)",
      "card-positive": "var(--color-card-positive)",
      "card-negative": "var(--color-card-negative)",
      "card-info":     "var(--color-card-info)",
    },
    textColor: {
      primary:   "var(--color-text-primary)",
      secondary: "var(--color-text-secondary)",
      muted:     "var(--color-text-muted)",
    }
  }
}
```

---

## 5. Theme Toggle Component — `components/ThemeToggle.tsx`

```tsx
"use client";

import { useTheme } from "@/context/ThemeContext";
import { Sun, Moon } from "lucide-react";

export function ThemeToggle() {
  const { toggleTheme, isDark } = useTheme();

  return (
    <button
      onClick={toggleTheme}
      aria-label={isDark ? "Switch to light mode" : "Switch to dark mode"}
      style={{
        background: "var(--color-toggle-bg)",
        color: "var(--color-toggle-icon)",
      }}
      className="w-8 h-8 rounded-lg flex items-center justify-center
                 hover:opacity-80 transition-opacity"
    >
      {isDark ? <Sun size={16} /> : <Moon size={16} />}
    </button>
  );
}
```

**Place the toggle** in the top bar of the main content panel (next to the page title area),
NOT in the sidebar. The sidebar is always dark — putting a light/dark toggle there is confusing.

---

## 6. Card Component — How to Use Semantic Tokens

Your stat cards should use the semantic variables, not hardcoded colours.
Here's the pattern for each card type:

```tsx
// Featured card (yellow) — Open Positions, Sent to Client
<div style={{
  background: "var(--color-card-featured)",
  color: "var(--color-card-featured-text)",
}}>

// Positive card — Seats Filled, Offers Accepted, Joined
<div style={{
  background: "var(--color-card-positive)",
  color: "var(--color-card-positive-text)",
}}>

// Negative card — Candidate Dropped
<div style={{
  background: "var(--color-card-negative)",
  color: "var(--color-card-negative-text)",
}}>

// Info card — Total Seats Open, Total in Pipeline
<div style={{
  background: "var(--color-card-info)",
  color: "var(--color-card-info-text)",
}}>

// Default widget — Pipeline Pie Chart, Analytics, etc.
<div style={{
  background: "var(--color-surface)",
  color: "var(--color-text-primary)",
  border: "1px solid var(--color-border)",
}}>
```

---

## 7. Page Header — Light Mode Typography

The "RECRUITMENT DASHBOARD" heading is currently `#FFFFFF`. In light mode it must flip:

```tsx
// Use the CSS variable — it auto-flips
<h1 style={{ color: "var(--color-text-primary)" }}>
  RECRUITMENT DASHBOARD
</h1>

// The eyebrow label "RECRUITMENT COMMAND CENTER"
<p style={{ color: "var(--color-accent)" }}>
  {/* accent yellow works — it only appears on navy-bg shell/sidebar,
      OR in this case as a label, which is fine as a highlight colour */}
  RECRUITMENT COMMAND CENTER
</p>
```

> ⚠️ Exception: "RECRUITMENT COMMAND CENTER" in yellow on white has poor contrast.
> In light mode, change it to `var(--color-text-secondary)` or `var(--color-sidebar)` (navy).
> Only use yellow on dark backgrounds.

**Updated approach:**

```tsx
<p style={{ color: isDark ? "var(--color-accent)" : "var(--color-sidebar)" }}>
  RECRUITMENT COMMAND CENTER
</p>
```

---

## 8. Files Touched Summary

| File                         | Change                                                                  |
| ---------------------------- | ----------------------------------------------------------------------- |
| `context/ThemeContext.tsx`   | **Create new** — ThemeProvider + useTheme hook                          |
| `globals.css`                | Add all `[data-theme="light"]` variables + transitions                  |
| `layout.tsx`                 | Wrap with `<ThemeProvider>`, add `suppressHydrationWarning` to `<html>` |
| `components/ThemeToggle.tsx` | **Create new** — sun/moon toggle button                                 |
| `components/StatCard.tsx`    | Replace hardcoded colors with semantic CSS vars                         |
| `components/WidgetCard.tsx`  | Replace hardcoded colors with `--color-surface` + `--color-border`      |
| Page headers                 | Swap hardcoded white to `var(--color-text-primary)`                     |
| Eyebrow labels               | Use `isDark ? accent : sidebar` pattern for yellow labels               |

---

## 9. What Does NOT Change

| Element                                       | Reason                                     |
| --------------------------------------------- | ------------------------------------------ |
| Sidebar background, nav colors, active states | Sidebar is always `#002348` — no change    |
| Yellow cards (featured)                       | `#F3FF54` on `#002348` works in both modes |
| Sidebar logo, user avatar row                 | Lives on navy — unchanged                  |
| Card layout and grid structure                | Visual structure only; colors change       |
| All animation/motion logic                    | Untouched                                  |

---

## 10. SSR / Hydration Note for Claude Code

Add `suppressHydrationWarning` to `<html>` to prevent React from complaining
that `data-theme` differs between server and client render. This is safe — it
only suppresses the warning on the html element, not on content.

```tsx
<html lang="en" suppressHydrationWarning>
```

Also add this script to `<head>` to prevent flash of wrong theme (FOIT):

```tsx
<script
  dangerouslySetInnerHTML={{
    __html: `
      (function() {
        var t = localStorage.getItem('binge-theme');
        if (!t) t = window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light';
        document.documentElement.setAttribute('data-theme', t);
      })();
    `,
  }}
/>
```

Place this as the **first child of `<head>`** before any stylesheets.
