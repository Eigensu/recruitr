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

export async function updateTeam(
  apiFetch: ApiFetch,
  teamId: string,
  changes: { name?: string; is_active?: boolean },
): Promise<Team> {
  return apiFetch(`/api/v1/teams/${teamId}`, {
    method: "PUT",
    body: JSON.stringify(changes),
  });
}

export interface EmployeeTeamInfo {
  id: string;
  name: string;
  email: string;
  team_id: string | null;
}

export async function listTeamEmployees(apiFetch: ApiFetch): Promise<EmployeeTeamInfo[]> {
  return apiFetch("/api/v1/teams/employees");
}

export async function assignEmployeesToTeam(
  apiFetch: ApiFetch,
  employeeIds: string[],
  teamId: string | null,
): Promise<{ status: string }> {
  return apiFetch("/api/v1/teams/employees/assign", {
    method: "PUT",
    body: JSON.stringify({ employee_ids: employeeIds, team_id: teamId }),
  });
}
