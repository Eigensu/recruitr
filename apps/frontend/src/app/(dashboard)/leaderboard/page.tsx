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
import {
  MOCK_RECRUITERS,
  LEADERBOARD_KPIS,
  COMPANY_HIRING,
  RECENT_ACTIVITY,
} from "@/lib/leaderboard-data";

export const metadata = {
  title: "Leaderboard — Binge Recruiting Intelligence",
  description:
    "Gamified recruiter performance rankings, XP scores, achievement badges and analytics.",
};

export default function LeaderboardPage() {
  const topRecruiter = MOCK_RECRUITERS[0]!;

  return (
    <div className="min-h-full bg-black px-4 py-5 text-white sm:px-6 lg:px-8">
      <div className="mx-auto flex w-full max-w-400 flex-col gap-5">
        {/* ── Header ────────────────────────────────────────────────────── */}
        <header className="border-b border-white/10 pb-4">
          <p className="text-xs font-bold uppercase tracking-normal text-yellow">
            Gamified Recruiter Rankings
          </p>
          <h1 className="mt-2 font-heading text-4xl leading-tight text-white sm:text-5xl">
            Leaderboard
          </h1>
        </header>

        {/* ── Hero Spotlight ────────────────────────────────────────────── */}
        <HeroSpotlight recruiter={topRecruiter} />

        {/* ── KPI Cards ─────────────────────────────────────────────────── */}
        <section aria-label="Leaderboard KPIs">
          <div className="grid grid-cols-2 gap-4 sm:grid-cols-4 xl:grid-cols-8">
            {LEADERBOARD_KPIS.map((kpi, index) => (
              <LeaderboardKpiCard key={kpi.id} kpi={kpi} index={index} />
            ))}
          </div>
        </section>

        {/* ── Analytics Charts ──────────────────────────────────────────── */}
        <div className="grid grid-cols-1 gap-5 xl:grid-cols-2">
          <MonthlyLineChart />
          <RecruiterBarChart />
        </div>

        {/* ── Main Leaderboard Table ────────────────────────────────────── */}
        <LeaderboardTable recruiters={MOCK_RECRUITERS} />

        {/* ── Progress + Activity ───────────────────────────────────────── */}
        <div className="grid grid-cols-1 gap-5 xl:grid-cols-[1fr_360px]">
          <RecruiterProgressSection recruiters={MOCK_RECRUITERS} />
          <RecentActivityFeed items={RECENT_ACTIVITY} />
        </div>

        {/* ── Company Hiring + Badges ───────────────────────────────────── */}
        <div className="grid grid-cols-1 gap-5 xl:grid-cols-[360px_1fr]">
          <CompanyHiringProgress companies={COMPANY_HIRING} />
          <AchievementBadgesSection />
        </div>
      </div>
    </div>
  );
}
