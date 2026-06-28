import Link from "next/link";
import { AlertCircle, CheckCircle2, Clock, XCircle } from "lucide-react";

import type { RunListItem } from "@/lib/api/types-helpers";
import { cn } from "@/lib/utils";

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

function VerdictSummaryLine({ item }: { item: RunListItem }) {
  const summary = item.verdict_summary;
  if (!summary || item.status !== "completed") {
    return (
      <p className="font-sans text-sm text-ink-subtle">
        {item.status === "completed" ? "No verdict summary" : statusLabel(item.status)}
      </p>
    );
  }

  const parts: string[] = [];
  if (summary.pass > 0) parts.push(`${summary.pass} PASS`);
  if (summary.conditional > 0) parts.push(`${summary.conditional} CONDITIONAL`);
  if (summary.fail > 0) parts.push(`${summary.fail} FAIL`);
  const avg =
    summary.avg_score != null ? ` · avg ${summary.avg_score.toFixed(1)}/10` : "";

  return (
    <p className="font-mono text-sm text-ink-muted">
      {parts.join(" · ")}
      {avg}
    </p>
  );
}

function formatDate(iso: string): string {
  return new Intl.DateTimeFormat(undefined, {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(new Date(iso));
}

export function RunHistoryItem({ item }: { item: RunListItem }) {
  return (
    <li>
      <Link
        href={`/run/${item.run_id}`}
        className={cn(
          "group flex flex-col gap-2 border-2 border-ink bg-card p-4 shadow-soft transition-colors",
          "hover:bg-paper-2 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-heat",
        )}
      >
        <div className="flex items-start justify-between gap-4">
          <p className="font-serif text-lg font-semibold text-ink group-hover:text-heat-ink">
            {item.idea_preview}
          </p>
          <span className="inline-flex shrink-0 items-center gap-1.5 font-sans text-xs font-semibold uppercase tracking-wide text-ink-muted">
            <StatusIcon status={item.status} />
            {statusLabel(item.status)}
          </span>
        </div>
        <VerdictSummaryLine item={item} />
        <p className="font-mono text-xs text-ink-subtle">
          {formatDate(item.created_at)} · {item.run_id.slice(0, 8)}…
        </p>
      </Link>
    </li>
  );
}
