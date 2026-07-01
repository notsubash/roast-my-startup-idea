"use client";

import { ClipboardList, FlaskConical, Target } from "lucide-react";

import { heatCtaClass } from "@/lib/cta-classes";
import type { Verdict } from "@/lib/sse/types";
import { cn } from "@/lib/utils";

import { RUN_PAGE_COPY } from "./run-page-copy";
import { deriveWorkflowBrief } from "./structured-synthesis";

const cardClass = "border-2 border-rule-soft bg-card";

export function WorkflowBrief({
  synthesisProse,
  structuredSynthesis,
  verdicts,
  completed,
  evidenceLink,
  className,
}: {
  synthesisProse: string | null;
  structuredSynthesis: unknown;
  verdicts: Verdict[];
  completed: boolean;
  evidenceLink?: { href: string; label: string } | null;
  className?: string;
}) {
  const { problems, blocker, experiment } = deriveWorkflowBrief(
    synthesisProse,
    structuredSynthesis,
    verdicts,
  );
  const hasContent = problems.length > 0 || blocker || completed;

  if (!hasContent) return null;

  return (
    <div className={cn("mt-6 space-y-4", className)}>
      {problems.length > 0 && (
        <section className={cardClass} aria-labelledby="top-problems-heading">
          <header className="border-b border-rule-soft px-5 py-3">
            <h3
              id="top-problems-heading"
              className="font-sans text-xs font-semibold uppercase tracking-widest text-ink-muted"
            >
              {RUN_PAGE_COPY.topProblems}
            </h3>
          </header>
          <ol className="list-none px-5 py-4" aria-label="Top three problems from this review">
            {problems.map((problem, index) => (
              <li
                key={index}
                className="flex min-h-7 gap-3 font-sans text-sm leading-relaxed text-ink"
              >
                <span className="w-5 shrink-0 font-mono text-xs font-bold text-heat-ink" aria-hidden>
                  {index + 1}.
                </span>
                {problem}
              </li>
            ))}
          </ol>
        </section>
      )}

      {blocker && (
        <section
          className={cn(cardClass, "flex items-start gap-4 px-5 py-4")}
          aria-labelledby="blocker-heading"
        >
          <Target className="mt-0.5 size-5 shrink-0 text-heat-ink" aria-hidden />
          <div>
            <h3
              id="blocker-heading"
              className="font-sans text-xs font-semibold uppercase tracking-widest text-ink-muted"
            >
              {RUN_PAGE_COPY.highestPriority}
            </h3>
            <p className="mt-2 font-sans text-sm leading-relaxed text-ink">{blocker}</p>
          </div>
        </section>
      )}

      <section
        className={cn(cardClass, "flex items-start gap-4 px-5 py-4")}
        aria-labelledby="experiment-heading"
      >
        <FlaskConical className="mt-0.5 size-5 shrink-0 text-heat-ink" aria-hidden />
        <div>
          <h3
            id="experiment-heading"
            className="font-sans text-xs font-semibold uppercase tracking-widest text-ink-muted"
          >
            {RUN_PAGE_COPY.recommendedExperiment}
          </h3>
          <p className="mt-2 font-sans text-sm leading-relaxed text-ink">{experiment}</p>
        </div>
      </section>

      {completed && evidenceLink && (
        <section
          className={cn(cardClass, "flex flex-wrap items-center justify-between gap-4 px-5 py-4")}
          aria-labelledby="present-evidence-heading"
        >
          <div className="flex items-start gap-3">
            <ClipboardList className="mt-0.5 size-5 shrink-0 text-heat-ink" aria-hidden />
            <div>
              <h3
                id="present-evidence-heading"
                className="font-sans text-sm font-semibold text-ink"
              >
                {RUN_PAGE_COPY.presentEvidence}
              </h3>
              <p className="mt-1 max-w-prose font-sans text-sm text-ink-muted">
                {RUN_PAGE_COPY.presentEvidenceLead}
              </p>
            </div>
          </div>
          <a href={evidenceLink.href} className={heatCtaClass}>
            {evidenceLink.label}
          </a>
        </section>
      )}
    </div>
  );
}
