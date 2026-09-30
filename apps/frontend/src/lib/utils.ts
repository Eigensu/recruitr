import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";

/**
 * Merge Tailwind classes safely, resolving conflicts last-wins.
 * Compatible with shadcn/ui component convention.
 */
export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

/**
 * Parse a datetime string returned by the API.
 * The backend serializes naive UTC (no offset), which `new Date()` would read as local time.
 */
export function parseApiDate(value: string): Date {
  const hasTimezone = /(?:Z|[+-]\d{2}:?\d{2})$/.test(value);
  return new Date(hasTimezone ? value : `${value}Z`);
}

/** A candidate salary. Both current and expected are stored as ₹ per month. */
export function formatMonthlySalary(amount: number): string {
  return `₹${amount.toLocaleString("en-IN")}/mo`;
}

/** Format a date as the local `YYYY-MM-DD` string an `<input type="date">` expects. */
export function toDateInputValue(date: Date): string {
  const month = String(date.getMonth() + 1).padStart(2, "0");
  const day = String(date.getDate()).padStart(2, "0");
  return `${date.getFullYear()}-${month}-${day}`;
}
