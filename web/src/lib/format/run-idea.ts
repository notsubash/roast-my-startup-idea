const KEY = "roast-run-idea";

/** ponytail: stash full idea on submit for same-tab export before REST round-trip. */
export function stashRunIdea(runId: string, idea: string): void {
  try {
    sessionStorage.setItem(KEY, JSON.stringify({ runId, idea }));
  } catch {
    /* quota/private mode — fall back to preview */
  }
}

/** Prefer API full idea, then same-tab stash, then truncated preview. */
export function resolveExportIdea(
  runId: string,
  preview: string,
  apiIdea?: string | null,
): string {
  if (typeof apiIdea === "string" && apiIdea.trim()) {
    return apiIdea;
  }

  try {
    const raw = sessionStorage.getItem(KEY);
    if (!raw) return preview;
    const parsed = JSON.parse(raw) as { runId?: string; idea?: string };
    if (parsed.runId === runId && typeof parsed.idea === "string" && parsed.idea.trim()) {
      return parsed.idea;
    }
  } catch {
    /* ignore */
  }
  return preview;
}
