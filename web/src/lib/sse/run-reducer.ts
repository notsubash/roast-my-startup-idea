import {
  initialRunState,
  JUDGE_ORDER,
  type ApiEventEnvelope,
  type DebateTurnView,
  type JudgeId,
  type RunState,
  type SpeakerId,
  type Verdict,
  type AppealResult,
  type ResearchFindings,
} from "./types.ts";
import { appealJudgeOutcomes } from "../appeal/coaching.ts";

function isJudgeId(value: string): value is JudgeId {
  return (JUDGE_ORDER as readonly string[]).includes(value);
}

function parseVerdict(raw: unknown): Verdict | null {
  if (!raw || typeof raw !== "object") return null;
  const v = raw as Record<string, unknown>;
  if (
    typeof v.judge === "string" &&
    isJudgeId(v.judge) &&
    typeof v.verdict === "string" &&
    typeof v.roast === "string" &&
    typeof v.score === "number" &&
    typeof v.key_concern === "string"
  ) {
    return {
      judge: v.judge,
      verdict: v.verdict as Verdict["verdict"],
      roast: v.roast,
      score: v.score,
      key_concern: v.key_concern,
      recommended_fix:
        typeof v.recommended_fix === "string" ? v.recommended_fix : null,
      evidence_to_change_verdict:
        typeof v.evidence_to_change_verdict === "string"
          ? v.evidence_to_change_verdict
          : null,
    };
  }
  return null;
}

function upsertTurn(
  turns: DebateTurnView[],
  round: number,
  speaker: SpeakerId,
  patch: Partial<DebateTurnView>,
): DebateTurnView[] {
  const idx = turns.findIndex((t) => t.round === round && t.speaker === speaker);
  if (idx === -1) {
    return [
      ...turns,
      {
        speaker,
        round,
        content: "",
        streaming: false,
        thinking: false,
        ...patch,
      },
    ];
  }
  const next = [...turns];
  next[idx] = { ...next[idx], ...patch };
  return next;
}

function failPendingJudges(state: RunState): RunState {
  const judges = { ...state.judges };
  for (const id of JUDGE_ORDER) {
    if (judges[id].status === "idle" || judges[id].status === "thinking") {
      judges[id] = { status: "failed" };
    }
  }
  return { ...state, judges };
}

function applyRoastPanel(state: RunState, verdicts: Verdict[]): RunState {
  const judges = { ...state.judges };
  for (const verdict of verdicts) {
    judges[verdict.judge] = { status: "revealed", verdict };
  }
  return { ...state, judges, roastPanelComplete: true };
}

function parseAppealPanel(raw: unknown): Record<JudgeId, Verdict> | null {
  if (!raw || typeof raw !== "object") return null;
  const verdicts = (raw as { verdicts?: unknown[] }).verdicts;
  if (!Array.isArray(verdicts)) return null;
  const byJudge = {} as Record<JudgeId, Verdict>;
  for (const item of verdicts) {
    const verdict = parseVerdict(item);
    if (verdict) byJudge[verdict.judge] = verdict;
  }
  return Object.keys(byJudge).length > 0 ? byJudge : null;
}

function parseResearchFindings(payload: Record<string, unknown>): ResearchFindings | null {
  const query = payload.query;
  const rawFindings = payload.findings;
  if (typeof query !== "string" || !Array.isArray(rawFindings)) return null;
  const findings = rawFindings
    .map((item) => {
      if (!item || typeof item !== "object") return null;
      const row = item as Record<string, unknown>;
      if (
        typeof row.title === "string" &&
        typeof row.url === "string" &&
        typeof row.snippet === "string"
      ) {
        return { title: row.title, url: row.url, snippet: row.snippet };
      }
      return null;
    })
    .filter((f): f is NonNullable<typeof f> => f !== null);
  if (findings.length === 0) return null;
  return { query, findings };
}

function parseTargetJudges(raw: unknown): JudgeId[] {
  if (!Array.isArray(raw)) return [];
  return raw.filter(
    (item): item is JudgeId =>
      typeof item === "string" && (JUDGE_ORDER as readonly string[]).includes(item),
  );
}

function parseEvidenceOutcomes(raw: unknown): AppealResult["evidenceOutcomes"] {
  if (!Array.isArray(raw)) return [];
  const outcomes: AppealResult["evidenceOutcomes"] = [];
  for (const item of raw) {
    if (!item || typeof item !== "object") continue;
    const row = item as Record<string, unknown>;
    if (
      typeof row.judge === "string" &&
      isJudgeId(row.judge) &&
      typeof row.evidence_ask === "string" &&
      typeof row.outcome === "string" &&
      typeof row.targeted === "boolean" &&
      typeof row.score_delta === "number"
    ) {
      outcomes.push({
        judge: row.judge,
        evidenceAsk: row.evidence_ask,
        outcome: row.outcome,
        targeted: row.targeted,
        scoreDelta: row.score_delta,
      });
    }
  }
  return outcomes;
}

function parseAppealResult(payload: Record<string, unknown>): AppealResult | null {
  const appealText = payload.appeal_text;
  const revisedSynthesis = payload.revised_synthesis;
  if (typeof appealText !== "string" || typeof revisedSynthesis !== "string") return null;
  const originalByJudge = parseAppealPanel(payload.original_panel);
  const revisedByJudge = parseAppealPanel(payload.revised_panel);
  if (!originalByJudge || !revisedByJudge) return null;
  const targetJudges = parseTargetJudges(payload.target_judges);
  let evidenceOutcomes = parseEvidenceOutcomes(payload.evidence_outcomes);
  if (evidenceOutcomes.length === 0) {
    evidenceOutcomes = appealJudgeOutcomes(
      Object.values(originalByJudge),
      Object.values(revisedByJudge),
      targetJudges,
    );
  }
  return {
    appealText,
    originalByJudge,
    revisedByJudge,
    revisedSynthesis,
    targetJudges,
    evidenceOutcomes,
  };
}

function reconcileDebateMessages(
  state: RunState,
  messages: Array<{ speaker?: string; round?: number; content?: string }>,
): RunState {
  let debateTurns = [...state.debateTurns];
  for (const msg of messages) {
    if (
      typeof msg.speaker !== "string" ||
      typeof msg.round !== "number" ||
      typeof msg.content !== "string"
    ) {
      continue;
    }
    const speaker = msg.speaker === "moderator" || isJudgeId(msg.speaker)
      ? (msg.speaker as SpeakerId)
      : null;
    if (!speaker) continue;
    debateTurns = upsertTurn(debateTurns, msg.round, speaker, {
      content: msg.content,
      streaming: false,
      thinking: false,
    });
  }
  return { ...state, debateTurns };
}

function applyRevoteFromPanels(
  state: RunState,
  initialVerdicts: unknown[],
  revisedVerdicts: unknown[],
): RunState {
  const revoteBaseline = { ...state.revoteBaseline };
  const revoteChangeReasons = { ...state.revoteChangeReasons };
  for (const item of initialVerdicts) {
    const verdict = parseVerdict(item);
    if (verdict) revoteBaseline[verdict.judge] = verdict;
  }
  const judges = { ...state.judges };
  for (const item of revisedVerdicts) {
    const revised = parseVerdict(item);
    const original = parseVerdict(
      initialVerdicts.find(
        (row) =>
          row &&
          typeof row === "object" &&
          (row as { judge?: string }).judge === revised?.judge,
      ),
    );
    if (!revised) continue;
    judges[revised.judge] = { status: "revealed", verdict: revised };
    if (original && revised.score !== original.score && revised.evidence_to_change_verdict) {
      revoteChangeReasons[revised.judge] = revised.evidence_to_change_verdict;
    } else if (original && revised.score === original.score) {
      delete revoteChangeReasons[revised.judge];
    }
  }
  return { ...state, judges, revoteBaseline, revoteChangeReasons };
}

function terminalStatus(
  state: RunState,
  status: RunState["status"],
): RunState {
  if (status === "failed") {
    return failPendingJudges({ ...state, status });
  }
  return { ...state, status };
}

/** Pure event-sourced reducer — `(state, envelope) => state`. */
export function runReducer(state: RunState, envelope: ApiEventEnvelope): RunState {
  if (envelope.sequence <= state.lastSequence) {
    return state;
  }

  let next: RunState = { ...state, lastSequence: envelope.sequence };
  const payload = envelope.payload;

  switch (envelope.type) {
    case "stream_connected":
      return { ...next, connected: true, status: next.status === "connecting" ? "running" : next.status };

    case "phase_started": {
      const phase = payload.phase;
      if (phase === "roast" || phase === "debate") {
        next = { ...next, phase };
      }
      if (phase === "debate") {
        next = { ...next, status: "running" };
      }
      return next;
    }

    case "judges_dispatched": {
      const judges = { ...next.judges };
      for (const id of JUDGE_ORDER) {
        if (judges[id].status === "idle") {
          judges[id] = { status: "thinking" };
        }
      }
      return {
        ...next,
        judges,
        judgesDispatched: true,
        phase: "roast",
        status: "running",
      };
    }

    case "judge_verdict_completed": {
      const judge = payload.judge;
      const verdict = parseVerdict(payload.verdict);
      if (typeof judge !== "string" || !isJudgeId(judge) || !verdict) return next;
      const judges = { ...next.judges, [judge]: { status: "revealed", verdict } };
      return { ...next, judges, phase: "roast", status: "running" };
    }

    case "roast_panel_completed": {
      const panel = payload.panel as { verdicts?: unknown[] } | undefined;
      const verdicts = (panel?.verdicts ?? [])
        .map(parseVerdict)
        .filter((v): v is Verdict => v !== null);
      if (verdicts.length === 0) {
        return { ...next, roastPanelComplete: true };
      }
      return applyRoastPanel(next, verdicts);
    }

    case "debate_round_started": {
      const round = payload.round;
      if (typeof round !== "number") return next;
      return {
        ...next,
        currentRound: round,
        phase: "debate",
        activeSpeaker: null,
        status: "running",
      };
    }

    case "debate_speaker_thinking": {
      const judge = payload.judge;
      const round = payload.round;
      if (typeof judge !== "string" || typeof round !== "number") return next;
      const speaker = judge === "moderator" || isJudgeId(judge) ? (judge as SpeakerId) : null;
      if (!speaker) return next;
      return {
        ...next,
        phase: "debate",
        currentRound: round,
        activeSpeaker: speaker,
        debateTurns: upsertTurn(next.debateTurns, round, speaker, {
          thinking: true,
          streaming: false,
        }),
        status: "running",
      };
    }

    case "debate_token_delta": {
      const speaker = payload.speaker;
      const round = payload.round;
      const delta = payload.delta;
      if (
        typeof speaker !== "string" ||
        typeof round !== "number" ||
        typeof delta !== "string"
      ) {
        return next;
      }
      const sp = speaker === "moderator" || isJudgeId(speaker) ? (speaker as SpeakerId) : null;
      if (!sp) return next;
      const existing = next.debateTurns.find((t) => t.round === round && t.speaker === sp);
      const content = (existing?.content ?? "") + delta;
      return {
        ...next,
        phase: "debate",
        currentRound: round,
        activeSpeaker: sp,
        debateTurns: upsertTurn(next.debateTurns, round, sp, {
          content,
          streaming: true,
          thinking: false,
        }),
        status: "running",
      };
    }

    case "debate_message_published": {
      const speaker = payload.speaker;
      const round = payload.round;
      const content = payload.content;
      if (
        typeof speaker !== "string" ||
        typeof round !== "number" ||
        typeof content !== "string"
      ) {
        return next;
      }
      const sp = speaker === "moderator" || isJudgeId(speaker) ? (speaker as SpeakerId) : null;
      if (!sp) return next;
      return {
        ...next,
        phase: "debate",
        debateTurns: upsertTurn(next.debateTurns, round, sp, {
          content,
          streaming: false,
          thinking: false,
        }),
        status: "running",
      };
    }

    case "debate_synthesis_published": {
      const content = payload.content;
      if (typeof content !== "string") return next;
      return {
        ...next,
        synthesis: content,
        phase: "synthesis",
        status: "running",
      };
    }

    case "revote_started": {
      const revoteBaseline = { ...next.revoteBaseline };
      for (const id of JUDGE_ORDER) {
        const verdict = next.judges[id].verdict;
        if (verdict) revoteBaseline[id] = verdict;
      }
      return {
        ...next,
        revoteBaseline,
        phase: "debate",
        status: "running",
      };
    }

    case "revote_judge_completed": {
      const judge = payload.judge;
      const verdict = parseVerdict(payload.verdict);
      const changeReason = payload.change_reason;
      const originalScore = payload.original_score;
      if (typeof judge !== "string" || !isJudgeId(judge) || !verdict) return next;
      const judges = { ...next.judges, [judge]: { status: "revealed", verdict } };
      const revoteChangeReasons = { ...next.revoteChangeReasons };
      if (typeof originalScore === "number" && verdict.score === originalScore) {
        delete revoteChangeReasons[judge];
      } else if (typeof changeReason === "string" && changeReason.trim()) {
        revoteChangeReasons[judge] = changeReason;
      }
      return {
        ...next,
        judges,
        revoteChangeReasons,
        phase: "debate",
        status: "running",
      };
    }

    case "debate_completed": {
      const messages = payload.debate_messages;
      const finalSynthesis = payload.final_synthesis;
      const structuredSynthesis = payload.structured_synthesis;
      next =
        Array.isArray(messages)
          ? reconcileDebateMessages(next, messages as Array<Record<string, unknown>>)
          : next;
      if (typeof finalSynthesis === "string") {
        next = { ...next, synthesis: finalSynthesis, phase: "synthesis" };
      }
      if (structuredSynthesis && typeof structuredSynthesis === "object") {
        next = {
          ...next,
          structuredSynthesis: structuredSynthesis as Record<string, unknown>,
        };
      }
      const initialVerdicts = payload.initial_verdicts;
      const revisedVerdicts = payload.revised_verdicts;
      if (Array.isArray(initialVerdicts) && Array.isArray(revisedVerdicts)) {
        next = applyRevoteFromPanels(next, initialVerdicts, revisedVerdicts);
      }
      return next;
    }

    case "run_metrics":
      return { ...next, metrics: payload as unknown as RunState["metrics"] };

    case "run_completed": {
      const roastPanel = (payload.roast_panel as { verdicts?: unknown[] } | undefined)?.verdicts;
      if (Array.isArray(roastPanel)) {
        const verdicts = roastPanel.map(parseVerdict).filter((v): v is Verdict => v !== null);
        if (verdicts.length > 0) next = applyRoastPanel(next, verdicts);
      }
      const debateResult = payload.debate_result as
        | {
            debate_messages?: unknown[];
            final_synthesis?: string;
            structured_synthesis?: Record<string, unknown>;
            initial_verdicts?: unknown[];
            revised_verdicts?: unknown[];
          }
        | undefined;
      if (debateResult) {
        if (Array.isArray(debateResult.debate_messages)) {
          next = reconcileDebateMessages(
            next,
            debateResult.debate_messages as Array<Record<string, unknown>>,
          );
        }
        if (typeof debateResult.final_synthesis === "string") {
          next = { ...next, synthesis: debateResult.final_synthesis, phase: "synthesis" };
        }
        if (debateResult.structured_synthesis) {
          next = { ...next, structuredSynthesis: debateResult.structured_synthesis };
        }
        if (
          Array.isArray(debateResult.initial_verdicts) &&
          Array.isArray(debateResult.revised_verdicts)
        ) {
          next = applyRevoteFromPanels(
            next,
            debateResult.initial_verdicts,
            debateResult.revised_verdicts,
          );
        }
      }
      return terminalStatus(next, "completed");
    }

    case "run_failed": {
      const message = typeof payload.message === "string" ? payload.message : "Run failed.";
      const recoverable = payload.recoverable === true;
      return terminalStatus(
        { ...next, error: { message, recoverable } },
        "failed",
      );
    }

    case "run_cancelled": {
      const message =
        typeof payload.message === "string" ? payload.message : "Run cancelled.";
      return terminalStatus(
        { ...next, cancelMessage: message },
        "cancelled",
      );
    }

    case "appeal_completed": {
      const appeal = parseAppealResult(payload);
      if (!appeal) return next;
      return { ...next, appeal };
    }

    case "research_findings": {
      const researchFindings = parseResearchFindings(payload);
      if (!researchFindings) return next;
      return { ...next, researchFindings };
    }

    default:
      return next;
  }
}

export function reduceEnvelopes(
  envelopes: ApiEventEnvelope[],
  initial = initialRunState(),
): RunState {
  return envelopes.reduce(runReducer, initial);
}

export { initialRunState };
