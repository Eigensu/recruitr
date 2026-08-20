import { Suspense } from "react";
import Link from "next/link";
import { IconBriefcase, IconBuilding, IconLayoutKanban } from "@tabler/icons-react";
import {
  ActionNeededCallout,
  AnalyticsWidgets,
  ClientPipelineSnapshot,
  ClientPositionsSnapshot,
  DashboardKpiCard,
  KpiGridSkeleton,
  PanelSkeleton,
  PipelinePieChart,
  RecruiterLineGraph,
} from "@/components/dashboard";
import ClientProfilesTable from "@/components/dashboard/organisms/ClientProfilesTable";
import SourcingAnalyticsTable from "@/components/dashboard/organisms/SourcingAnalyticsTable";
import {
  getDashboardAnalyticsData,
  getClientProfilesData,
  getDashboardOverview,
  getPipelineDashboardData,
  getRecruiterDashboardData,
  getSourcingDashboardData,
} from "@/lib/dashboard-data";
import { ThemeToggle } from "@/components/ui/ThemeToggle";
import { getUserServer } from "@/lib/api/auth.server";
import type { DashboardKpi } from "@/types/dashboard";
import {
  getActiveClientMessages,
  getDashboardOverview as getApiDashboardOverview,
  getDashboardPipeline,
  getPositionsPreview,
} from "@/lib/api/dashboard";
import { ClientMessagingBanner } from "@/components/dashboard/ClientMessagingBanner";
import { CLIENT_STAGE_LABELS, CLIENT_STAGES } from "@/lib/constants/client-pipeline";

const QUICK_LINKS = [
  { href: "/positions", label: "Open Positions", icon: IconBriefcase },
  { href: "/pipeline", label: "Pipeline Board", icon: IconLayoutKanban },
  { href: "/company", label: "Company Profile", icon: IconBuilding },
] as const;

async function LiveOverviewSection() {
  const { kpis } = await getDashboardOverview();

  return (
    <section
      aria-label="Live overview"
      className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-2 xl:grid-rows-2 xl:auto-rows-fr h-full"
    >
      {kpis.map((metric, index) => (
        <DashboardKpiCard key={metric.id} metric={metric} index={index} />
      ))}
    </section>
  );
}

async function AnalyticsSection() {
  const { analytics } = await getDashboardAnalyticsData();

  return <AnalyticsWidgets widgets={analytics} />;
}

async function PipelinePieSection() {
  const stages = await getPipelineDashboardData();

  return <PipelinePieChart stages={stages} />;
}

async function RecruiterLineSection() {
  const recruiters = await getRecruiterDashboardData();

  return <RecruiterLineGraph recruiters={recruiters} />;
}

async function ClientProfilesSection() {
  const rows = await getClientProfilesData();

  return <ClientProfilesTable rows={rows} />;
}

async function SourcingAnalyticsSection() {
  const data = await getSourcingDashboardData();
  const metrics = data.map((item) => ({
    source_type: item.source,
    source_channel: item.source_channel,
    candidate_count: item.count,
    pipeline_candidates: item.pipeline_candidates,
    offers_accepted: item.offers_accepted,
    joined_candidates: item.joined_candidates,
  }));
  return <SourcingAnalyticsTable metrics={metrics} />;
}

async function ClientOverviewSection() {
  // Raw, viewer-scoped fetch — deliberately bypasses the staff dashboard
  // aggregator (getDashboardOverview from lib/dashboard-data), which also
  // calls several staff-only endpoints that 403 for the client role.
  const overview = await getApiDashboardOverview();
  const { summary } = overview;

  const [messages, user, positionsSettled, pipelineSettled] = await Promise.all([
    getActiveClientMessages(),
    getUserServer(),
    getPositionsPreview({ status: "open", limit: 5 }).then(
      (value) => ({ ok: true as const, value }),
      () => ({ ok: false as const, value: null }),
    ),
    getDashboardPipeline().then(
      (value) => ({ ok: true as const, value }),
      () => ({ ok: false as const, value: null }),
    ),
  ]);

  const metrics: DashboardKpi[] = [
    {
      id: "open_roles",
      label: "Open Roles with Binge",
      value: summary.open_positions,
      helper: "Active hiring mandates",
      tone: "yellow",
      trend: "Open now",
    },
    {
      id: "in_process",
      label: "Candidates Currently in Process",
      value: summary.candidates_in_pipeline,
      helper: "Moving through your pipeline",
      tone: "navy",
      trend: "Active pipeline",
    },
    {
      id: "seats_filled",
      label: "Seats Filled",
      value: summary.seats_filled,
      helper: "Positions successfully closed",
      tone: "green",
      trend: "Closed",
    },
    {
      id: "avg_days_to_shortlist",
      label: "Avg. Days to First Shortlist",
      value: summary.avg_days_to_shortlist,
      helper: "From opening the role to your first shortlist",
      tone: "neutral",
      trend: "Per role",
      suffix: "days",
    },
  ];

  const positionsPreview = positionsSettled.value?.items ?? [];
  const totalOpenPositions = positionsSettled.value?.meta.total ?? summary.open_positions;

  const stageCounts = new Map(pipelineSettled.value?.stages.map((s) => [s.stage, s.count]) ?? []);
  const clientPipelineStages = CLIENT_STAGES.map((stage) => ({
    stage,
    label: CLIENT_STAGE_LABELS[stage],
    count: stageCounts.get(stage) ?? 0,
  }));

  return (
    <div className="flex flex-col gap-6">
      {/* ── Section 1: Snapshot — hero numbers, action needed, announcements ── */}
      <section className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-4">
        {metrics.map((metric, index) => (
          <DashboardKpiCard key={metric.id} metric={metric} index={index} />
        ))}
      </section>

      <ActionNeededCallout count={summary.action_needed_count} />

      {messages && messages.length > 0 && user?.user_id && (
        <ClientMessagingBanner messages={messages} userId={user.user_id} />
      )}

      {/* ── Section 2: Your Pipeline at a Glance — the "show your work" layer ── */}
      <div className="mt-2 flex flex-col gap-4">
        <div className="flex flex-wrap items-end justify-between gap-3">
          <div>
            <h2 className="font-heading text-2xl" style={{ color: "var(--color-text-primary)" }}>
              Your Pipeline at a Glance
            </h2>
            <p className="mt-1 text-sm" style={{ color: "var(--color-text-secondary)" }}>
              A closer look at your open roles and where candidates stand, without digging through
              every tab.
            </p>
          </div>

          <nav aria-label="Quick links" className="flex flex-wrap gap-2">
            {QUICK_LINKS.map(({ href, label, icon: Icon }) => (
              <Link
                key={href}
                href={href}
                className="flex items-center gap-1.5 rounded-lg border px-3 py-2 text-xs font-bold transition-colors hover:border-yellow hover:text-yellow"
                style={{
                  borderColor: "var(--color-border-val)",
                  color: "var(--color-text-primary)",
                  background: "var(--color-surface-val)",
                }}
              >
                <Icon className="size-4" />
                {label}
              </Link>
            ))}
          </nav>
        </div>

        <div className="grid grid-cols-1 items-stretch gap-4 xl:grid-cols-[minmax(0,1.4fr)_minmax(280px,1fr)]">
          <ClientPositionsSnapshot
            positions={positionsPreview}
            totalOpen={totalOpenPositions}
            failed={!positionsSettled.ok}
          />
          <ClientPipelineSnapshot stages={clientPipelineStages} failed={!pipelineSettled.ok} />
        </div>
      </div>
    </div>
  );
}

export default async function DashboardPage() {
  const user = await getUserServer();
  const isClient = user?.role === "client";

  return (
    <div
      className="min-h-full px-4 py-5 sm:px-6 lg:px-8"
      style={{ background: "var(--color-canvas)", color: "var(--color-text-primary)" }}
    >
      <div className="mx-auto flex w-full max-w-400 flex-col gap-5">
        <header className="pb-4" style={{ borderBottom: "1px solid var(--color-border-val)" }}>
          <div className="flex items-start justify-between gap-4">
            <div>
              <p
                className="text-xs font-bold uppercase tracking-normal"
                style={{ color: "var(--color-text-secondary)" }}
              >
                {isClient ? "Client Portal" : "Recruitment command center"}
              </p>
              <h1
                className="mt-2 font-heading text-4xl leading-tight sm:text-5xl"
                style={{ color: "var(--color-text-primary)" }}
              >
                {isClient ? `Welcome, ${user?.client_name ?? "back"}` : "Recruitment Dashboard"}
              </h1>
            </div>
            <div className="mt-1 shrink-0">
              <ThemeToggle />
            </div>
          </div>
        </header>

        {isClient ? (
          <Suspense fallback={<KpiGridSkeleton />}>
            <ClientOverviewSection />
          </Suspense>
        ) : (
          <>
            <div className="grid grid-cols-1 items-stretch gap-6 xl:grid-cols-[minmax(300px,0.9fr)_minmax(0,1.9fr)]">
              <Suspense fallback={<PanelSkeleton rows={7} />}>
                <PipelinePieSection />
              </Suspense>
              <Suspense fallback={<KpiGridSkeleton />}>
                <LiveOverviewSection />
              </Suspense>
            </div>

            <div className="grid grid-cols-1 items-stretch gap-6 xl:grid-cols-[minmax(320px,0.8fr)_minmax(0,1.2fr)]">
              <Suspense fallback={<PanelSkeleton rows={2} />}>
                <AnalyticsSection />
              </Suspense>
              <Suspense fallback={<PanelSkeleton rows={5} />}>
                <RecruiterLineSection />
              </Suspense>
            </div>

            <Suspense fallback={<PanelSkeleton rows={8} />}>
              <ClientProfilesSection />
            </Suspense>

            <Suspense fallback={<PanelSkeleton rows={6} />}>
              <SourcingAnalyticsSection />
            </Suspense>
          </>
        )}
      </div>
    </div>
  );
}
