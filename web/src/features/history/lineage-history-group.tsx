"use client";

import { useState } from "react";
import Link from "next/link";
import { ChevronDown, ChevronUp } from "lucide-react";

import type { RunListItem } from "@/lib/api/types-helpers";
import { sidebarLineageVersions } from "@/lib/lineage/lineage";
import { cn } from "@/lib/utils";

import { RunHistoryItem } from "./run-history-item";

function formatAvg(item: RunListItem): string | null {
  const avg = item.verdict_summary?.avg_score;
  if (avg == null || item.status !== "completed") return null;
  return `${avg.toFixed(1)}/10`;
}

function VersionRow({ item }: { item: RunListItem }) {
  const avg = formatAvg(item);
  return (
    <Link
      href={`/run/${item.run_id}`}
      className={cn(
        "flex items-center justify-between gap-3 py-2 pl-4 font-sans text-sm",
        "border-l-2 border-rule-soft hover:bg-paper-2 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-heat",
      )}
    >
      <span className="font-mono text-ink-muted">
        v{item.version}
        {avg ? ` · ${avg}` : ""}
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
  const latestAvg = formatAvg(latest);
  const { visible, hidden } = sidebarLineageVersions(lineage);

  return (
    <li className="border-2 border-ink bg-card shadow-soft">
      <Link
        href={`/run/${latest.run_id}`}
        className={cn(
          "group block p-4 transition-colors hover:bg-paper-2",
          "focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-heat",
        )}
      >
        <p className="font-serif text-lg font-semibold text-ink group-hover:text-heat-ink">
          {root.idea_preview}
        </p>
        <p className="mt-1 font-sans text-sm text-ink-muted">
          {lineage.length} versions
          {latestAvg ? ` · latest v${latest.version} (${latestAvg})` : ""}
        </p>
      </Link>

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
            {hidden.length} older version{hidden.length === 1 ? "" : "s"}
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
