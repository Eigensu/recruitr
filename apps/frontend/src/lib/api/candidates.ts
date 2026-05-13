import { getDashboardMappings } from "@/lib/api/dashboard";

/** Single-page cap for dashboard recruiter rollups; avoids unbounded pagination. */
const DASHBOARD_MAPPINGS_SAMPLE_LIMIT = 500;

export async function getCandidateMappingsForDashboard() {
  const response = await getDashboardMappings({ page: 1, limit: DASHBOARD_MAPPINGS_SAMPLE_LIMIT });
  return response.items;
}
