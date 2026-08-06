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
  "Indeed",
  "Naukri",
  "Reference from Candidate",
  "WhatsApp Groups",
  "Instagram",
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
