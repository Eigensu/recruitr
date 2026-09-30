"use client";

import React, { useEffect, useState } from "react";
import { IconLoader2, IconPlayerPause, IconPlayerPlay, IconPlus } from "@tabler/icons-react";
import { cn } from "@/lib/utils";
import { apiErrorMessage, useApiFetch } from "@/lib/api";
import { useToast } from "@/components/ui/Toast";
import {
  addTelecaller,
  fetchTelecallers,
  setTelecallerActive,
  type IntakeTelecaller,
} from "@/lib/api/intake";

const STATUS_STYLES: Record<string, string> = {
  Active: "bg-green-100 text-green-700",
  Paused: "bg-red-100 text-red-700",
  "Not signed up": "bg-yellow-100 text-yellow-800",
};

function telecallerStatus(person: IntakeTelecaller): string {
  if (!person.is_active) return "Paused";
  return person.has_account ? "Active" : "Not signed up";
}

function upsert(list: IntakeTelecaller[], row: IntakeTelecaller): IntakeTelecaller[] {
  const next = list.some((p) => p.id === row.id)
    ? list.map((p) => (p.id === row.id ? row : p))
    : [...list, row];
  return next.sort((a, b) => a.name.localeCompare(b.name));
}

/**
 * Who screens inbound leads. Admins add and pause; maintainers can see the list.
 *
 * Adding writes the role onto both the login and the employee record, so the
 * person joins the lead rotation at once — not at their next sign-in, which is
 * what promoting the login alone used to mean.
 */
export default function TelecallerSettingsTab({ isAdmin }: Readonly<{ isAdmin: boolean }>) {
  const apiFetch = useApiFetch();
  const toast = useToast();

  const [people, setPeople] = useState<IntakeTelecaller[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [isAdding, setIsAdding] = useState(false);
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [addError, setAddError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [toggling, setToggling] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    fetchTelecallers(apiFetch)
      .then((data) => {
        if (!cancelled) setPeople(data);
      })
      .catch((err: unknown) => {
        if (!cancelled) setError(apiErrorMessage(err, "Failed to load telecallers"));
      })
      .finally(() => {
        if (!cancelled) setIsLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [apiFetch]);

  async function handleAdd(e: React.FormEvent) {
    e.preventDefault();
    setAddError(null);
    setIsSubmitting(true);
    try {
      const row = await addTelecaller(apiFetch, {
        email: email.trim(),
        name: name.trim() || null,
      });
      setPeople((prev) => upsert(prev, row));
      setIsAdding(false);
      setName("");
      setEmail("");
      toast(
        row.has_account
          ? `${row.name} is now a telecaller and will start receiving leads.`
          : `${row.name} can now sign up with ${row.email} and will land in the lead queue.`,
        "success",
      );
    } catch (err) {
      setAddError(apiErrorMessage(err, "Failed to add telecaller"));
    } finally {
      setIsSubmitting(false);
    }
  }

  async function handleToggle(person: IntakeTelecaller) {
    setToggling(person.id);
    try {
      const row = await setTelecallerActive(apiFetch, person.id, !person.is_active);
      setPeople((prev) => upsert(prev, row));
      if (!row.is_active && row.open_leads > 0) {
        toast(
          `${row.name} is paused but still holds ${row.open_leads} open lead${row.open_leads === 1 ? "" : "s"} — reassign them from the Leads page.`,
          "info",
        );
      }
    } catch (err) {
      toast(apiErrorMessage(err, "Failed to update telecaller"), "error");
    } finally {
      setToggling(null);
    }
  }

  if (isLoading) {
    return <div className="py-12 flex justify-center text-text-muted">Loading telecallers...</div>;
  }

  if (error) {
    return <div className="py-12 flex justify-center text-red-500">{error}</div>;
  }

  const columns = isAdmin ? 5 : 4;

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-lg font-bold text-text-primary">Telecallers</h2>
        <p className="text-sm text-text-secondary mt-1">
          People who screen inbound leads by phone. New leads are shared between active telecallers
          in turn.
        </p>
      </div>

      <div className="border border-border rounded-xl bg-surface overflow-hidden shadow-sm">
        <div className="flex items-center justify-between p-4 border-b border-border bg-surface-2">
          <h3 className="font-bold text-text-primary">Telecaller roster</h3>
          {isAdmin && (
            <button
              type="button"
              onClick={() => setIsAdding(true)}
              className="flex items-center gap-2 px-3 py-1.5 bg-navy dark:bg-yellow dark:text-navy text-white rounded-lg text-sm font-medium hover:opacity-90 transition-opacity cursor-pointer shadow-sm"
            >
              <IconPlus className="size-4" /> Add Telecaller
            </button>
          )}
        </div>

        {isAdding && (
          <div className="p-4 border-b border-border bg-canvas/50">
            <form onSubmit={handleAdd} className="space-y-4">
              <div>
                <h4 className="text-sm font-bold text-text-primary">Add a telecaller</h4>
                <p className="mt-1 text-xs text-text-secondary">
                  An existing recruiter is switched to telecaller. Someone without an account can
                  sign up with this email, even outside the company domain.
                </p>
              </div>
              {addError && (
                <div className="p-3 bg-red-50 text-red-600 text-sm rounded-lg border border-red-100">
                  {addError}
                </div>
              )}
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                <div>
                  <label
                    htmlFor="telecaller-name"
                    className="block text-xs font-medium text-text-secondary mb-1"
                  >
                    Name (Optional)
                  </label>
                  <input
                    id="telecaller-name"
                    type="text"
                    value={name}
                    onChange={(e) => setName(e.target.value)}
                    placeholder="Jane Doe"
                    className="w-full px-3 py-2 bg-surface border border-border rounded-lg text-sm focus:ring-2 focus:ring-navy outline-none text-text-primary"
                    disabled={isSubmitting}
                  />
                </div>
                <div>
                  <label
                    htmlFor="telecaller-email"
                    className="block text-xs font-medium text-text-secondary mb-1"
                  >
                    Email Address
                  </label>
                  <input
                    id="telecaller-email"
                    type="email"
                    required
                    value={email}
                    onChange={(e) => setEmail(e.target.value)}
                    placeholder="jane@example.com"
                    className="w-full px-3 py-2 bg-surface border border-border rounded-lg text-sm focus:ring-2 focus:ring-navy outline-none text-text-primary"
                    disabled={isSubmitting}
                  />
                </div>
              </div>
              <div className="flex justify-end gap-3 pt-2">
                <button
                  type="button"
                  onClick={() => {
                    setIsAdding(false);
                    setAddError(null);
                  }}
                  className="px-4 py-2 text-sm font-medium text-text-secondary hover:text-text-primary transition-colors cursor-pointer"
                  disabled={isSubmitting}
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={isSubmitting}
                  className="px-4 py-2 bg-navy dark:bg-yellow dark:text-navy text-white text-sm font-medium rounded-lg hover:opacity-90 transition-opacity disabled:opacity-50 cursor-pointer"
                >
                  {isSubmitting ? "Adding..." : "Add Telecaller"}
                </button>
              </div>
            </form>
          </div>
        )}

        <div className="overflow-x-auto">
          <table className="w-full text-sm text-left">
            <thead className="bg-surface-2 border-b border-border text-xs uppercase text-text-secondary font-semibold">
              <tr>
                <th className="px-4 py-3">Name</th>
                <th className="px-4 py-3">Email</th>
                <th className="px-4 py-3">Status</th>
                <th className="px-4 py-3">Open leads</th>
                {isAdmin && <th className="px-4 py-3 text-right">Actions</th>}
              </tr>
            </thead>
            <tbody className="divide-y divide-border">
              {people.map((person) => {
                const status = telecallerStatus(person);
                return (
                  <tr key={person.id} className="hover:bg-surface-2/50 transition-colors">
                    <td className="px-4 py-3 font-medium text-text-primary">{person.name}</td>
                    <td className="px-4 py-3 text-text-secondary">{person.email}</td>
                    <td className="px-4 py-3">
                      <span
                        className={`px-2 py-1 rounded-full text-[10px] font-bold tracking-wider uppercase ${STATUS_STYLES[status]}`}
                      >
                        {status}
                      </span>
                    </td>
                    <td className="px-4 py-3 text-text-secondary">{person.open_leads}</td>
                    {isAdmin && (
                      <td className="px-4 py-3 text-right">
                        <button
                          type="button"
                          onClick={() => handleToggle(person)}
                          disabled={toggling === person.id}
                          title={person.is_active ? "Pause — no new leads" : "Resume"}
                          className={cn(
                            "inline-flex items-center gap-1.5 rounded-md px-2 py-1.5 text-xs font-medium transition-colors cursor-pointer disabled:opacity-50",
                            person.is_active
                              ? "text-text-muted hover:text-red-500 hover:bg-red-50"
                              : "text-text-muted hover:text-green-600 hover:bg-green-50",
                          )}
                        >
                          {toggling === person.id && (
                            <IconLoader2 className="size-4 animate-spin" />
                          )}
                          {toggling !== person.id &&
                            (person.is_active ? (
                              <IconPlayerPause className="size-4" />
                            ) : (
                              <IconPlayerPlay className="size-4" />
                            ))}
                          {person.is_active ? "Pause" : "Resume"}
                        </button>
                      </td>
                    )}
                  </tr>
                );
              })}
              {people.length === 0 && !isAdding && (
                <tr>
                  <td colSpan={columns} className="px-4 py-12 text-center text-text-muted">
                    No telecallers yet.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
