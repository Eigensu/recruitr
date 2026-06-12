import { cookies } from "next/headers";
import BoardClientWrapper from "@/components/kanban/BoardClientWrapper";

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

interface EmployeeItem {
  id: string;
  name: string;
  email: string;
}

interface PageProps {
  readonly params: Promise<{ id: string }>;
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

export default async function PipelinePage({ params }: PageProps) {
  const { id } = await params;

  let employees: { id: string; name: string }[] = [];
  let availableTags: string[] = [];

  try {
    const data = await serverFetch<EmployeeItem[]>("/api/v1/teams/employees");
    employees = data.map((e) => ({ id: e.id, name: e.name }));
  } catch {
    /* non-critical */
  }

  try {
    availableTags = await serverFetch<string[]>("/api/v1/candidates/tags");
  } catch {
    /* non-critical */
  }

  return (
    <div className="flex h-screen flex-col gap-4 p-6">
      <div>
        <h1 className="text-2xl font-bold" style={{ color: "var(--color-text-primary)" }}>
          Candidate Pipeline
        </h1>
        <p className="mt-1 text-sm" style={{ color: "var(--color-text-secondary)" }}>
          Drag candidates between columns to update their status.
        </p>
      </div>
      <div className="flex-1 overflow-hidden">
        <BoardClientWrapper positionId={id} employees={employees} availableTags={availableTags} />
      </div>
    </div>
  );
}
