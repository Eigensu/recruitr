import { Suspense } from "react";
import {
  AnalyticsWidgets,
  ClientActivityTable,
  DashboardKpiCard,
  KpiGridSkeleton,
  PanelSkeleton,
  PipelinePieChart,
  RecruiterLineGraph,
  PipelineBreakdown,
} from "@/components/dashboard";
import {
  getDashboardAnalyticsData,
  getClientActivityData,
  getDashboardOverview,
  getPipelineDashboardData,
  getRecruiterDashboardData,
} from "@/lib/dashboard-data";

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

async function PipelineSection() {
  const stages = await getPipelineDashboardData();

  return <PipelineBreakdown stages={stages} />;
}

async function PipelinePieSection() {
  const stages = await getPipelineDashboardData();

  return <PipelinePieChart stages={stages} />;
}

async function RecruiterLineSection() {
  const recruiters = await getRecruiterDashboardData();

  return <RecruiterLineGraph recruiters={recruiters} />;
}

async function ClientActivitySection() {
  const clients = await getClientActivityData();

  return <ClientActivityTable rows={clients} />;
}

export default function DashboardPage() {
  return (
    <div className="min-h-full bg-black px-4 py-5 text-white sm:px-6 lg:px-8">
      <div className="mx-auto flex w-full max-w-400 flex-col gap-5">
        <header className="border-b border-white/10 pb-4">
          <div>
            <p className="text-xs font-bold uppercase tracking-normal text-yellow">
              Recruitment command center
            </p>
            <h1 className="mt-2 font-heading text-4xl leading-tight text-white sm:text-5xl">
              Recruitment Dashboard
            </h1>
          </div>
        </header>

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
          <ClientActivitySection />
        </Suspense>
      </div>
    </div>
  );
}
