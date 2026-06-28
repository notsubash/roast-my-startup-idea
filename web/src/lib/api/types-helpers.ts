import type { components } from "./types";

export type CreateRunRequest = components["schemas"]["CreateRunRequest"];
export type RunCreatedResponse = components["schemas"]["RunCreatedResponse"];
export type RunStatusResponse = components["schemas"]["RunStatusResponse"];
export type AppealRequest = components["schemas"]["AppealRequest"];
export type AppealResponse = components["schemas"]["AppealResponse"];
export type RunListResponse = components["schemas"]["RunListResponse"];
export type RunListItem = components["schemas"]["RunListItem"];
export type VerdictSummary = components["schemas"]["VerdictSummary"];
export type SimilarRunsResponse = components["schemas"]["SimilarRunsResponse"];
export type SimilarRunItem = components["schemas"]["SimilarRunItem"];

export type ApiRunStatus = RunStatusResponse["status"];

/** Mirror ``src/api/schemas.py`` appeal bounds (OpenAPI does not emit min/max). */
export const APPEAL_MIN_LENGTH = 10;
export const APPEAL_MAX_LENGTH = 4000;

export const RATE_LIMIT_MESSAGE =
  "Too many run requests. Please try again shortly.";

export const APPEAL_RATE_LIMIT_MESSAGE =
  "Too many appeal requests. Please try again shortly.";

export function parseApiDetail(body: string): string | null {
  try {
    const parsed = JSON.parse(body) as { detail?: unknown };
    if (typeof parsed.detail === "string") return parsed.detail;
    if (Array.isArray(parsed.detail)) {
      const first = parsed.detail[0] as { msg?: string } | undefined;
      return first?.msg ?? null;
    }
  } catch {
    /* ponytail: body wasn't JSON */
  }
  return null;
}
