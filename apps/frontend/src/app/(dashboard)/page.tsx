import { Suspense } from "react";
import ActivityFeed from "@/components/dashboard/ActivityFeed";
import AnalyticsWidgets from "@/components/dashboard/AnalyticsWidgets";
import ClientActivityTable from "@/components/dashboard/ClientActivityTable";
import DashboardKpiCard from "@/components/dashboard/DashboardKpiCard";
import DashboardRealtimeStatus from "@/components/dashboard/DashboardRealtimeStatus";
import { KpiGridSkeleton, PanelSkeleton } from "@/components/dashboard/DashboardSkeleton";
import PipelineBreakdown from "@/components/dashboard/PipelineBreakdown";
import PipelinePieChart from "@/components/dashboard/PipelinePieChart";
import RecruiterBarGraph from "@/components/dashboard/RecruiterBarGraph";
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
      className="grid grid-cols-1 gap-3 sm:grid-cols-2 xl:grid-cols-4"
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

async function RecruiterBarSection() {
  const recruiters = await getRecruiterDashboardData();

  return <RecruiterBarGraph recruiters={recruiters} />;
}

async function ClientActivitySection() {
  const clients = await getClientActivityData();

  return <ClientActivityTable rows={clients} />;
}

async function ActivitySection() {
  const { activity } = await getDashboardOverview();

  return <ActivityFeed items={activity} />;
}

export default function DashboardPage() {
  return (
    <div className="min-h-full bg-[radial-gradient(circle_at_top_right,rgba(243,255,84,0.10),transparent_30%),linear-gradient(135deg,#001a36_0%,#111827_48%,#262626_100%)] px-4 py-5 text-white sm:px-6 lg:px-8">
      <div className="mx-auto flex w-full max-w-[1600px] flex-col gap-5">
        <header className="flex flex-col gap-4 border-b border-white/10 pb-5 lg:flex-row lg:items-end lg:justify-between">
          <div>
            <p className="text-xs font-bold uppercase tracking-normal text-yellow">
              Recruitment command center
            </p>
            <h1 className="mt-2 font-heading text-4xl leading-tight text-white sm:text-5xl">
              Recruitment Dashboard
            </h1>
            <p className="mt-2 max-w-2xl text-sm text-white/60">
              Auto-updating operational view for open seats, recruiter movement, client activity,
              and final joining conversion.
            </p>
          </div>
          <div className="flex flex-wrap items-center gap-2">
            <DashboardRealtimeStatus />
            <span className="rounded-full border border-white/10 bg-white/5 px-3 py-1.5 text-xs font-semibold text-white/70">
              Sheet placeholders normalized
            </span>
          </div>
        </header>

        <Suspense fallback={<KpiGridSkeleton />}>
          <LiveOverviewSection />
        </Suspense>

        <Suspense fallback={<PanelSkeleton rows={2} />}>
          <AnalyticsSection />
        </Suspense>

        <div className="grid grid-cols-1 gap-5 xl:grid-cols-[minmax(0,1.1fr)_minmax(360px,0.9fr)]">
          <Suspense fallback={<PanelSkeleton rows={6} />}>
            <PipelinePieSection />
          </Suspense>
          <Suspense fallback={<PanelSkeleton rows={5} />}>
            <RecruiterBarSection />
          </Suspense>
        </div>

        <div className="grid grid-cols-1 gap-5">
          <Suspense fallback={<PanelSkeleton rows={10} />}>
            <PipelineSection />
          </Suspense>
        </div>

        <div className="grid grid-cols-1 gap-5 xl:grid-cols-[minmax(0,1fr)_360px]">
          <Suspense fallback={<PanelSkeleton rows={8} />}>
            <ClientActivitySection />
          </Suspense>
          <Suspense fallback={<PanelSkeleton rows={4} />}>
            <ActivitySection />
          </Suspense>
        </div>
      </div>
    </div>
  );
}
