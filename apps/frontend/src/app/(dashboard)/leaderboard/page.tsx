import {
  HeroSpotlight,
  LeaderboardTable,
  MonthlyLineChart,
  RecruiterBarChart,
  RecentActivityFeed,
  CompanyHiringProgress,
  RecruiterProgressSection,
  AchievementBadgesSection,
  LeaderboardKpiCard,
} from "@/components/leaderboard";
import { getLeaderboardPageData } from "@/lib/api/leaderboard";
import { ThemeToggle } from "@/components/ui/ThemeToggle";

export const metadata = {
  title: "Leaderboard — Binge Recruiting Intelligence",
  description:
    "Gamified recruiter performance rankings, XP scores, achievement badges and analytics.",
};

export default async function LeaderboardPage() {
  const { topRecruiter, recruiters, kpis, companies, activity, monthLabels } =
    await getLeaderboardPageData();

  return (
    <div
      className="min-h-full px-4 py-5 sm:px-6 lg:px-8"
      style={{ background: "var(--color-canvas)", color: "var(--color-text-primary)" }}
    >
      <div className="mx-auto flex w-full max-w-400 flex-col gap-5">
        {/* ── Header ────────────────────────────────────────────────────── */}
        <header
          className="pb-4 flex items-start justify-between gap-4"
          style={{ borderBottom: "1px solid var(--color-border-val)" }}
        >
          <div>
            <p
              className="text-xs font-bold uppercase tracking-normal"
              style={{ color: "var(--color-text-secondary)" }}
            >
              Gamified Recruiter Rankings
            </p>
            <h1
              className="mt-2 font-heading text-4xl leading-tight sm:text-5xl"
              style={{ color: "var(--color-text-primary)" }}
            >
              Leaderboard
            </h1>
          </div>
          <div className="mt-1 shrink-0">
            <ThemeToggle />
          </div>
        </header>

        {/* ── Hero Spotlight ────────────────────────────────────────────── */}
        {topRecruiter ? (
          <HeroSpotlight recruiter={topRecruiter} />
        ) : (
          <section
            aria-label="Leaderboard spotlight"
            className="rounded-lg border-border bg-surface-2 p-5"
          >
            <p className="text-sm text-(--color-text-secondary)">
              No leaderboard data available yet.
            </p>
          </section>
        )}

        {/* ── KPI Cards ─────────────────────────────────────────────────── */}
        <section aria-label="Leaderboard KPIs">
          <div className="grid grid-cols-2 gap-4 sm:grid-cols-4 xl:grid-cols-8">
            {kpis.map((kpi, index) => (
              <LeaderboardKpiCard key={kpi.id} kpi={kpi} index={index} />
            ))}
          </div>
        </section>

        {/* ── Analytics Charts ──────────────────────────────────────────── */}
        <div className="grid grid-cols-1 gap-5 xl:grid-cols-2">
          <MonthlyLineChart recruiters={recruiters} monthLabels={monthLabels} />
          <RecruiterBarChart recruiters={recruiters} />
        </div>

        {/* ── Main Leaderboard Table ────────────────────────────────────── */}
        <LeaderboardTable recruiters={recruiters} />

        {/* ── Progress + Activity ───────────────────────────────────────── */}
        <div className="grid grid-cols-1 gap-5 xl:grid-cols-[1fr_360px]">
          <RecruiterProgressSection recruiters={recruiters} />
          <RecentActivityFeed items={activity} />
        </div>

        {/* ── Company Hiring + Badges ───────────────────────────────────── */}
        <div className="grid grid-cols-1 gap-5 xl:grid-cols-[360px_1fr]">
          <CompanyHiringProgress companies={companies} />
          <AchievementBadgesSection />
        </div>
      </div>
    </div>
  );
}
