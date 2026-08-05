import { NextResponse } from "next/server";
import type { NextRequest } from "next/server";

export function middleware(request: NextRequest) {
  const token = request.cookies.get("access_token")?.value;
  const { pathname } = request.nextUrl;

  const isAuthPage = pathname.startsWith("/sign-in") || pathname.startsWith("/sign-up");

  // Onboarding: requires a cookie but should not bounce authenticated users away.
  const isOnboarding = pathname.startsWith("/onboarding");

  // Public form: requires no authentication
  const isPublicForm = pathname.startsWith("/form");

  // Already logged in → don't show auth pages again
  if (token && isAuthPage) {
    return NextResponse.redirect(new URL("/", request.url));
  }

  // Not logged in → block all non-auth, non-onboarding, non-public pages
  if (!token && !isAuthPage && !isOnboarding && !isPublicForm) {
    return NextResponse.redirect(new URL("/sign-in", request.url));
  }

  // Not logged in + visiting /onboarding directly → send to sign-in
  if (!token && isOnboarding) {
    return NextResponse.redirect(new URL("/sign-in", request.url));
  }

  return NextResponse.next();
}

export const config = {
  matcher: [
    "/((?!api|_next/static|_next/image|favicon.ico|sitemap.xml|robots.txt|.*\\.(?:svg|png|jpg|jpeg|gif|webp)$).*)",
  ],
};
