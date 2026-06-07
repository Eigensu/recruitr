import KanbanBoard from "@/components/kanban/Board";

export default function PipelinePage() {
  return (
    <div className="flex flex-col h-full overflow-hidden bg-canvas">
      {/* Header */}
      <div className="px-6 pt-6 pb-5 border-b border-border shrink-0">
        <h1 className="text-3xl font-heading font-bold text-text-primary tracking-wide">
          Recruitment Pipeline
        </h1>
        <p className="text-sm mt-1 text-text-muted">
          Drag candidates across stages to advance them through the pipeline.
        </p>
      </div>

      {/* Board */}
      <div className="flex-1 overflow-hidden p-5">
        <KanbanBoard />
      </div>
    </div>
  );
}
