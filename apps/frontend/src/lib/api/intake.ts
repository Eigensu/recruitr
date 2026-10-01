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
  | "pending_review"
  | "pending_recruiter"
  | "actioned"
  | "duplicate";

export type IntakeSource = "google_sheet" | "public_form" | "naukri_import";

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
  source: IntakeSource;
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
  team_id: string | null;
  team_name: string | null;
  reviewed_at: string | null;
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
  pending_review: number;
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

/**
 * What a telecaller fills in before accepting. Mirrors `IntakeCandidateDetails`:
 * the manual add-candidate form's required fields, minus brand experience
 * (the recruiter's to fill) and with the CV link optional.
 */
export interface IntakeCandidateDetails {
  full_name: string;
  email?: string;
  phone: string;
  communication: string;
  education: string;
  department: string;
  specialization: string;
  establishment_tag?: string;
  current_role: string;
  experience_years: number;
  city: string;
  area?: string;
  gender: "male" | "female" | "other";
  age?: number;
  expected_salary: number;
  salary: number;
  notice_period: string;
  cv_link?: string;
}

/** What the system already holds on the person, to prefill the form. */
export type IntakeCandidateDraft = {
  [K in keyof IntakeCandidateDetails]-?: IntakeCandidateDetails[K] | null;
} & { has_resume: boolean };

export function fetchLeadCandidate(apiFetch: ApiFetch, id: string): Promise<IntakeCandidateDraft> {
  return apiFetch<IntakeCandidateDraft>(`/api/v1/intake/leads/${id}/candidate`);
}

/** Department → roles. The telecaller's copy of /positions/role-catalog. */
export function fetchIntakeRoleCatalog(apiFetch: ApiFetch): Promise<Record<string, string[]>> {
  return apiFetch("/api/v1/intake/role-catalog");
}

export function acceptLead(
  apiFetch: ApiFetch,
  id: string,
  details: IntakeCandidateDetails,
  notes?: string,
): Promise<IntakeLead> {
  return apiFetch<IntakeLead>(`/api/v1/intake/leads/${id}/accept`, {
    method: "POST",
    body: JSON.stringify({ details, notes: notes || null }),
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

// ── Review ────────────────────────────────────────────────────────────────────

export interface IntakeTeamOption {
  id: string;
  name: string;
  /** Active recruiters the team's round-robin can pick from. */
  recruiters: number;
  /** Leads its recruiters hold and have not yet mapped. */
  open_leads: number;
}

export function fetchReviewTeams(apiFetch: ApiFetch): Promise<IntakeTeamOption[]> {
  return apiFetch<IntakeTeamOption[]>("/api/v1/intake/teams");
}

export function assignLeadsToTeam(
  apiFetch: ApiFetch,
  leadIds: string[],
  teamId: string,
): Promise<{ assigned: IntakeLead[]; skipped: string[] }> {
  return apiFetch("/api/v1/intake/leads/assign-team", {
    method: "POST",
    body: JSON.stringify({ lead_ids: leadIds, team_id: teamId }),
  });
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
  pending_review: "Awaiting review",
  pending_recruiter: "With recruiter",
  actioned: "Actioned",
  duplicate: "Duplicate",
};

export const STATUS_STYLES: Record<IntakeLeadStatus, string> = {
  pending_telecaller: "bg-yellow/10 text-yellow border-yellow/20",
  unassigned: "bg-orange-500/10 text-orange-400 border-orange-500/20",
  rejected: "bg-red-500/10 text-red-400 border-red-500/20",
  pending_review: "bg-violet-500/10 text-violet-400 border-violet-500/20",
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

// ── Naukri import ─────────────────────────────────────────────────────────────

/**
 * What would happen to one row: `new` becomes a lead for the telecallers;
 * `matched_existing` is someone already in the pool (filed as a duplicate);
 * `already_ingested` was imported before; `duplicate_in_sheet` is on an
 * earlier row of the same file.
 */
export type NaukriRowOutcome =
  | "new"
  | "matched_existing"
  | "already_ingested"
  | "duplicate_in_sheet";

export const NAUKRI_OUTCOME_LABELS: Record<NaukriRowOutcome, string> = {
  new: "New lead",
  matched_existing: "Already in the pool",
  already_ingested: "Imported before",
  duplicate_in_sheet: "Repeated in this file",
};

export interface NaukriPreviewRow {
  row_number: number;
  full_name: string;
  phone: string;
  email: string | null;
  city: string | null;
  designation: string | null;
  current_company: string | null;
  experience_years: number;
  /** ₹ per month, converted from Naukri's yearly figure. */
  salary: number | null;
  outcome: NaukriRowOutcome;
  warnings: string[];
}

export interface NaukriPreview {
  rows: NaukriPreviewRow[];
  skipped: { row_number: number; reason: string }[];
  new: number;
  matched_existing: number;
  already_ingested: number;
  duplicate_in_sheet: number;
}

export interface NaukriImportResult {
  rows_read: number;
  created: number;
  assigned: number;
  unassigned: number;
  matched_existing: number;
  already_ingested: number;
  repeated_in_file: number;
  unusable: number;
  errors: string[];
}

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

/**
 * Multipart, so not through apiFetch: it sets a JSON content type, and an
 * upload needs the browser to write the multipart boundary itself. Errors are
 * thrown as the raw body, like apiFetch, so apiErrorMessage reads them the same.
 */
async function postMultipart<T>(path: string, body: FormData): Promise<T> {
  const res = await fetch(`${API_URL}/api/v1/intake${path}`, {
    method: "POST",
    body,
    credentials: "include",
  });
  if (!res.ok) throw new Error((await res.text()) || `API error: ${res.status}`);
  return res.json() as Promise<T>;
}

function oneFile(file: File): FormData {
  const body = new FormData();
  body.append("file", file);
  return body;
}

/** What importing this export would do, row by row. Writes nothing. */
export function previewNaukriImport(file: File): Promise<NaukriPreview> {
  return postMultipart<NaukriPreview>("/imports/naukri/preview", oneFile(file));
}

/** Import the export: each new person becomes a lead in the telecaller queue. */
export function importNaukri(file: File): Promise<NaukriImportResult> {
  return postMultipart<NaukriImportResult>("/imports/naukri", oneFile(file));
}

// ── Leads added by hand or from resumes ──────────────────────────────────────

/** One resume read into the lead form's fields — best guesses, nothing saved. */
export interface ResumeLeadDraft {
  filename: string;
  full_name: string | null;
  phone: string | null;
  email: string | null;
  city: string | null;
  current_role: string | null;
  department: string | null;
  current_company: string | null;
  experience_years: number | null;
  /** The file couldn't be used at all. */
  error: string | null;
  /** The file was taken but not read (resume parsing is off). */
  notice: string | null;
}

/** A lead as submitted. Salaries are ₹ per month; `resume_index` points into the files sent. */
export interface ManualLeadInput {
  full_name: string;
  phone: string;
  email?: string;
  city?: string;
  current_role?: string;
  department?: string;
  current_company?: string;
  experience_years?: number;
  salary: number;
  expected_salary?: number;
  resume_index?: number;
}

export type ManualLeadStatus = "queued" | "waiting" | "duplicate" | "error";

export interface ManualLeadsResponse {
  results: {
    index: number;
    full_name: string | null;
    status: ManualLeadStatus;
    detail: string;
  }[];
  queued: number;
  waiting: number;
  duplicate: number;
  error: number;
}

/** Read resumes into drafts for a person to check. Saves and uploads nothing. */
export function parseResumes(files: File[]): Promise<ResumeLeadDraft[]> {
  const body = new FormData();
  files.forEach((file) => body.append("files", file));
  return postMultipart<ResumeLeadDraft[]>("/leads/parse-resumes", body);
}

/** Add checked drafts as leads; each succeeds or fails on its own. */
export function addLeads(drafts: ManualLeadInput[], files: File[]): Promise<ManualLeadsResponse> {
  const body = new FormData();
  body.append("drafts", JSON.stringify(drafts));
  files.forEach((file) => body.append("files", file));
  return postMultipart<ManualLeadsResponse>("/leads/manual", body);
}

/** Leads the signed-in staff member put in themselves, newest first. */
export function listSubmittedLeads(apiFetch: ApiFetch): Promise<IntakeLead[]> {
  return apiFetch<IntakeLead[]>("/api/v1/intake/leads/submitted");
}
