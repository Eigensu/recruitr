import { cookies } from "next/headers";
import GlobalPipelineBoard from "@/components/kanban/GlobalPipelineBoard";
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
  let employees: { id: string; name: string }[] = [];
  let positions: { id: string; label: string; client: string }[] = [];

  try {
    // GET /api/v1/teams/employees — brand-scoped employee list
    const data = await serverFetch<EmployeeItem[]>("/api/v1/teams/employees");
    employees = data.map((e) => ({ id: e.id, name: e.name }));
  } catch {
    /* non-critical — filter bar will just be empty */
  }

  try {
    // GET /api/v1/positions — paginated; accumulate all pages (backend cap: 100/page)
    const allPositions: ApiPosition[] = [];
    let page = 1;

    while (true) {
      const data = await serverFetch<PaginatedResponse<ApiPosition>>(
        `/api/v1/positions?limit=100&page=${page}`,
      );
      allPositions.push(...data.items);
      if (!data.meta.has_next) break;
      page++;
    }
    positions = allPositions.map((p) => ({
      id: p.id,
      label: `${p.code} · ${p.role}`,
      client: p.client_name,
    }));
  } catch {
    /* non-critical */
  }

  return (
    <div className="flex h-full flex-col overflow-hidden bg-canvas">
      <div className="shrink-0 border-b border-border px-6 pb-5 pt-6">
        <h1 className="font-heading text-3xl font-bold tracking-wide text-text-primary">
          Recruitment Pipeline
        </h1>
        <p className="mt-1 text-sm text-text-muted">
          Drag candidates across stages to advance them through the pipeline.
        </p>
      </div>

      <div className="flex-1 overflow-hidden p-5">
        <GlobalPipelineBoard employees={employees} positions={positions} />
      </div>
    </div>
  );
}
