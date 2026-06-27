"use client";

import { useState } from "react";
import { IconChevronDown, IconChevronUp } from "@tabler/icons-react";
import type { CandidateFilters, CandidateSource } from "@/types";

interface Props {
  availableTags: string[];
  onFilterChange: (filters: Partial<CandidateFilters>) => void;
}

const inputStyle = {
  background: "var(--color-canvas-val)",
  color: "var(--color-text-primary)",
  border: "1px solid var(--color-border-val)",
};

export default function CandidateFilterBar({ availableTags, onFilterChange }: Props) {
  const [search, setSearch] = useState("");
  const [source, setSource] = useState<CandidateSource | "">("");
  const [selectedTags, setSelectedTags] = useState<string[]>([]);
  const [hasResume, setHasResume] = useState<boolean | undefined>(undefined);
  const [hasCvLink, setHasCvLink] = useState<boolean | undefined>(undefined);
  const [city, setCity] = useState("");
  const [gender, setGender] = useState("");
  const [tagsOpen, setTagsOpen] = useState(false);

  function emit(
    over: Partial<{
      search: string;
      source: CandidateSource | "";
      selectedTags: string[];
      hasResume: boolean | undefined;
      hasCvLink: boolean | undefined;
      city: string;
      gender: string;
    }> = {},
  ) {
    const s = over.search ?? search;
    const src = over.source ?? source;
    const tags = over.selectedTags ?? selectedTags;
    const resume = "hasResume" in over ? over.hasResume : hasResume;
    const cv = "hasCvLink" in over ? over.hasCvLink : hasCvLink;
    const c = over.city ?? city;
    const g = over.gender ?? gender;
    onFilterChange({
      search: s || undefined,
      source: (src as CandidateSource) || undefined,
      tags: tags.length > 0 ? tags : undefined,
      has_resume: resume,
      has_cv_link: cv,
      city: c || undefined,
      gender: g || undefined,
      page: 1,
      limit: 50,
    });
  }

  function toggleTag(tag: string) {
    const next = selectedTags.includes(tag)
      ? selectedTags.filter((t) => t !== tag)
      : [...selectedTags, tag];
    setSelectedTags(next);
    emit({ selectedTags: next });
  }

  function clearAll() {
    setSearch("");
    setSource("");
    setSelectedTags([]);
    setHasResume(undefined);
    setHasCvLink(undefined);
    setCity("");
    setGender("");
    onFilterChange({ page: 1, limit: 50 });
  }

  const hasActive =
    !!search ||
    !!source ||
    selectedTags.length > 0 ||
    hasResume !== undefined ||
    hasCvLink !== undefined ||
    !!city ||
    !!gender;

  return (
    <div
      className="flex flex-wrap items-center gap-3 rounded-lg p-3"
      style={{
        background: "var(--color-surface-val)",
        border: "1px solid var(--color-border-val)",
      }}
    >
      <input
        type="text"
        placeholder="Search name, email, skill, tag…"
        value={search}
        onChange={(e) => {
          setSearch(e.target.value);
          emit({ search: e.target.value });
        }}
        className="min-w-[200px] flex-1 rounded-lg px-3 py-1.5 text-sm outline-none"
        style={inputStyle}
      />

      <select
        value={source}
        onChange={(e) => {
          const v = e.target.value as CandidateSource | "";
          setSource(v);
          emit({ source: v });
        }}
        className="rounded-lg px-3 py-1.5 text-sm outline-none"
        style={inputStyle}
      >
        <option value="">All Sources</option>
        <option value="internal">Internal</option>
        <option value="external">External</option>
      </select>

      <input
        type="text"
        placeholder="City…"
        value={city}
        onChange={(e) => {
          setCity(e.target.value);
          emit({ city: e.target.value });
        }}
        className="w-24 rounded-lg px-3 py-1.5 text-sm outline-none"
        style={inputStyle}
      />

      <select
        value={gender}
        onChange={(e) => {
          const v = e.target.value;
          setGender(v);
          emit({ gender: v });
        }}
        className="rounded-lg px-3 py-1.5 text-sm outline-none"
        style={inputStyle}
      >
        <option value="">All Genders</option>
        <option value="male">Male</option>
        <option value="female">Female</option>
        <option value="other">Other</option>
      </select>

      <div className="relative">
        <button
          type="button"
          onClick={() => setTagsOpen((o) => !o)}
          className="flex items-center gap-1 rounded-lg px-3 py-1.5 text-sm"
          style={{
            ...inputStyle,
            background: selectedTags.length > 0 ? "var(--color-yellow)" : "var(--color-canvas-val)",
            color: selectedTags.length > 0 ? "#002348" : "var(--color-text-primary)",
          }}
        >
          <span>Tags {selectedTags.length > 0 ? `(${selectedTags.length})` : ""}</span>
          {tagsOpen ? (
            <IconChevronUp className="size-4 opacity-50" />
          ) : (
            <IconChevronDown className="size-4 opacity-50" />
          )}
        </button>
        {tagsOpen && (
          <div
            className="absolute top-full z-20 mt-1 max-h-48 min-w-[180px] overflow-y-auto rounded-lg p-2 shadow-xl"
            style={{
              background: "var(--color-surface-val)",
              border: "1px solid var(--color-border-val)",
            }}
          >
            {availableTags.length === 0 && (
              <p className="px-2 py-1 text-xs" style={{ color: "var(--color-text-secondary)" }}>
                No tags yet
              </p>
            )}
            {availableTags.map((tag) => (
              <label
                key={tag}
                className="flex cursor-pointer items-center gap-2 rounded px-2 py-1 hover:bg-white/10"
              >
                <input
                  type="checkbox"
                  checked={selectedTags.includes(tag)}
                  onChange={() => toggleTag(tag)}
                />
                <span className="text-sm" style={{ color: "var(--color-text-primary)" }}>
                  {tag}
                </span>
              </label>
            ))}
          </div>
        )}
      </div>

      <button
        type="button"
        onClick={() => {
          const next = hasResume === true ? undefined : true;
          setHasResume(next);
          emit({ hasResume: next });
        }}
        className="rounded-lg px-3 py-1.5 text-sm"
        style={{ ...inputStyle, opacity: hasResume === true ? 1 : 0.6 }}
      >
        Has Resume
      </button>

      <button
        type="button"
        onClick={() => {
          const next = hasCvLink === true ? undefined : true;
          setHasCvLink(next);
          emit({ hasCvLink: next });
        }}
        className="rounded-lg px-3 py-1.5 text-sm"
        style={{ ...inputStyle, opacity: hasCvLink === true ? 1 : 0.6 }}
      >
        Has CV Link
      </button>

      {hasActive && (
        <button
          type="button"
          onClick={clearAll}
          className="text-sm underline"
          style={{ color: "var(--color-text-secondary)" }}
        >
          Clear all
        </button>
      )}
    </div>
  );
}
