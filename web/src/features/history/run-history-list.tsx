"use client";

import Link from "next/link";
import { useQuery } from "@tanstack/react-query";

import { EditorialContainer } from "@/components/app-shell";
import { ApiError } from "@/lib/api/client";
import { listRuns } from "@/lib/api/runs";
import { heatCtaClass } from "@/lib/cta-classes";
import { cn } from "@/lib/utils";
import { Skeleton } from "@/ui/skeleton";

import { groupByLineage } from "@/lib/lineage/lineage";

import { HISTORY_COPY, RUN_PAGE_COPY } from "@/features/run/run-page-copy";

import { LineageHistoryGroup } from "./lineage-history-group";

function HistorySkeleton() {
  return (
    <ul className="space-y-4">
      {Array.from({ length: 4 }).map((_, i) => (
        <li key={i} className="border border-rule-soft bg-card p-4">
          <Skeleton className="h-6 w-3/4" />
          <Skeleton className="mt-3 h-4 w-1/2" />
          <Skeleton className="mt-2 h-3 w-1/3" />
        </li>
      ))}
    </ul>
  );
}

export function RunHistoryList() {
  const query = useQuery({
    queryKey: ["runs", "list"],
    queryFn: () => listRuns(),
    retry: 1,
  });

  return (
    <EditorialContainer className="py-12 md:py-16 lg:py-24">
      <header>
        <p className="font-sans text-sm font-semibold uppercase tracking-widest text-cta">
          {HISTORY_COPY.eyebrow}
        </p>
        <h1 className="mt-2 font-sans text-title font-semibold text-ink md:text-display-md">
          {HISTORY_COPY.title}
        </h1>
        <p className="mt-4 max-w-prose font-sans text-ink-muted">
          {HISTORY_COPY.description}
        </p>
      </header>

      <div className="mt-10">
        {query.isLoading && <HistorySkeleton />}

        {query.isError && (
          <div className="border border-fail/40 bg-card p-6" role="alert">
            <p className="font-sans text-sm font-semibold text-ink">Could not load history</p>
            <p className="mt-2 font-sans text-sm text-ink-muted">
              {query.error instanceof ApiError
                ? "The API returned an error. Try refreshing."
                : "Check your connection and try again."}
            </p>
          </div>
        )}

        {query.isSuccess && query.data.runs.length === 0 && (
          <div className="border border-dashed border-rule-soft bg-paper-2 p-10 text-center">
            <p className="font-sans text-xl font-semibold text-ink">{HISTORY_COPY.emptyTitle}</p>
            <p className="mt-2 font-sans text-sm text-ink-muted">
              {HISTORY_COPY.emptyDescription}
            </p>
            <Link href="/" className={cn("mt-6 inline-flex", heatCtaClass)}>
              {RUN_PAGE_COPY.submitIdea}
            </Link>
          </div>
        )}

        {query.isSuccess && query.data.runs.length > 0 && (
          <ul className="space-y-4">
            {groupByLineage(query.data.runs).map((lineage) => (
              <LineageHistoryGroup key={lineage[0]!.run_id} lineage={lineage} />
            ))}
          </ul>
        )}
      </div>
    </EditorialContainer>
  );
}
