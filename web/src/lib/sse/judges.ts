import type { JudgeId, SpeakerId } from "./types";

export interface JudgeMeta {
  id: JudgeId;
  name: string;
  /** Concise rubric tag shown on verdict cards. */
  lensTag: string;
  role: string;
  accentClass: string;
}

export const JUDGE_META: Record<JudgeId, JudgeMeta> = {
  vc: {
    id: "vc",
    name: "The VC",
    lensTag: "Fundability",
    role: "Market size, moat, CAC, scalability, fundability.",
    accentClass: "text-judge-vc border-judge-vc",
  },
  engineer: {
    id: "engineer",
    name: "The Engineer",
    lensTag: "Feasibility",
    role: "Feasibility, complexity, reliability, technical differentiation.",
    accentClass: "text-judge-engineer border-judge-engineer",
  },
  pm: {
    id: "pm",
    name: "The PM",
    lensTag: "Product-market fit",
    role: "ICP, pain, positioning, prioritization, product-market fit.",
    accentClass: "text-judge-pm border-judge-pm",
  },
  customer: {
    id: "customer",
    name: "The Customer",
    lensTag: "Willingness to pay",
    role: "Willingness to pay, friction, alternatives, urgency.",
    accentClass: "text-judge-customer border-judge-customer",
  },
  competitor: {
    id: "competitor",
    name: "The Competitor",
    lensTag: "Defensibility",
    role: "Defensibility, replication risk, switching costs, market position.",
    accentClass: "text-judge-competitor border-judge-competitor",
  },
};

export const MODERATOR_META = {
  name: "The Moderator",
  role: "Weighs the debate and hands down the synthesis.",
  accentClass: "text-judge-moderator border-judge-moderator",
};

export function speakerMeta(speaker: SpeakerId) {
  if (speaker === "moderator") return MODERATOR_META;
  return JUDGE_META[speaker];
}

export function speakerName(speaker: SpeakerId): string {
  return speakerMeta(speaker).name;
}
