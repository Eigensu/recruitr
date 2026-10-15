/**
 * Dates on the agency's clock. The telecaller reports cut their days in India
 * Standard Time (UTC+5:30, no daylight saving), so the screens that ask for a
 * day must mean the same day the server does, wherever the browser is.
 */

const IST_OFFSET = "+05:30";

/** Today's date in IST, as YYYY-MM-DD. */
export function todayIst(now: Date = new Date()): string {
  return now.toLocaleDateString("en-CA", { timeZone: "Asia/Kolkata" });
}

/** A YYYY-MM-DD date moved by whole days. Pure calendar arithmetic, no timezone. */
export function shiftDate(date: string, days: number): string {
  const d = new Date(`${date}T00:00:00Z`);
  d.setUTCDate(d.getUTCDate() + days);
  return d.toISOString().slice(0, 10);
}

/** The Monday of the week containing a YYYY-MM-DD date. */
export function mondayOf(date: string): string {
  const weekday = new Date(`${date}T00:00:00Z`).getUTCDay(); // 0 = Sunday
  return shiftDate(date, -((weekday + 6) % 7));
}

/** The instant an IST day starts, as an ISO datetime the API can filter on. */
export function istDayStart(date: string): string {
  return new Date(`${date}T00:00:00${IST_OFFSET}`).toISOString();
}

/** The last instant of an IST day, for an inclusive end filter. */
export function istDayEnd(date: string): string {
  return new Date(`${date}T23:59:59.999${IST_OFFSET}`).toISOString();
}

/** "14 Oct" for a YYYY-MM-DD date. */
export function shortDate(date: string): string {
  return new Date(`${date}T00:00:00Z`).toLocaleDateString("en-IN", {
    day: "numeric",
    month: "short",
    timeZone: "UTC",
  });
}

/** A timestamp as the agency reads it: "14 Oct, 3:05 pm", IST. */
export function istTimestamp(iso: string): string {
  return new Date(iso).toLocaleString("en-IN", {
    day: "numeric",
    month: "short",
    hour: "numeric",
    minute: "2-digit",
    timeZone: "Asia/Kolkata",
  });
}
