"use client";

import { ChevronDown } from "lucide-react";

import type { ResearchFindings, RunMetrics, RunStatus } from "@/lib/sse/types";

import { RUN_PAGE_COPY } from "./run-page-copy";

import { RelatedRoasts } from "./related-roasts";
import { RunMetricsBar } from "./run-metrics-bar";
import { SourcesPanel } from "./sources-panel";

export const collapsibleSummaryClass =
  "flex cursor-pointer list-none items-center gap-2 font-serif text-2xl font-semibold text-ink focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-heat [&::-webkit-details-marker]:hidden";

const subsectionHeadingClass =
  "font-sans text-xs font-semibold uppercase tracking-widest text-ink-muted";

export function RunContextGroup({
  runId,
  researchFindings,
  metrics,
  status,
}: {
  runId: string;
  researchFindings?: ResearchFindings | null;
  metrics: RunMetrics | null;
  status: RunStatus;
}) {
  const hasSources = Boolean(researchFindings?.findings.length);

  return (
    <details
      className="group mt-8 border-t-2 border-rule-soft pt-8"
      aria-labelledby="context-heading"
    >
      <summary className={collapsibleSummaryClass}>
        <ChevronDown
          className="size-5 shrink-0 transition-transform group-open:rotate-180"
          aria-hidden
        />
        <h2 id="context-heading" className="m-0">
          Context
        </h2>
        <span className="font-sans text-sm font-normal text-ink-muted">
          {RUN_PAGE_COPY.contextSummary}
        </span>
      </summary>
      <div className="mt-6 space-y-10">
        <RelatedRoasts runId={runId} />
        {hasSources && researchFindings && (
          <SourcesPanel research={researchFindings} headingLevel="h3" />
        )}
        <section aria-labelledby="context-metrics-heading">
          <h3 id="context-metrics-heading" className={subsectionHeadingClass}>
            Run metrics
          </h3>
          <RunMetricsBar metrics={metrics} status={status} className="mt-4 border-t-0 pt-0" />
        </section>
      </div>
    </details>
  );
}
