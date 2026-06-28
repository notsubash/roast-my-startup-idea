import type { VerdictLabel } from "@/lib/sse/types";
import { JUDGE_ORDER } from "@/lib/sse/types";
import type { JudgeView } from "@/lib/sse/types";

export interface VerdictTally {
  pass: number;
  conditional: number;
  fail: number;
  pending: number;
  total: number;
}

export function verdictTally(
  judges: Record<(typeof JUDGE_ORDER)[number], JudgeView>,
): VerdictTally {
  const tally = { pass: 0, conditional: 0, fail: 0, pending: 0, total: JUDGE_ORDER.length };
  for (const id of JUDGE_ORDER) {
    const label = judges[id].verdict?.verdict;
    if (label === "PASS") tally.pass += 1;
    else if (label === "CONDITIONAL") tally.conditional += 1;
    else if (label === "FAIL") tally.fail += 1;
    else tally.pending += 1;
  }
  return tally;
}

export function verdictTallySummary(tally: VerdictTally): string {
  const parts: string[] = [];
  if (tally.pass) parts.push(`${tally.pass} PASS`);
  if (tally.conditional) parts.push(`${tally.conditional} CONDITIONAL`);
  if (tally.fail) parts.push(`${tally.fail} FAIL`);
  if (tally.pending) parts.push(`${tally.pending} pending`);
  return parts.join(", ") || "No verdicts yet";
}

export const VERDICT_SEGMENT: Record<
  VerdictLabel,
  { label: string; barClass: string; textClass: string }
> = {
  PASS: { label: "PASS", barClass: "bg-pass", textClass: "text-pass" },
  CONDITIONAL: {
    label: "CONDITIONAL",
    barClass: "bg-conditional",
    textClass: "text-conditional",
  },
  FAIL: { label: "FAIL", barClass: "bg-fail", textClass: "text-fail" },
};
