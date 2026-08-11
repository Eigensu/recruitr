type ApiFetch = <T>(path: string, options?: RequestInit) => Promise<T>;

export interface ClientMessageBase {
  message_text: string;
  target_type: "all" | "specific";
  target_client_ids: string[];
  start_at: string;
  end_at: string;
  type: string;
  cta_url?: string;
}

export async function getClientMessagesAdmin(apiFetch: ApiFetch) {
  return apiFetch<{ items: unknown[]; total: number }>("/api/v1/client-messaging");
}

export async function createClientMessage(apiFetch: ApiFetch, data: ClientMessageBase) {
  return apiFetch("/api/v1/client-messaging", {
    method: "POST",
    body: JSON.stringify(data),
  });
}

export async function updateClientMessage(
  apiFetch: ApiFetch,
  id: string,
  data: Partial<ClientMessageBase>,
) {
  return apiFetch(`/api/v1/client-messaging/${id}`, {
    method: "PATCH",
    body: JSON.stringify(data),
  });
}

export async function deleteClientMessage(apiFetch: ApiFetch, id: string) {
  return apiFetch(`/api/v1/client-messaging/${id}`, {
    method: "DELETE",
  });
}
