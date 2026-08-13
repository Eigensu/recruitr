"use client";

import { useRouter } from "next/navigation";
import { useApiFetch } from "@/lib/api";

export default function SignOutButton() {
  const router = useRouter();
  const apiFetch = useApiFetch();

  const handleSignOut = async () => {
    try {
      await apiFetch("/api/v1/auth/logout", {
        method: "POST",
      });
    } catch (err) {
      console.error("Logout failed:", err);
    } finally {
      // Safely remove only client messaging dismissals
      for (let i = sessionStorage.length - 1; i >= 0; i--) {
        const key = sessionStorage.key(i);
        if (key && key.startsWith("dismissed_banners_")) {
          sessionStorage.removeItem(key);
        }
      }
      window.location.href = "/sign-in";
    }
  };

  return (
    <button
      onClick={handleSignOut}
      className="text-sm font-medium text-white hover:text-white transition-colors cursor-pointer"
    >
      Sign Out
    </button>
  );
}
