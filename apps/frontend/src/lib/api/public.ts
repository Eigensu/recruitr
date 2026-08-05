import type { PublicBrand } from "@/types";

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

/**
 * Resolve an agency by its public domain (the value entered at onboarding).
 *
 * Returns null when the domain is unknown so callers can render a not-found
 * state; anything else is a genuine failure and throws.
 */
export async function fetchPublicBrand(domain: string): Promise<PublicBrand | null> {
  const res = await fetch(`${API_URL}/api/v1/public/brands/${encodeURIComponent(domain)}`, {
    cache: "no-store",
  });
  if (res.status === 404) return null;
  if (!res.ok) throw new Error(`Failed to resolve agency "${domain}" (${res.status})`);
  return res.json();
}
