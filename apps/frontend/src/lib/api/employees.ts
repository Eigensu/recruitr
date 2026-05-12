import { getDashboardEmployees } from "@/lib/api/dashboard";

export async function getEmployeesForDashboard(limit = 100) {
  const response = await getDashboardEmployees({ page: 1, limit });
  return response.items;
}
