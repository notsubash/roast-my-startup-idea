"use client";

import { AlertTriangle } from "lucide-react";

import type { Verdict } from "@/lib/sse/types";
import { cn } from "@/lib/utils";

import {
  parseDecisionVerdictProse,
  parseStructuredSynthesis,
  type StructuredSynthesis,
} from "./structured-synthesis";
import { assessVerdictOutputQuality } from "./verdict-quality";
import { parseSynthesis } from "./synthesis-format";
import { SynthesisBlock } from "./synthesis-block";

const RECOMMENDATION_LABEL: Record<StructuredSynthesis["overall_recommendation"], string> = {
  GO: "Go",
  ITERATE: "Iterate",
  "NO-GO": "No-go",
};

const RECOMMENDATION_CLASS: Record<StructuredSynthesis["overall_recommendation"], string> = {
  GO: "text-pass",
  ITERATE: "text-conditional",
  "NO-GO": "text-fail",
};

export function VerdictCard({
  synthesisProse,
  structuredSynthesis,
  verdicts,
  className,
}: {
  synthesisProse: string | null;
  structuredSynthesis: unknown;
  verdicts: Verdict[];
  className?: string;
}) {
  const structuredFromPayload = parseStructuredSynthesis(structuredSynthesis);
  const numberedProse =
    !structuredFromPayload && synthesisProse ? parseSynthesis(synthesisProse) : null;
  const structuredFromProse =
    !structuredFromPayload && synthesisProse
      ? parseDecisionVerdictProse(synthesisProse)
      : null;
  const structured = structuredFromPayload ?? structuredFromProse;
  const quality = assessVerdictOutputQuality(
    verdicts,
    structured,
    Boolean(synthesisProse) && !structuredFromPayload && !numberedProse,
  );

  if (!structured) {
    if (!synthesisProse) {
      return (
        <p className={cn("font-sans text-sm text-ink-subtle", className)}>
          The moderator&apos;s verdict will land here after the debate.
        </p>
      );
    }
    return (
      <div className={cn("space-y-4", className)}>
        {quality.lowConfidence && (
          <LowConfidenceBanner reasons={quality.reasons} proseFallback />
        )}
        <SynthesisBlock content={synthesisProse} variant="debate" />
      </div>
    );
  }

  const detailRisks = structured.top_risks.length > 0;

  return (
    <article
      className={cn("border border-rule-soft bg-card shadow-soft", className)}
      aria-labelledby="decision-verdict-heading"
    >
      {quality.lowConfidence && <LowConfidenceBanner reasons={quality.reasons} />}

      <header className="border-b border-rule-soft px-5 py-4">
        <p className="font-sans text-xs font-semibold uppercase tracking-widest text-ink-muted">
          Recommendation
        </p>
        <h3
          id="decision-verdict-heading"
          className={cn(
            "mt-2 font-sans text-3xl font-semibold md:text-4xl",
            RECOMMENDATION_CLASS[structured.overall_recommendation],
          )}
        >
          {RECOMMENDATION_LABEL[structured.overall_recommendation]}
        </h3>
        <p className="mt-2 font-sans text-sm text-ink-muted">
          {structured.confidence} confidence
        </p>
      </header>

      <details className="group px-5 py-4">
        <summary className="cursor-pointer list-none font-sans text-sm font-semibold text-ink underline decoration-rule-soft underline-offset-4 marker:content-none group-open:mb-4">
          Full rationale
        </summary>
        <div className="space-y-5 border-t border-rule-soft pt-3">
          {structured.top_strengths.length > 0 && (
            <section>
              <h4 className="font-sans text-lg font-semibold text-ink">Strengths</h4>
              <ul className="mt-2 space-y-2 border-l-2 border-rule-soft pl-4">
                {structured.top_strengths.map((item, index) => (
                  <li key={index} className="font-sans text-sm leading-relaxed text-ink-muted">
                    {item}
                  </li>
                ))}
              </ul>
            </section>
          )}
          {detailRisks && (
            <section>
              <h4 className="font-sans text-lg font-semibold text-ink">Top risks</h4>
              <ul className="mt-2 space-y-2 border-l-2 border-rule-soft pl-4">
                {structured.top_risks.map((item, index) => (
                  <li key={index} className="font-sans text-sm leading-relaxed text-ink-muted">
                    {item}
                  </li>
                ))}
              </ul>
            </section>
          )}
          <section>
            <h4 className="font-sans text-lg font-semibold text-ink">Biggest disagreement</h4>
            <p className="mt-2 font-sans text-sm leading-relaxed text-ink-muted">
              {structured.biggest_disagreement}
            </p>
          </section>
        </div>
      </details>
    </article>
  );
}

function LowConfidenceBanner({
  reasons,
  proseFallback = false,
}: {
  reasons: string[];
  proseFallback?: boolean;
}) {
  return (
    <div className="flex items-start gap-3 border-b-2 border-conditional bg-paper-2 px-6 py-4">
      <AlertTriangle className="mt-0.5 size-5 shrink-0 text-conditional" aria-hidden />
      <div>
        <p className="font-sans text-sm font-semibold text-ink">Low-confidence verdict</p>
        <p className="mt-1 font-sans text-sm text-ink-muted">
          {proseFallback
            ? "Treat this synthesis as directional. "
            : "Treat next actions as directional, not precise. "}
          {reasons.join(" ")}
        </p>
      </div>
    </div>
  );
}
