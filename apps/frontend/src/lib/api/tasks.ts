type ApiFetch = <T>(path: string, options?: RequestInit) => Promise<T>;

export type TaskAssignmentType = "single" | "team" | "all";
export type TrackedActivityType =
  | "mapped"
  | "stage_moved"
  | "offer_sent"
  | "offer_accepted"
  | "joined"
  | "rejected"
  | "unmapped";

export interface RecruiterProgress {
  employee_id: string;
  name: string;
  completed_count: number;
  progress_percentage: number;
}

export interface TaskResponse {
  id: string;
  title: string;
  description: string | null;
  tracked_activity_type: TrackedActivityType;
  target_count: number;
  assignee_type: TaskAssignmentType;
  assignee_id: string | null;
  start_date: string;
  due_date: string;
  is_active: boolean;
  created_at: string;
  completed_count: number;
  progress_percentage: number;
  detailed_progress: RecruiterProgress[] | null;
}

export interface TaskCreatePayload {
  title: string;
  description?: string;
  tracked_activity_type: TrackedActivityType;
  target_count: number;
  assignee_type: TaskAssignmentType;
  assignee_id?: string;
  start_date: string;
  due_date: string;
}

export async function listTasks(apiFetch: ApiFetch): Promise<TaskResponse[]> {
  return await apiFetch<TaskResponse[]>("/api/v1/tasks/");
}

export async function createTask(
  apiFetch: ApiFetch,
  payload: TaskCreatePayload,
): Promise<TaskResponse> {
  return await apiFetch<TaskResponse>("/api/v1/tasks/", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
}

export async function deleteTask(apiFetch: ApiFetch, taskId: string): Promise<void> {
  await apiFetch<void>(`/api/v1/tasks/${taskId}`, { method: "DELETE" });
}
