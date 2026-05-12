/**
 * Centralised leaderboard mock data.
 * Replace with real API calls when production data is available.
 */

export interface LeaderboardRecruiter {
  id: string;
  name: string;
  initials: string;
  rank: number;
  xp: number;
  level: number;
  totalMappings: number;
  offersReceived: number;
  joined: number;
  rejected: number;
  monthlyGrowth: number; // percent
  successRate: number; // percent
  badge: LeaderboardBadgeKey;
  monthlyData: number[]; // 6 months of mapping counts
  avatarColor: string;
}

export type LeaderboardBadgeKey =
  | "top_mapper"
  | "hiring_champion"
  | "offer_king"
  | "consistency_star"
  | "rising_recruiter"
  | "fast_closer"
  | "elite_recruiter"
  | "recruitment_ninja";

export interface BadgeDefinition {
  key: LeaderboardBadgeKey;
  label: string;
  emoji: string;
  rarity: "legendary" | "epic" | "rare" | "uncommon";
  description: string;
}

export interface LeaderboardKpi {
  id: string;
  label: string;
  value: number;
  suffix?: string;
  helper: string;
  tone: "yellow" | "green" | "red" | "navy" | "neutral";
}

export interface CompanyHiringItem {
  company: string;
  role: string;
  totalSeats: number;
  filled: number;
  recruiterCount: number;
}

export interface RecentActivityItem {
  id: string;
  recruiter: string;
  initials: string;
  action: string;
  target: string;
  timestamp: string;
  tone: "yellow" | "green" | "red" | "neutral";
  avatarColor: string;
}

// ─── Badge Definitions ────────────────────────────────────────────────────────

export const BADGE_DEFINITIONS: Record<LeaderboardBadgeKey, BadgeDefinition> = {
  top_mapper: {
    key: "top_mapper",
    label: "Top Mapper",
    emoji: "🗺️",
    rarity: "epic",
    description: "Mapped 50+ candidates this month",
  },
  hiring_champion: {
    key: "hiring_champion",
    label: "Hiring Champion",
    emoji: "🏆",
    rarity: "legendary",
    description: "Closed the most positions in Q1",
  },
  offer_king: {
    key: "offer_king",
    label: "Offer King",
    emoji: "👑",
    rarity: "legendary",
    description: "Sent 20+ offers in a single month",
  },
  consistency_star: {
    key: "consistency_star",
    label: "Consistency Star",
    emoji: "⭐",
    rarity: "rare",
    description: "Maintained 80%+ success rate for 3 months",
  },
  rising_recruiter: {
    key: "rising_recruiter",
    label: "Rising Recruiter",
    emoji: "🚀",
    rarity: "uncommon",
    description: "50% month-over-month growth",
  },
  fast_closer: {
    key: "fast_closer",
    label: "Fast Closer",
    emoji: "⚡",
    rarity: "rare",
    description: "Average time-to-close under 14 days",
  },
  elite_recruiter: {
    key: "elite_recruiter",
    label: "Elite Recruiter",
    emoji: "💎",
    rarity: "legendary",
    description: "Top 1% across all metrics",
  },
  recruitment_ninja: {
    key: "recruitment_ninja",
    label: "Recruitment Ninja",
    emoji: "🥷",
    rarity: "epic",
    description: "Silent operator — joins with minimal rejections",
  },
};

// ─── Rarity colours ───────────────────────────────────────────────────────────

export const RARITY_STYLES: Record<
  BadgeDefinition["rarity"],
  { border: string; glow: string; label: string; bg: string }
> = {
  legendary: {
    border: "border-yellow/70",
    glow: "shadow-yellow/30",
    label: "text-yellow",
    bg: "bg-yellow/10",
  },
  epic: {
    border: "border-purple-400/60",
    glow: "shadow-purple-400/25",
    label: "text-purple-300",
    bg: "bg-purple-500/10",
  },
  rare: {
    border: "border-blue-400/60",
    glow: "shadow-blue-400/25",
    label: "text-blue-300",
    bg: "bg-blue-500/10",
  },
  uncommon: {
    border: "border-emerald-400/60",
    glow: "shadow-emerald-400/25",
    label: "text-emerald-300",
    bg: "bg-emerald-500/10",
  },
};

// ─── Mock Recruiters ──────────────────────────────────────────────────────────

export const MOCK_RECRUITERS: LeaderboardRecruiter[] = [
  {
    id: "1",
    name: "Manokamna Rao",
    initials: "MR",
    rank: 1,
    xp: 9420,
    level: 18,
    totalMappings: 67,
    offersReceived: 24,
    joined: 19,
    rejected: 8,
    monthlyGrowth: 34,
    successRate: 87,
    badge: "elite_recruiter",
    monthlyData: [28, 34, 41, 52, 61, 67],
    avatarColor: "#F3FF54",
  },
  {
    id: "2",
    name: "Hardik Patel",
    initials: "HP",
    rank: 2,
    xp: 8150,
    level: 16,
    totalMappings: 58,
    offersReceived: 20,
    joined: 16,
    rejected: 11,
    monthlyGrowth: 28,
    successRate: 81,
    badge: "hiring_champion",
    monthlyData: [22, 27, 35, 42, 50, 58],
    avatarColor: "#3DDC97",
  },
  {
    id: "3",
    name: "Edwin D'Souza",
    initials: "ED",
    rank: 3,
    xp: 7840,
    level: 15,
    totalMappings: 54,
    offersReceived: 19,
    joined: 15,
    rejected: 9,
    monthlyGrowth: 22,
    successRate: 79,
    badge: "offer_king",
    monthlyData: [20, 25, 31, 38, 47, 54],
    avatarColor: "#60A5FA",
  },
  {
    id: "4",
    name: "Riya Chatterjee",
    initials: "RC",
    rank: 4,
    xp: 6920,
    level: 14,
    totalMappings: 48,
    offersReceived: 16,
    joined: 12,
    rejected: 13,
    monthlyGrowth: 18,
    successRate: 72,
    badge: "top_mapper",
    monthlyData: [18, 22, 28, 34, 42, 48],
    avatarColor: "#F7C948",
  },
  {
    id: "5",
    name: "Aakash Menon",
    initials: "AM",
    rank: 5,
    xp: 6210,
    level: 13,
    totalMappings: 43,
    offersReceived: 14,
    joined: 10,
    rejected: 10,
    monthlyGrowth: 15,
    successRate: 68,
    badge: "fast_closer",
    monthlyData: [16, 20, 26, 31, 37, 43],
    avatarColor: "#FB923C",
  },
  {
    id: "6",
    name: "Tanvi Kulkarni",
    initials: "TK",
    rank: 6,
    xp: 5680,
    level: 12,
    totalMappings: 38,
    offersReceived: 12,
    joined: 9,
    rejected: 8,
    monthlyGrowth: 24,
    successRate: 76,
    badge: "consistency_star",
    monthlyData: [12, 16, 21, 27, 33, 38],
    avatarColor: "#C084FC",
  },
  {
    id: "7",
    name: "Nikhil Bhat",
    initials: "NB",
    rank: 7,
    xp: 4950,
    level: 10,
    totalMappings: 32,
    offersReceived: 10,
    joined: 7,
    rejected: 12,
    monthlyGrowth: 11,
    successRate: 59,
    badge: "recruitment_ninja",
    monthlyData: [10, 13, 18, 23, 28, 32],
    avatarColor: "#2DD4BF",
  },
  {
    id: "8",
    name: "Arjun Iyer",
    initials: "AI",
    rank: 8,
    xp: 4310,
    level: 9,
    totalMappings: 28,
    offersReceived: 8,
    joined: 6,
    rejected: 9,
    monthlyGrowth: 52,
    successRate: 61,
    badge: "rising_recruiter",
    monthlyData: [6, 8, 12, 17, 22, 28],
    avatarColor: "#FF8A8A",
  },
  {
    id: "9",
    name: "Priya Nair",
    initials: "PN",
    rank: 9,
    xp: 3780,
    level: 8,
    totalMappings: 24,
    offersReceived: 7,
    joined: 5,
    rejected: 7,
    monthlyGrowth: 9,
    successRate: 63,
    badge: "consistency_star",
    monthlyData: [8, 10, 14, 18, 22, 24],
    avatarColor: "#94A3B8",
  },
  {
    id: "10",
    name: "Mohit Sharma",
    initials: "MS",
    rank: 10,
    xp: 3120,
    level: 7,
    totalMappings: 20,
    offersReceived: 6,
    joined: 4,
    rejected: 8,
    monthlyGrowth: 7,
    successRate: 55,
    badge: "rising_recruiter",
    monthlyData: [6, 8, 11, 14, 17, 20],
    avatarColor: "#6B7280",
  },
];

// ─── KPI Data ─────────────────────────────────────────────────────────────────

export const LEADERBOARD_KPIS: LeaderboardKpi[] = [
  {
    id: "total_recruiters",
    label: "Active Recruiters",
    value: 10,
    helper: "Competing this month",
    tone: "yellow",
  },
  {
    id: "total_mappings",
    label: "Total Mappings",
    value: 412,
    helper: "Across all recruiters",
    tone: "neutral",
  },
  {
    id: "offers_received",
    label: "Offers Sent",
    value: 136,
    helper: "Client-facing profiles",
    tone: "navy",
  },
  {
    id: "successful_joins",
    label: "Successful Joins",
    value: 103,
    helper: "Onboarded this cycle",
    tone: "green",
  },
  {
    id: "conversion_rate",
    label: "Conversion Rate",
    value: 76,
    suffix: "%",
    helper: "Offers → Joins",
    tone: "yellow",
  },
  {
    id: "monthly_growth",
    label: "Avg Monthly Growth",
    value: 22,
    suffix: "%",
    helper: "Team-wide MoM",
    tone: "green",
  },
  {
    id: "active_companies",
    label: "Active Companies",
    value: 24,
    helper: "Open hiring mandates",
    tone: "neutral",
  },
  {
    id: "top_score",
    label: "Top XP Score",
    value: 9420,
    helper: "Manokamna Rao",
    tone: "yellow",
  },
];

// ─── Company Hiring Progress ──────────────────────────────────────────────────

export const COMPANY_HIRING: CompanyHiringItem[] = [
  {
    company: "August Cafe",
    role: "Restaurant Manager",
    totalSeats: 8,
    filled: 6,
    recruiterCount: 3,
  },
  { company: "Olive", role: "Sous Chef", totalSeats: 5, filled: 5, recruiterCount: 2 },
  {
    company: "Aures Hospitality",
    role: "Commis Chef",
    totalSeats: 12,
    filled: 7,
    recruiterCount: 4,
  },
  {
    company: "Ghost Kitchens",
    role: "Kitchen Assistant",
    totalSeats: 10,
    filled: 4,
    recruiterCount: 3,
  },
  { company: "Hunger Inc", role: "Captain", totalSeats: 6, filled: 3, recruiterCount: 2 },
  { company: "Le 15", role: "Pastry Chef", totalSeats: 4, filled: 4, recruiterCount: 1 },
  { company: "NOTO", role: "Bartender", totalSeats: 7, filled: 2, recruiterCount: 2 },
];

// ─── Recent Activity ──────────────────────────────────────────────────────────

export const RECENT_ACTIVITY: RecentActivityItem[] = [
  {
    id: "a1",
    recruiter: "Manokamna Rao",
    initials: "MR",
    action: "Candidate joined",
    target: "Aarav Shah → August Cafe",
    timestamp: "2 min ago",
    tone: "green",
    avatarColor: "#F3FF54",
  },
  {
    id: "a2",
    recruiter: "Hardik Patel",
    initials: "HP",
    action: "Offer sent",
    target: "Diya Nair → Olive",
    timestamp: "18 min ago",
    tone: "yellow",
    avatarColor: "#3DDC97",
  },
  {
    id: "a3",
    recruiter: "Riya Chatterjee",
    initials: "RC",
    action: "Candidate mapped",
    target: "Kabir Singh → Ghost Kitchens",
    timestamp: "45 min ago",
    tone: "neutral",
    avatarColor: "#F7C948",
  },
  {
    id: "a4",
    recruiter: "Edwin D'Souza",
    initials: "ED",
    action: "Offer accepted",
    target: "Meera Pillai → Hunger Inc",
    timestamp: "1 hr ago",
    tone: "green",
    avatarColor: "#60A5FA",
  },
  {
    id: "a5",
    recruiter: "Aakash Menon",
    initials: "AM",
    action: "Candidate rejected",
    target: "Vivaan Rao → Le 15",
    timestamp: "2 hr ago",
    tone: "red",
    avatarColor: "#FB923C",
  },
  {
    id: "a6",
    recruiter: "Tanvi Kulkarni",
    initials: "TK",
    action: "Candidate mapped",
    target: "Nitya Gupta → NOTO",
    timestamp: "3 hr ago",
    tone: "neutral",
    avatarColor: "#C084FC",
  },
];

// ─── Month labels (last 6 months) ─────────────────────────────────────────────

export const MONTH_LABELS = ["Dec", "Jan", "Feb", "Mar", "Apr", "May"];
