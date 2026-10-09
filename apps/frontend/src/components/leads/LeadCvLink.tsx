import { IconFileOff, IconFileText, IconLink, IconLock } from "@tabler/icons-react";
import { resolveCvRef } from "@/lib/api/candidates";
import type { IntakeLead } from "@/lib/api/intake";

const muted = "inline-flex items-center gap-1.5 text-xs text-text-muted";

/**
 * A lead's CV as one inline item: a link that opens it, or a muted note saying
 * why there is nothing to open — another recruiter sourced it, it is on file
 * without a usable address yet, or there is no CV at all.
 */
export default function LeadCvLink({
  lead,
}: Readonly<{ lead: Pick<IntakeLead, "cv_link" | "resume_url" | "cv_locked"> }>) {
  if (lead.cv_locked) {
    return (
      <span className={muted}>
        <IconLock className="size-3.5 shrink-0" />
        CV held by another recruiter
      </span>
    );
  }
  const cv = resolveCvRef(lead.cv_link, lead.resume_url);
  if (!cv) {
    return (
      <span className={muted}>
        <IconFileOff className="size-3.5 shrink-0" />
        No CV on file
      </span>
    );
  }
  if (!cv.href) {
    return (
      <span className={muted} title="CV on file — not yet uploaded">
        <IconFileText className="size-3.5 shrink-0" />
        CV on file
      </span>
    );
  }
  const Icon = lead.cv_link ? IconLink : IconFileText;
  return (
    <a
      href={cv.href}
      target="_blank"
      rel="noreferrer noopener"
      className="inline-flex items-center gap-1.5 text-xs font-semibold text-text-primary hover:underline"
    >
      <Icon className="size-3.5 shrink-0 text-text-muted" />
      View CV ↗
    </a>
  );
}
