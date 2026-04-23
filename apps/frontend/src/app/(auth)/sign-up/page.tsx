"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { useApiFetch } from "@/lib/api";

export default function SignUpPage() {
  const router = useRouter();
  const apiFetch = useApiFetch();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [fullName, setFullName] = useState("");
  const [error, setError] = useState("");

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");

    try {
      await apiFetch("/api/v1/auth/signup", {
        method: "POST",
        body: JSON.stringify({ email, password, full_name: fullName }),
      });
      // Send user to signin upon successful registration
      router.push("/sign-in");
    } catch (err: unknown) {
      const errorMessage =
        err instanceof Error ? err.message : "Failed to create account. Please try again.";
      setError(errorMessage);
    }
  };

  return (
    <main className="min-h-screen flex items-center justify-center bg-gray-950 p-4">
      <div className="w-full max-w-md bg-gray-900 border border-gray-800 rounded-xl p-8">
        <div className="text-center mb-8">
          <h1 className="text-2xl font-bold text-white mb-2">Create an Account</h1>
          <p className="text-gray-400">Join Eigensu to master your recruitment</p>
        </div>

        <form onSubmit={handleSubmit} className="space-y-4">
          {error && (
            <div className="bg-red-500/10 border border-red-500/20 text-red-400 p-3 rounded-lg text-sm">
              {error}
            </div>
          )}

          <div>
            <label className="block text-sm font-medium text-gray-300 mb-1" htmlFor="name">
              Full Name
            </label>
            <input
              id="name"
              type="text"
              className="w-full bg-gray-950 border border-gray-800 rounded-lg px-4 py-2 text-white focus:outline-none focus:ring-2 focus:ring-violet-500"
              value={fullName}
              onChange={(e) => setFullName(e.target.value)}
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-300 mb-1" htmlFor="email">
              Email
            </label>
            <input
              id="email"
              type="email"
              required
              className="w-full bg-gray-950 border border-gray-800 rounded-lg px-4 py-2 text-white focus:outline-none focus:ring-2 focus:ring-violet-500"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-300 mb-1" htmlFor="password">
              Password
            </label>
            <input
              id="password"
              type="password"
              required
              minLength={8}
              className="w-full bg-gray-950 border border-gray-800 rounded-lg px-4 py-2 text-white focus:outline-none focus:ring-2 focus:ring-violet-500"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
            />
          </div>

          <button
            type="submit"
            className="w-full bg-violet-600 hover:bg-violet-700 text-white font-medium py-2 px-4 rounded-lg transition-colors mt-6"
          >
            Sign Up
          </button>

          <p className="text-center text-sm text-gray-400 mt-6">
            Already have an account?{" "}
            <Link href="/sign-in" className="text-violet-400 hover:text-violet-300">
              Sign in
            </Link>
          </p>
        </form>
      </div>
    </main>
  );
}
