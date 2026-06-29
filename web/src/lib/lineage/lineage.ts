import type { RunListItem } from "@/lib/api/types-helpers";
import type { Verdict, VerdictLabel } from "@/lib/sse/types";

/** ponytail: show latest two in sidebar; full chain still available via expander. */
export const SIDEBAR_VERSION_TAIL = 2;

const VERDICT_RANK: Record<VerdictLabel, number> = {
  FAIL: 0,
  CONDITIONAL: 1,
  PASS: 2,
};

export type AddressedStatus = "Likely addressed" | "Still open" | "Concern shifted";

function addressedStatus(prior: Verdict, current: Verdict): AddressedStatus {
  // ponytail: score/verdict/concern heuristics only; LLM diff is the upgrade path.
  if (current.score > prior.score) return "Likely addressed";
  if (current.score < prior.score) return "Still open";
  if (prior.key_concern.trim().toLowerCase() === current.key_concern.trim().toLowerCase()) {
    return "Still open";
  }
  const priorRank = VERDICT_RANK[prior.verdict] ?? 0;
  const currentRank = VERDICT_RANK[current.verdict] ?? 0;
  if (currentRank > priorRank) return "Likely addressed";
  return "Concern shifted";
}

export function concernAddressedStatus(prior: Verdict, current: Verdict): AddressedStatus {
  return addressedStatus(prior, current);
}

export function recommendedFixStatus(prior: Verdict, current: Verdict): AddressedStatus | null {
  if (!(prior.recommended_fix ?? "").trim()) return null;
  return addressedStatus(prior, current);
}

/** Neutral label when fix adherence is inferred from score/concern heuristics. */
export function fixStatusLabel(status: AddressedStatus): string {
  if (status === "Concern shifted") return "Status unclear";
  return status;
}

export function lineageRootId(
  run: Pick<RunListItem, "run_id" | "parent_run_id">,
  byId: Map<string, Pick<RunListItem, "run_id" | "parent_run_id">>,
): string {
  let current = run;
  const seen = new Set([current.run_id]);
  while (current.parent_run_id && byId.has(current.parent_run_id)) {
    const parent = byId.get(current.parent_run_id)!;
    if (seen.has(parent.run_id)) break;
    seen.add(parent.run_id);
    current = parent;
  }
  return current.run_id;
}

export function groupByLineage(runs: RunListItem[]): RunListItem[][] {
  if (runs.length === 0) return [];
  const byId = new Map(runs.map((run) => [run.run_id, run]));
  const groups = new Map<string, RunListItem[]>();
  for (const run of runs) {
    const root = lineageRootId(run, byId);
    const bucket = groups.get(root) ?? [];
    bucket.push(run);
    groups.set(root, bucket);
  }
  const grouped = [...groups.values()].map((group) =>
    [...group].sort((a, b) => (a.version ?? 1) - (b.version ?? 1)),
  );
  grouped.sort(
    (a, b) =>
      new Date(b[b.length - 1]!.created_at).getTime() -
      new Date(a[a.length - 1]!.created_at).getTime(),
  );
  return grouped;
}

export function sidebarLineageVersions(lineage: RunListItem[]): {
  visible: RunListItem[];
  hidden: RunListItem[];
} {
  if (lineage.length <= SIDEBAR_VERSION_TAIL) {
    return { visible: lineage, hidden: [] };
  }
  return {
    visible: lineage.slice(-SIDEBAR_VERSION_TAIL),
    hidden: lineage.slice(0, -SIDEBAR_VERSION_TAIL),
  };
}

export function parseVerdict(raw: unknown): Verdict | null {
  if (!raw || typeof raw !== "object") return null;
  const item = raw as Record<string, unknown>;
  const judge = item.judge;
  const verdict = item.verdict;
  if (typeof judge !== "string" || typeof verdict !== "string") return null;
  if (typeof item.roast !== "string" || typeof item.key_concern !== "string") return null;
  if (typeof item.score !== "number") return null;
  return {
    judge: judge as Verdict["judge"],
    verdict: verdict as VerdictLabel,
    roast: item.roast,
    score: item.score,
    key_concern: item.key_concern,
    recommended_fix:
      typeof item.recommended_fix === "string" ? item.recommended_fix : null,
    evidence_to_change_verdict:
      typeof item.evidence_to_change_verdict === "string"
        ? item.evidence_to_change_verdict
        : null,
  };
}
