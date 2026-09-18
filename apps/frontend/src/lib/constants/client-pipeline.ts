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

// Mirrors the client whitelist in the backend's move_mapping_to_stage
// (recruitment/controller/pipeline.py). Anything outside this map is a 403 for
// a client account, so the board checks it before firing a request rather than
// letting the user drop a card and then bounce it back.
export const CLIENT_ALLOWED_TRANSITIONS: Readonly<Record<string, readonly ClientStage[]>> = {
  sent_to_client: ["interview", "rejected"],
  interview: ["selected", "rejected"],
};

export function isClientTransitionAllowed(from: string, to: string): boolean {
  return (CLIENT_ALLOWED_TRANSITIONS[from] ?? []).includes(to as ClientStage);
}
