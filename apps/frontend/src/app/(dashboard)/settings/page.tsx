"use client";
import React, { useState } from "react";
import { useRouter } from "next/navigation";
import { IconUser, IconUsers } from "@tabler/icons-react";
import TeamSettingsTab from "@/components/settings/TeamSettingsTab";
import RefereeSettingsTab from "@/components/settings/RefereeSettingsTab";
import AutomationSettingsPanel from "@/components/settings/AutomationSettings";
import NotificationPreferences from "@/components/settings/NotificationPreferences";
import SettingsShell from "@/components/settings/SettingsShell";
import PreferencesPanel from "@/components/settings/PreferencesPanel";
import AccountPanel from "@/components/settings/AccountPanel";
import { useCurrentUser } from "@/hooks/useCurrentUser";
import { useApiFetch } from "@/lib/api";
import { listTeams, listTeamEmployees, type Team, type EmployeeTeamInfo } from "@/lib/api/teams";

export default function SettingsPage() {
  const router = useRouter();
  const apiFetch = useApiFetch();

  const { user, isLoading: userLoading, isMaintainer } = useCurrentUser();

  const [myTeam, setMyTeam] = useState<Team | null>(null);
  const [teammates, setTeammates] = useState<EmployeeTeamInfo[]>([]);
  const [teamLoading, setTeamLoading] = useState(false);

  React.useEffect(() => {
    if (!user || user.role !== "employee") return;
    let cancelled = false;
    async function load() {
      setTeamLoading(true);
      try {
        const [teams, employees] = await Promise.all([
          listTeams(apiFetch),
          listTeamEmployees(apiFetch),
        ]);
        if (cancelled) return;
        const me = employees.find((e) => e.id === user?.employee_id);
        if (!me?.team_id) {
          setMyTeam(null);
          setTeammates([]);
          return;
        }
        const team = teams.find((t) => t.id === me.team_id) ?? null;
        setMyTeam(team);
        setTeammates(employees.filter((e) => e.team_id === me.team_id && e.id !== me.id));
      } catch {
        // ignore
      } finally {
        if (!cancelled) setTeamLoading(false);
      }
    }
    load();
    return () => {
      cancelled = true;
    };
  }, [user, apiFetch]);

  const TABS = [
    "Preferences",
    ...(isMaintainer ? ["Team", "Referees", "Automation"] : []),
    "Account",
  ];
  const [activeTab, setActiveTab] = useState("Preferences");

  async function handleLogout() {
    try {
      await fetch(
        `${process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000"}/api/v1/auth/logout`,
        { method: "POST", credentials: "include" },
      );
    } catch (err) {
      console.error("Logout failed:", err);
    } finally {
      // Safely remove only client messaging dismissals
      try {
        for (let i = sessionStorage.length - 1; i >= 0; i--) {
          const key = sessionStorage.key(i);
          if (key?.startsWith("dismissed_banners_")) {
            sessionStorage.removeItem(key);
          }
        }
      } catch (storageErr) {
        console.warn("Failed to clear session storage:", storageErr);
      } finally {
        router.push("/sign-in");
      }
    }
  }

  const myTeamRow = user?.role === "employee" && (
    <div className="grid grid-cols-1 md:grid-cols-3 gap-4 md:gap-6 py-6 items-start">
      <div>
        <p className="text-sm font-medium text-text-primary flex items-center gap-1.5">
          <IconUsers className="w-4 h-4 text-text-muted" /> My Team
        </p>
        <p className="text-sm text-text-secondary mt-1">Your assigned team and teammates.</p>
      </div>
      <div className="md:col-span-2 max-w-md">
        <MyTeamCard
          loading={teamLoading}
          team={myTeam}
          teammates={teammates}
          selfName={user.full_name ?? user.email}
          selfEmail={user.email}
        />
      </div>
    </div>
  );

  return (
    <SettingsShell tabs={TABS} activeTab={activeTab} onTabChange={setActiveTab}>
      {activeTab === "Preferences" && (
        <PreferencesPanel extraRows={myTeamRow}>
          <div className="pt-2">
            <NotificationPreferences />
          </div>
        </PreferencesPanel>
      )}
      {activeTab === "Account" && (
        <AccountPanel user={user} isLoading={userLoading} onLogout={handleLogout} />
      )}
      {activeTab === "Team" && isMaintainer && <TeamSettingsTab />}
      {activeTab === "Referees" && isMaintainer && <RefereeSettingsTab />}
      {activeTab === "Automation" && isMaintainer && <AutomationSettingsPanel />}
    </SettingsShell>
  );
}

interface MyTeamCardProps {
  loading: boolean;
  team: Team | null;
  teammates: EmployeeTeamInfo[];
  selfName: string;
  selfEmail: string;
}

/** The team roster shown on the Preferences tab, current user pinned first. */
function MyTeamCard({ loading, team, teammates, selfName, selfEmail }: MyTeamCardProps) {
  if (loading) return <p className="text-sm text-text-muted">Loading…</p>;
  if (!team) return <p className="text-sm text-text-muted italic">Not assigned to a team yet.</p>;

  return (
    <div className="border border-border rounded-lg bg-surface overflow-hidden">
      <div className="px-4 py-3 bg-surface-2 border-b border-border flex items-center justify-between">
        <span className="text-sm font-semibold text-text-primary">{team.name}</span>
        <span className="text-xs text-text-muted">
          {teammates.length + 1} member{teammates.length !== 0 ? "s" : ""}
        </span>
      </div>
      <div className="divide-y divide-border">
        <div className="px-4 py-2.5 flex items-center gap-3">
          <div className="w-7 h-7 rounded-full bg-navy/10 dark:bg-yellow/10 flex items-center justify-center shrink-0">
            <IconUser className="w-3.5 h-3.5 text-navy dark:text-yellow" />
          </div>
          <div className="min-w-0">
            <p className="text-sm font-medium text-text-primary truncate">{selfName}</p>
            <p className="text-xs text-text-muted truncate">{selfEmail}</p>
          </div>
          <span className="ml-auto text-xs font-medium px-2 py-0.5 rounded-full bg-navy/10 dark:bg-yellow/10 text-navy dark:text-yellow border border-navy/20 dark:border-yellow/20 shrink-0">
            You
          </span>
        </div>
        {teammates.map((m) => (
          <div key={m.id} className="px-4 py-2.5 flex items-center gap-3">
            <div className="w-7 h-7 rounded-full bg-surface-2 border border-border flex items-center justify-center shrink-0">
              <IconUser className="w-3.5 h-3.5 text-text-muted" />
            </div>
            <div className="min-w-0">
              <p className="text-sm text-text-primary truncate">{m.name}</p>
              <p className="text-xs text-text-muted truncate">{m.email}</p>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
