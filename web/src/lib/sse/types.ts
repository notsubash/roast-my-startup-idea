export type VerdictLabel = "PASS" | "FAIL" | "CONDITIONAL";

export const JUDGE_ORDER = [
  "vc",
  "engineer",
  "pm",
  "customer",
  "competitor",
] as const;

export type JudgeId = (typeof JUDGE_ORDER)[number];
export type SpeakerId = JudgeId | "moderator";

export interface Verdict {
  judge: JudgeId;
  verdict: VerdictLabel;
  roast: string;
  score: number;
  key_concern: string;
  recommended_fix?: string | null;
  evidence_to_change_verdict?: string | null;
}

export type RunPhase = "roast" | "debate" | "synthesis" | null;

export type RunStatus =
  | "connecting"
  | "created"
  | "running"
  | "completed"
  | "failed"
  | "cancelled";

export type JudgeViewStatus = "idle" | "thinking" | "revealed" | "failed";

export interface JudgeView {
  status: JudgeViewStatus;
  verdict?: Verdict;
}

export interface DebateTurnView {
  speaker: SpeakerId;
  round: number;
  content: string;
  streaming: boolean;
  thinking: boolean;
}

export interface RunMetrics {
  roast_seconds: number;
  debate_seconds: number;
  total_seconds: number;
  input_tokens: number;
  output_tokens: number;
  total_tokens: number;
  estimated_cost_usd: number;
  model_runtime: "local" | "deepseek";
  judge_calls: CallMetric[];
  debate_calls: CallMetric[];
  revote_seconds?: number;
  revote_calls?: CallMetric[];
}

export interface CallMetric {
  label: string;
  phase: "roast" | "debate";
  seconds: number;
  input_tokens: number;
  output_tokens: number;
  total_tokens: number;
}

export interface RunError {
  message: string;
  recoverable: boolean;
}

export interface AppealJudgeOutcome {
  judge: JudgeId;
  evidenceAsk: string;
  outcome: string;
  targeted: boolean;
  scoreDelta: number;
}

export interface AppealResult {
  appealText: string;
  originalByJudge: Record<JudgeId, Verdict>;
  revisedByJudge: Record<JudgeId, Verdict>;
  revisedSynthesis: string;
  targetJudges: JudgeId[];
  evidenceOutcomes: AppealJudgeOutcome[];
}

export interface ResearchFinding {
  title: string;
  url: string;
  snippet: string;
}

export interface ResearchFindings {
  query: string;
  findings: ResearchFinding[];
}

export interface RunState {
  lastSequence: number;
  connected: boolean;
  phase: RunPhase;
  judges: Record<JudgeId, JudgeView>;
  judgesDispatched: boolean;
  roastPanelComplete: boolean;
  /** Initial roast scores preserved for post-debate delta badges. */
  revoteBaseline: Partial<Record<JudgeId, Verdict>>;
  revoteChangeReasons: Partial<Record<JudgeId, string>>;
  currentRound: number | null;
  activeSpeaker: SpeakerId | null;
  debateTurns: DebateTurnView[];
  synthesis: string | null;
  structuredSynthesis: Record<string, unknown> | null;
  metrics: RunMetrics | null;
  status: RunStatus;
  error: RunError | null;
  cancelMessage: string | null;
  appeal: AppealResult | null;
  researchFindings: ResearchFindings | null;
}

export interface ApiEventEnvelope {
  type: string;
  run_id: string;
  sequence: number;
  payload: Record<string, unknown>;
  created_at: string;
}

export function turnKey(round: number, speaker: SpeakerId): string {
  return `${round}:${speaker}`;
}

export function initialRunState(
  status: RunStatus = "connecting",
): RunState {
  const judges = {} as Record<JudgeId, JudgeView>;
  for (const id of JUDGE_ORDER) {
    judges[id] = { status: "idle" };
  }
  return {
    lastSequence: -1,
    connected: false,
    phase: null,
    judges,
    judgesDispatched: false,
    roastPanelComplete: false,
    revoteBaseline: {},
    revoteChangeReasons: {},
    currentRound: null,
    activeSpeaker: null,
    debateTurns: [],
    synthesis: null,
    structuredSynthesis: null,
    metrics: null,
    status,
    error: null,
    cancelMessage: null,
    appeal: null,
    researchFindings: null,
  };
}
