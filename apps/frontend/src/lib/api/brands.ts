type ApiFetch = <T>(path: string, options?: RequestInit) => Promise<T>;

/** Workspace-level switches for what happens automatically to a new resume. */
export interface AutomationSettings {
  /** Extract text and infer skills / phone / experience from uploaded resumes. */
  resume_parsing_enabled: boolean;
  /** Copy the top parsed skills onto the candidate as tags. */
  auto_tagging_enabled: boolean;
}

export interface BrandSettings {
  automation: AutomationSettings;
}

export async function getBrandSettings(apiFetch: ApiFetch): Promise<BrandSettings> {
  return apiFetch("/api/v1/brands/settings");
}

/** Maintainers only — the API returns 403 for anyone else. */
export async function updateBrandSettings(
  apiFetch: ApiFetch,
  automation: Partial<AutomationSettings>,
): Promise<BrandSettings> {
  return apiFetch("/api/v1/brands/settings", {
    method: "PATCH",
    body: JSON.stringify({ automation }),
  });
}
