export default function PositionsPage() {
  return (
    <div className="p-8">
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-3xl font-bold text-white">Positions</h1>
        <a
          href="/positions/new"
          className="px-4 py-2 rounded-lg bg-violet-600 hover:bg-violet-500 text-white text-sm font-medium transition-colors"
        >
          + New Position
        </a>
      </div>
      <p className="text-white text-sm">No positions yet. Create one to get started.</p>
    </div>
  );
}
