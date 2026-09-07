import { cookies } from "next/headers";
import GlobalPipelineBoard from "@/components/kanban/GlobalPipelineBoard";
import ClientPipelineBoard from "@/components/kanban/ClientPipelineBoard";
import { getUserServer } from "@/lib/api/auth.server";
import type { ApiPosition, PaginatedResponse } from "@/types";

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

interface EmployeeItem {
  id: string;
  name: string;
  email: string;
}

async function serverFetch<T>(path: string): Promise<T> {
  const cookieStore = await cookies();
  const cookieHeader = cookieStore
    .getAll()
    .map((c) => `${c.name}=${c.value}`)
    .join("; ");
  const res = await fetch(`${API_URL}${path}`, {
    headers: { ...(cookieHeader ? { Cookie: cookieHeader } : {}) },
    cache: "no-store",
  });
  if (!res.ok) throw new Error(`${path} → ${res.status}`);
  return res.json() as Promise<T>;
}

export default async function PipelinePage() {
  const user = await getUserServer();
  const isClient = user?.role === "client";

  let employees: { id: string; name: string }[] = [];
  let positions: { id: string; label: string; client: string }[] = [];

  try {
    if (!isClient) {
      const data = await serverFetch<EmployeeItem[]>("/api/v1/teams/employees");
      employees = data.map((e) => ({ id: e.id, name: e.name }));
    }
  } catch {
    /* non-critical */
  }

  try {
    const MAX_PAGE_ITER = 100;
    const collected: { id: string; label: string; client: string }[] = [];
    let page = 1;

    for (; page <= MAX_PAGE_ITER; page++) {
      const data = await serverFetch<PaginatedResponse<ApiPosition>>(
        `/api/v1/positions?limit=100&page=${page}`,
      );
      for (const p of data.items) {
        collected.push({ id: p.id, label: `${p.code} · ${p.role}`, client: p.client_name });
      }
      if (!data.meta.has_next) break;
    }
    positions = collected;
  } catch {
    /* non-critical */
  }

  return (
    <div className="flex h-full flex-col overflow-hidden bg-canvas">
      <div className="shrink-0 border-b border-border px-6 pb-5 pt-6">
        <h1
          className="mt-2 font-heading text-4xl leading-tight sm:text-5xl"
          style={{ color: "var(--color-text-primary)" }}
        >
          {isClient ? "Hiring Pipeline" : "Recruitment Pipeline"}
        </h1>
        <p className="mt-1 text-sm text-text-muted">
          {isClient
            ? "Track candidates progressing through your open positions."
            : "Drag candidates across stages to advance them through the pipeline."}
        </p>
      </div>

      <div className="flex-1 overflow-hidden p-5">
        {isClient ? (
          <ClientPipelineBoard positions={positions} />
        ) : (
          <GlobalPipelineBoard employees={employees} positions={positions} />
        )}
      </div>
    </div>
  );
}
