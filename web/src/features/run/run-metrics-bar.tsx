"use client";

import { useId } from "react";
import {
  Bar,
  BarChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { ChevronDown } from "lucide-react";

import {
  formatModelRuntimeLabel,
  formatRunMetricsFooter,
} from "@/lib/format/metrics";
import type { CallMetric, RunMetrics, RunStatus } from "@/lib/sse/types";
import { cn } from "@/lib/utils";
import { Badge } from "@/ui/badge";

function allCalls(metrics: RunMetrics): CallMetric[] {
  return [
    ...metrics.judge_calls,
    ...metrics.debate_calls,
    ...(metrics.revote_calls ?? []),
  ];
}

/** Stable React keys and chart labels when the same judge speaks across debate rounds. */
function indexedCalls(calls: CallMetric[]) {
  const seen = new Map<string, number>();
  return calls.map((call, index) => {
    const group = `${call.phase}-${call.label}`;
    const occurrence = (seen.get(group) ?? 0) + 1;
    seen.set(group, occurrence);
    return {
      call,
      key: `${group}-${index}`,
      chartLabel: occurrence === 1 ? call.label : `${call.label} (${occurrence})`,
    };
  });
}

function chartRows(metrics: RunMetrics) {
  return indexedCalls(allCalls(metrics)).map(({ call, chartLabel }) => ({
    label: chartLabel,
    seconds: call.seconds,
    tokens: call.total_tokens,
    phase: call.phase,
  }));
}

function MetricsTooltip({
  active,
  payload,
}: {
  active?: boolean;
  payload?: Array<{ payload: { label: string; seconds: number; tokens: number; phase: string } }>;
}) {
  if (!active || !payload?.[0]) return null;
  const row = payload[0].payload;
  return (
    <div className="border-2 border-ink bg-card px-3 py-2 font-sans text-xs shadow-hard">
      <p className="font-semibold text-ink">{row.label}</p>
      <p className="mt-1 text-ink-muted">
        {row.seconds.toFixed(1)}s · {row.tokens.toLocaleString()} tokens · {row.phase}
      </p>
    </div>
  );
}

export function RunMetricsBar({
  metrics,
  status,
  className,
}: {
  metrics: RunMetrics | null;
  status?: RunStatus;
  className?: string;
}) {
  const detailsId = useId();

  if (!metrics) {
    const isTerminal =
      status === "completed" || status === "failed" || status === "cancelled";
    const message =
      status === "failed" || status === "cancelled"
        ? "Run metrics unavailable."
        : isTerminal
          ? "Run metrics were not recorded for this run."
          : "Run metrics will appear when the roast finishes.";

    return (
      <footer
        className={cn(
          "border-t-2 border-rule-soft pt-6 font-mono text-xs text-ink-subtle",
          className,
        )}
        aria-label="Run metrics"
      >
        {message}
      </footer>
    );
  }

  const calls = indexedCalls(allCalls(metrics));
  const rows = chartRows(metrics);
  const chartSummary = rows
    .map((row) => `${row.label} ${row.seconds.toFixed(1)} seconds`)
    .join(", ");

  return (
    <footer className={cn("border-t-2 border-rule-soft pt-6", className)} aria-label="Run metrics">
      <div className="flex flex-wrap items-center gap-3">
        <p className="font-mono text-xs text-ink">{formatRunMetricsFooter(metrics)}</p>
        <Badge>{formatModelRuntimeLabel(metrics.model_runtime)}</Badge>
      </div>

      {calls.length > 0 && (
        <details className="group mt-4">
          <summary
            className="flex cursor-pointer list-none items-center gap-2 font-sans text-sm font-semibold text-ink hover:text-heat-ink [&::-webkit-details-marker]:hidden"
            aria-controls={detailsId}
          >
            <ChevronDown
              className="size-4 transition-transform group-open:rotate-180"
              aria-hidden
            />
            Per-call breakdown
          </summary>
          <div id={detailsId} className="mt-4 space-y-6">
            <div
              className="border-2 border-ink bg-card p-4"
              role="img"
              aria-label={`Per-call duration chart: ${chartSummary}`}
            >
              <ResponsiveContainer width="100%" height={Math.max(160, rows.length * 28)} minWidth={0}>
                <BarChart data={rows} layout="vertical" margin={{ left: 8, right: 16, top: 4, bottom: 4 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="var(--rule-soft)" horizontal={false} />
                  <XAxis
                    type="number"
                    unit="s"
                    tick={{ fill: "var(--ink-subtle)", fontSize: 10, fontFamily: "var(--font-mono)" }}
                    axisLine={{ stroke: "var(--rule-soft)" }}
                  />
                  <YAxis
                    type="category"
                    dataKey="label"
                    width={120}
                    tick={{ fill: "var(--ink-muted)", fontSize: 10, fontFamily: "var(--font-ui)" }}
                    axisLine={false}
                    tickLine={false}
                  />
                  <Tooltip content={<MetricsTooltip />} cursor={{ fill: "var(--paper-2)" }} />
                  <Bar
                    dataKey="seconds"
                    fill="var(--heat)"
                    radius={0}
                    isAnimationActive={false}
                    name="Seconds"
                  />
                </BarChart>
              </ResponsiveContainer>
            </div>

            <div className="overflow-x-auto border-2 border-rule-soft bg-paper-2">
              <table className="w-full min-w-[480px] border-collapse font-sans text-sm">
                <caption className="sr-only">Per-call metrics</caption>
                <thead>
                  <tr className="border-b-2 border-ink text-left">
                    <th scope="col" className="px-3 py-2 font-semibold">
                      Call
                    </th>
                    <th scope="col" className="px-3 py-2 font-semibold">
                      Phase
                    </th>
                    <th scope="col" className="px-3 py-2 font-semibold">
                      Time
                    </th>
                    <th scope="col" className="px-3 py-2 font-semibold">
                      Tokens
                    </th>
                  </tr>
                </thead>
                <tbody>
                  {calls.map(({ call, key, chartLabel }) => (
                    <tr key={key} className="border-b border-rule-soft last:border-b-0">
                      <th scope="row" className="px-3 py-2 font-medium text-ink">
                        {chartLabel}
                      </th>
                      <td className="px-3 py-2 capitalize text-ink-muted">{call.phase}</td>
                      <td className="px-3 py-2 font-mono tabular-nums">{call.seconds.toFixed(1)}s</td>
                      <td className="px-3 py-2 font-mono tabular-nums">
                        {call.total_tokens.toLocaleString()}
                        <span className="text-ink-subtle">
                          {" "}
                          ({call.input_tokens.toLocaleString()} in / {call.output_tokens.toLocaleString()} out)
                        </span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </details>
      )}
    </footer>
  );
}
