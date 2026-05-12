"use client";

import { useRouter } from "next/navigation";

export default function SignOutButton() {
  const router = useRouter();

  const handleSignOut = async () => {
    try {
      const response = await fetch(
        `${process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000"}/api/v1/auth/logout`,
        {
          method: "POST",
          credentials: "include",
        },
      );
      if (response.ok) {
        router.push("/sign-in");
      } else {
        console.error("Logout failed with status:", response.status);
      }
    } catch (error) {
      console.error("Logout request failed:", error);
    }
  };

  return (
    <button
      onClick={handleSignOut}
      className="text-sm font-medium text-white/40 hover:text-white transition-colors cursor-pointer"
    >
      Sign Out
    </button>
  );
}
