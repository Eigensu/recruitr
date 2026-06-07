"use client";

import React, { useEffect, useState } from "react";
import { IconPlus, IconTag, IconUsers, IconTrash } from "@tabler/icons-react";
import { useApiFetch } from "@/lib/api";
import { listTeams, createTeam, type Team } from "@/lib/api/teams";
import { listTags, createTag, type RecruiterTag } from "@/lib/api/tags";

export default function TeamSettingsTab() {
  const apiFetch = useApiFetch();

  const [teams, setTeams] = useState<Team[]>([]);
  const [tags, setTags] = useState<RecruiterTag[]>([]);
  const [isLoading, setIsLoading] = useState(true);

  const [newTeamName, setNewTeamName] = useState("");
  const [newTagName, setNewTagName] = useState("");

  useEffect(() => {
    async function load() {
      setIsLoading(true);
      try {
        const [teamsData, tagsData] = await Promise.all([listTeams(apiFetch), listTags(apiFetch)]);
        setTeams(teamsData);
        setTags(tagsData);
      } catch (err) {
        console.error("Failed to load team data:", err);
      } finally {
        setIsLoading(false);
      }
    }
    load();
  }, [apiFetch]);

  async function handleAddTeam(e: React.FormEvent) {
    e.preventDefault();
    if (!newTeamName.trim()) return;
    try {
      const created = await createTeam(apiFetch, newTeamName.trim());
      setTeams((prev) => [...prev, created]);
      setNewTeamName("");
    } catch (err) {
      console.error("Failed to create team:", err);
    }
  }

  async function handleAddTag(e: React.FormEvent) {
    e.preventDefault();
    if (!newTagName.trim()) return;
    try {
      const created = await createTag(apiFetch, newTagName.trim());
      setTags((prev) => [...prev, created]);
      setNewTagName("");
    } catch (err) {
      console.error("Failed to create tag:", err);
    }
  }

  if (isLoading) {
    return (
      <div className="py-12 flex justify-center text-text-muted">Loading team settings...</div>
    );
  }

  return (
    <div className="space-y-8 animate-in fade-in duration-300">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h2 className="text-lg font-bold text-text-primary">Team Management</h2>
          <p className="text-sm text-text-secondary mt-1">
            Manage your recruitment teams and tags for candidates.
          </p>
        </div>
      </div>

      {/* Teams Section */}
      <div className="divide-y divide-border border-y border-border">
        <div className="py-6 items-start md:items-center">
          <h3 className="text-md font-medium text-text-primary flex items-center gap-2 mb-4">
            <IconUsers className="w-5 h-5" /> Teams
          </h3>
          <div className="flex flex-col md:flex-row gap-6">
            <div className="w-full md:w-1/3">
              <form onSubmit={handleAddTeam} className="flex flex-col gap-2">
                <input
                  type="text"
                  placeholder="New team name..."
                  value={newTeamName}
                  onChange={(e) => setNewTeamName(e.target.value)}
                  className="w-full px-3 py-2 rounded-lg border border-border bg-surface text-text-primary focus:outline-none focus:ring-2 focus:ring-navy transition-shadow"
                />
                <button
                  type="submit"
                  disabled={!newTeamName.trim()}
                  className="flex items-center justify-center gap-2 px-4 py-2 rounded-lg bg-navy dark:bg-yellow dark:text-navy text-white hover:opacity-90 disabled:opacity-50 transition-colors font-medium text-sm"
                >
                  <IconPlus className="w-4 h-4" /> Add Team
                </button>
              </form>
            </div>
            <div className="w-full md:w-2/3 border border-border rounded-lg bg-surface divide-y divide-border overflow-hidden">
              {teams.length === 0 ? (
                <div className="p-4 text-center text-sm text-text-muted">No teams created yet.</div>
              ) : (
                teams.map((team) => (
                  <div key={team.id} className="p-3 px-4 flex items-center justify-between">
                    <span className="text-sm font-medium text-text-primary">{team.name}</span>
                  </div>
                ))
              )}
            </div>
          </div>
        </div>

        {/* Tags Section */}
        <div className="py-6 items-start md:items-center">
          <h3 className="text-md font-medium text-text-primary flex items-center gap-2 mb-4">
            <IconTag className="w-5 h-5" /> Recruiter Tags
          </h3>
          <p className="text-sm text-text-secondary mb-4">
            Predefined tags that recruiters can attach to candidates.
          </p>
          <div className="flex flex-col md:flex-row gap-6">
            <div className="w-full md:w-1/3">
              <form onSubmit={handleAddTag} className="flex flex-col gap-2">
                <input
                  type="text"
                  placeholder="New tag name..."
                  value={newTagName}
                  onChange={(e) => setNewTagName(e.target.value)}
                  className="w-full px-3 py-2 rounded-lg border border-border bg-surface text-text-primary focus:outline-none focus:ring-2 focus:ring-navy transition-shadow"
                />
                <button
                  type="submit"
                  disabled={!newTagName.trim()}
                  className="flex items-center justify-center gap-2 px-4 py-2 rounded-lg bg-navy dark:bg-yellow dark:text-navy text-white hover:opacity-90 disabled:opacity-50 transition-colors font-medium text-sm"
                >
                  <IconPlus className="w-4 h-4" /> Add Tag
                </button>
              </form>
            </div>
            <div className="w-full md:w-2/3">
              <div className="flex flex-wrap gap-2">
                {tags.length === 0 ? (
                  <div className="p-4 w-full text-center border border-dashed border-border rounded-lg text-sm text-text-muted">
                    No predefined tags.
                  </div>
                ) : (
                  tags.map((tag) => (
                    <div
                      key={tag.id}
                      className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full bg-surface border border-border text-xs font-medium text-text-primary"
                    >
                      {tag.name}
                    </div>
                  ))
                )}
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
