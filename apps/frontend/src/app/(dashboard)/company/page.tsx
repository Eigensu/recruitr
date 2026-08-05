"use client";

import { useEffect, useState } from "react";
import {
  IconBuilding,
  IconMail,
  IconPhone,
  IconGlobe,
  IconMapPin,
  IconBriefcase,
} from "@tabler/icons-react";
import { apiErrorMessage, useApiFetch } from "@/lib/api";

interface ClientProfile {
  id: string;
  name: string;
  code: string;
  city?: string;
  industry?: string;
  website?: string;
  contact_person?: string;
  contact_email?: string;
  contact_phone?: string;
  allowed_domains: string[];
  allowed_emails: string[];
  is_active: boolean;
  user_count?: number;
  position_count?: number;
  candidate_count?: number;
}

export default function CompanyProfilePage() {
  const apiFetch = useApiFetch();
  const [client, setClient] = useState<ClientProfile | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    async function loadClient() {
      try {
        // apiFetch returns the parsed body, not a Response — treating it as one
        // made every load fail on `res.ok` being undefined.
        setClient(await apiFetch<ClientProfile>("/api/v1/clients/me"));
      } catch (err: unknown) {
        setError(apiErrorMessage(err, "Failed to load company profile."));
      } finally {
        setLoading(false);
      }
    }
    void loadClient();
  }, [apiFetch]);

  if (loading) {
    return (
      <div className="flex h-full items-center justify-center p-6 bg-canvas">
        <div className="size-8 animate-spin rounded-full border-4 border-navy border-t-yellow" />
      </div>
    );
  }

  if (error || !client) {
    return (
      <div className="flex h-full flex-col items-center justify-center p-6 bg-canvas text-center">
        <div className="mb-4 rounded-full bg-red-500/10 p-4">
          <IconBuilding className="size-8 text-red-500" />
        </div>
        <h2 className="text-xl font-bold text-text-primary">Failed to load company profile</h2>
        <p className="mt-2 text-sm text-text-secondary">{error}</p>
      </div>
    );
  }

  return (
    <div className="flex flex-col h-full bg-canvas">
      {/* Header */}
      <div className="flex items-center justify-between border-b border-border bg-surface px-6 py-4 shrink-0">
        <div className="flex items-center gap-3">
          <div className="flex size-10 shrink-0 items-center justify-center rounded-lg bg-navy/5 text-navy border border-border">
            <IconBuilding size={20} />
          </div>
          <div>
            <h1 className="text-lg font-bold font-heading text-text-primary">{client.name}</h1>
            <p className="text-sm text-text-secondary flex items-center gap-2">
              <span className="font-mono text-xs uppercase bg-navy/5 px-2 py-0.5 rounded text-text-muted">
                {client.code}
              </span>
              {client.industry && <span>• {client.industry}</span>}
            </p>
          </div>
        </div>
        <div className="flex items-center gap-3">
          <div
            className={`px-3 py-1 rounded-full text-xs font-semibold ${client.is_active ? "bg-green-500/10 text-green-600" : "bg-red-500/10 text-red-600"}`}
          >
            {client.is_active ? "Active" : "Inactive"}
          </div>
        </div>
      </div>

      <div className="flex-1 overflow-y-auto p-6 space-y-6">
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          {/* Contact Details */}
          <div className="bg-surface border border-border rounded-xl p-5">
            <h3 className="text-sm font-bold text-text-primary uppercase tracking-wider mb-4 border-b border-border pb-2">
              Contact Details
            </h3>
            <div className="space-y-4">
              <div className="flex items-center gap-3 text-text-secondary">
                <IconBriefcase size={18} className="text-navy/40" />
                <div className="flex-1">
                  <p className="text-xs text-text-muted uppercase tracking-wider">Contact Person</p>
                  <p className="text-sm font-medium text-text-primary">
                    {client.contact_person || "—"}
                  </p>
                </div>
              </div>
              <div className="flex items-center gap-3 text-text-secondary">
                <IconMail size={18} className="text-navy/40" />
                <div className="flex-1">
                  <p className="text-xs text-text-muted uppercase tracking-wider">Email</p>
                  <p className="text-sm font-medium text-text-primary">
                    {client.contact_email || "—"}
                  </p>
                </div>
              </div>
              <div className="flex items-center gap-3 text-text-secondary">
                <IconPhone size={18} className="text-navy/40" />
                <div className="flex-1">
                  <p className="text-xs text-text-muted uppercase tracking-wider">Phone</p>
                  <p className="text-sm font-medium text-text-primary">
                    {client.contact_phone || "—"}
                  </p>
                </div>
              </div>
            </div>
          </div>

          {/* Company Info */}
          <div className="bg-surface border border-border rounded-xl p-5">
            <h3 className="text-sm font-bold text-text-primary uppercase tracking-wider mb-4 border-b border-border pb-2">
              Company Info
            </h3>
            <div className="space-y-4">
              <div className="flex items-center gap-3 text-text-secondary">
                <IconMapPin size={18} className="text-navy/40" />
                <div className="flex-1">
                  <p className="text-xs text-text-muted uppercase tracking-wider">City</p>
                  <p className="text-sm font-medium text-text-primary">{client.city || "—"}</p>
                </div>
              </div>
              <div className="flex items-center gap-3 text-text-secondary">
                <IconGlobe size={18} className="text-navy/40" />
                <div className="flex-1">
                  <p className="text-xs text-text-muted uppercase tracking-wider">Website</p>
                  {client.website ? (
                    <a
                      href={
                        client.website.startsWith("http")
                          ? client.website
                          : `https://${client.website}`
                      }
                      target="_blank"
                      rel="noopener noreferrer"
                      className="text-sm font-medium text-yellow hover:underline"
                    >
                      {client.website}
                    </a>
                  ) : (
                    <p className="text-sm font-medium text-text-primary">—</p>
                  )}
                </div>
              </div>
            </div>
          </div>
        </div>

        {/* Statistics */}
        <div className="bg-surface border border-border rounded-xl p-5">
          <h3 className="text-sm font-bold text-text-primary uppercase tracking-wider mb-4 border-b border-border pb-2">
            Statistics
          </h3>
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-6">
            <div className="flex flex-col gap-1">
              <span className="text-2xl font-bold font-heading text-navy dark:text-yellow">
                {client.position_count ?? 0}
              </span>
              <span className="text-xs text-text-muted uppercase tracking-wider">
                Active Positions
              </span>
            </div>
            <div className="flex flex-col gap-1">
              <span className="text-2xl font-bold font-heading text-navy dark:text-yellow">
                {client.candidate_count ?? 0}
              </span>
              <span className="text-xs text-text-muted uppercase tracking-wider">Candidates</span>
            </div>
            <div className="flex flex-col gap-1">
              <span className="text-2xl font-bold font-heading text-navy dark:text-yellow">
                {client.user_count ?? 0}
              </span>
              <span className="text-xs text-text-muted uppercase tracking-wider">
                Authorized Users
              </span>
            </div>
          </div>
        </div>

        {/* Access Configuration */}
        <div className="bg-surface border border-border rounded-xl p-5">
          <h3 className="text-sm font-bold text-text-primary uppercase tracking-wider mb-4 border-b border-border pb-2">
            Access Configuration
          </h3>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            <div>
              <p className="text-xs text-text-muted uppercase tracking-wider mb-2">
                Allowed Emails
              </p>
              <div className="flex flex-wrap gap-2">
                {client.allowed_emails && client.allowed_emails.length > 0 ? (
                  client.allowed_emails.map((email) => (
                    <span
                      key={email}
                      className="px-2.5 py-1 rounded-md bg-navy/5 border border-border text-xs font-medium text-text-primary"
                    >
                      {email}
                    </span>
                  ))
                ) : (
                  <span className="text-sm text-text-muted">—</span>
                )}
              </div>
            </div>
            <div>
              <p className="text-xs text-text-muted uppercase tracking-wider mb-2">
                Allowed Domains
              </p>
              <div className="flex flex-wrap gap-2">
                {client.allowed_domains && client.allowed_domains.length > 0 ? (
                  client.allowed_domains.map((domain) => (
                    <span
                      key={domain}
                      className="px-2.5 py-1 rounded-md bg-navy/5 border border-border text-xs font-medium text-text-primary"
                    >
                      {domain}
                    </span>
                  ))
                ) : (
                  <span className="text-sm text-text-muted">—</span>
                )}
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
