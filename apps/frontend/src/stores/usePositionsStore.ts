import { create } from "zustand";

export interface MockPosition {
  id: string;
  clientName: string;
  role: string;
  department: string;
  city: string;
  seniority: "Junior" | "Mid" | "Senior";
  dateOpened: string;
  targetClose: string;
  assignedTo: string;
  openingsCount: number;
  status: "Open" | "Closed";
  notes?: string;
}

export interface MockCandidate {
  id: string;
  name: string;
  email: string;
  phone: string;
  skills: string[];
  matchScore: number;
  previousCompany?: string;
  experienceYears: number;
}

interface PositionsState {
  positions: MockPosition[];
  candidates: MockCandidate[];
  mappings: Record<string, string[]>; // positionId -> candidateIds
  selectedPositionId: string | null;
  setSelectedPositionId: (id: string | null) => void;
  mapCandidate: (positionId: string, candidateId: string) => void;
  unmapCandidate: (positionId: string, candidateId: string) => void;
  addCandidate: (candidate: Omit<MockCandidate, "id" | "matchScore">) => void;
}

const MOCK_POSITIONS: MockPosition[] = [
  {
    id: "CLI-031-POS-001",
    clientName: "Hunger Inc",
    role: "Cafe Steward",
    department: "F&B - Service",
    city: "Mumbai",
    seniority: "Junior",
    dateOpened: "2026-05-01",
    targetClose: "2026-06-01",
    assignedTo: "Edwin",
    openingsCount: 7,
    status: "Open",
  },
  {
    id: "CLI-031-POS-002",
    clientName: "Hunger Inc",
    role: "Captain",
    department: "F&B - Service",
    city: "Mumbai",
    seniority: "Junior",
    dateOpened: "2026-05-03",
    targetClose: "2026-06-03",
    assignedTo: "Edwin",
    openingsCount: 7,
    status: "Open",
  },
  {
    id: "CLI-026-POS-001",
    clientName: "Foodmatters",
    role: "Captain",
    department: "F&B - Service",
    city: "Mumbai",
    seniority: "Junior",
    dateOpened: "2026-04-10",
    targetClose: "2026-05-10",
    assignedTo: "Edwin",
    openingsCount: 0,
    status: "Closed",
  },
  {
    id: "CLI-026-POS-002",
    clientName: "Foodmatters",
    role: "Steward",
    department: "F&B - Service",
    city: "Mumbai",
    seniority: "Junior",
    dateOpened: "2026-05-05",
    targetClose: "2026-06-05",
    assignedTo: "Edwin",
    openingsCount: 8,
    status: "Open",
  },
  {
    id: "CLI-026-POS-003",
    clientName: "Foodmatters",
    role: "Bartender",
    department: "F&B - Service",
    city: "Mumbai",
    seniority: "Junior",
    dateOpened: "2026-04-12",
    targetClose: "2026-05-12",
    assignedTo: "Edwin",
    openingsCount: 0,
    status: "Closed",
  },
  {
    id: "CLI-001-POS-001",
    clientName: "ABNAH",
    role: "Steward",
    department: "F&B - Service",
    city: "Mumbai",
    seniority: "Junior",
    dateOpened: "2026-05-08",
    targetClose: "2026-06-08",
    assignedTo: "Mohit",
    openingsCount: 5,
    status: "Open",
  },
  {
    id: "CLI-001-POS-002",
    clientName: "ABNAH",
    role: "GRE",
    department: "F&B - Service",
    city: "Mumbai",
    seniority: "Junior",
    dateOpened: "2026-05-10",
    targetClose: "2026-06-10",
    assignedTo: "Mohit",
    openingsCount: 3,
    status: "Open",
  },
  {
    id: "CLI-001-POS-003",
    clientName: "ABNAH",
    role: "Bartender",
    department: "F&B - Service",
    city: "Mumbai",
    seniority: "Junior",
    dateOpened: "2026-05-12",
    targetClose: "2026-06-12",
    assignedTo: "Mohit",
    openingsCount: 3,
    status: "Open",
  },
  {
    id: "CLI-014-POS-001",
    clientName: "Blondie",
    role: "ARM",
    department: "F&B - Service",
    city: "Mumbai",
    seniority: "Mid",
    dateOpened: "2026-05-15",
    targetClose: "2026-06-15",
    assignedTo: "Aakash",
    openingsCount: 3,
    status: "Open",
  },
  {
    id: "CLI-014-POS-002",
    clientName: "Blondie",
    role: "RM",
    department: "F&B - Service",
    city: "Mumbai",
    seniority: "Mid",
    dateOpened: "2026-05-16",
    targetClose: "2026-06-16",
    assignedTo: "Aakash",
    openingsCount: 3,
    status: "Open",
  },
  {
    id: "CLI-014-POS-003",
    clientName: "Blondie",
    role: "Operations Head",
    department: "Operations",
    city: "Mumbai",
    seniority: "Senior",
    dateOpened: "2026-04-01",
    targetClose: "2026-05-01",
    assignedTo: "Aakash",
    openingsCount: 1,
    status: "Closed",
  },
  {
    id: "CLI-014-POS-004",
    clientName: "Blondie",
    role: "Social Media Manager",
    department: "Marketing & PR",
    city: "Mumbai",
    seniority: "Junior",
    dateOpened: "2026-05-20",
    targetClose: "2026-06-20",
    assignedTo: "Aakash",
    openingsCount: 2,
    status: "Open",
  },
  {
    id: "CLI-016-POS-001",
    clientName: "CocoCart",
    role: "F&B Associate",
    department: "F&B - Service",
    city: "Mumbai",
    seniority: "Junior",
    dateOpened: "2026-05-01",
    targetClose: "2026-06-15",
    assignedTo: "Mohit",
    openingsCount: 35,
    status: "Open",
  },
  {
    id: "CLI-071-POS-001",
    clientName: "UGIPL",
    role: "Sous Chef",
    department: "F&B - Kitchen",
    city: "Mumbai",
    seniority: "Senior",
    dateOpened: "2026-05-22",
    targetClose: "2026-06-22",
    assignedTo: "Mohit",
    openingsCount: 1,
    status: "Open",
    notes: "Pizza Chef",
  },
  {
    id: "CLI-071-POS-002",
    clientName: "UGIPL",
    role: "Outlet Supervisor",
    department: "F&B - Service",
    city: "Mumbai",
    seniority: "Mid",
    dateOpened: "2026-05-24",
    targetClose: "2026-06-24",
    assignedTo: "Manokamna",
    openingsCount: 3,
    status: "Open",
  },
  {
    id: "CLI-071-POS-003",
    clientName: "UGIPL",
    role: "Steward",
    department: "F&B - Service",
    city: "Mumbai",
    seniority: "Junior",
    dateOpened: "2026-05-25",
    targetClose: "2026-06-25",
    assignedTo: "Manokamna",
    openingsCount: 8,
    status: "Open",
  },
];

const MOCK_CANDIDATES: MockCandidate[] = [
  // F&B / Stewards & Captains
  {
    id: "mc1",
    name: "Priya Nair",
    email: "priya.nair@example.com",
    phone: "+91 98765 43210",
    skills: ["Guest Relations", "Table Service", "POS Systems", "Order Taking"],
    matchScore: 94,
    previousCompany: "The Taj Mahal Palace",
    experienceYears: 2,
  },
  {
    id: "mc2",
    name: "Karan Malhotra",
    email: "karan.m@example.com",
    phone: "+91 98123 45678",
    skills: ["F&B Service", "Fine Dining", "Banquets", "Team Leadership"],
    matchScore: 89,
    previousCompany: "JW Marriott Mumbai",
    experienceYears: 3,
  },
  {
    id: "mc3",
    name: "Sneha Gupta",
    email: "sneha.g@example.com",
    phone: "+91 97654 32109",
    skills: ["Hostess", "Table Reservation", "Billing", "Guest Relations"],
    matchScore: 85,
    previousCompany: "Leela Palace",
    experienceYears: 1.5,
  },
  // Bartenders
  {
    id: "mc4",
    name: "Sunil Mehta",
    email: "sunil.bartender@example.com",
    phone: "+91 99887 76655",
    skills: ["Mixology", "Classic Cocktails", "Inventory Management", "Speed Pouring"],
    matchScore: 92,
    previousCompany: "Trident Nariman Point",
    experienceYears: 4,
  },
  // Chefs
  {
    id: "mc5",
    name: "Rajesh Kumar",
    email: "chef.rajesh@example.com",
    phone: "+91 95555 44444",
    skills: ["Pizza Dough Crafting", "Wood-fired Oven", "Italian Cuisine", "Food Safety"],
    matchScore: 96,
    previousCompany: "Pizza Express Mumbai",
    experienceYears: 6,
  },
  {
    id: "mc6",
    name: "Amit Sharma",
    email: "amit.souschef@example.com",
    phone: "+91 94444 33333",
    skills: ["Sous Chef", "Kitchen Management", "Continental Cuisine", "Plating"],
    matchScore: 88,
    previousCompany: "Oberoi Hotels",
    experienceYears: 5,
  },
  {
    id: "mc7",
    name: "Vikram Singh",
    email: "vikram.cook@example.com",
    phone: "+91 93333 22222",
    skills: ["Tandoor Cook", "Indian Curry", "Bulk Cooking", "Prep Work"],
    matchScore: 75,
    previousCompany: "Local Dhaba Elite",
    experienceYears: 3,
  },
  // Management & Ops
  {
    id: "mc8",
    name: "Rohan Joshi",
    email: "rohan.joshi@example.com",
    phone: "+91 92222 11111",
    skills: [
      "Restaurant Operations",
      "P&L Management",
      "Staff Scheduling",
      "Customer Satisfaction",
    ],
    matchScore: 95,
    previousCompany: "Olive Bar & Kitchen",
    experienceYears: 8,
  },
  {
    id: "mc9",
    name: "Nisha Rao",
    email: "nisha.ops@example.com",
    phone: "+91 91111 00000",
    skills: ["Assistant Manager", "Inventory Audits", "Staff Training", "Escalation Handling"],
    matchScore: 87,
    previousCompany: "Social Offline",
    experienceYears: 4.5,
  },
  // Marketing & PR
  {
    id: "mc10",
    name: "Ananya Sen",
    email: "ananya.marketing@example.com",
    phone: "+91 90000 99999",
    skills: ["Instagram Marketing", "Content Creation", "Canva", "Brand Strategy"],
    matchScore: 93,
    previousCompany: "F&B Marketing Agency",
    experienceYears: 3,
  },
  {
    id: "mc11",
    name: "Rahul Verma",
    email: "rahul.ads@example.com",
    phone: "+91 89999 88888",
    skills: ["Digital Ads (Meta/Google)", "Graphic Design", "Video Reels Editing", "Analytics"],
    matchScore: 81,
    previousCompany: "Freelance Brand Specialist",
    experienceYears: 2,
  },
];

export const usePositionsStore = create<PositionsState>((set) => ({
  positions: MOCK_POSITIONS,
  candidates: MOCK_CANDIDATES,
  mappings: {
    "CLI-031-POS-001": ["mc1", "mc3"],
    "CLI-031-POS-002": ["mc2"],
    "CLI-026-POS-002": ["mc1"],
    "CLI-001-POS-001": ["mc2", "mc3"],
    "CLI-014-POS-004": ["mc10"],
    "CLI-071-POS-001": ["mc5"],
  },
  selectedPositionId: null,

  setSelectedPositionId: (id) => set({ selectedPositionId: id }),

  mapCandidate: (positionId, candidateId) =>
    set((state) => {
      const currentList = state.mappings[positionId] || [];
      if (currentList.includes(candidateId)) return state;
      return {
        mappings: {
          ...state.mappings,
          [positionId]: [...currentList, candidateId],
        },
      };
    }),

  unmapCandidate: (positionId, candidateId) =>
    set((state) => {
      const currentList = state.mappings[positionId] || [];
      return {
        mappings: {
          ...state.mappings,
          [positionId]: currentList.filter((id) => id !== candidateId),
        },
      };
    }),

  addCandidate: (candidate) =>
    set((state) => {
      const newCandidate: MockCandidate = {
        ...candidate,
        id: `mc${state.candidates.length + 1}`,
        matchScore: Math.floor(Math.random() * 20) + 75, // mock random score 75-95
      };
      return { candidates: [newCandidate, ...state.candidates] };
    }),
}));
