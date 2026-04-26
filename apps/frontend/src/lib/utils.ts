import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";

/**
 * Merge Tailwind classes safely, resolving conflicts last-wins.
 * Compatible with shadcn/ui component convention.
 */
export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}
