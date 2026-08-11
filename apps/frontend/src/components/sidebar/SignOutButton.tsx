"use client";

import { useRouter } from "next/navigation";

export default function SignOutButton() {
  const router = useRouter();

  const handleSignOut = async () => {
    try {
      await fetch(
        `${process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000"}/api/v1/auth/logout`,
        {
          method: "POST",
          credentials: "include",
        },
      );
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
      router.push("/sign-in");
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
