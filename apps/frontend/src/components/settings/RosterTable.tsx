import React from "react";

/** Cancel and submit for the add-a-person forms above a settings roster. */
export function FormActions({
  onCancel,
  submitting,
  label,
  pendingLabel,
}: {
  readonly onCancel: () => void;
  readonly submitting: boolean;
  readonly label: string;
  readonly pendingLabel: string;
}) {
  return (
    <div className="flex justify-end gap-3 pt-2">
      <button
        type="button"
        onClick={onCancel}
        className="px-4 py-2 text-sm font-medium text-text-secondary hover:text-text-primary transition-colors cursor-pointer"
        disabled={submitting}
      >
        Cancel
      </button>
      <button
        type="submit"
        disabled={submitting}
        className="px-4 py-2 bg-navy dark:bg-yellow dark:text-navy text-white text-sm font-medium rounded-lg hover:opacity-90 transition-opacity disabled:opacity-50 cursor-pointer"
      >
        {submitting ? pendingLabel : label}
      </button>
    </div>
  );
}

/** A settings roster: one header row, then the rows the tab renders. */
export function RosterTable({
  columns,
  withActions,
  children,
}: {
  readonly columns: readonly string[];
  /** Adds a right-aligned Actions column after `columns`. */
  readonly withActions: boolean;
  readonly children: React.ReactNode;
}) {
  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm text-left">
        <thead className="bg-surface-2 border-b border-border text-xs uppercase text-text-secondary font-semibold">
          <tr>
            {columns.map((column) => (
              <th key={column} className="px-4 py-3">
                {column}
              </th>
            ))}
            {withActions && <th className="px-4 py-3 text-right">Actions</th>}
          </tr>
        </thead>
        <tbody className="divide-y divide-border">{children}</tbody>
      </table>
    </div>
  );
}
