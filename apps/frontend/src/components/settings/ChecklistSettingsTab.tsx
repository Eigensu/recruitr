"use client";

import React, { useEffect, useState } from "react";
import {
  IconChecklist,
  IconPlus,
  IconUsers,
  IconUser,
  IconCalendarEvent,
  IconTrash,
} from "@tabler/icons-react";
import { useApiFetch } from "@/lib/api";
import { useToast } from "@/components/ui/Toast";
import type { UserInfo } from "@/types";
import {
  listTasks,
  createTask,
  deleteTask,
  type TaskResponse,
  type TrackedActivityType,
} from "@/lib/api/tasks";
import { listTeams, listTeamEmployees, type Team, type EmployeeTeamInfo } from "@/lib/api/teams";

interface ChecklistSettingsTabProps {
  readonly user: UserInfo | null;
}

export default function ChecklistSettingsTab({ user }: ChecklistSettingsTabProps) {
  const apiFetch = useApiFetch();
  const toast = useToast();

  const [tasks, setTasks] = useState<TaskResponse[]>([]);
  const [loading, setLoading] = useState(true);
  const [showCreateModal, setShowCreateModal] = useState(false);

  const isMaintainer = user?.role === "admin" || user?.role === "maintainer";

  // Data needed for assignment options
  const [teams, setTeams] = useState<Team[]>([]);
  const [employees, setEmployees] = useState<EmployeeTeamInfo[]>([]);

  useEffect(() => {
    fetchTasks();
    if (isMaintainer) {
      fetchTeamsAndEmployees();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [isMaintainer]);

  async function fetchTasks() {
    try {
      setLoading(true);
      const data = await listTasks(apiFetch);
      setTasks(data);
    } catch {
      toast("Failed to load tasks", "error");
    } finally {
      setLoading(false);
    }
  }

  async function fetchTeamsAndEmployees() {
    try {
      const [t, e] = await Promise.all([listTeams(apiFetch), listTeamEmployees(apiFetch)]);
      setTeams(t);
      setEmployees(e);
    } catch {
      console.error("Failed to fetch");
    }
  }

  const handleDelete = async (taskId: string) => {
    if (!confirm("Are you sure you want to delete this task?")) return;
    try {
      await deleteTask(apiFetch, taskId);
      toast("Task deleted successfully", "success");
      fetchTasks();
    } catch {
      toast("Failed to delete task", "error");
    }
  };

  if (loading) {
    return (
      <div className="p-8 text-center text-text-muted">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary mx-auto mb-4" />
        <p>Loading tasks...</p>
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-6">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-xl font-bold text-text-primary">Checklist</h2>
          <p className="text-sm text-text-muted mt-1">
            {isMaintainer
              ? "Manage and monitor recruitment tasks across your team."
              : "Track your personal recruitment targets and assigned tasks."}
          </p>
        </div>
        {isMaintainer && (
          <button
            onClick={() => setShowCreateModal(true)}
            className="flex items-center gap-2 px-4 py-2 bg-navy text-white dark:bg-yellow dark:text-navy font-semibold text-sm rounded-lg hover:opacity-90 transition-opacity"
          >
            <IconPlus className="w-4 h-4" />
            Create Task
          </button>
        )}
      </div>

      {tasks.length === 0 ? (
        <div className="border border-border rounded-xl bg-surface p-12 text-center flex flex-col items-center">
          <div className="w-16 h-16 rounded-full bg-surface-2 flex items-center justify-center mb-4">
            <IconChecklist className="w-8 h-8 text-text-muted" />
          </div>
          <h3 className="text-lg font-medium text-text-primary">No active tasks</h3>
          <p className="text-sm text-text-muted mt-2 max-w-sm">
            {isMaintainer
              ? "Create a new task to set targets for your recruitment team."
              : "You don't have any assigned tasks right now."}
          </p>
        </div>
      ) : (
        <div className="grid grid-cols-1 gap-4">
          {tasks.map((task) => (
            <TaskCard
              key={task.id}
              task={task}
              isMaintainer={isMaintainer}
              onDelete={() => handleDelete(task.id)}
            />
          ))}
        </div>
      )}

      {showCreateModal && isMaintainer && (
        <CreateTaskModal
          teams={teams}
          employees={employees}
          onClose={() => setShowCreateModal(false)}
          onSuccess={() => {
            setShowCreateModal(false);
            fetchTasks();
          }}
        />
      )}
    </div>
  );
}

// ── TASK CARD ─────────────────────────────────────────────────────────────

function TaskCard({
  task,
  isMaintainer,
  onDelete,
}: {
  readonly task: TaskResponse;
  readonly isMaintainer: boolean;
  readonly onDelete: () => void;
}) {
  const isCompleted = task.completed_count >= task.target_count;
  let assigneeLabel = (
    <>
      <IconUser className="w-3.5 h-3.5" /> Single Assignment
    </>
  );
  if (task.assignee_type === "all") {
    assigneeLabel = (
      <>
        <IconUsers className="w-3.5 h-3.5" /> All Recruiters
      </>
    );
  } else if (task.assignee_type === "team") {
    assigneeLabel = (
      <>
        <IconUsers className="w-3.5 h-3.5" /> Team Task
      </>
    );
  }

  return (
    <div className="border border-border rounded-xl bg-surface overflow-hidden flex flex-col">
      <div className="p-5 flex flex-col gap-4">
        <div className="flex items-start justify-between">
          <div className="flex flex-col gap-1">
            <h3 className="font-semibold text-text-primary text-base flex items-center gap-2">
              {task.title}
              {isCompleted && (
                <span className="text-[10px] uppercase font-bold tracking-wider px-2 py-0.5 rounded-full bg-green-500/20 text-green-500">
                  Completed
                </span>
              )}
            </h3>
            {task.description && <p className="text-sm text-text-muted">{task.description}</p>}
          </div>

          <div className="flex items-center gap-3">
            <div className="flex flex-col items-end text-xs text-text-muted">
              <span className="flex items-center gap-1">
                <IconCalendarEvent className="w-3.5 h-3.5" />
                Due {new Date(task.due_date).toLocaleDateString()}
              </span>
              <span className="flex items-center gap-1 mt-1 opacity-70">{assigneeLabel}</span>
            </div>

            {isMaintainer && (
              <button
                onClick={onDelete}
                className="p-1.5 text-text-muted hover:text-red-500 hover:bg-red-500/10 rounded-md transition-colors"
                title="Delete Task"
              >
                <IconTrash className="w-4 h-4" />
              </button>
            )}
          </div>
        </div>

        {/* Progress Bar (Overall / Own) */}
        <div className="flex flex-col gap-2 mt-2">
          <div className="flex items-center justify-between text-sm">
            <span className="text-text-primary font-medium">
              {task.completed_count} / {task.target_count} completed
            </span>
            <span className="text-text-muted font-medium">{task.progress_percentage}%</span>
          </div>
          <div className="w-full h-2 rounded-full bg-surface-2 overflow-hidden">
            <div
              className={`h-full rounded-full transition-all duration-500 ${isCompleted ? "bg-green-500" : "bg-navy dark:bg-yellow"}`}
              style={{ width: `${Math.min(100, task.progress_percentage)}%` }}
            />
          </div>
        </div>

        {/* Admin Detailed Progress */}
        {isMaintainer && task.detailed_progress && task.detailed_progress.length > 0 && (
          <div className="mt-4 pt-4 border-t border-border flex flex-col gap-3">
            <h4 className="text-xs font-semibold text-text-muted uppercase tracking-wider">
              Team Progress Breakdown
            </h4>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-x-6 gap-y-3">
              {task.detailed_progress.map((rp) => (
                <div key={rp.employee_id} className="flex items-center justify-between text-sm">
                  <span className="text-text-primary truncate pr-4">{rp.name}</span>
                  <div className="flex items-center gap-3 shrink-0">
                    <span className="text-text-muted tabular-nums">
                      {rp.completed_count}/{task.target_count}
                    </span>
                    <div className="w-16 h-1.5 rounded-full bg-surface-2 overflow-hidden">
                      <div
                        className={`h-full rounded-full ${rp.progress_percentage >= 100 ? "bg-green-500" : "bg-primary"}`}
                        style={{ width: `${Math.min(100, rp.progress_percentage)}%` }}
                      />
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

// ── CREATE TASK MODAL ──────────────────────────────────────────────────────

function CreateTaskModal({
  teams,
  employees,
  onClose,
  onSuccess,
}: {
  readonly teams: Team[];
  readonly employees: EmployeeTeamInfo[];
  readonly onClose: () => void;
  readonly onSuccess: () => void;
}) {
  const apiFetch = useApiFetch();
  const toast = useToast();

  const [submitting, setSubmitting] = useState(false);
  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");
  const [targetCount, setTargetCount] = useState("5");
  const [trackedActivity, setTrackedActivity] = useState<TrackedActivityType>("mapped");
  const [assigneeType, setAssigneeType] = useState<"single" | "team" | "all">("all");
  const [assigneeId, setAssigneeId] = useState("");

  const today = new Date().toISOString().split("T")[0];
  const [dueDate, setDueDate] = useState(today);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!title || !targetCount || !dueDate) return;
    if ((assigneeType === "single" || assigneeType === "team") && !assigneeId) {
      toast("Please select an assignee", "error");
      return;
    }

    try {
      setSubmitting(true);
      // Start of day today, due date at end of day
      const startObj = new Date();
      startObj.setHours(0, 0, 0, 0);

      const dueObj = new Date(dueDate);
      dueObj.setHours(23, 59, 59, 999);

      await createTask(apiFetch, {
        title,
        description: description || undefined,
        tracked_activity_type: trackedActivity,
        target_count: Number.parseInt(targetCount, 10),
        assignee_type: assigneeType,
        assignee_id: assigneeType === "all" ? undefined : assigneeId,
        start_date: startObj.toISOString(),
        due_date: dueObj.toISOString(),
      });

      toast("Task created successfully", "success");
      onSuccess();
    } catch {
      toast("Failed to create task", "error");
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60 backdrop-blur-sm">
      <div className="bg-surface border border-border rounded-xl shadow-xl w-full max-w-lg overflow-hidden flex flex-col max-h-[90vh]">
        <div className="px-6 py-4 border-b border-border flex items-center justify-between bg-surface-2">
          <h2 className="text-lg font-bold text-text-primary">Create New Task</h2>
          <button onClick={onClose} className="text-text-muted hover:text-text-primary text-xl">
            &times;
          </button>
        </div>

        <form onSubmit={handleSubmit} className="flex flex-col overflow-y-auto p-6 gap-5">
          <div className="flex flex-col gap-1.5">
            <label htmlFor="task-title" className="text-sm font-medium text-text-primary">
              Task Title
            </label>
            <input
              type="text"
              required
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              placeholder="e.g. Map 4 candidates today"
              className="w-full px-3 py-2 bg-surface border border-border rounded-lg text-sm text-text-primary focus:outline-none focus:border-primary"
            />
          </div>

          <div className="flex flex-col gap-1.5">
            <label htmlFor="task-description" className="text-sm font-medium text-text-primary">
              Description (Optional)
            </label>
            <textarea
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              id="task-description"
              placeholder="Any additional instructions..."
              rows={2}
              className="w-full px-3 py-2 bg-surface border border-border rounded-lg text-sm text-text-primary focus:outline-none focus:border-primary resize-none"
            />
          </div>

          <div className="flex flex-col gap-1.5">
            <label htmlFor="task-activity" className="text-sm font-medium text-text-primary">
              Activity to Track
            </label>
            <select
              value={trackedActivity}
              onChange={(e) => setTrackedActivity(e.target.value as TrackedActivityType)}
              className="w-full px-3 py-2 bg-surface border border-border rounded-lg text-sm text-text-primary focus:outline-none focus:border-primary"
            >
              <option value="mapped">Candidate Mapped</option>
              <option value="stage_moved">Candidate Moved</option>
              <option value="rejected">Candidate Rejected</option>
              <option value="joined">Candidate Joined</option>
              <option value="offer_accepted">Offer Accepted</option>
              <option value="offer_sent">Offer Sent</option>
              <option value="unmapped">Candidate Unmapped</option>
            </select>
          </div>

          <div className="grid grid-cols-2 gap-4">
            <div className="flex flex-col gap-1.5">
              <label htmlFor="task-target-count" className="text-sm font-medium text-text-primary">
                Target Count
              </label>
              <input
                type="number"
                id="task-target-count"
                min="1"
                required
                value={targetCount}
                onChange={(e) => setTargetCount(e.target.value)}
                className="w-full px-3 py-2 bg-surface border border-border rounded-lg text-sm text-text-primary focus:outline-none focus:border-primary"
              />
            </div>
            <div className="flex flex-col gap-1.5">
              <label htmlFor="task-due-date" className="text-sm font-medium text-text-primary">
                Due Date
              </label>
              <input
                id="task-due-date"
                type="date"
                required
                min={today}
                value={dueDate}
                onChange={(e) => setDueDate(e.target.value)}
                className="w-full px-3 py-2 bg-surface border border-border rounded-lg text-sm text-text-primary focus:outline-none focus:border-primary"
              />
            </div>
          </div>

          <div className="flex flex-col gap-1.5 border-t border-border pt-5">
            <label htmlFor="task-assignment" className="text-sm font-medium text-text-primary">
              Assignment
            </label>
            <select
              value={assigneeType}
              onChange={(e) => {
                setAssigneeType(e.target.value as "single" | "team" | "all");
                setAssigneeId("");
              }}
              className="w-full px-3 py-2 bg-surface border border-border rounded-lg text-sm text-text-primary focus:outline-none focus:border-primary"
            >
              <option value="all">All Recruiters</option>
              <option value="team">Specific Team</option>
              <option value="single">Single Recruiter</option>
            </select>
          </div>

          {assigneeType === "team" && (
            <div className="flex flex-col gap-1.5">
              <label htmlFor="task-team" className="text-sm font-medium text-text-primary">
                Select Team
              </label>
              <select
                required
                value={assigneeId}
                onChange={(e) => setAssigneeId(e.target.value)}
                className="w-full px-3 py-2 bg-surface border border-border rounded-lg text-sm text-text-primary focus:outline-none focus:border-primary"
              >
                <option value="">-- Choose a Team --</option>
                {teams.map((t) => (
                  <option key={t.id} value={t.id}>
                    {t.name}
                  </option>
                ))}
              </select>
            </div>
          )}

          {assigneeType === "single" && (
            <div className="flex flex-col gap-1.5">
              <label htmlFor="task-recruiter" className="text-sm font-medium text-text-primary">
                Select Recruiter
              </label>
              <select
                required
                value={assigneeId}
                onChange={(e) => setAssigneeId(e.target.value)}
                className="w-full px-3 py-2 bg-surface border border-border rounded-lg text-sm text-text-primary focus:outline-none focus:border-primary"
              >
                <option value="">-- Choose a Recruiter --</option>
                {employees.map((e) => (
                  <option key={e.id} value={e.id}>
                    {e.name}
                  </option>
                ))}
              </select>
            </div>
          )}

          <div className="flex justify-end gap-3 mt-4">
            <button
              type="button"
              onClick={onClose}
              disabled={submitting}
              className="px-4 py-2 text-sm font-medium text-text-muted hover:text-text-primary"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={submitting}
              className="px-4 py-2 bg-navy text-white dark:bg-yellow dark:text-navy text-sm font-bold rounded-lg disabled:opacity-50"
            >
              {submitting ? "Creating..." : "Create Task"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
