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

/** What the public CV upload page shows — GET /public/cv-upload/{token}. */
export interface CvUploadLinkInfo {
  first_name: string;
  brand_name: string;
  brand_logo_url: string | null;
  expires_at: string;
  uploaded: boolean;
}

/**
 * Who a CV upload link is for. Null once it no longer works — expired, replaced
 * by a newer link, or never issued; the API does not say which.
 */
export async function fetchCvUploadLink(token: string): Promise<CvUploadLinkInfo | null> {
  const res = await fetch(`${API_URL}/api/v1/public/cv-upload/${encodeURIComponent(token)}`, {
    cache: "no-store",
  });
  if (res.status === 404) return null;
  if (!res.ok) throw new Error(`Could not open this link (${res.status})`);
  return res.json();
}

/** Upload the candidate's CV through their link; replaces any they sent before. */
export async function uploadCvThroughLink(token: string, file: File): Promise<CvUploadLinkInfo> {
  const body = new FormData();
  body.append("resume", file);
  const res = await fetch(`${API_URL}/api/v1/public/cv-upload/${encodeURIComponent(token)}`, {
    method: "POST",
    body,
  });
  if (!res.ok) {
    // FastAPI's `detail` is written for the person uploading; the envelope is not.
    const data = await res.json().catch(() => null);
    throw new Error(
      typeof data?.detail === "string" ? data.detail : "Could not upload your CV. Try again.",
    );
  }
  return res.json();
}
