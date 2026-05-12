import KanbanBoard from "@/components/kanban/Board";

interface PageProps {
  params: Promise<{ id: string }>;
}

export default async function PipelinePage({ params }: PageProps) {
  const { id } = await params;

  return (
    <div className="flex flex-col h-screen p-6 gap-4">
      <div>
        <h1 className="text-2xl font-bold text-white">Candidate Pipeline</h1>
        <p className="text-sm text-white mt-1">
          Drag candidates between columns to update their status.
        </p>
      </div>
      <div className="flex-1 overflow-hidden">
        <KanbanBoard positionId={id} />
      </div>
    </div>
  );
}
