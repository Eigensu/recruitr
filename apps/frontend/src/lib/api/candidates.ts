import { getAllDashboardMappings } from "@/lib/api/dashboard";

export async function getCandidateMappingsForDashboard(maxMappings = 500) {
  return getAllDashboardMappings(maxMappings);
}
