import { redirect } from "next/navigation";
import { getUserServer } from "@/lib/api/auth.server";

export default async function ClientMessagingLayout({ children }: { children: React.ReactNode }) {
  const user = await getUserServer();

  if (!user || user.role === "client") {
    redirect("/error");
  }

  return <>{children}</>;
}
