"use client";

import Link from "next/link";
import { AlertCircle, CheckCircle2, Clock, XCircle } from "lucide-react";

import type { RunListItem } from "@/lib/api/types-helpers";
import { cn } from "@/lib/utils";

import { HISTORY_COPY } from "../run/run-page-copy";

import { HistoryConfidencePreview } from "./history-confidence-preview";

function statusLabel(status: RunListItem["status"]): string {
  switch (status) {
    case "completed":
      return "Completed";
    case "failed":
      return "Failed";
    case "cancelled":
      return "Cancelled";
    case "running":
      return "Running";
    default:
      return "Created";
  }
}

function StatusIcon({ status }: { status: RunListItem["status"] }) {
  switch (status) {
    case "completed":
      return <CheckCircle2 className="size-4 text-pass" aria-hidden />;
    case "failed":
      return <AlertCircle className="size-4 text-fail" aria-hidden />;
    case "cancelled":
      return <XCircle className="size-4 text-conditional" aria-hidden />;
    default:
      return <Clock className="size-4 text-ink-muted" aria-hidden />;
  }
}

function formatDate(iso: string): string {
  return new Intl.DateTimeFormat(undefined, {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(new Date(iso));
}

export function RunHistoryItem({ item }: { item: RunListItem }) {
  const avg = item.verdict_summary?.avg_score;
  const showScore = item.status === "completed" && avg != null;
  const showConfidence = item.status === "completed";

  return (
    <li className="border border-rule-soft bg-card shadow-soft">
      <Link
        href={`/run/${item.run_id}`}
        className={cn(
          "group block p-4 transition-colors",
          "hover:bg-paper-2 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-cta",
        )}
      >
        <div className="flex items-start justify-between gap-4">
          <p className="font-sans text-lg font-semibold text-ink group-hover:text-cta">
            {item.idea_preview}
          </p>
          <span className="inline-flex shrink-0 items-center gap-1.5 font-sans text-xs font-semibold uppercase tracking-wide text-ink-muted">
            <StatusIcon status={item.status} />
            {statusLabel(item.status)}
          </span>
        </div>

        <dl className="mt-3 flex flex-wrap items-center gap-x-4 gap-y-1 font-sans text-sm text-ink-muted">
          <div>
            <dt className="sr-only">Version</dt>
            <dd>v{item.version ?? 1}</dd>
          </div>
          {showScore && (
            <div>
              <dt className="sr-only">{HISTORY_COPY.currentScore}</dt>
              <dd>
                {HISTORY_COPY.currentScore}:{" "}
                <span className="font-mono font-semibold text-ink">{avg.toFixed(1)}/10</span>
              </dd>
            </div>
          )}
        </dl>

        <p className="mt-3 font-mono text-xs text-ink-subtle">
          {formatDate(item.created_at)} · {item.run_id.slice(0, 8)}…
        </p>
      </Link>

      {showConfidence && (
        <div className="border-t border-rule-soft px-4 pb-4">
          <HistoryConfidencePreview runId={item.run_id} className="mt-3" />
        </div>
      )}
    </li>
  );
}
