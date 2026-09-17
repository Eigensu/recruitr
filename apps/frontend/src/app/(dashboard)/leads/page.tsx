import { IconPhoneCall } from "@tabler/icons-react";

// Landing route for telecallers: sign-in, Google OAuth and RouteGuard all send
// the role here, since every other staff page is built on endpoints it is
// refused. The review queue itself arrives with the intake workflow.
export default function LeadsPage() {
  return (
    <main className="mx-auto w-full max-w-7xl p-4 sm:p-6 lg:p-8 animate-in fade-in duration-300">
      <header className="mb-8">
        <h1 className="text-2xl font-bold text-text-primary tracking-tight">Leads</h1>
        <p className="text-sm text-text-secondary mt-1">
          Inbound candidates waiting for a screening call.
        </p>
      </header>
      <div className="flex flex-col items-center justify-center gap-3 rounded-xl border border-dashed border-border py-16 text-center">
        <IconPhoneCall className="size-8 text-text-secondary" />
        <p className="text-sm text-text-secondary">No leads assigned to you yet.</p>
      </div>
    </main>
  );
}
