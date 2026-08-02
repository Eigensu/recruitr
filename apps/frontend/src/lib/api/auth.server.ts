import { cookies } from "next/headers";
import type { UserInfo } from "@/types";

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export async function getUserServer(): Promise<UserInfo | null> {
  try {
    const cookieStore = await cookies();
    const token = cookieStore.get("access_token")?.value;

    if (!token) return null;

    const res = await fetch(`${API_URL}/api/v1/auth/me`, {
      headers: {
        Cookie: `access_token=${token}`,
      },
      next: { revalidate: 60 }, // Cache the role for 60 seconds
    });

    if (!res.ok) {
      return null;
    }

    return (await res.json()) as UserInfo;
  } catch (error) {
    console.error("Failed to fetch user server-side", error);
    return null;
  }
}
