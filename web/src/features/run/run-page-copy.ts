/**
 * Run page copy freeze (Phase 0).
 *
 * Checklist — block new above-fold sections unless they pass:
 * 1. One primary action per screen (evidence or refine, not browse judges).
 * 2. Above the fold answers: what should I do next?
 * 3. Top 3 problems visible before judge detail.
 * 4. Judges only after action guidance (appeal precedes panel in fold order).
 * 5. Evidence/iteration language only — no "appeal", "roast panel", or "verdict sheet".
 * 6. Every completed run shows version progress when lineage exists.
 */

export const RUN_PAGE_COPY = {
  reviewEyebrow: "Review",
  overallDecision: "Overall decision",
  topProblems: "Top problems",
  highestPriority: "Highest priority",
  recommendedExperiment: "Recommended experiment",
  todaysGoal: "Today's goal",
  presentEvidence: "Present evidence",
  presentEvidenceLead: "Completed your experiment? Share results to update this review.",
  viewEvidenceResult: "View evidence result",
  judgePanel: "Judge detail",
  debateTranscript: "Debate transcript",
  reviewComplete: "Review complete",
  reviewNotFound: "This review does not exist or the link is wrong.",
  submitIdea: "Review an idea",
  refineIdea: "Refine this idea",
  submitAnother: "Review another idea",
  phaseReviewing: "The panel is reviewing your idea",
  reviewCancelled: "You stopped this review before it finished.",
  stopReviewTitle: "Stop this review?",
  stopReviewDescription: "The judges will halt between turns. You can always submit a new idea.",
  contextSummary: "Related reviews, sources, metrics",
} as const;

export const HOME_COPY = {
  eyebrow: "Startup iteration review",
  headline: "Five AI judges review your startup idea, debate it, and recommend your next step.",
  lead: "Submit your pitch. Watch five distinct critics score, challenge, and argue in real time.",
} as const;

export const SETTINGS_COPY = {
  intro:
    "Defaults for new reviews and how completed review pages are laid out. Stored in this browser only — founders can ignore this page and use the simple submit flow on",
  newReviewDefaults: "New review defaults",
  newReviewDescription:
    "Applied every time you submit or refine an idea. The submit form no longer shows these controls.",
  reviewLayoutDescription:
    "Controls section order on /run/[id] after a review finishes. Does not change API behavior or scores — only what you scroll past first.",
  webSearchLabel: "Enable web search for new reviews",
} as const;

export const HISTORY_COPY = {
  eyebrow: "Archive",
  title: "Idea timeline",
  description: "Every iteration of your startup ideas — reopen any review.",
  emptyTitle: "No reviews yet",
  emptyDescription: "Submit your first idea — it will show up here when the review finishes.",
} as const;

export const EVIDENCE_COPY = {
  formTitle: "Present evidence",
  formLead:
    "Share what you learned from your experiment. Tag the judges you are addressing so the panel knows what you are trying to prove.",
  evidenceLabel: "What happened?",
  evidencePlaceholder:
    "We completed two validation studies, signed LOIs with pilot customers, and filed a provisional patent…",
  submit: "Submit evidence",
  submitting: "Submitting evidence — the panel is revising their verdicts.",
  submitFailed: "Evidence submission failed",
  submitFailedDetail: "Could not submit evidence.",
  resultTitle: "Evidence result",
  resultLead:
    "Updated verdicts after your evidence. Outcome badges show whether each judge's ask was met.",
  yourEvidence: "Your evidence:",
  minLengthError: (min: number) => `Evidence must be at least ${min} characters.`,
  maxLengthError: (max: number) => `Evidence must be at most ${max} characters.`,
} as const;
