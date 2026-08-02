type ApiFetch = <T>(path: string, options?: RequestInit) => Promise<T>;

export interface Client {
  id: string;
  code: string;
  name: string;
  city: string | null;
  industry?: string | null;
  website?: string | null;
  contact_person?: string | null;
  contact_email?: string | null;
  contact_phone?: string | null;
  created_by_id?: string | null;
  updated_by_id?: string | null;
  created_at?: string;
  updated_at?: string;
  is_active: boolean;
  position_count: number;
  candidate_count: number;
  user_count: number;
  allowed_emails?: string[];
  allowed_domains?: string[];
}

export interface ClientCreatePayload {
  name: string;
  city?: string;
  industry?: string;
  website?: string;
  contact_person?: string;
  contact_email?: string;
  contact_phone?: string;
  allowed_emails?: string[];
  allowed_domains?: string[];
}

export interface ClientUpdatePayload {
  name?: string;
  city?: string;
  industry?: string;
  website?: string;
  contact_person?: string;
  contact_email?: string;
  contact_phone?: string;
  is_active?: boolean;
  allowed_emails?: string[];
  allowed_domains?: string[];
}

export interface ClientUser {
  id: string;
  name: string | null;
  email: string;
  role: string;
  status: string;
  last_login: string | null;
  created_at: string;
}

export interface ClientUserInvitePayload {
  email: string;
  role?: string;
}

export function listClients(apiFetch: ApiFetch, includeArchived = false): Promise<Client[]> {
  const q = includeArchived ? "?include_archived=true" : "";
  return apiFetch(`/api/v1/clients${q}`);
}

export function createClient(apiFetch: ApiFetch, payload: ClientCreatePayload): Promise<Client> {
  return apiFetch("/api/v1/clients", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function updateClient(
  apiFetch: ApiFetch,
  clientId: string,
  payload: ClientUpdatePayload,
): Promise<Client> {
  return apiFetch(`/api/v1/clients/${clientId}`, {
    method: "PATCH",
    body: JSON.stringify(payload),
  });
}

export function archiveClient(apiFetch: ApiFetch, clientId: string): Promise<void> {
  return apiFetch(`/api/v1/clients/${clientId}`, { method: "DELETE" });
}

export function listClientUsers(apiFetch: ApiFetch, clientId: string): Promise<ClientUser[]> {
  return apiFetch(`/api/v1/clients/${clientId}/users`);
}

export function inviteClientUser(
  apiFetch: ApiFetch,
  clientId: string,
  payload: ClientUserInvitePayload,
): Promise<ClientUser> {
  return apiFetch(`/api/v1/clients/${clientId}/users`, {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function removeClientUser(
  apiFetch: ApiFetch,
  clientId: string,
  userId: string,
): Promise<void> {
  return apiFetch(`/api/v1/clients/${clientId}/users/${userId}`, { method: "DELETE" });
}

export function getClient(apiFetch: ApiFetch, clientId: string): Promise<Client> {
  return apiFetch(`/api/v1/clients/${clientId}`);
}
