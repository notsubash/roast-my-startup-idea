import type { components } from "./types";

export type CreateRunRequest = components["schemas"]["CreateRunRequest"];
export type RunCreatedResponse = components["schemas"]["RunCreatedResponse"];
export type RunStatusResponse = components["schemas"]["RunStatusResponse"];

export const RATE_LIMIT_MESSAGE =
  "Too many run requests. Please try again shortly.";

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
