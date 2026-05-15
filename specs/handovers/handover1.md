# Project Handover: Binge Consulting Recruitment Platform

## Project Overview

A recruitment platform with a **Next.js 16 (App Router)** frontend and a **FastAPI** backend.
Monorepo managed with **pnpm workspaces** and **Turborepo**.

---

## Stack

| Layer           | Tech                                              |
| --------------- | ------------------------------------------------- |
| Frontend        | Next.js 16.2.4, React 19, TypeScript, Tailwind v4 |
| Animations      | `motion/react` (Framer Motion v12)                |
| Icons           | `@tabler/icons-react`                             |
| Drag & Drop     | `@dnd-kit`                                        |
| State           | Zustand                                           |
| Backend         | FastAPI, Python 3.12, MongoDB (Beanie ODM)        |
| Package manager | pnpm 10                                           |
| Build           | Turborepo                                         |

---

## Repository Structure

```
apps/
  frontend/          Next.js app
    src/
      app/           App Router pages
        (auth)/      Login / OAuth callback
        (dashboard)/ All dashboard pages — layout.tsx wraps with sidebar
      components/
        ui/          sidebar.tsx, ThemeToggle.tsx
        sidebar/     DashboardSidebar.tsx, SignOutButton.tsx
        dashboard/   KPI cards, charts, tables, skeletons
        leaderboard/ Full leaderboard feature components
        kanban/      Drag-and-drop candidate pipeline board
        common/      dashboard-constants.ts — shared class strings & TONE_STYLES
      context/       ThemeContext.tsx
      lib/           api helpers, dashboard-data fetchers, leaderboard-data
      stores/        usePipelineStore (Zustand)
      types/         dashboard.ts, index.ts
  backend/           FastAPI app
    app/
      modules/
        auth/        Google OAuth, JWT, session
        positions/   Hiring mandates
        candidates/  Candidate pipeline
        pipeline/    Kanban match status
specs/               Design specs and implementation docs
```

---

## Key Files to Know

| File                                                     | What it does                                                                                                      |
| -------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------- |
| `src/app/globals.css`                                    | **All theming lives here** — CSS variables for both dark/light mode, Tailwind v4 `@theme` block, transition rules |
| `src/app/layout.tsx`                                     | Root layout — wraps with `ThemeProvider`, has FOIT-prevention script                                              |
| `src/app/(dashboard)/layout.tsx`                         | Dashboard shell — `bg-shell p-3 gap-3` floating panel layout                                                      |
| `src/context/ThemeContext.tsx`                           | `ThemeProvider` + `useTheme()` hook — reads/writes `localStorage` and sets `data-theme` on `<html>`               |
| `src/components/ui/sidebar.tsx`                          | Sidebar primitives — `SidebarProvider`, `DesktopSidebar`, `SidebarLink`, `SidebarBody`                            |
| `src/components/sidebar/DashboardSidebar.tsx`            | Full sidebar implementation — logo, nav, pin button, user popover                                                 |
| `src/components/common/constants/dashboard-constants.ts` | `DASHBOARD_PANEL_CLASS`, `DASHBOARD_CARD_CLASS`, `TONE_STYLES` — used by every dashboard component                |
| `src/components/ui/ThemeToggle.tsx`                      | Sun/moon toggle button — placed in page headers                                                                   |

---

## Design System

### Theming Architecture

- Theme is controlled by `data-theme="dark|light"` on `<html>`
- All colour tokens are CSS variables defined in `globals.css`
- Tailwind `@theme inline` block maps `bg-shell`, `bg-canvas`, `bg-surface` etc. to the CSS vars
- **Never hardcode hex colours in components** — always use CSS vars or `TONE_STYLES`

### Dark Mode Colour Tokens

```
--color-shell-val:     #002348   (outer frame — brand navy)
--color-sidebar-val:   #0d2347   (sidebar panel)
--color-canvas-val:    #0a1628   (main content bg)
--color-surface-val:   #0f1e35   (cards/panels)
--color-surface-2-val: #1a3058   (hover/active states)
```

### Light Mode Colour Tokens

```
--color-shell-val:     #c8c8cc   (outer frame — medium grey)
--color-sidebar-val:   #0d2347   (UNCHANGED — sidebar always dark navy)
--color-canvas-val:    #e4e4e8   (page bg — clearly grey)
--color-surface-val:   #ffffff   (panels/cards — pure white)
--color-surface-2-val: #f4f4f6   (sub-surfaces, hover)
```

### Light Mode Rules

- **Sidebar never changes** — always dark navy in both modes
- **No shadows in light mode** — `[data-theme="light"] * { box-shadow: none !important; }`
- Hierarchy is achieved purely through background shading (grey canvas → white panels)
- Panel backgrounds use `.bg-surface-panel` CSS class (resolves to `var(--color-surface-val)`)

### KPI Card Tones (`TONE_STYLES` in dashboard-constants.ts)

Cards use inline `style={{}}` not Tailwind classes — this is intentional so they work in both themes.

| Tone      | Dark bg                    | Light bg                   | Used for                              |
| --------- | -------------------------- | -------------------------- | ------------------------------------- |
| `yellow`  | `#f3ff54`                  | `#f3ff54`                  | Open Positions, Sent to Client        |
| `navy`    | `#002348`                  | `#002348`                  | Total Seats Open                      |
| `green`   | `#052e16`                  | `#ecfdf5`                  | Seats Filled, Offers Accepted, Joined |
| `red`     | `#2d0a0a`                  | `#fff1f2`                  | Candidate Dropped                     |
| `neutral` | `var(--color-surface-val)` | `var(--color-surface-val)` | Total in Pipeline                     |

### Contrast Rule

`#F3FF54` (yellow) is **only safe on dark navy backgrounds**. Never use yellow text/icons on white or light grey.

---

## Layout: Floating Panel System

The dashboard uses a "floating panel" layout — both the sidebar and main content are rounded panels floating on a visible shell background.

```
<div bg-shell p-3 gap-3>          ← outer shell, shows as frame
  <DashboardSidebar />             ← sidebar: rounded-xl, always dark navy
  <main bg-canvas rounded-xl>      ← content panel: rounded, theme-aware
    <div overflow-y-auto>          ← inner scroll container (NOT main itself)
      {children}
    </div>
  </main>
</div>
```

**Important:** `<main>` never scrolls directly — the inner `<div>` scrolls. This keeps `rounded-xl` corners intact.

---

## Sidebar

- **Collapsed width:** `64px` — icons centred
- **Open width:** `200px` — labels fade in
- **Hover to expand**, mouse-out to collapse
- **Pin button** (top right when open) — locks sidebar open, disables hover behaviour
- **User row** — shows avatar + name only; hover reveals popover with email + sign out
- Active nav item: `rgba(255,255,255,0.12)` background, always — never a Tailwind colour class (sidebar is always dark)

---

## Component Patterns

### Text colour in panels

Set `style={{ color: "var(--color-text-primary)" }}` on the panel root. All children inherit. Use `style={{ opacity: 0.6 }}` for secondary text — never `text-white/60` or similar hardcoded classes.

### Panel backgrounds

Use `DASHBOARD_PANEL_CLASS` from `dashboard-constants.ts`. This applies `.bg-surface-panel` which resolves to `var(--color-surface-val)` in both themes.

### Chart colours

- Donut track: `var(--color-chart-track)` — dark: `rgba(255,255,255,0.08)`, light: `#d1d1d6`
- SVG text: `fill="currentColor"` with `opacity` attribute — inherits from parent

---

## Authentication

- Google OAuth via FastAPI backend
- Session managed with `httpx` + `SessionMiddleware`
- `SESSION_SECRET` is separate from `JWT_SECRET`
- Frontend fetches `/api/v1/auth/me` on sidebar mount to get user info
- Backend runs as non-privileged `appuser` in Docker

---

## Environment Variables

```bash
# Frontend (.env.local)
NEXT_PUBLIC_API_URL=http://localhost:8000

# Backend (.env)
JWT_SECRET=...
SESSION_SECRET=...
GOOGLE_CLIENT_ID=...
GOOGLE_CLIENT_SECRET=...
MONGODB_URL=...
```

---

## Running Locally

```bash
# Install
pnpm install

# Frontend (from repo root)
pnpm --filter frontend dev

# Backend
cd apps/backend
uvicorn app.main:app --reload

# Or both via Turborepo
pnpm dev
```

---

## Outstanding / Next Steps

1. **Light mode polish** — leaderboard page components (`text-white` in leaderboard organisms) still need the same CSS var treatment applied to dashboard components
2. **API Proxying** — Next.js rewrites for production cross-origin cookie handling
3. **Onboarding flow** — `onboarding/page.tsx` state management incomplete
4. **Deployment** — Railway/Vercel; monitor session persistence across subdomains
5. **Positions & Candidates pages** — scaffolded but not fully built out
6. **Settings page** — placeholder only

---

## Known Gotchas

- **Tailwind v4** — uses `@theme inline` block in `globals.css`, not `tailwind.config.ts`. No `tailwind.config.ts` exists. Read `node_modules/next/dist/docs/` before writing new Tailwind code.
- **`motion/react`** — this is Framer Motion v12, imported as `motion/react` not `framer-motion`. API is the same but the import path differs.
- **`TONE_CLASSES` is gone** — renamed to `TONE_STYLES` with a different shape. Any component importing `TONE_CLASSES` will break at build time.
- **`bg-black` / `text-white` in page wrappers** — these were removed from dashboard and leaderboard pages. Use `style={{ background: "var(--color-canvas)", color: "var(--color-text-primary)" }}` instead.
- **Sidebar is always dark** — do not apply theme-aware colours to sidebar components. All sidebar text/icon colours are hardcoded white/rgba values.
- **`<main>` must not scroll** — the inner `<div className="flex-1 overflow-y-auto scrollbar-none">` is the scroll container. If you add `overflow-auto` to `<main>` the rounded corners will clip on scroll.
