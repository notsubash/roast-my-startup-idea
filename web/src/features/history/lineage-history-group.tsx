"use client";

import { useState } from "react";
import Link from "next/link";
import { ChevronDown, ChevronUp } from "lucide-react";

import type { RunListItem } from "@/lib/api/types-helpers";
import { lineageCurrentScore, lineageScoreDelta } from "@/lib/confidence/confidence";
import { sidebarLineageVersions } from "@/lib/lineage/lineage";
import { cn } from "@/lib/utils";

import { ScoreDeltaBadge } from "../appeal/score-delta-badge";
import { HISTORY_COPY } from "../run/run-page-copy";

import { HistoryConfidencePreview } from "./history-confidence-preview";
import { RunHistoryItem } from "./run-history-item";

function formatAvg(score: number): string {
  return `${score.toFixed(1)}/10`;
}

function VersionRow({ item }: { item: RunListItem }) {
  const avg = item.verdict_summary?.avg_score;
  return (
    <Link
      href={`/run/${item.run_id}`}
      className={cn(
        "flex items-center justify-between gap-3 py-2 pl-4 font-sans text-sm",
        "border-l-2 border-rule-soft hover:bg-paper-2 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-cta",
      )}
    >
      <span className="font-mono text-ink-muted">
        v{item.version}
        {avg != null && item.status === "completed" ? ` · ${formatAvg(avg)}` : ""}
      </span>
      <span className="font-mono text-xs text-ink-subtle">
        {new Intl.DateTimeFormat(undefined, { dateStyle: "medium" }).format(
          new Date(item.created_at),
        )}
      </span>
    </Link>
  );
}

export function LineageHistoryGroup({ lineage }: { lineage: RunListItem[] }) {
  const [expanded, setExpanded] = useState(false);
  const root = lineage[0]!;

  if (lineage.length === 1) {
    return <RunHistoryItem item={root} />;
  }

  const latest = lineage[lineage.length - 1]!;
  const currentScore = lineageCurrentScore(lineage);
  const latestDelta = lineageScoreDelta(lineage);
  const { visible, hidden } = sidebarLineageVersions(lineage);
  const showConfidence = latest.status === "completed";

  return (
    <li className="border border-rule-soft bg-card shadow-soft">
      <Link
        href={`/run/${latest.run_id}`}
        className={cn(
          "group block p-4 transition-colors hover:bg-paper-2",
          "focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-cta",
        )}
      >
        <p className="font-sans text-lg font-semibold text-ink group-hover:text-cta">
          {root.idea_preview}
        </p>

        <dl className="mt-3 flex flex-wrap items-center gap-x-4 gap-y-1 font-sans text-sm text-ink-muted">
          <div>
            <dt className="sr-only">Version count</dt>
            <dd>
              {lineage.length} {HISTORY_COPY.versions}
            </dd>
          </div>
          {currentScore != null && (
            <div>
              <dt className="sr-only">{HISTORY_COPY.currentScore}</dt>
              <dd>
                {HISTORY_COPY.currentScore}:{" "}
                <span className="font-mono font-semibold text-ink">
                  {formatAvg(currentScore)}
                </span>
              </dd>
            </div>
          )}
          {latestDelta != null && (
            <div className="flex items-center gap-2">
              <dt className="sr-only">{HISTORY_COPY.latestDelta}</dt>
              <dd className="flex items-center gap-2">
                {HISTORY_COPY.latestDelta}:
                {latestDelta !== 0 ? (
                  <ScoreDeltaBadge delta={latestDelta} />
                ) : (
                  <span className="font-sans text-xs text-ink-muted">unchanged</span>
                )}
              </dd>
            </div>
          )}
        </dl>
      </Link>

      {showConfidence && (
        <div className="border-t border-rule-soft px-4 pb-4">
          <HistoryConfidencePreview runId={latest.run_id} className="mt-3" />
        </div>
      )}

      {hidden.length > 0 && (
        <div className="border-t border-rule-soft px-4 py-2">
          <button
            type="button"
            className="inline-flex min-h-9 items-center gap-2 font-sans text-xs font-semibold text-ink-muted hover:text-ink"
            aria-expanded={expanded}
            onClick={() => setExpanded((open) => !open)}
          >
            {expanded ? (
              <ChevronUp className="size-3.5" aria-hidden />
            ) : (
              <ChevronDown className="size-3.5" aria-hidden />
            )}
            {HISTORY_COPY.olderVersions(hidden.length)}
          </button>
          {expanded && (
            <div className="mt-1">
              {hidden.map((item) => (
                <VersionRow key={item.run_id} item={item} />
              ))}
            </div>
          )}
        </div>
      )}

      <div className="border-t border-rule-soft px-4 pb-2">
        {visible.map((item) => (
          <VersionRow key={item.run_id} item={item} />
        ))}
      </div>
    </li>
  );
}
