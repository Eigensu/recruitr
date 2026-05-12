import { getAllDashboardMappings } from "@/lib/api/dashboard";

export async function getCandidateMappingsForDashboard() {
  return getAllDashboardMappings();
}
