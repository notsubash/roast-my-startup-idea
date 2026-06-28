import { ExternalLink, Search } from "lucide-react";

import type { ResearchFindings } from "@/lib/sse/types";

function safeHttpUrl(raw: string): string | null {
  try {
    const url = new URL(raw);
    if (url.protocol === "http:" || url.protocol === "https:") {
      return url.href;
    }
  } catch {
    /* ponytail: malformed URL renders as plain text */
  }
  return null;
}

export function SourcesPanel({ research }: { research: ResearchFindings }) {
  if (research.findings.length === 0) return null;

  return (
    <section
      className="border-2 border-ink bg-paper-2 p-4"
      aria-labelledby="research-sources-heading"
    >
      <div className="flex items-start gap-3">
        <Search className="mt-0.5 size-5 shrink-0 text-heat-ink" aria-hidden />
        <div className="min-w-0 flex-1">
          <h2
            id="research-sources-heading"
            className="font-sans text-sm font-semibold uppercase tracking-widest text-ink"
          >
            Web research
          </h2>
          <p className="mt-2 font-mono text-xs text-ink-muted">
            Query: <span className="text-ink">{research.query}</span>
          </p>
          <ul className="mt-4 space-y-3">
            {research.findings.map((finding, index) => {
              const href = safeHttpUrl(finding.url);
              return (
                <li
                  key={`${finding.url}-${index}`}
                  className="border-t border-rule-soft pt-3 first:border-t-0 first:pt-0"
                >
                  {href ? (
                    <a
                      href={href}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="group inline-flex items-start gap-1.5 font-sans text-sm font-semibold text-heat-ink hover:text-heat focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-heat"
                    >
                      <span className="min-w-0">{finding.title}</span>
                      <ExternalLink
                        className="mt-0.5 size-3.5 shrink-0 opacity-70 group-hover:opacity-100"
                        aria-hidden
                      />
                      <span className="sr-only">(opens in new tab)</span>
                    </a>
                  ) : (
                    <p className="font-sans text-sm font-semibold text-ink">{finding.title}</p>
                  )}
                  <p className="mt-1 font-sans text-sm leading-relaxed text-ink-muted">
                    {finding.snippet}
                  </p>
                </li>
              );
            })}
          </ul>
        </div>
      </div>
    </section>
  );
}
