"use client";

import {
  PolarAngleAxis,
  PolarGrid,
  PolarRadiusAxis,
  Radar,
  RadarChart,
  ResponsiveContainer,
} from "recharts";

import { JUDGE_META } from "@/lib/sse/judges";
import { JUDGE_ORDER } from "@/lib/sse/types";
import type { JudgeView } from "@/lib/sse/types";
import { cn } from "@/lib/utils";

export interface ScoreRadarPoint {
  judge: string;
  judgeId: (typeof JUDGE_ORDER)[number];
  score: number | null;
  verdict: string | null;
}

export function scoreRadarData(judges: Record<(typeof JUDGE_ORDER)[number], JudgeView>): ScoreRadarPoint[] {
  return JUDGE_ORDER.map((id) => ({
    judge: JUDGE_META[id].name.replace(/^The /, ""),
    judgeId: id,
    score: judges[id].verdict?.score ?? null,
    verdict: judges[id].verdict?.verdict ?? null,
  }));
}

export function ScoreRadar({
  judges,
  className,
}: {
  judges: Record<(typeof JUDGE_ORDER)[number], JudgeView>;
  className?: string;
}) {
  const data = scoreRadarData(judges);
  const revealed = data.filter((d) => d.score !== null);
  const hasAny = revealed.length > 0;
  const chartData = data.map((d) => ({
    ...d,
    plotScore: d.score,
  }));

  return (
    <div className={cn("grid gap-6 lg:grid-cols-2", className)}>
      <div
        className="border-2 border-ink bg-card p-4"
        role="img"
        aria-label={
          hasAny
            ? `Judge scores radar: ${revealed.map((d) => `${d.judge} ${d.score} out of 10`).join(", ")}`
            : "Judge scores radar, awaiting verdicts"
        }
      >
        <ResponsiveContainer width="100%" height={280} minWidth={0}>
          <RadarChart data={chartData} cx="50%" cy="50%" outerRadius="72%">
            <PolarGrid stroke="var(--rule-soft)" />
            <PolarAngleAxis
              dataKey="judge"
              tick={{ fill: "var(--ink-muted)", fontSize: 11, fontFamily: "var(--font-ui)" }}
            />
            <PolarRadiusAxis
              angle={90}
              domain={[0, 10]}
              tick={{ fill: "var(--ink-subtle)", fontSize: 10, fontFamily: "var(--font-mono)" }}
              axisLine={false}
            />
            <Radar
              name="Score"
              dataKey="plotScore"
              stroke="var(--heat)"
              fill="var(--heat)"
              fillOpacity={hasAny ? 0.2 : 0}
              strokeWidth={2}
              connectNulls={false}
              isAnimationActive={false}
            />
          </RadarChart>
        </ResponsiveContainer>
        {!hasAny && (
          <p className="-mt-2 text-center font-sans text-xs text-ink-subtle">
            Scores appear as each judge delivers a verdict.
          </p>
        )}
      </div>

      <div className="overflow-x-auto border-2 border-rule-soft bg-paper-2">
        <table className="w-full min-w-[240px] border-collapse font-sans text-sm">
          <caption className="sr-only">Judge scores</caption>
          <thead>
            <tr className="border-b-2 border-ink text-left">
              <th scope="col" className="px-4 py-2 font-semibold text-ink">
                Judge
              </th>
              <th scope="col" className="px-4 py-2 font-semibold text-ink">
                Score
              </th>
              <th scope="col" className="px-4 py-2 font-semibold text-ink">
                Verdict
              </th>
            </tr>
          </thead>
          <tbody>
            {data.map((row) => (
              <tr key={row.judgeId} className="border-b border-rule-soft last:border-b-0">
                <th scope="row" className="px-4 py-2 font-medium text-ink">
                  {JUDGE_META[row.judgeId].name}
                </th>
                <td className="px-4 py-2 font-mono tabular-nums text-ink">
                  {row.score !== null ? `${row.score}/10` : "—"}
                </td>
                <td className="px-4 py-2 text-ink-muted">
                  {row.verdict ?? "—"}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
