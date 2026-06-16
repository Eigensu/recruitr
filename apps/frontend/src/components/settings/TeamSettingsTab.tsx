"use client";

import React, { useEffect, useState } from "react";
import {
  IconPlus,
  IconTag,
  IconUsers,
  IconTrash,
  IconUserCheck,
  IconPencil,
  IconCheck,
  IconX,
} from "@tabler/icons-react";
import { useApiFetch } from "@/lib/api";
import {
  listTeams,
  createTeam,
  updateTeam,
  listTeamEmployees,
  assignEmployeesToTeam,
  type Team,
  type EmployeeTeamInfo,
} from "@/lib/api/teams";
import { listTags, createTag, type RecruiterTag } from "@/lib/api/tags";

export default function TeamSettingsTab() {
  const apiFetch = useApiFetch();

  const [teams, setTeams] = useState<Team[]>([]);
  const [tags, setTags] = useState<RecruiterTag[]>([]);
  const [employees, setEmployees] = useState<EmployeeTeamInfo[]>([]);
  const [isLoading, setIsLoading] = useState(true);

  const [newTeamName, setNewTeamName] = useState("");
  const [newTagName, setNewTagName] = useState("");

  const [editingTeamId, setEditingTeamId] = useState<string | null>(null);
  const [editingName, setEditingName] = useState("");

  const [selectedEmployees, setSelectedEmployees] = useState<Set<string>>(new Set());
  const [targetTeamId, setTargetTeamId] = useState<string>("");

  useEffect(() => {
    async function load() {
      setIsLoading(true);
      try {
        const [teamsData, tagsData, employeesData] = await Promise.all([
          listTeams(apiFetch),
          listTags(apiFetch),
          listTeamEmployees(apiFetch),
        ]);
        setTeams(teamsData);
        setTags(tagsData);
        setEmployees(employeesData);
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

  function startEditTeam(team: Team) {
    setEditingTeamId(team.id);
    setEditingName(team.name);
  }

  function cancelEditTeam() {
    setEditingTeamId(null);
    setEditingName("");
  }

  async function handleRenameTeam(teamId: string) {
    const name = editingName.trim();
    if (!name) return;
    try {
      const updated = await updateTeam(apiFetch, teamId, { name });
      setTeams((prev) => prev.map((t) => (t.id === teamId ? updated : t)));
      cancelEditTeam();
    } catch (err) {
      console.error("Failed to rename team:", err);
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

  function handleToggleSelect(empId: string) {
    setSelectedEmployees((prev) => {
      const next = new Set(prev);
      if (next.has(empId)) {
        next.delete(empId);
      } else {
        next.add(empId);
      }
      return next;
    });
  }

  function handleToggleSelectAll() {
    if (selectedEmployees.size === employees.length) {
      setSelectedEmployees(new Set());
    } else {
      setSelectedEmployees(new Set(employees.map((e) => e.id)));
    }
  }

  async function handleBulkAssign(e: React.FormEvent) {
    e.preventDefault();
    if (selectedEmployees.size === 0) return;
    const empIds = Array.from(selectedEmployees);
    const teamId = targetTeamId === "" ? null : targetTeamId;
    try {
      await assignEmployeesToTeam(apiFetch, empIds, teamId);
      // Refresh employees list
      const employeesData = await listTeamEmployees(apiFetch);
      setEmployees(employeesData);
      setSelectedEmployees(new Set());
    } catch (err) {
      console.error("Failed to assign employees to team:", err);
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
            Manage your recruitment teams, recruiter assignments, and candidate tags.
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
                  className="flex items-center justify-center gap-2 px-4 py-2 rounded-lg bg-navy dark:bg-yellow dark:text-navy text-white hover:opacity-90 disabled:opacity-50 transition-colors font-medium text-sm cursor-pointer"
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
                  <div key={team.id} className="p-3 px-4 flex items-center justify-between gap-2">
                    {editingTeamId === team.id ? (
                      <>
                        <input
                          type="text"
                          autoFocus
                          value={editingName}
                          onChange={(e) => setEditingName(e.target.value)}
                          onKeyDown={(e) => {
                            if (e.key === "Enter") handleRenameTeam(team.id);
                            if (e.key === "Escape") cancelEditTeam();
                          }}
                          className="flex-1 px-2 py-1 rounded-md border border-border bg-canvas text-text-primary text-sm focus:outline-none focus:ring-2 focus:ring-navy"
                        />
                        <button
                          type="button"
                          onClick={() => handleRenameTeam(team.id)}
                          disabled={!editingName.trim()}
                          className="p-1 rounded-md text-green-600 hover:bg-surface-2 disabled:opacity-40 cursor-pointer"
                          aria-label="Save team name"
                        >
                          <IconCheck className="w-4 h-4" />
                        </button>
                        <button
                          type="button"
                          onClick={cancelEditTeam}
                          className="p-1 rounded-md text-text-muted hover:bg-surface-2 cursor-pointer"
                          aria-label="Cancel"
                        >
                          <IconX className="w-4 h-4" />
                        </button>
                      </>
                    ) : (
                      <>
                        <span className="text-sm font-medium text-text-primary">{team.name}</span>
                        <button
                          type="button"
                          onClick={() => startEditTeam(team)}
                          className="p-1 rounded-md text-text-muted hover:bg-surface-2 hover:text-text-primary cursor-pointer"
                          aria-label="Edit team"
                        >
                          <IconPencil className="w-4 h-4" />
                        </button>
                      </>
                    )}
                  </div>
                ))
              )}
            </div>
          </div>
        </div>

        {/* Recruiters Assignment Section */}
        <div className="py-6">
          <h3 className="text-md font-medium text-text-primary flex items-center gap-2 mb-2">
            <IconUserCheck className="w-5 h-5" /> Assign Recruiters to Teams
          </h3>
          <p className="text-sm text-text-secondary mb-4">
            Select one or more recruiters below and assign them to a team in bulk.
          </p>

          <div className="flex flex-col md:flex-row gap-6">
            {/* Assignment Form */}
            <div className="w-full md:w-1/3">
              <form
                onSubmit={handleBulkAssign}
                className="flex flex-col gap-3 p-4 border border-border rounded-lg bg-surface"
              >
                <div>
                  <label
                    htmlFor="target-team"
                    className="text-xs font-semibold text-text-secondary uppercase tracking-wider block mb-1"
                  >
                    Select Target Team
                  </label>
                  <select
                    id="target-team"
                    value={targetTeamId}
                    onChange={(e) => setTargetTeamId(e.target.value)}
                    className="w-full px-3 py-2 rounded-lg border border-border bg-canvas text-text-primary focus:outline-none focus:ring-2 focus:ring-navy transition-shadow text-sm"
                  >
                    <option value="">-- No Team (Unassign) --</option>
                    {teams.map((t) => (
                      <option key={t.id} value={t.id}>
                        {t.name}
                      </option>
                    ))}
                  </select>
                </div>

                <button
                  type="submit"
                  disabled={selectedEmployees.size === 0}
                  className="w-full flex items-center justify-center gap-2 px-4 py-2 rounded-lg bg-navy dark:bg-yellow dark:text-navy text-white hover:opacity-90 disabled:opacity-50 transition-colors font-medium text-sm cursor-pointer"
                >
                  Assign {selectedEmployees.size > 0 ? `(${selectedEmployees.size})` : ""}
                </button>
              </form>
            </div>

            {/* Recruiters List */}
            <div className="w-full md:w-2/3 border border-border rounded-lg bg-surface overflow-hidden">
              <div className="bg-surface-2 p-3 px-4 flex items-center justify-between border-b border-border">
                <label className="flex items-center gap-3 text-sm font-medium text-text-primary cursor-pointer select-none">
                  <input
                    type="checkbox"
                    checked={employees.length > 0 && selectedEmployees.size === employees.length}
                    onChange={handleToggleSelectAll}
                    disabled={employees.length === 0}
                    className="rounded border-border text-navy focus:ring-navy w-4 h-4"
                  />
                  <span>Select All Recruiters</span>
                </label>
                <span className="text-xs font-semibold text-text-secondary uppercase tracking-wider">
                  Total: {employees.length}
                </span>
              </div>

              <div className="divide-y divide-border max-h-[300px] overflow-y-auto">
                {employees.length === 0 ? (
                  <div className="p-8 text-center text-sm text-text-muted">
                    No recruiters found.
                  </div>
                ) : (
                  employees.map((emp) => {
                    const matchedTeam = teams.find((t) => t.id === emp.team_id);
                    return (
                      <div
                        key={emp.id}
                        className={`p-3 px-4 flex items-center justify-between hover:bg-surface-2 transition-colors ${
                          selectedEmployees.has(emp.id) ? "bg-surface-2" : ""
                        }`}
                      >
                        <div className="flex items-center gap-3">
                          <input
                            type="checkbox"
                            checked={selectedEmployees.has(emp.id)}
                            onChange={() => handleToggleSelect(emp.id)}
                            className="rounded border-border text-navy focus:ring-navy w-4 h-4 cursor-pointer"
                          />
                          <div className="flex flex-col">
                            <span className="text-sm font-medium text-text-primary">
                              {emp.name}
                            </span>
                            <span className="text-xs text-text-secondary">{emp.email}</span>
                          </div>
                        </div>

                        {matchedTeam ? (
                          <span className="px-2.5 py-0.5 rounded-full bg-green-100 text-green-800 dark:bg-green-950/40 dark:text-green-400 text-xs font-semibold border border-green-200 dark:border-green-900/60">
                            {matchedTeam.name}
                          </span>
                        ) : (
                          <span className="px-2.5 py-0.5 rounded-full bg-canvas text-text-secondary text-xs font-semibold border border-border">
                            No Team
                          </span>
                        )}
                      </div>
                    );
                  })
                )}
              </div>
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
                  className="flex items-center justify-center gap-2 px-4 py-2 rounded-lg bg-navy dark:bg-yellow dark:text-navy text-white hover:opacity-90 disabled:opacity-50 transition-colors font-medium text-sm cursor-pointer"
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
