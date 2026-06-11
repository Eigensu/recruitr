"use client";

import { useState } from "react";
import type { KanbanFilters } from "@/stores/usePipelineStore";

interface Employee {
  id: string;
  name: string;
}

const PIPELINE_STAGES = [
  "added",
  "shortlisted",
  "sent_to_client",
  "rejected",
  "hold",
  "offer_sent",
  "offer_accepted",
  "joined",
  "dropped",
];
const STAGE_LABELS: Record<string, string> = {
  added: "Added",
  shortlisted: "Shortlisted",
  sent_to_client: "Sent to Client",
  rejected: "Rejected",
  hold: "Hold",
  offer_sent: "Offer Sent",
  offer_accepted: "Offer Accepted",
  joined: "Joined",
  dropped: "Dropped",
};

interface ClientOption {
  id: string;
  label: string;
}

interface Props {
  employees: Employee[];
  clients: ClientOption[];
  availableTags: string[];
  onFilterChange: (filters: KanbanFilters) => void;
}

const selectStyle = {
  background: "var(--color-canvas-val)",
  color: "var(--color-text-primary)",
  border: "1px solid var(--color-border-val)",
};

export default function KanbanFilterBar({
  employees,
  clients,
  availableTags,
  onFilterChange,
}: Props) {
  const [f, setF] = useState<KanbanFilters>({});

  function update<K extends keyof KanbanFilters>(key: K, value: KanbanFilters[K]) {
    const next = { ...f, [key]: value };
    (Object.keys(next) as (keyof KanbanFilters)[]).forEach((k) => {
      const v = next[k];
      if (v === undefined || v === "" || (Array.isArray(v) && v.length === 0)) {
        delete next[k];
      }
    });
    setF(next);
    onFilterChange(next);
  }

  function clear() {
    setF({});
    onFilterChange({});
  }

  const hasFilters = Object.keys(f).length > 0;
  const selectCls = "rounded-lg px-2 py-1.5 text-xs outline-none";

  return (
    <div className="flex flex-wrap items-center gap-2 pb-3">
      <select
        value={f.recruiter_id ?? ""}
        onChange={(e) => update("recruiter_id", e.target.value || undefined)}
        className={selectCls}
        style={selectStyle}
      >
        <option value="">All Recruiters</option>
        {employees.map((e) => (
          <option key={e.id} value={e.id}>
            {e.name}
          </option>
        ))}
      </select>

      {clients.length > 0 && (
        <select
          value={f.client_id ?? ""}
          onChange={(e) => update("client_id", e.target.value || undefined)}
          className={selectCls}
          style={selectStyle}
        >
          <option value="">All Clients</option>
          {clients.map((c) => (
            <option key={c.id} value={c.id}>
              {c.label}
            </option>
          ))}
        </select>
      )}

      <select
        value={f.source ?? ""}
        onChange={(e) => update("source", (e.target.value as "internal" | "external") || undefined)}
        className={selectCls}
        style={selectStyle}
      >
        <option value="">All Sources</option>
        <option value="internal">Internal</option>
        <option value="external">External</option>
      </select>

      <select
        value={f.stage ?? ""}
        onChange={(e) => update("stage", e.target.value || undefined)}
        className={selectCls}
        style={selectStyle}
      >
        <option value="">All Stages</option>
        {PIPELINE_STAGES.map((s) => (
          <option key={s} value={s}>
            {STAGE_LABELS[s]}
          </option>
        ))}
      </select>

      {availableTags.length > 0 && (
        <select
          value=""
          onChange={(e) => {
            const tag = e.target.value;
            if (!tag) return;
            const current = f.tags ?? [];
            if (!current.includes(tag)) update("tags", [...current, tag]);
          }}
          className={selectCls}
          style={selectStyle}
        >
          <option value="">+ Tag filter</option>
          {availableTags.map((t) => (
            <option key={t} value={t}>
              {t}
            </option>
          ))}
        </select>
      )}

      {(f.tags ?? []).map((tag) => (
        <span
          key={tag}
          className="inline-flex items-center gap-1 rounded-full px-2 py-1 text-xs"
          style={selectStyle}
        >
          {tag}
          <button
            type="button"
            onClick={() =>
              update(
                "tags",
                (f.tags ?? []).filter((t) => t !== tag),
              )
            }
            className="opacity-60 hover:opacity-100"
          >
            ×
          </button>
        </span>
      ))}

      <input
        type="date"
        value={f.mapped_after ?? ""}
        onChange={(e) => update("mapped_after", e.target.value || undefined)}
        className={selectCls}
        style={selectStyle}
        title="Mapped after"
      />
      <input
        type="date"
        value={f.mapped_before ?? ""}
        onChange={(e) => update("mapped_before", e.target.value || undefined)}
        className={selectCls}
        style={selectStyle}
        title="Mapped before"
      />

      {hasFilters && (
        <button
          type="button"
          onClick={clear}
          className="text-xs underline"
          style={{ color: "var(--color-text-secondary)" }}
        >
          Clear filters
        </button>
      )}
    </div>
  );
}
