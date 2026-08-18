// Shared with app/(dashboard)/page.tsx (a Server Component), so this file must
// stay directive-free — a "use client" module's runtime exports aren't safe to
// dereference from server code.
export type ClientStage =
  | "sourced"
  | "sent_to_client"
  | "interview"
  | "decision_pending"
  | "offer"
  | "offer_accepted"
  | "position_close"
  | "selected"
  | "joined"
  | "rejected"
  | "candidate_dropped";

// Exactly which stages a client is allowed to see — notably excluding
// "on_hold", which is internal-only.
export const CLIENT_STAGE_LABELS: Record<ClientStage, string> = {
  sourced: "Sourced",
  sent_to_client: "Sent to Client",
  interview: "Interview",
  decision_pending: "Decision Pending",
  offer: "Offer",
  offer_accepted: "Offer Accepted",
  position_close: "Joined (Legacy)",
  selected: "Selected",
  joined: "Joined",
  rejected: "Rejected",
  candidate_dropped: "Candidate Dropped",
};

export const CLIENT_STAGES: ClientStage[] = [
  "sourced",
  "sent_to_client",
  "interview",
  "decision_pending",
  "offer",
  "offer_accepted",
  "position_close",
  "selected",
  "joined",
  "rejected",
  "candidate_dropped",
];
