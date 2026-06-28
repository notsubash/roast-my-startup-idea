import {
  initialRunState,
  JUDGE_ORDER,
  type ApiEventEnvelope,
  type DebateTurnView,
  type JudgeId,
  type RunState,
  type SpeakerId,
  type Verdict,
} from "./types.ts";

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
    return v as unknown as Verdict;
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

    case "debate_completed": {
      const messages = payload.debate_messages;
      const finalSynthesis = payload.final_synthesis;
      next =
        Array.isArray(messages)
          ? reconcileDebateMessages(next, messages as Array<Record<string, unknown>>)
          : next;
      if (typeof finalSynthesis === "string") {
        next = { ...next, synthesis: finalSynthesis, phase: "synthesis" };
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
        | { debate_messages?: unknown[]; final_synthesis?: string }
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
