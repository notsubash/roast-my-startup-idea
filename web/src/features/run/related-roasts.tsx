"use client";

import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import { Sparkles } from "lucide-react";

import { ApiError } from "@/lib/api/client";
import { getSimilarRuns } from "@/lib/api/runs";
import type { SimilarRunItem } from "@/lib/api/types-helpers";
import { Skeleton } from "@/ui/skeleton";

function formatDate(iso: string): string {
  return new Intl.DateTimeFormat(undefined, { dateStyle: "medium" }).format(
    new Date(iso),
  );
}

function VerdictHint({ item }: { item: SimilarRunItem }) {
  const summary = item.verdict_summary;
  const date = formatDate(item.created_at);

  if (!summary) {
    return <p className="font-mono text-xs text-ink-subtle">{date}</p>;
  }

  const parts: string[] = [];
  if (summary.pass > 0) parts.push(`${summary.pass} PASS`);
  if (summary.conditional > 0) parts.push(`${summary.conditional} COND`);
  if (summary.fail > 0) parts.push(`${summary.fail} FAIL`);
  const avg =
    summary.avg_score != null ? ` · ${summary.avg_score.toFixed(1)}/10` : "";

  return (
    <p className="font-mono text-xs text-ink-subtle">
      {date}
      {parts.length > 0 ? ` · ${parts.join(" · ")}` : ""}
      {avg}
    </p>
  );
}

export function RelatedRoasts({
  runId,
  headingLevel: Heading = "h3",
}: {
  runId: string;
  headingLevel?: "h2" | "h3";
}) {
  const query = useQuery({
    queryKey: ["run", runId, "similar"],
    queryFn: () => getSimilarRuns(runId),
    staleTime: 60_000,
  });

  if (query.isLoading) {
    return (
      <aside className="space-y-3" aria-label="Related past roasts loading">
        <Skeleton className="h-5 w-32" />
        <Skeleton className="h-16 w-full" />
        <Skeleton className="h-16 w-full" />
      </aside>
    );
  }

  if (query.isError) {
    if (query.error instanceof ApiError && query.error.status === 404) return null;
    return (
      <aside aria-live="polite">
        <p className="font-sans text-xs text-ink-muted">Could not load related roasts.</p>
        <button
          type="button"
          onClick={() => void query.refetch()}
          className="mt-2 font-sans text-xs font-semibold text-heat-ink underline-offset-2 hover:underline focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-heat"
        >
          Retry
        </button>
      </aside>
    );
  }

  if (!query.data?.runs.length) {
    return null;
  }

  return (
    <aside aria-labelledby="related-roasts-heading">
      <div className="flex items-center gap-2">
        <Sparkles className="size-4 text-heat-ink" aria-hidden />
        <Heading
          id="related-roasts-heading"
          className="font-sans text-xs font-semibold uppercase tracking-widest text-ink-muted"
        >
          Related past roasts
        </Heading>
      </div>
      <ul className="mt-4 space-y-3">
        {query.data.runs.map((item) => (
          <li key={item.run_id}>
            <Link
              href={`/run/${item.run_id}`}
              className="block border border-rule-soft bg-card p-3 transition-colors hover:border-ink hover:bg-paper-2 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-heat"
            >
              <p className="font-serif text-sm font-semibold leading-snug text-ink">
                {item.idea_preview}
              </p>
              <VerdictHint item={item} />
            </Link>
          </li>
        ))}
      </ul>
    </aside>
  );
}
