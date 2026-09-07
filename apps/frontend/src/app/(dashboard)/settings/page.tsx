import { getUserServer } from "@/lib/api/auth.server";
import SettingsClient from "./SettingsClient";

export default async function SettingsPage() {
  const user = await getUserServer();
  return <SettingsClient initialUser={user} />;
}
