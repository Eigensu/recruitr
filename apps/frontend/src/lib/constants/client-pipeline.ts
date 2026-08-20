// Shared with app/(dashboard)/page.tsx (a Server Component), so this file must
// stay directive-free — a "use client" module's runtime exports aren't safe to
// dereference from server code.
export type ClientStage = "sent_to_client" | "interview" | "selected" | "joined" | "rejected";

export const CLIENT_STAGE_LABELS: Record<ClientStage, string> = {
  sent_to_client: "Mapped to Role",
  interview: "Interview",
  selected: "Selected",
  joined: "Joined",
  rejected: "Rejected",
};

export const CLIENT_STAGES: ClientStage[] = [
  "sent_to_client",
  "interview",
  "selected",
  "joined",
  "rejected",
];
