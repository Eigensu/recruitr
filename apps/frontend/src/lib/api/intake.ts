/**
 * The inbound lead pipeline: a telecaller's queue, the admin list, and the
 * observability behind both.
 *
 * Types mirror `app/modules/recruitment/schemas/intake.py`. Rates come back as
 * 0–1 proportions and may be null, which means "no decisions yet" rather than
 * zero — see `formatRate` for why that distinction is kept all the way to the
 * screen.
 */

type ApiFetch = <T>(path: string, options?: RequestInit) => Promise<T>;

export type IntakeLeadStatus =
  | "pending_telecaller"
  | "unassigned"
  | "rejected"
  | "pending_recruiter"
  | "actioned"
  | "duplicate";

export type IntakeDecision = "accept" | "reject";

export type IntakeRejectReason =
  | "wrong_number"
  | "not_reachable"
  | "not_interested"
  | "not_eligible"
  | "duplicate"
  | "other";

export interface IntakeLead {
  id: string;
  status: IntakeLeadStatus;
  candidate_id: string;
  full_name: string;
  phone: string | null;
  email: string | null;
  city: string | null;
  current_role: string | null;
  experience_years: number;
  role_interest: string | null;
  education: string | null;
  source_channel: string | null;
  campaign_name: string | null;
  external_created_at: string | null;
  ingested_at: string;
  telecaller_id: string | null;
  telecaller_assigned_at: string | null;
  telecaller_actioned_at: string | null;
  telecaller_decision: IntakeDecision | null;
  telecaller_reject_reason: IntakeRejectReason | null;
  telecaller_notes: string | null;
  telecaller_response_seconds: number | null;
  recruiter_id: string | null;
  recruiter_assigned_at: string | null;
  recruiter_actioned_at: string | null;
  recruiter_response_seconds: number | null;
  reassignment_count: number;
  telecaller_name: string | null;
  recruiter_name: string | null;
  overdue: boolean;
}

export interface IntakeLegStats {
  assigned: number;
  actioned: number;
  pending: number;
  overdue: number;
  avg_hours: number | null;
  median_hours: number | null;
  p90_hours: number | null;
  within_sla: number;
  sla_hours: number;
  sla_compliance: number | null;
  oldest_pending_hours: number | null;
  accepted: number | null;
  rejected: number | null;
  accept_rate: number | null;
}

export interface IntakePersonStats extends IntakeLegStats {
  employee_id: string | null;
  name: string;
  email: string | null;
}

export interface IntakeFunnel {
  ingested: number;
  pending_telecaller: number;
  unassigned: number;
  rejected: number;
  pending_recruiter: number;
  actioned: number;
  duplicate: number;
}

export interface IntakeOverview {
  start_date: string | null;
  end_date: string | null;
  funnel: IntakeFunnel;
  telecaller: IntakeLegStats;
  recruiter: IntakeLegStats;
  reject_reasons: { reason: string; count: number }[];
  source: {
    configured: boolean;
    enabled: boolean;
    last_synced_at: string | null;
    last_success_at: string | null;
    last_error: string | null;
    consecutive_failures: number;
  };
}

export type IntakeCampaignGroup = "campaign" | "ad" | "form" | "channel";

export interface IntakeCampaignRow {
  label: string;
  leads: number;
  accepted: number;
  rejected: number;
  actioned: number;
  duplicate: number;
  accept_rate: number | null;
  actioned_rate: number | null;
}

export interface IntakeLeadPage {
  items: IntakeLead[];
  meta: {
    page: number;
    limit: number;
    total: number;
    pages: number;
    has_next: boolean;
    has_prev: boolean;
  };
}

export interface IntakeConfig {
  configured: boolean;
  brand_id: string | null;
  spreadsheet_id: string;
  sheet_range: string;
  default_source_channel: string;
  enabled: boolean;
  activated_at: string | null;
  last_synced_at: string | null;
  last_success_at: string | null;
  last_row_count: number;
  last_ingested_count: number;
  last_skipped_count: number;
  last_error: string | null;
  consecutive_failures: number;
  credentials_configured: boolean;
  poll_minutes: number;
  telecaller_sla_hours: number;
  recruiter_sla_hours: number;
}

export interface IntakeSyncResult {
  ran: boolean;
  detail: string;
  created: number;
  matched_existing: number;
  already_ingested: number;
  unusable: number;
}

export interface IntakeLeadFilters {
  status?: string;
  telecaller_id?: string;
  recruiter_id?: string;
  campaign?: string;
  overdue?: boolean;
  start_date?: string;
  end_date?: string;
  page?: number;
  limit?: number;
}

function query(params: Record<string, string | number | boolean | undefined>): string {
  const q = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    if (value !== undefined && value !== "" && value !== false) q.set(key, String(value));
  }
  const s = q.toString();
  return s ? `?${s}` : "";
}

// ── The telecaller's queue ─────────────────────────────────────────────────────

export function fetchMyLeads(apiFetch: ApiFetch, includeActioned = false): Promise<IntakeLead[]> {
  return apiFetch<IntakeLead[]>(
    `/api/v1/intake/leads/mine${query({ include_actioned: includeActioned })}`,
  );
}

export function acceptLead(apiFetch: ApiFetch, id: string, notes?: string): Promise<IntakeLead> {
  return apiFetch<IntakeLead>(`/api/v1/intake/leads/${id}/accept`, {
    method: "POST",
    body: JSON.stringify({ notes: notes || null }),
  });
}

export function rejectLead(
  apiFetch: ApiFetch,
  id: string,
  reason?: IntakeRejectReason,
  notes?: string,
): Promise<IntakeLead> {
  return apiFetch<IntakeLead>(`/api/v1/intake/leads/${id}/reject`, {
    method: "POST",
    body: JSON.stringify({ reason: reason ?? null, notes: notes || null }),
  });
}

// ── Management ────────────────────────────────────────────────────────────────

export function fetchLeads(
  apiFetch: ApiFetch,
  filters: IntakeLeadFilters,
): Promise<IntakeLeadPage> {
  return apiFetch<IntakeLeadPage>(`/api/v1/intake/leads${query({ ...filters })}`);
}

export function fetchLead(apiFetch: ApiFetch, id: string): Promise<IntakeLead> {
  return apiFetch<IntakeLead>(`/api/v1/intake/leads/${id}`);
}

export function reassignLead(
  apiFetch: ApiFetch,
  id: string,
  employeeId: string,
): Promise<IntakeLead> {
  return apiFetch<IntakeLead>(`/api/v1/intake/leads/${id}/reassign`, {
    method: "POST",
    body: JSON.stringify({ employee_id: employeeId }),
  });
}

export interface IntakeAssignee {
  id: string;
  name: string;
  email: string | null;
  open_leads: number;
}

export function fetchAssignees(
  apiFetch: ApiFetch,
): Promise<{ telecallers: IntakeAssignee[]; recruiters: IntakeAssignee[] }> {
  return apiFetch("/api/v1/intake/assignees");
}

export function syncNow(apiFetch: ApiFetch): Promise<IntakeSyncResult> {
  return apiFetch<IntakeSyncResult>("/api/v1/intake/sync", { method: "POST" });
}

// ── Observability ─────────────────────────────────────────────────────────────

interface Window {
  start_date?: string;
  end_date?: string;
}

export function fetchOverview(apiFetch: ApiFetch, window: Window = {}): Promise<IntakeOverview> {
  return apiFetch<IntakeOverview>(`/api/v1/intake/analytics/overview${query({ ...window })}`);
}

export function fetchTelecallerStats(
  apiFetch: ApiFetch,
  window: Window = {},
): Promise<IntakePersonStats[]> {
  return apiFetch<IntakePersonStats[]>(
    `/api/v1/intake/analytics/telecallers${query({ ...window })}`,
  );
}

export function fetchRecruiterStats(
  apiFetch: ApiFetch,
  window: Window = {},
): Promise<IntakePersonStats[]> {
  return apiFetch<IntakePersonStats[]>(
    `/api/v1/intake/analytics/recruiters${query({ ...window })}`,
  );
}

export function fetchCampaigns(
  apiFetch: ApiFetch,
  groupBy: IntakeCampaignGroup,
  window: Window = {},
): Promise<{ group_by: string; rows: IntakeCampaignRow[] }> {
  return apiFetch(`/api/v1/intake/analytics/campaigns${query({ group_by: groupBy, ...window })}`);
}

export function fetchIntakeConfig(apiFetch: ApiFetch): Promise<IntakeConfig> {
  return apiFetch<IntakeConfig>("/api/v1/intake/config");
}

export function updateIntakeConfig(
  apiFetch: ApiFetch,
  payload: Partial<Pick<IntakeConfig, "spreadsheet_id" | "sheet_range" | "enabled">>,
): Promise<IntakeConfig> {
  return apiFetch<IntakeConfig>("/api/v1/intake/config", {
    method: "PUT",
    body: JSON.stringify(payload),
  });
}

// ── Display helpers ───────────────────────────────────────────────────────────

export const REJECT_REASON_LABELS: Record<IntakeRejectReason, string> = {
  wrong_number: "Wrong number",
  not_reachable: "Not reachable",
  not_interested: "Not interested",
  not_eligible: "Not eligible",
  duplicate: "Already in the system",
  other: "Other",
};

export const STATUS_LABELS: Record<IntakeLeadStatus, string> = {
  pending_telecaller: "Awaiting call",
  unassigned: "Unassigned",
  rejected: "Rejected",
  pending_recruiter: "With recruiter",
  actioned: "Actioned",
  duplicate: "Duplicate",
};

export const STATUS_STYLES: Record<IntakeLeadStatus, string> = {
  pending_telecaller: "bg-yellow/10 text-yellow border-yellow/20",
  unassigned: "bg-orange-500/10 text-orange-400 border-orange-500/20",
  rejected: "bg-red-500/10 text-red-400 border-red-500/20",
  pending_recruiter: "bg-blue-500/10 text-blue-400 border-blue-500/20",
  actioned: "bg-emerald-500/10 text-emerald-400 border-emerald-500/20",
  duplicate: "bg-surface-panel text-text-muted border-border",
};

/**
 * A 0–1 proportion as a percentage, or an em dash when it is null.
 *
 * Null is not zero: a telecaller who has not actioned anything yet has an
 * unknown accept rate, and printing "0%" would read as someone who rejects
 * everybody. The backend is careful to distinguish the two, so the UI is too.
 */
export function formatRate(rate: number | null): string {
  return rate === null ? "—" : `${Math.round(rate * 100)}%`;
}

/** Hours as something readable at a glance: "4h", "1d 6h", "—". */
export function formatHours(hours: number | null): string {
  if (hours === null) return "—";
  if (hours < 1) return `${Math.round(hours * 60)}m`;
  if (hours < 24) return `${Math.round(hours)}h`;
  const days = Math.floor(hours / 24);
  const rest = Math.round(hours % 24);
  return rest ? `${days}d ${rest}h` : `${days}d`;
}

/**
 * How long a lead has been waiting, in hours, or null if never assigned.
 *
 * The UI reports elapsed time and takes `lead.overdue` from the server rather
 * than recomputing "time left" against its own copy of the SLA limit. The limit
 * is configuration; a stale copy in the browser would disagree with the alerts
 * and the reports, and the one place that must not be ambiguous is whether
 * somebody is late.
 */
export function elapsedHours(assignedAt: string | null): number | null {
  if (!assignedAt) return null;
  return (Date.now() - new Date(assignedAt).getTime()) / 3_600_000;
}
