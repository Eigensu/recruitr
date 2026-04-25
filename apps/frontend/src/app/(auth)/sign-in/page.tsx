"use client";
import { useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import Image from "next/image";
import { useApiFetch } from "@/lib/api";
import "../auth.css";

export default function SignInPage() {
  const router = useRouter();
  const apiFetch = useApiFetch();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [rememberMe, setRememberMe] = useState(false);
  const [error, setError] = useState("");
  const [isLoading, setIsLoading] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    setIsLoading(true);
    try {
      await apiFetch("/api/v1/auth/login", {
        method: "POST",
        body: JSON.stringify({ email, password }),
      });
      router.push("/");
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Failed to sign in.");
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <main className="grid min-h-dvh grid-cols-1 bg-white lg:grid-cols-2">
      {/* ── MOBILE HERO BANNER (visible < lg) ── */}
      <div
        className="relative overflow-hidden rounded-b-[24px] bg-black lg:hidden"
        style={{ height: "220px" }}
      >
        <Image
          src="/login-hero.png"
          alt=""
          fill
          sizes="100vw"
          className="object-cover anim-in"
          priority
        />
        <div className="hero-gradient absolute inset-0 z-10" />
        <div className="absolute top-5 left-5 z-30 size-10 overflow-hidden rounded-lg shadow-lg anim-scale d3">
          <Image
            src="/logo-yellow.jpeg"
            alt="Binge"
            width={40}
            height={40}
            className="size-full object-cover"
          />
        </div>
        <div className="absolute top-5 right-5 z-30 anim-down d2">
          <span className="font-heading text-lg font-bold tracking-tight text-white">
            binge <span className="text-yellow">ai</span>
          </span>
        </div>
        <div className="absolute right-6 bottom-6 left-6 z-30">
          <h2 className="font-heading text-2xl font-bold uppercase leading-[1.1] tracking-tight text-white anim-up d4">
            Find The <span className="text-yellow">Right Talent.</span>
          </h2>
          <p className="mt-1 font-subtitle text-xs tracking-wide text-white/50 anim-up d5">
            Hospitality Recruitment, Reimagined.
          </p>
        </div>
      </div>

      {/* ── DESKTOP HERO (visible >= lg) ── */}
      <section className="relative m-3 hidden overflow-hidden rounded-[20px] bg-black lg:block">
        <Image
          src="/login-hero.png"
          alt=""
          fill
          sizes="50vw"
          className="object-cover anim-in"
          priority
        />
        <div className="hero-gradient absolute inset-0 z-10" />

        <div className="absolute top-7 left-7 z-30 size-12 overflow-hidden rounded-xl shadow-lg anim-scale d5">
          <Image
            src="/logo-yellow.jpeg"
            alt="Binge"
            width={48}
            height={48}
            className="size-full object-cover"
          />
        </div>

        <div className="absolute right-10 bottom-14 left-10 z-30">
          <p className="mb-4 flex items-center gap-3 text-[11px] font-medium uppercase tracking-[0.2em] text-yellow/60 anim-left d6">
            [ Binge Consulting ] <span className="inline-block h-px w-7 bg-yellow/40" />
          </p>
          <h2 className="mb-3 font-heading text-[clamp(2rem,3.5vw,3.5rem)] font-bold uppercase leading-[1.05] tracking-tight text-white anim-up d7">
            Find The
            <br />
            <span className="text-yellow">Right Talent.</span>
            <br />
            Every Time.
          </h2>
          <p className="font-subtitle text-sm tracking-wide text-white/50 anim-up d9">
            Hospitality Recruitment, Reimagined.
          </p>
          <div className="mt-6 flex items-center gap-2 anim-in d10">
            <span className="h-2 w-6 rounded bg-yellow anim-glow" />
            <span className="size-2 rounded-full bg-white/20" />
            <span className="size-2 rounded-full bg-white/20" />
          </div>
        </div>
      </section>

      {/* ── FORM PANEL ── */}
      <section className="relative flex flex-1 flex-col items-center justify-center overflow-hidden bg-white px-6 py-8 sm:px-12 lg:py-0">
        {/* Watermark */}
        <div className="pointer-events-none absolute bottom-6 left-1/2 z-0 hidden w-64 -translate-x-1/2 select-none opacity-[0.04] lg:block">
          <Image
            src="/logo.jpeg"
            alt=""
            width={256}
            height={100}
            className="h-auto w-full"
            style={{ width: "100%", height: "auto" }}
          />
        </div>

        {/* binge ai — desktop only (mobile has it in the banner) */}
        <div className="absolute right-8 top-6 z-10 hidden anim-down d2 lg:block">
          <span className="font-heading text-xl font-bold tracking-tight text-navy">
            binge <span className="text-yellow">ai</span>
          </span>
        </div>

        <div className="w-full max-w-sm">
          <div className="mb-8 text-center anim-up d3 lg:mb-10">
            <h1 className="mb-1.5 font-heading text-[28px] font-bold normal-case tracking-tight text-navy sm:text-[34px]">
              Welcome Back
            </h1>
            <p className="text-sm text-muted">
              Enter your email and password to access your account
            </p>
          </div>

          <form
            onSubmit={handleSubmit}
            className="flex flex-col gap-4 lg:gap-[18px]"
            id="signin-form"
          >
            {error && (
              <div
                className="flex items-center gap-2.5 rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-600 anim-shake"
                role="alert"
              >
                <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
                  <circle cx="8" cy="8" r="7" stroke="currentColor" strokeWidth="1.5" />
                  <path
                    d="M8 5v3.5"
                    stroke="currentColor"
                    strokeWidth="1.5"
                    strokeLinecap="round"
                  />
                  <circle cx="8" cy="11" r="0.75" fill="currentColor" />
                </svg>
                {error}
              </div>
            )}

            <div className="anim-up d4">
              <label
                className="mb-1.5 block text-[13px] font-semibold tracking-wide text-charcoal"
                htmlFor="si-email"
              >
                Email
              </label>
              <input
                id="si-email"
                type="email"
                placeholder="Enter your email"
                required
                autoComplete="email"
                className="block w-full rounded-[10px] border-[1.5px] border-gray-200 bg-white px-4 py-3 text-sm text-charcoal outline-none transition-all placeholder:text-gray-400 focus:border-navy focus:ring-2 focus:ring-navy/10"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
              />
            </div>

            <div className="anim-up d5">
              <label
                className="mb-1.5 block text-[13px] font-semibold tracking-wide text-charcoal"
                htmlFor="si-pass"
              >
                Password
              </label>
              <div className="relative">
                <input
                  id="si-pass"
                  type={showPassword ? "text" : "password"}
                  placeholder="Enter your password"
                  required
                  autoComplete="current-password"
                  className="block w-full rounded-[10px] border-[1.5px] border-gray-200 bg-white px-4 py-3 pr-11 text-sm text-charcoal outline-none transition-all placeholder:text-gray-400 focus:border-navy focus:ring-2 focus:ring-navy/10"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                />
                <button
                  type="button"
                  className="absolute right-3 top-1/2 -translate-y-1/2 cursor-pointer text-muted transition-colors hover:text-navy"
                  onClick={() => setShowPassword(!showPassword)}
                  aria-label={showPassword ? "Hide" : "Show"}
                >
                  {showPassword ? (
                    <svg
                      width="18"
                      height="18"
                      viewBox="0 0 24 24"
                      fill="none"
                      stroke="currentColor"
                      strokeWidth="1.5"
                      strokeLinecap="round"
                      strokeLinejoin="round"
                    >
                      <path d="M17.94 17.94A10.07 10.07 0 0 1 12 20c-7 0-11-8-11-8a18.45 18.45 0 0 1 5.06-5.94" />
                      <path d="M9.9 4.24A9.12 9.12 0 0 1 12 4c7 0 11 8 11 8a18.5 18.5 0 0 1-2.16 3.19" />
                      <path d="M14.12 14.12a3 3 0 1 1-4.24-4.24" />
                      <line x1="1" y1="1" x2="23" y2="23" />
                    </svg>
                  ) : (
                    <svg
                      width="18"
                      height="18"
                      viewBox="0 0 24 24"
                      fill="none"
                      stroke="currentColor"
                      strokeWidth="1.5"
                      strokeLinecap="round"
                      strokeLinejoin="round"
                    >
                      <path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z" />
                      <circle cx="12" cy="12" r="3" />
                    </svg>
                  )}
                </button>
              </div>
            </div>

            <div className="flex items-center justify-between anim-up d6">
              <label className="flex cursor-pointer items-center gap-2" htmlFor="si-rem">
                <input
                  id="si-rem"
                  type="checkbox"
                  checked={rememberMe}
                  onChange={(e) => setRememberMe(e.target.checked)}
                  className="ck-hide"
                />
                <span className="ck-box">
                  <svg
                    width="10"
                    height="10"
                    viewBox="0 0 10 10"
                    fill="none"
                    stroke="currentColor"
                    strokeWidth="1.5"
                    strokeLinecap="round"
                    strokeLinejoin="round"
                  >
                    <polyline points="1.5 5 4 7.5 8.5 2.5" />
                  </svg>
                </span>
                <span className="text-[13px] text-charcoal">Remember me</span>
              </label>
              <Link href="#" className="text-[13px] font-medium text-navy hover:text-charcoal">
                Forgot Password
              </Link>
            </div>

            <button
              type="submit"
              disabled={isLoading}
              className="btn-shimmer mt-1 w-full cursor-pointer rounded-[10px] bg-navy px-6 py-3.5 font-subtitle text-sm font-bold tracking-wide text-white transition-all hover:-translate-y-0.5 hover:bg-navy-dark hover:shadow-lg active:translate-y-0 disabled:cursor-not-allowed disabled:opacity-70 anim-up d7"
              id="si-sub"
            >
              {isLoading ? <span className="spinner" /> : "Sign In"}
            </button>

            <div className="flex items-center gap-4 anim-up d8">
              <span className="h-px flex-1 bg-gray-200" />
              <span className="text-[13px] text-muted">or</span>
              <span className="h-px flex-1 bg-gray-200" />
            </div>

            <button
              type="button"
              className="flex w-full cursor-pointer items-center justify-center gap-2.5 rounded-[10px] border-[1.5px] border-gray-200 bg-white px-6 py-3 text-sm font-medium text-charcoal transition-all hover:-translate-y-px hover:border-gray-300 hover:bg-light hover:shadow-sm anim-up d9"
              id="si-g"
            >
              <svg width="18" height="18" viewBox="0 0 48 48">
                <path
                  fill="#EA4335"
                  d="M24 9.5c3.54 0 6.71 1.22 9.21 3.6l6.85-6.85C35.9 2.38 30.47 0 24 0 14.62 0 6.51 5.38 2.56 13.22l7.98 6.19C12.43 13.72 17.74 9.5 24 9.5z"
                />
                <path
                  fill="#4285F4"
                  d="M46.98 24.55c0-1.57-.15-3.09-.38-4.55H24v9.02h12.94c-.58 2.96-2.26 5.48-4.78 7.18l7.73 6c4.51-4.18 7.09-10.36 7.09-17.65z"
                />
                <path
                  fill="#FBBC05"
                  d="M10.53 28.59c-.48-1.45-.76-2.99-.76-4.59s.27-3.14.76-4.59l-7.98-6.19C.92 16.46 0 20.12 0 24c0 3.88.92 7.54 2.56 10.78l7.97-6.19z"
                />
                <path
                  fill="#34A853"
                  d="M24 48c6.48 0 11.93-2.13 15.89-5.81l-7.73-6c-2.15 1.45-4.92 2.3-8.16 2.3-6.26 0-11.57-4.22-13.47-9.91l-7.98 6.19C6.51 42.62 14.62 48 24 48z"
                />
              </svg>
              Sign In with Google
            </button>
          </form>

          <p className="mt-7 text-center text-sm text-muted anim-in d10">
            Don&apos;t have an account?{" "}
            <Link href="/sign-up" className="font-semibold text-navy hover:text-charcoal">
              Sign up
            </Link>
          </p>
        </div>
      </section>
    </main>
  );
}
