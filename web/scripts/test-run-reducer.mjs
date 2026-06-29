import assert from "node:assert/strict";
import test from "node:test";

import {
  initialRunState,
  reduceEnvelopes,
  runReducer,
} from "../src/lib/sse/run-reducer.ts";

const VERDICT = {
  judge: "vc",
  verdict: "FAIL",
  roast: "The go-to-market path is unclear and the wedge is too weak to win attention.",
  score: 3,
  key_concern: "Weak distribution.",
};

function env(sequence, type, payload) {
  return {
    type,
    run_id: "run-test",
    sequence,
    payload,
    created_at: "2026-01-01T00:00:00Z",
  };
}

const HAPPY_PATH = [
  env(0, "stream_connected", { status: "connected" }),
  env(1, "phase_started", { phase: "roast" }),
  env(2, "judges_dispatched", { total: 5 }),
  env(3, "judge_verdict_completed", {
    judge: "vc",
    verdict: VERDICT,
    completed: 1,
    total: 5,
  }),
  env(4, "phase_started", { phase: "debate" }),
  env(5, "debate_round_started", { round: 1 }),
  env(6, "debate_speaker_thinking", { judge: "vc", round: 1 }),
  env(7, "debate_token_delta", { speaker: "vc", round: 1, delta: "Still " }),
  env(8, "debate_token_delta", { speaker: "vc", round: 1, delta: "weak." }),
  env(9, "debate_message_published", {
    speaker: "vc",
    round: 1,
    content: "Still weak distribution.",
  }),
  env(10, "debate_synthesis_published", { content: "The panel is not convinced." }),
  env(11, "run_completed", {
    roast_panel: { verdicts: [VERDICT] },
    debate_result: {
      debate_messages: [{ speaker: "vc", round: 1, content: "Still weak distribution." }],
      final_synthesis: "The panel is not convinced.",
    },
  }),
];

test("happy path: roast → debate → synthesis → completed", () => {
  const state = reduceEnvelopes(HAPPY_PATH);
  assert.equal(state.status, "completed");
  assert.equal(state.judges.vc.status, "revealed");
  assert.equal(state.judges.vc.verdict?.score, 3);
  assert.equal(state.debateTurns.length, 1);
  assert.equal(state.debateTurns[0].content, "Still weak distribution.");
  assert.equal(state.debateTurns[0].streaming, false);
  assert.equal(state.synthesis, "The panel is not convinced.");
});

test("debate_token_delta reconciles on debate_message_published", () => {
  const partial = HAPPY_PATH.slice(0, 9);
  let state = reduceEnvelopes(partial);
  assert.equal(state.debateTurns[0].content, "Still weak.");
  assert.equal(state.debateTurns[0].streaming, true);

  state = runReducer(state, HAPPY_PATH[9]);
  assert.equal(state.debateTurns[0].content, "Still weak distribution.");
  assert.equal(state.debateTurns[0].streaming, false);
});

test("reconnect: duplicate sequences are ignored", () => {
  const first = reduceEnvelopes(HAPPY_PATH.slice(0, 6));
  const replayed = HAPPY_PATH.slice(0, 6).reduce(runReducer, first);
  assert.equal(replayed.lastSequence, first.lastSequence);

  const resumed = HAPPY_PATH.slice(6).reduce(runReducer, first);
  assert.equal(resumed.lastSequence, 11);
  assert.equal(resumed.status, "completed");
});

test("run_cancelled terminal state", () => {
  const events = [
    env(0, "stream_connected", { status: "connected" }),
    env(1, "phase_started", { phase: "roast" }),
    env(2, "judges_dispatched", { total: 5 }),
    env(3, "run_cancelled", { message: "Run cancelled by user." }),
  ];
  const state = reduceEnvelopes(events);
  assert.equal(state.status, "cancelled");
  assert.equal(state.cancelMessage, "Run cancelled by user.");
});

test("run_failed marks pending judges failed", () => {
  const events = [
    env(0, "stream_connected", { status: "connected" }),
    env(1, "judges_dispatched", { total: 5 }),
    env(2, "run_failed", {
      message: "Run exceeded the wall-clock budget. Please try again.",
      recoverable: true,
    }),
  ];
  const state = reduceEnvelopes(events);
  assert.equal(state.status, "failed");
  assert.equal(state.error?.recoverable, true);
  assert.equal(state.judges.vc.status, "failed");
});

test("unknown event types are ignored safely", () => {
  const state = runReducer(
    initialRunState("running"),
    env(1, "future_event_type", { foo: "bar" }),
  );
  assert.equal(state.lastSequence, 1);
  assert.equal(state.status, "running");
});

test("moderator debate turn is supported", () => {
  const events = [
    env(0, "stream_connected", { status: "connected" }),
    env(1, "debate_token_delta", { speaker: "moderator", round: 2, delta: "Verdict: " }),
    env(2, "debate_message_published", {
      speaker: "moderator",
      round: 2,
      content: "Verdict: no path to PMF.",
    }),
  ];
  const state = reduceEnvelopes(events);
  assert.equal(state.debateTurns[0].speaker, "moderator");
  assert.equal(state.debateTurns[0].content, "Verdict: no path to PMF.");
});

test("research_findings stores query and sources", () => {
  const events = [
    env(0, "stream_connected", { status: "connected" }),
    env(1, "research_findings", {
      query: "AI startup market size 2026",
      findings: [
        {
          title: "Market report",
          url: "https://example.com/report",
          snippet: "The AI tools market grew 40% year over year.",
        },
      ],
    }),
  ];
  const state = reduceEnvelopes(events);
  assert.equal(state.researchFindings?.query, "AI startup market size 2026");
  assert.equal(state.researchFindings?.findings.length, 1);
  assert.equal(state.researchFindings?.findings[0].url, "https://example.com/report");
});

test("appeal_completed restores appeal state from replay", () => {
  const revised = { ...VERDICT, score: 6, verdict: "CONDITIONAL" };
  const events = [
    env(0, "stream_connected", { status: "connected" }),
    env(1, "run_completed", {
      roast_panel: { verdicts: [VERDICT] },
      debate_result: { debate_messages: [], final_synthesis: "Original synthesis." },
    }),
    env(2, "appeal_completed", {
      appeal_text: "We signed two LOIs and completed a validation study.",
      original_panel: { verdicts: [VERDICT] },
      revised_panel: { verdicts: [revised] },
      revised_synthesis: "Revised synthesis after appeal.",
    }),
  ];
  const state = reduceEnvelopes(events);
  assert.equal(state.appeal?.appealText, "We signed two LOIs and completed a validation study.");
  assert.equal(state.appeal?.revisedByJudge.vc.score, 6);
  assert.equal(state.appeal?.revisedSynthesis, "Revised synthesis after appeal.");
});

test("revote events update judges and preserve baseline for deltas", () => {
  const revised = {
    ...VERDICT,
    score: 5,
    evidence_to_change_verdict: "The engineer changed my view in round 1.",
  };
  const events = [
    env(0, "stream_connected", { status: "connected" }),
    env(1, "judge_verdict_completed", {
      judge: "vc",
      verdict: VERDICT,
      completed: 1,
      total: 5,
    }),
    env(2, "revote_started", { total: 5 }),
    env(3, "revote_judge_completed", {
      judge: "vc",
      verdict: revised,
      original_score: 3,
      completed: 1,
      total: 5,
      change_reason: "The engineer changed my view in round 1.",
    }),
  ];
  const state = reduceEnvelopes(events);
  assert.equal(state.judges.vc.verdict?.score, 5);
  assert.equal(state.revoteBaseline.vc?.score, 3);
  assert.equal(
    state.revoteChangeReasons.vc,
    "The engineer changed my view in round 1.",
  );
});

test("revote_judge_completed clears change reason when score is unchanged", () => {
  const events = [
    env(0, "stream_connected", { status: "connected" }),
    env(1, "judge_verdict_completed", {
      judge: "engineer",
      verdict: { ...VERDICT, judge: "engineer", score: 5 },
      completed: 1,
      total: 5,
    }),
    env(2, "revote_started", { total: 5 }),
    env(3, "revote_judge_completed", {
      judge: "engineer",
      verdict: {
        ...VERDICT,
        judge: "engineer",
        score: 5,
        evidence_to_change_verdict: "Would need a signed pilot contract.",
      },
      original_score: 5,
      completed: 1,
      total: 5,
    }),
  ];
  const state = reduceEnvelopes(events);
  assert.equal(state.judges.engineer.verdict?.score, 5);
  assert.equal(state.revoteChangeReasons.engineer, undefined);
});

test("debate_completed replay restores revote state without live revote events", () => {
  const initial = { ...VERDICT };
  const revised = {
    ...VERDICT,
    score: 5,
    evidence_to_change_verdict: "Round 1 engineer argument was persuasive.",
  };
  const events = [
    env(0, "stream_connected", { status: "connected" }),
    env(1, "debate_completed", {
      debate_messages: [{ speaker: "vc", round: 1, content: "Still weak." }],
      final_synthesis: "Not convinced.",
      initial_verdicts: [initial],
      revised_verdicts: [revised],
    }),
  ];
  const state = reduceEnvelopes(events);
  assert.equal(state.judges.vc.verdict?.score, 5);
  assert.equal(state.revoteBaseline.vc?.score, 3);
  assert.equal(
    state.revoteChangeReasons.vc,
    "Round 1 engineer argument was persuasive.",
  );
});
