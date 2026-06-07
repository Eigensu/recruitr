type ApiFetch = <T>(path: string, options?: RequestInit) => Promise<T>;

export interface Team {
  id: string;
  name: string;
}

export async function listTeams(apiFetch: ApiFetch): Promise<Team[]> {
  return apiFetch("/api/v1/teams");
}

export async function createTeam(apiFetch: ApiFetch, name: string): Promise<Team> {
  return apiFetch("/api/v1/teams", {
    method: "POST",
    body: JSON.stringify({ name }),
  });
}
