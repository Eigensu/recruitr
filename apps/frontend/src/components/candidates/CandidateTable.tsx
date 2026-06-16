import type { Candidate } from "@/types";

interface Props {
  candidates: Candidate[];
}

const SOURCE_STYLES = {
  internal: { color: "#3DDC97", label: "Internal" },
  external: { color: "#FF5A5F", label: "External" },
};

const chipStyle = {
  background: "var(--color-canvas-val)",
  color: "var(--color-text-secondary)",
  border: "1px solid var(--color-border-val)",
};

export default function CandidateTable({ candidates }: Props) {
  if (candidates.length === 0) {
    return (
      <div className="py-12 text-center" style={{ color: "var(--color-text-secondary)" }}>
        No candidates found. Adjust your filters or add a new candidate.
      </div>
    );
  }

  return (
    <div
      className="overflow-x-auto rounded-lg"
      style={{ border: "1px solid var(--color-border-val)" }}
    >
      <table className="w-full text-sm">
        <thead>
          <tr
            style={{
              background: "var(--color-surface-val)",
              borderBottom: "1px solid var(--color-border-val)",
            }}
          >
            {["Name", "Email", "Source", "Tags", "CV", "Skills"].map((h) => (
              <th
                key={h}
                className="px-4 py-3 text-left text-xs font-semibold uppercase tracking-normal"
                style={{ color: "var(--color-text-secondary)" }}
              >
                {h}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {candidates.map((c) => (
            <tr
              key={c.id}
              className="border-b last:border-0 hover:bg-white/5"
              style={{ borderColor: "var(--color-border-val)" }}
            >
              <td className="px-4 py-3 font-medium" style={{ color: "var(--color-text-primary)" }}>
                {c.name}
              </td>
              <td className="px-4 py-3" style={{ color: "var(--color-text-secondary)" }}>
                {c.email}
              </td>
              <td className="px-4 py-3">
                <span
                  className="inline-flex items-center gap-1.5 text-xs font-medium"
                  style={{ color: SOURCE_STYLES[c.source].color }}
                >
                  <span className="text-[8px]">●</span>
                  {SOURCE_STYLES[c.source].label}
                </span>
              </td>
              <td className="px-4 py-3">
                <div className="flex flex-wrap gap-1">
                  {c.tags.slice(0, 4).map((tag) => (
                    <span
                      key={tag}
                      className="rounded-full px-1.5 py-0.5 text-[10px]"
                      style={chipStyle}
                    >
                      {tag}
                    </span>
                  ))}
                  {c.tags.length > 4 && (
                    <span className="text-[10px]" style={{ color: "var(--color-text-secondary)" }}>
                      +{c.tags.length - 4}
                    </span>
                  )}
                </div>
              </td>
              <td className="px-4 py-3">
                {(() => {
                  const cvHref = c.cv_link ?? c.resume_url;
                  return cvHref ? (
                    <a
                      href={cvHref}
                      target="_blank"
                      rel="noreferrer"
                      className="text-xs underline"
                      style={{ color: "var(--color-yellow)" }}
                    >
                      {c.cv_link ? "CV Link ↗" : "Resume ↗"}
                    </a>
                  ) : (
                    <span className="text-xs" style={{ color: "var(--color-text-secondary)" }}>
                      —
                    </span>
                  );
                })()}
              </td>
              <td className="px-4 py-3">
                <div className="flex flex-wrap gap-1">
                  {c.extracted_skills.slice(0, 3).map((skill) => (
                    <span
                      key={skill}
                      className="rounded px-1.5 py-0.5 text-[10px]"
                      style={chipStyle}
                    >
                      {skill}
                    </span>
                  ))}
                  {c.extracted_skills.length > 3 && (
                    <span className="text-[10px]" style={{ color: "var(--color-text-secondary)" }}>
                      +{c.extracted_skills.length - 3}
                    </span>
                  )}
                </div>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
