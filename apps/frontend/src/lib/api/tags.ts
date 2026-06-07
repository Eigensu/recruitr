type ApiFetch = <T>(path: string, options?: RequestInit) => Promise<T>;

export interface RecruiterTag {
  id: string;
  name: string;
}

export async function listTags(apiFetch: ApiFetch): Promise<RecruiterTag[]> {
  return apiFetch("/api/v1/tags");
}

export async function createTag(apiFetch: ApiFetch, name: string): Promise<RecruiterTag> {
  return apiFetch("/api/v1/tags", {
    method: "POST",
    body: JSON.stringify({ name }),
  });
}
