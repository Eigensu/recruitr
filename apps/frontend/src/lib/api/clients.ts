type ApiFetch = <T>(path: string, options?: RequestInit) => Promise<T>;

export interface Client {
  id: string;
  code: string;
  name: string;
  city: string | null;
  is_active: boolean;
  /** Active positions pointing at this client — 0 means it is safe to archive. */
  position_count: number;
}

export interface ClientCreatePayload {
  name: string;
  city?: string;
}

export interface ClientUpdatePayload {
  name?: string;
  city?: string;
  is_active?: boolean;
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
