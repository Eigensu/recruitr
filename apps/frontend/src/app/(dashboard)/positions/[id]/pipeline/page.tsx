import KanbanBoard from "@/components/kanban/Board";
import { getDashboardClients, getDashboardEmployees } from "@/lib/api/dashboard";
import { getCandidateTags } from "@/lib/api/candidates";

interface PageProps {
  readonly params: Promise<{ id: string }>;
}

export default async function PipelinePage({ params }: PageProps) {
  const { id } = await params;

  // Filter-bar data — best-effort, non-blocking on failure.
  let employees: { id: string; name: string }[] = [];
  let clients: { id: string; label: string }[] = [];
  let availableTags: string[] = [];
  try {
    const { items } = await getDashboardEmployees({ limit: 100 });
    employees = items.map((e) => ({ id: e.id, name: e.name }));
  } catch {
    /* non-critical */
  }
  try {
    const { items } = await getDashboardClients({ limit: 100 });
    clients = items.map((c) => ({ id: c.id, label: `${c.client_name} · ${c.role}` }));
  } catch {
    /* non-critical */
  }
  try {
    availableTags = await getCandidateTags();
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
        <KanbanBoard
          positionId={id}
          employees={employees}
          clients={clients}
          availableTags={availableTags}
        />
      </div>
    </div>
  );
}
