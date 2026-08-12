type ApiFetch = <T>(path: string, options?: RequestInit) => Promise<T>;

export interface RefereeUser {
  id: string;
  brand_id: string;
  email: string;
  name: string | null;
  role: string;
  is_active: boolean;
  last_login: string | null;
  created_at: string;
  updated_at: string;
}

export interface RefereeUserInvitePayload {
  email: string;
  name: string | null;
  role: string;
}

export function listReferees(apiFetch: ApiFetch): Promise<RefereeUser[]> {
  return apiFetch<RefereeUser[]>("/api/v1/referees");
}

export function inviteReferee(
  apiFetch: ApiFetch,
  payload: RefereeUserInvitePayload,
): Promise<RefereeUser> {
  return apiFetch<RefereeUser>("/api/v1/referees/invite", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function removeReferee(apiFetch: ApiFetch, userId: string): Promise<void> {
  return apiFetch(`/api/v1/referees/${userId}`, {
    method: "DELETE",
  });
}
