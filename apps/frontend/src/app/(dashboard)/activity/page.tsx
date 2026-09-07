"use client";

import React, { useCallback, useEffect, useState } from "react";
import {
  IconActivity,
  IconArrowRight,
  IconLoader2,
  IconUser,
  IconAlertCircle,
  IconSearch,
} from "@tabler/icons-react";
import { useApiFetch } from "@/lib/api";
import { useCurrentUser } from "@/hooks/useCurrentUser";
import { useRouter, useSearchParams } from "next/navigation";

// ── Types ──────────────────────────────────────────────────────────────────────

interface ActivityItem {
  id: string;
  activity_type: string;
  description: string;
  target_entity_type: string;
  target_entity_id: string;
  employee_id: string | null;
  employee_name: string | null;
  created_at: string;
}

interface ActivityPage {
  items: ActivityItem[];
  meta: {
    page: number;
    limit: number;
    total: number;
    pages: number;
    has_next: boolean;
    has_prev: boolean;
  };
}

// ── Helpers ────────────────────────────────────────────────────────────────────

const ACTIVITY_LABELS: Record<string, string> = {
  mapped: "mapped candidate to position",
  stage_moved: "moved candidate to next stage",
  offer_sent: "sent offer",
  offer_accepted: "accepted offer",
  joined: "candidate joined",
  rejected: "rejected candidate",
  unmapped: "unmapped candidate from position",
};

const ACTIVITY_COLORS: Record<string, string> = {
  mapped: "bg-blue-500/10 text-blue-400 border-blue-500/20",
  stage_moved: "bg-yellow/10 text-yellow border-yellow/20",
  offer_sent: "bg-purple-500/10 text-purple-400 border-purple-500/20",
  offer_accepted: "bg-emerald-500/10 text-emerald-400 border-emerald-500/20",
  joined: "bg-emerald-500/10 text-emerald-400 border-emerald-500/20",
  rejected: "bg-red-500/10 text-red-400 border-red-500/20",
  unmapped: "bg-orange-500/10 text-orange-400 border-orange-500/20",
};

function formatDate(iso: string): string {
  const d = new Date(iso);
  return d.toLocaleString(undefined, {
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

function timeAgo(iso: string): string {
  const diff = Date.now() - new Date(iso).getTime();
  const mins = Math.floor(diff / 60000);
  if (mins < 1) return "just now";
  if (mins < 60) return `${mins}m ago`;
  const hrs = Math.floor(mins / 60);
  if (hrs < 24) return `${hrs}h ago`;
  return `${Math.floor(hrs / 24)}d ago`;
}

// ── Component ──────────────────────────────────────────────────────────────────

export default function ActivityPage() {
  const apiFetch = useApiFetch();
  const router = useRouter();
  const searchParams = useSearchParams();
  const { isMaintainer, isLoading: authLoading } = useCurrentUser();

  const [items, setItems] = useState<ActivityItem[]>([]);
  const [meta, setMeta] = useState<ActivityPage["meta"] | null>(null);
  const [loading, setLoading] = useState(true);
  const [loadingMore, setLoadingMore] = useState(false);
  const [page, setPage] = useState(1);

  const [employees, setEmployees] = useState<{ id: string; name: string }[]>([]);

  // Filters from URL
  const searchParam = searchParams?.get("search") || "";
  const activityTypeParam = searchParams?.get("activityType") || "";
  const recruiterIdParam = searchParams?.get("recruiterId") || "";
  const categoryParam = searchParams?.get("category") || "";

  // Local state for debounced search
  const [searchValue, setSearchValue] = useState(searchParam);

  const fetchPage = useCallback(
    async (p: number, append = false, queryParams: string = "") => {
      try {
        const data = await apiFetch<ActivityPage>(
          `/api/v1/activity?page=${p}&limit=50${queryParams}`,
        );
        setItems((prev) => (append ? [...prev, ...data.items] : data.items));
        setMeta(data.meta);
      } catch {
        // silently fail — user will see empty state
      }
    },
    [apiFetch],
  );

  // Initial load of employees
  useEffect(() => {
    if (authLoading || !isMaintainer) return;
    apiFetch<{ id: string; name: string }[]>("/api/v1/teams/employees")
      .then((data) => setEmployees(data))
      .catch(() => {});
  }, [authLoading, isMaintainer, apiFetch]);

  // Update URL function
  const updateUrl = useCallback(
    (newParams: Record<string, string>) => {
      const params = new URLSearchParams(searchParams?.toString() || "");
      for (const [k, v] of Object.entries(newParams)) {
        if (v) params.set(k, v);
        else params.delete(k);
      }
      router.replace(`?${params.toString()}`);
    },
    [searchParams, router],
  );

  // Debounce search effect
  useEffect(() => {
    const timer = setTimeout(() => {
      if (searchValue !== searchParam) {
        updateUrl({ search: searchValue });
      }
    }, 400);
    return () => clearTimeout(timer);
  }, [searchValue, searchParam, updateUrl]);

  // Fetch when URL params change
  useEffect(() => {
    if (authLoading) return;
    if (!isMaintainer) {
      router.replace("/");
      return;
    }
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setLoading(true);
    const params = new URLSearchParams();
    if (searchParam) params.set("search", searchParam);
    if (activityTypeParam) params.set("activityType", activityTypeParam);
    if (recruiterIdParam) params.set("recruiterId", recruiterIdParam);
    if (categoryParam) params.set("category", categoryParam);

    setPage(1);
    fetchPage(1, false, `&${params.toString()}`).finally(() => setLoading(false));
  }, [
    authLoading,
    isMaintainer,
    router,
    fetchPage,
    searchParam,
    activityTypeParam,
    recruiterIdParam,
    categoryParam,
  ]);

  async function handleLoadMore() {
    const next = page + 1;
    setLoadingMore(true);
    const params = new URLSearchParams();
    if (searchParam) params.set("search", searchParam);
    if (activityTypeParam) params.set("activityType", activityTypeParam);
    if (recruiterIdParam) params.set("recruiterId", recruiterIdParam);
    if (categoryParam) params.set("category", categoryParam);

    await fetchPage(next, true, `&${params.toString()}`);
    setPage(next);
    setLoadingMore(false);
  }

  const hasFilters = Boolean(searchParam || activityTypeParam || recruiterIdParam || categoryParam);

  if (authLoading) {
    return (
      <div className="flex items-center justify-center h-64">
        <IconLoader2 className="size-6 animate-spin text-text-muted" />
      </div>
    );
  }

  return (
    <div className="p-6 md:p-8 max-w-4xl mx-auto w-full animate-in fade-in duration-300">
      {/* Header */}
      <div className="flex items-center gap-3 mb-8">
        <div className="size-10 rounded-xl bg-yellow/10 border border-yellow/20 flex items-center justify-center">
          <IconActivity className="size-5 text-yellow" />
        </div>
        <div>
          <h1 className="text-2xl font-heading font-bold text-text-primary">Activity Log</h1>
          <p className="text-sm text-text-secondary mt-0.5">
            {meta ? `${meta.total} matching actions across your team` : "All recruitment actions"}
          </p>
        </div>
      </div>

      {/* Filters Toolbar */}
      <div className="mb-8 flex flex-col md:flex-row flex-wrap items-center gap-3 bg-surface-2 p-3 rounded-xl border border-border">
        {/* Search */}
        <div className="flex-1 min-w-[200px] w-full relative">
          <input
            type="text"
            placeholder="Search activities..."
            value={searchValue}
            onChange={(e) => setSearchValue(e.target.value)}
            className="w-full pl-9 pr-3 py-2 text-sm bg-surface rounded-lg border border-border text-text-primary placeholder-text-muted focus:outline-none focus:border-text-secondary"
          />
          <IconSearch className="size-4 text-text-muted absolute left-3 top-2.5" />
        </div>

        {/* Activity Type Dropdown */}
        <select
          value={activityTypeParam}
          onChange={(e) => updateUrl({ activityType: e.target.value })}
          className="w-full md:w-auto px-3 py-2 text-sm bg-surface rounded-lg border border-border text-text-primary focus:outline-none"
        >
          <option value="">All Activities</option>
          <option value="mapped">Candidate Mapped</option>
          <option value="stage_moved">Candidate Moved</option>
          <option value="rejected">Candidate Rejected</option>
          <option value="joined">Candidate Joined</option>
          <option value="offer_accepted">Offer Accepted</option>
          <option value="offer_sent">Offer Sent</option>
          <option value="unmapped">Candidate Unmapped</option>
        </select>

        {/* Recruiter Dropdown */}
        <select
          value={recruiterIdParam}
          onChange={(e) => updateUrl({ recruiterId: e.target.value })}
          className="w-full md:w-auto px-3 py-2 text-sm bg-surface rounded-lg border border-border text-text-primary focus:outline-none"
        >
          <option value="">All Recruiters</option>
          {employees.map((e) => (
            <option key={e.id} value={e.id}>
              {e.name}
            </option>
          ))}
          <option value="system">System</option>
        </select>

        {/* Category Dropdown */}
        <select
          value={categoryParam}
          onChange={(e) => updateUrl({ category: e.target.value })}
          className="w-full md:w-auto px-3 py-2 text-sm bg-surface rounded-lg border border-border text-text-primary focus:outline-none"
        >
          <option value="">All Categories</option>
          <option value="mapping">Mapping</option>
          <option value="candidate">Candidate</option>
        </select>

        {/* Clear Filters */}
        {hasFilters && (
          <button
            onClick={() => {
              setSearchValue("");
              router.replace("?");
            }}
            className="w-full md:w-auto px-3 py-2 text-sm text-text-secondary hover:text-text-primary transition-colors text-left"
          >
            Clear filters
          </button>
        )}
      </div>

      {/* Loading overlay during filtering */}
      {loading ? (
        <div className="flex items-center justify-center py-16">
          <IconLoader2 className="size-6 animate-spin text-text-muted" />
        </div>
      ) : items.length === 0 ? (
        <div className="flex flex-col items-center justify-center py-16 text-center border border-border rounded-xl bg-surface">
          <IconAlertCircle className="size-10 text-text-muted opacity-30 mb-3" />
          <p className="text-text-primary font-semibold">No activities found</p>
          <p className="text-text-secondary text-sm mt-1">Try changing your search or filters.</p>
          {hasFilters && (
            <button
              onClick={() => {
                setSearchValue("");
                router.replace("?");
              }}
              className="mt-4 px-4 py-2 rounded-lg bg-surface-2 border border-border text-sm font-medium text-text-primary hover:bg-surface-panel transition-colors"
            >
              Clear filters
            </button>
          )}
        </div>
      ) : (
        <div className="relative">
          {/* Timeline line */}
          <div className="absolute left-5 top-0 bottom-0 w-px bg-border" />

          <div className="space-y-1">
            {items.map((item) => {
              const colorClass =
                ACTIVITY_COLORS[item.activity_type] ?? "bg-surface-2 text-text-muted border-border";
              const label =
                ACTIVITY_LABELS[item.activity_type] ?? item.activity_type.replace(/_/g, " ");

              return (
                <div key={item.id} className="relative flex gap-4 pl-12 py-3 group">
                  {/* Dot */}
                  <div
                    className={`absolute left-3.5 top-4 size-3 rounded-full border-2 ${colorClass}`}
                  />

                  {/* Content */}
                  <div className="flex-1 min-w-0 rounded-xl border border-border bg-surface-panel px-4 py-3 transition-colors group-hover:border-border/80">
                    <div className="flex items-start justify-between gap-3 flex-wrap">
                      <div className="flex-1 min-w-0">
                        {/* Actor */}
                        <div className="flex items-center gap-1.5 mb-1">
                          <IconUser className="size-3 text-text-muted shrink-0" />
                          <span className="text-xs font-semibold text-text-primary">
                            {item.employee_name ?? "System"}
                          </span>
                          <IconArrowRight className="size-3 text-text-muted shrink-0" />
                          <span
                            className={`text-[10px] font-bold px-1.5 py-0.5 rounded-full border ${colorClass}`}
                          >
                            {label}
                          </span>
                        </div>

                        {/* Description */}
                        <p className="text-xs text-text-secondary leading-relaxed">
                          {item.description}
                        </p>

                        {/* Entity type */}
                        <p className="text-[10px] text-text-muted mt-1 font-medium uppercase tracking-wide">
                          {item.target_entity_type}
                        </p>
                      </div>

                      {/* Timestamp */}
                      <div className="shrink-0 text-right">
                        <span
                          className="text-[10px] font-medium text-text-muted"
                          title={formatDate(item.created_at)}
                        >
                          {timeAgo(item.created_at)}
                        </span>
                      </div>
                    </div>
                  </div>
                </div>
              );
            })}
          </div>

          {meta?.has_next && (
            <div className="flex justify-center mt-6 pl-12">
              <button
                type="button"
                onClick={handleLoadMore}
                disabled={loadingMore}
                className="px-5 py-2 rounded-lg text-sm font-medium border border-border bg-surface text-text-primary hover:bg-surface-2 transition-colors disabled:opacity-60"
              >
                {loadingMore ? (
                  <span className="flex items-center gap-2">
                    <IconLoader2 className="size-4 animate-spin" />
                    Loading…
                  </span>
                ) : (
                  `Load more (${meta.total - items.length} remaining)`
                )}
              </button>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
