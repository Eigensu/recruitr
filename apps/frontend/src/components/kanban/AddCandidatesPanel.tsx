"use client";

import { useEffect, useState } from "react";
import type { Candidate, CandidateSource } from "@/types";
import { clientFetchCandidates } from "@/lib/api/candidates.client";
import { assignCandidate, fetchSuggestions, type SuggestedCandidate } from "@/lib/api/pipeline";

interface Props {
  positionId: string;
  onAssigned: () => void;
  onClose: () => void;
}

type Tab = "suggested" | "search";

const SOURCE_COLOR: Record<CandidateSource, string> = { internal: "#3DDC97", external: "#FF5A5F" };

const panelStyle = {
  background: "var(--color-surface-val)",
  border: "1px solid var(--color-border-val)",
};
const inputStyle = {
  background: "var(--color-canvas-val)",
  color: "var(--color-text-primary)",
  border: "1px solid var(--color-border-val)",
};

function SourceChip({ source }: { source: CandidateSource }) {
  return (
    <span
      className="inline-flex items-center gap-1 text-[10px] font-medium"
      style={{ color: SOURCE_COLOR[source] }}
    >
      <span className="text-[8px]">●</span>
      {source === "internal" ? "Internal" : "External"}
    </span>
  );
}

function Chips({ items, max = 4 }: { items: string[]; max?: number }) {
  if (items.length === 0) return null;
  return (
    <div className="mt-1 flex flex-wrap gap-1">
      {items.slice(0, max).map((t) => (
        <span
          key={t}
          className="rounded-full px-1.5 py-0.5 text-[10px]"
          style={{
            background: "var(--color-canvas-val)",
            color: "var(--color-text-secondary)",
            border: "1px solid var(--color-border-val)",
          }}
        >
          {t}
        </span>
      ))}
      {items.length > max && (
        <span className="text-[10px]" style={{ color: "var(--color-text-secondary)" }}>
          +{items.length - max}
        </span>
      )}
    </div>
  );
}

export default function AddCandidatesPanel({ positionId, onAssigned, onClose }: Props) {
  const [tab, setTab] = useState<Tab>("suggested");
  const [suggested, setSuggested] = useState<SuggestedCandidate[]>([]);
  const [search, setSearch] = useState("");
  const [results, setResults] = useState<Candidate[]>([]);
  const [loading, setLoading] = useState(true);
  const [assigning, setAssigning] = useState<string | null>(null);
  const [assignedIds, setAssignedIds] = useState<Set<string>>(new Set());

  useEffect(() => {
    let active = true;
    // `loading` starts true; only flip it after the fetch resolves (no sync setState).
    fetchSuggestions(positionId)
      .then((data) => active && setSuggested(data))
      .catch(() => active && setSuggested([]))
      .finally(() => active && setLoading(false));
    return () => {
      active = false;
    };
  }, [positionId]);

  useEffect(() => {
    if (tab !== "search") return;
    const handle = setTimeout(() => {
      setLoading(true);
      clientFetchCandidates({ search: search || undefined, page: 1, limit: 25 })
        .then(setResults)
        .catch(() => setResults([]))
        .finally(() => setLoading(false));
    }, 250);
    return () => clearTimeout(handle);
  }, [tab, search]);

  async function handleAssign(candidateId: string) {
    setAssigning(candidateId);
    try {
      await assignCandidate(positionId, candidateId);
      setAssignedIds((prev) => new Set(prev).add(candidateId));
      onAssigned();
    } catch {
      // surfaced inline by leaving the row un-assigned
    } finally {
      setAssigning(null);
    }
  }

  function AssignButton({ id }: { id: string }) {
    const done = assignedIds.has(id);
    return (
      <button
        type="button"
        disabled={done || assigning === id}
        onClick={() => handleAssign(id)}
        className="shrink-0 rounded-lg px-2.5 py-1 text-xs font-semibold disabled:opacity-60"
        style={{
          background: done ? "var(--color-canvas-val)" : "var(--color-yellow)",
          color: done ? "var(--color-text-secondary)" : "#002348",
        }}
      >
        {done ? "Added ✓" : assigning === id ? "…" : "Add"}
      </button>
    );
  }

  return (
    <div className="flex h-full w-full max-w-sm flex-col rounded-lg p-4" style={panelStyle}>
      <div className="mb-3 flex items-center justify-between">
        <h3 className="text-sm font-semibold" style={{ color: "var(--color-text-primary)" }}>
          Add Candidates
        </h3>
        <button
          type="button"
          onClick={onClose}
          className="text-xs opacity-60 hover:opacity-100"
          style={{ color: "var(--color-text-secondary)" }}
        >
          Close
        </button>
      </div>

      <div
        className="mb-3 flex gap-1 rounded-lg p-0.5"
        style={{ background: "var(--color-canvas-val)" }}
      >
        {(["suggested", "search"] as Tab[]).map((t) => (
          <button
            key={t}
            type="button"
            onClick={() => setTab(t)}
            className="flex-1 rounded-md px-2 py-1 text-xs font-medium capitalize"
            style={{
              background: tab === t ? "var(--color-surface-val)" : "transparent",
              color: "var(--color-text-primary)",
            }}
          >
            {t}
          </button>
        ))}
      </div>

      {tab === "search" && (
        <input
          type="text"
          placeholder="Search name, email, skill, tag…"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          className="mb-2 rounded-lg px-3 py-1.5 text-sm outline-none"
          style={inputStyle}
        />
      )}

      <div className="flex-1 space-y-2 overflow-y-auto">
        {loading && (
          <p className="py-4 text-center text-xs" style={{ color: "var(--color-text-secondary)" }}>
            Loading…
          </p>
        )}

        {!loading && tab === "suggested" && suggested.length === 0 && (
          <p className="py-4 text-center text-xs" style={{ color: "var(--color-text-secondary)" }}>
            No keyword matches. Try the Search tab.
          </p>
        )}

        {!loading &&
          tab === "suggested" &&
          suggested.map((c) => (
            <div
              key={c.id}
              className="flex items-start justify-between gap-2 rounded-lg p-2"
              style={{ background: "var(--color-canvas-val)" }}
            >
              <div className="min-w-0">
                <div className="flex items-center gap-2">
                  <p
                    className="truncate text-sm font-medium"
                    style={{ color: "var(--color-text-primary)" }}
                  >
                    {c.name}
                  </p>
                  <span className="shrink-0 rounded bg-violet-500/15 px-1.5 py-0.5 text-[10px] font-bold text-violet-400">
                    {Math.round(c.match_score * 100)}%
                  </span>
                </div>
                <SourceChip source={c.source} />
                <Chips items={[...c.tags, ...c.extracted_skills]} />
              </div>
              <AssignButton id={c.id} />
            </div>
          ))}

        {!loading && tab === "search" && results.length === 0 && (
          <p className="py-4 text-center text-xs" style={{ color: "var(--color-text-secondary)" }}>
            No candidates found.
          </p>
        )}

        {!loading &&
          tab === "search" &&
          results.map((c) => (
            <div
              key={c.id}
              className="flex items-start justify-between gap-2 rounded-lg p-2"
              style={{ background: "var(--color-canvas-val)" }}
            >
              <div className="min-w-0">
                <p
                  className="truncate text-sm font-medium"
                  style={{ color: "var(--color-text-primary)" }}
                >
                  {c.name}
                </p>
                <p
                  className="truncate text-[11px]"
                  style={{ color: "var(--color-text-secondary)" }}
                >
                  {c.email}
                </p>
                <SourceChip source={c.source} />
                <Chips items={[...c.tags, ...c.extracted_skills]} />
              </div>
              <AssignButton id={c.id} />
            </div>
          ))}
      </div>
    </div>
  );
}
