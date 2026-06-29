import type { RunMetrics } from "../sse/types.ts";

/** Mirrors backend `format_run_metrics_footer`. */
export function formatRunMetricsFooter(metrics: RunMetrics): string {
  const totalTokens = metrics.total_tokens;
  const tokensLabel =
    totalTokens >= 1000
      ? `~${(totalTokens / 1000).toFixed(1)}k tokens`
      : `~${totalTokens} tokens`;

  const cost = metrics.estimated_cost_usd;
  let costLabel: string;
  if (cost >= 0.01) {
    costLabel = `~$${cost.toFixed(2)}`;
  } else if (cost > 0) {
    costLabel = `~$${cost.toFixed(3)}`;
  } else {
    costLabel = "~$0.00";
  }

  const revoteSeconds = metrics.revote_seconds ?? 0;
  const revoteLabel = revoteSeconds > 0 ? ` · Re-vote ${revoteSeconds.toFixed(1)}s` : "";

  return (
    `Roast ${metrics.roast_seconds.toFixed(1)}s · ` +
    `Debate ${metrics.debate_seconds.toFixed(1)}s` +
    `${revoteLabel} · ` +
    `${tokensLabel} · ` +
    `${costLabel}`
  );
}

export function formatRunMetricsMarkdown(metrics: RunMetrics | null): string[] {
  if (!metrics) return [];

  const revoteSeconds = metrics.revote_seconds ?? 0;
  const lines = [
    "## Run Metrics",
    "",
    `**Summary:** ${formatRunMetricsFooter(metrics)}`,
    "",
    `- **Roast phase:** ${metrics.roast_seconds.toFixed(1)}s wall-clock`,
    `- **Debate phase:** ${metrics.debate_seconds.toFixed(1)}s wall-clock`,
  ];
  if (revoteSeconds > 0) {
    lines.push(`- **Re-vote phase:** ${revoteSeconds.toFixed(1)}s wall-clock (included in debate)`);
  }
  lines.push(
    `- **Total time:** ${metrics.total_seconds.toFixed(1)}s`,
    `- **Tokens:** ${metrics.input_tokens.toLocaleString()} input / ${metrics.output_tokens.toLocaleString()} output (${metrics.total_tokens.toLocaleString()} total)`,
    `- **Estimated cost:** $${metrics.estimated_cost_usd.toFixed(4)} (${metrics.model_runtime})`,
    "",
  );
  return lines;
}

export function formatModelRuntimeLabel(runtime: RunMetrics["model_runtime"]): string {
  return runtime === "local" ? "Local (free)" : "DeepSeek";
}
