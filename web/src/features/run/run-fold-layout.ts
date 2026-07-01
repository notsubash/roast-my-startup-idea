/** Section keys for the workflow-first run fold. */
export type RunFoldSection =
  | "decision"
  | "version"
  | "appeal"
  | "judges"
  | "transcript"
  | "context";

/** A = panel before evidence loop; B = action guidance before judge detail (default). */
export type RunFoldVariant = "panel-first" | "iterate-first";

/** @deprecated Use ADVANCED_SETTINGS_STORAGE_KEY via advanced-settings.ts */
export const RUN_FOLD_STORAGE_KEY = "rms-run-fold-variant";

/** Default — workflow-first: decision, progress, evidence, then collapsed detail. */
export const DEFAULT_RUN_FOLD_VARIANT: RunFoldVariant = "iterate-first";

export const RUN_FOLD_SECTION_LABELS: Record<RunFoldSection, string> = {
  decision: "Overall decision and next steps",
  version: "Progress since last version",
  appeal: "Present evidence",
  judges: "Judge detail (collapsed)",
  transcript: "Debate transcript (collapsed)",
  context: "Sources, metrics, and related reviews (collapsed)",
};

export const RUN_FOLD_VARIANTS: Record<
  RunFoldVariant,
  {
    label: string;
    queryFlag: "a" | "b";
    summary: string;
    bestFor: string;
  }
> = {
  "panel-first": {
    label: "Judges first",
    queryFlag: "a",
    summary:
      "Read every judge score before the evidence loop and version progress.",
    bestFor: "Rollback — panel detail before action guidance.",
  },
  "iterate-first": {
    label: "Workflow first",
    queryFlag: "b",
    summary:
      "See decision, progress, and evidence guidance before judge detail.",
    bestFor: "Default — one next action above the fold.",
  },
};

export const RUN_FOLD_ORDERS: Record<RunFoldVariant, RunFoldSection[]> = {
  "panel-first": ["decision", "judges", "version", "appeal", "transcript", "context"],
  "iterate-first": ["decision", "version", "appeal", "judges", "transcript", "context"],
};

export function formatFoldSectionOrder(variant: RunFoldVariant): string[] {
  return RUN_FOLD_ORDERS[variant].map((section) => RUN_FOLD_SECTION_LABELS[section]);
}

const QUERY_TO_VARIANT: Record<string, RunFoldVariant> = {
  a: "panel-first",
  b: "iterate-first",
  "panel-first": "panel-first",
  "iterate-first": "iterate-first",
};

export function parseFoldQueryParam(value: string | null | undefined): RunFoldVariant | null {
  if (!value) return null;
  return QUERY_TO_VARIANT[value.toLowerCase()] ?? null;
}

export function foldVariantToQueryFlag(variant: RunFoldVariant): "a" | "b" {
  return RUN_FOLD_VARIANTS[variant].queryFlag;
}

export function resolveRunFoldVariant(
  queryParam: string | null | undefined,
  stored: string | null | undefined,
): RunFoldVariant {
  return (
    parseFoldQueryParam(queryParam) ??
    parseFoldQueryParam(stored) ??
    DEFAULT_RUN_FOLD_VARIANT
  );
}
