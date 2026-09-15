/** Shared option lists for candidate intake, so every form offers the same values. */

export const CITIES = [
  "Mumbai",
  "Delhi",
  "Bangalore",
  "Hyderabad",
  "Pune",
  "Goa",
  "Chennai",
  "Kolkata",
  "Ahmedabad",
  "Jaipur",
  "Other",
] as const;

/**
 * Sub-classification of an `external` candidate: which channel they came from.
 * Kept separate from `source` (internal | external), which drives resume-upload
 * and CV-link behaviour and must stay a two-value union.
 */
export const SOURCE_CHANNELS = [
  "LinkedIn",
  "Instagram",
  "WhatsApp",
  "Referred by a Friend",
  "Connected by a Binge Partner",
  "Other",
] as const;

/** Selecting this reveals a free-text box; the typed value is stored instead. */
export const SOURCE_CHANNEL_OTHER = "Other";

/**
 * Highest education. Values must match the backend EducationLevel enum exactly
 * — it rejects anything else — so only the labels are free to differ.
 */
export const EDUCATION_LEVELS = [
  { value: "High School", label: "High School" },
  { value: "Bachelors", label: "Bachelors (Undergraduate)" },
  { value: "Masters", label: "Masters (Postgraduate)" },
  { value: "PhD", label: "PhD / Doctorate" },
] as const;

export const GENDER_OPTIONS = [
  { value: "male", label: "Male" },
  { value: "female", label: "Female" },
  { value: "other", label: "Other" },
] as const;

export const CANDIDATE_SOURCES = ["internal", "external"] as const;

export const COMMUNICATION_OPTIONS = ["Basic", "Good", "Excellent"] as const;

export const STRUCTURED_EDUCATION_OPTIONS = [
  "SSC",
  "HSC",
  "Diploma",
  "Graduate",
  "Hospitality Graduate",
] as const;

export const BRAND_EXPERIENCE_OPTIONS = ["Low", "Mid", "Premium"] as const;

/**
 * Values must match the backend Department enum exactly (BOH | Service | Corporate)
 * — it rejects anything else — so only the labels are free to differ.
 */
export const DEPARTMENT_OPTIONS = [
  { value: "BOH", label: "Kitchen (BOH)" },
  { value: "Service", label: "Front of House (Service)" },
  { value: "Corporate", label: "Corporate" },
] as const;

/**
 * Establishment tag. Values must match the backend EstablishmentTag enum
 * exactly — it rejects anything else — so only the labels are free to differ.
 */
export const ESTABLISHMENT_TAG_OPTIONS = [
  { value: "Cafe", label: "Cafe" },
  { value: "QSR", label: "QSR" },
  { value: "Restaurant", label: "Restaurant" },
  { value: "Hotel", label: "Hotel" },
  { value: "Other", label: "Other" },
] as const;

/** Selecting this reveals a free-text box; the typed value is stored instead. */
export const CURRENT_ROLE_OTHER = "Other";

/**
 * Role options grouped by department, shared with the Positions role dropdown.
 * "Other" is appended to every group so a role missing from the list can still
 * be entered as free text.
 */
export const ROLE_OPTIONS_BY_DEPARTMENT: Record<string, string[]> = {
  Service: [
    "Bar Assistant",
    "Bar Manager",
    "Bar Supervisor",
    "Barback",
    "Barista",
    "Bartender",
    "Café Manager",
    "Café Supervisor",
    "Captain",
    "Cashier",
    "Counter Sales",
    "Duty Manager",
    "F&B Executive",
    "F&B Supervisor",
    "Floor Supervisor",
    "Front Office Executive",
    "GRE",
    "Hostess",
    "Mixologist",
    "Outlet Manager",
    "Shift Manager",
    "Sommelier",
    "Steward",
    "Waiter / Server",
    "RM",
    "ARM",
    "Head Bartender",
    "Beverage Head",
    CURRENT_ROLE_OTHER,
  ],
  BOH: [
    "CDP",
    "Commi 1",
    "Commi 2",
    "Commi 3",
    "DCDP",
    "Executive Chef",
    "Food Production Manager",
    "Head Baker",
    "Head Chef",
    "Kitchen Supervisor",
    "Packaging Assistant",
    "Sous Chef",
    "Staff Cook",
    "Store Manager",
    "Storekeeper",
    CURRENT_ROLE_OTHER,
  ],
  Corporate: [
    "Accountant / Accounts",
    "Admin / Back Office",
    "Brand Manager",
    "Business Development",
    "Community Manager",
    "Content Strategist",
    "CRM",
    "Data Analyst",
    "EA / PA",
    "F&B Controller",
    "General Manager",
    "Graphic Designer",
    "HR",
    "Lawyer",
    "Marketing",
    "MIS Executive",
    "Operations Head",
    "Payroll",
    "PR",
    "Project Manager",
    "Purchase",
    "Sales",
    "Social Media",
    "Supply Chain / SCM",
    "Training Manager / L&D",
    CURRENT_ROLE_OTHER,
  ],
};

export const SPECIALIZATION_OPTIONS: Record<string, string[]> = {
  BOH: ["Continental", "Pastry", "Bakery", "Pan-Asian", "Japanese", "Indian / Tandoor"],
  Service: ["Service", "Guest Relations", "Bar", "Coffee", "Operations"],
  Corporate: [
    "HR",
    "Accounts & Finance",
    "Business Development",
    "Marketing",
    "PR",
    "Social Media",
    "Design",
    "Admin",
  ],
};
