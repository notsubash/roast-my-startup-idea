"use client";

import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import { AlertTriangle, CheckCircle2, XCircle } from "lucide-react";

import { EditorialContainer } from "@/components/app-shell";
import { resolveExportIdea } from "@/lib/format/run-idea";
import { ApiError } from "@/lib/api/client";
import { getRunStatus } from "@/lib/api/runs";
import { heatCtaClass } from "@/lib/cta-classes";
import { JUDGE_ORDER } from "@/lib/sse/types";
import { useRunStream } from "@/lib/sse/use-run-stream";
import type { RunState, RunStatus, Verdict } from "@/lib/sse/types";
import { cn } from "@/lib/utils";
import { Skeleton } from "@/ui/skeleton";

import { DebateTranscript } from "./debate-transcript";
import { AppealSection } from "../appeal/appeal-section";
import { RelatedRoasts } from "./related-roasts";
import { JudgeColumn, JudgeColumnSkeleton } from "./judge-column";
import { PhaseRail } from "./phase-rail";
import { RunControls } from "./run-controls";
import { RunMetricsBar } from "./run-metrics-bar";
import { ScoreLollipopStrip } from "./score-lollipop-strip";
import { SourcesPanel } from "./sources-panel";
import { ScoreRadar } from "./score-radar";
import { VerdictCard } from "./verdict-card";
import { VerdictTallyBar } from "./verdict-tally";

function isTerminalStatus(status: RunStatus): boolean {
  return status === "completed" || status === "failed" || status === "cancelled";
}

/** Prefer stream status; fall back to REST when SSE missed a terminal event. */
function effectiveStatus(streamStatus: RunStatus, restStatus: RunStatus): RunStatus {
  if (streamStatus === "connecting") return restStatus;
  if (isTerminalStatus(restStatus) && !isTerminalStatus(streamStatus)) return restStatus;
  return streamStatus;
}
function headlineForStatus(status: RunStatus, phase: RunState["phase"]): string {
  if (status === "completed") return "Verdict delivered";
  if (status === "failed") return "Run failed";
  if (status === "cancelled") return "Run cancelled";
  if (phase === "debate") return "The judges are debating";
  if (phase === "synthesis") return "The moderator is summing up";
  if (phase === "roast") return "The panel is roasting your idea";
  return "The judges are convening";
}

function TerminalBanner({ state }: { state: RunState }) {
  if (state.status === "completed") {
    return (
      <div className="flex items-start gap-3 border-2 border-pass bg-card p-4">
        <CheckCircle2 className="mt-0.5 size-5 shrink-0 text-pass" aria-hidden />
        <div>
          <p className="font-sans text-sm font-semibold text-ink">Run complete</p>
          <p className="mt-1 font-sans text-sm text-ink-muted">
            Five roasts, a full debate, and a final synthesis — saved at this URL.
          </p>
        </div>
      </div>
    );
  }

  if (state.status === "failed") {
    return (
      <div className="flex items-start gap-3 border-2 border-fail bg-card p-4">
        <AlertTriangle className="mt-0.5 size-5 shrink-0 text-fail" aria-hidden />
        <div>
          <p className="font-sans text-sm font-semibold text-ink">Run failed</p>
          <p className="mt-1 font-sans text-sm text-ink-muted">
            {state.error?.message ?? "Something went wrong during the run."}
          </p>
          {state.error?.recoverable && (
            <Link href="/" className={`mt-4 inline-flex ${heatCtaClass}`}>
              Try again
            </Link>
          )}
        </div>
      </div>
    );
  }

  if (state.status === "cancelled") {
    return (
      <div className="flex items-start gap-3 border-2 border-conditional bg-card p-4">
        <XCircle className="mt-0.5 size-5 shrink-0 text-conditional" aria-hidden />
        <div>
          <p className="font-sans text-sm font-semibold text-ink">Run cancelled</p>
          <p className="mt-1 font-sans text-sm text-ink-muted">
            {state.cancelMessage ?? "You stopped this roast before it finished."}
          </p>
        </div>
      </div>
    );
  }

  return null;
}

function RunSheetContent({
  runId,
  ideaPreview,
  idea,
  restStatus,
  refetchStatus,
}: {
  runId: string;
  ideaPreview: string;
  idea: string;
  restStatus: RunStatus;
  refetchStatus: () => void;
}) {
  const stream = useRunStream(runId, {
    initialStatus:
      restStatus === "completed" ||
      restStatus === "failed" ||
      restStatus === "cancelled"
        ? restStatus
        : "connecting",
  });

  const streamStatus =
    stream.status === "connecting" ? restStatus : stream.status;
  const status = effectiveStatus(streamStatus, restStatus);
  const hasAnyVerdict = JUDGE_ORDER.some((id) => stream.judges[id].status === "revealed");
  const awaitingReplay =
    restStatus === "completed" && !hasAnyVerdict && !stream.roastPanelComplete;
  const initialLoad = !stream.connected && !isTerminalStatus(restStatus);
  const showJudgeSkeletons = awaitingReplay || initialLoad;
  const revealedVerdicts = JUDGE_ORDER.map((id) => stream.judges[id].verdict).filter(
    (verdict): verdict is Verdict => verdict !== undefined,
  );
  const hasRevote = Object.keys(stream.revoteBaseline).length > 0;
  const showDecisionCard = Boolean(stream.synthesis || stream.structuredSynthesis);

  return (
    <>
      <header className="col-span-12 lg:col-span-10 lg:col-start-2">
        <div className="lg:grid lg:grid-cols-10 lg:gap-8">
          <div className="lg:col-span-7">
            <p className="font-sans text-sm font-semibold uppercase tracking-widest text-heat-ink">
              Verdict sheet
            </p>
            <h1 className="mt-2 font-serif text-title font-semibold text-ink md:text-display-md">
              {headlineForStatus(status, stream.phase)}
            </h1>
            <p className="mt-4 max-w-prose font-sans text-ink-muted">
              <span className="font-semibold text-ink">Idea:</span> {ideaPreview}
            </p>
            <p className="mt-2 font-mono text-xs text-ink-subtle">Run {runId}</p>
            <div className="mt-6">
              <RunControls
                runId={runId}
                status={status}
                onCancelSettled={refetchStatus}
                exportInput={{
                  idea: resolveExportIdea(runId, ideaPreview, idea),
                  runId,
                  judges: stream.judges,
                  debateTurns: stream.debateTurns,
                  synthesis: stream.synthesis,
                  metrics: stream.metrics,
                }}
              />
            </div>
          </div>
          <div className="mt-8 lg:col-span-3 lg:mt-0">
            <RelatedRoasts runId={runId} />
          </div>
        </div>
      </header>

      <div
        className="col-span-12 mt-10 lg:col-span-10 lg:col-start-2"
        aria-live="polite"
        aria-busy={status === "running" || status === "created"}
      >
        <TerminalBanner state={{ ...stream, status }} />

        <div className="mt-8">
          <PhaseRail phase={stream.phase} />
        </div>

        {showDecisionCard && (
          <section className="mt-10" aria-labelledby="decision-heading">
            <h2 id="decision-heading" className="font-serif text-2xl font-semibold text-ink">
              Decision
            </h2>
            <div className="mt-6">
              <VerdictCard
                synthesisProse={stream.synthesis}
                structuredSynthesis={stream.structuredSynthesis}
                verdicts={revealedVerdicts}
              />
            </div>
          </section>
        )}

        {stream.researchFindings && (
          <div className="mt-8">
            <SourcesPanel research={stream.researchFindings} />
          </div>
        )}

        <section className="mt-10" aria-labelledby="roast-panel-heading">
          <h2
            id="roast-panel-heading"
            className="font-serif text-2xl font-semibold text-ink"
          >
            The roast panel
          </h2>
          <div className="mt-6 grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
            {showJudgeSkeletons
              ? JUDGE_ORDER.map((id) => <JudgeColumnSkeleton key={id} />)
              : JUDGE_ORDER.map((id) => {
                  const baseline = stream.revoteBaseline[id];
                  const current = stream.judges[id].verdict;
                  const scoreDelta =
                    baseline && current ? current.score - baseline.score : undefined;
                  return (
                    <JudgeColumn
                      key={id}
                      judgeId={id}
                      view={stream.judges[id]}
                      animateStamp={stream.judges[id].status === "revealed"}
                      scoreDelta={scoreDelta}
                      scoreChangeReason={stream.revoteChangeReasons[id]}
                    />
                  );
                })}
          </div>
          {hasRevote && (
            <p className="mt-4 max-w-prose font-sans text-sm text-ink-muted">
              Delta badges compare each judge&apos;s current score to their initial roast verdict
              after the post-debate re-vote.
            </p>
          )}
        </section>

        <section className="mt-12 border-t-2 border-rule-soft pt-10" aria-labelledby="scores-heading">
          <h2 id="scores-heading" className="font-serif text-2xl font-semibold text-ink">
            Score panel
          </h2>
          <p className="mt-2 max-w-prose font-sans text-sm text-ink-muted">
            The split, the report card, and the radar — three views of the same verdict.
          </p>

          <div className="mt-6 space-y-8">
            <div aria-labelledby="verdict-split-heading">
              <h3
                id="verdict-split-heading"
                className="font-sans text-xs font-semibold uppercase tracking-widest text-ink-muted"
              >
                The split
              </h3>
              <div className="mt-3">
                <VerdictTallyBar judges={stream.judges} />
              </div>
            </div>

            <div aria-labelledby="report-card-heading">
              <h3
                id="report-card-heading"
                className="font-sans text-xs font-semibold uppercase tracking-widest text-ink-muted"
              >
                Report card
              </h3>
              <div className="mt-3">
                <ScoreLollipopStrip judges={stream.judges} />
              </div>
            </div>

            <div aria-labelledby="radar-heading">
              <h3
                id="radar-heading"
                className="font-sans text-xs font-semibold uppercase tracking-widest text-ink-muted"
              >
                Radar
              </h3>
              <div className="mt-3">
                <ScoreRadar judges={stream.judges} />
              </div>
            </div>
          </div>
        </section>

        <section className="mt-12 border-t-2 border-rule-soft pt-10" aria-labelledby="debate-heading">
          <h2 id="debate-heading" className="font-serif text-2xl font-semibold text-ink">
            Debate transcript
          </h2>
          <div className="mt-6">
            <DebateTranscript turns={stream.debateTurns} currentRound={stream.currentRound} />
          </div>
        </section>

        <RunMetricsBar metrics={stream.metrics} status={status} className="col-span-12 mt-12" />

        <AppealSection
          runId={runId}
          completed={status === "completed"}
          streamAppeal={stream.appeal}
        />
      </div>
    </>
  );
}

export function RunSheet({ runId }: { runId: string }) {
  const statusQuery = useQuery({
    queryKey: ["run", runId, "status"],
    queryFn: () => getRunStatus(runId),
    retry: (count, error) => {
      if (error instanceof ApiError && error.status === 404) return false;
      return count < 1;
    },
  });

  if (statusQuery.isLoading) {
    return (
      <EditorialContainer className="py-12 md:py-16 lg:py-24">
        <div className="col-span-12 lg:col-span-10 lg:col-start-2 space-y-4">
          <Skeleton className="h-8 w-64" />
          <Skeleton className="h-12 w-full max-w-xl" />
          <Skeleton className="h-24 w-full" />
        </div>
      </EditorialContainer>
    );
  }

  if (statusQuery.isError) {
    const notFound =
      statusQuery.error instanceof ApiError && statusQuery.error.status === 404;
    return (
      <EditorialContainer className="py-12 md:py-16 lg:py-24">
        <div className="col-span-12 lg:col-span-8 lg:col-start-3 text-center">
          <h1 className="font-serif text-title font-semibold text-ink">
            {notFound ? "Run not found" : "Could not load run"}
          </h1>
          <p className="mt-4 font-sans text-ink-muted">
            {notFound
              ? "This verdict sheet does not exist or the link is wrong."
              : "Check your connection and try refreshing."}
          </p>
          <Link href="/" className={cn("mt-8 inline-flex", heatCtaClass)}>
            Roast an idea
          </Link>
        </div>
      </EditorialContainer>
    );
  }

  if (!statusQuery.data) {
    return null;
  }

  const { idea_preview: ideaPreview, idea, status: restStatus } = statusQuery.data;

  return (
    <EditorialContainer className="py-12 md:py-16 lg:py-24">
      <RunSheetContent
        key={runId}
        runId={runId}
        ideaPreview={ideaPreview}
        idea={idea}
        restStatus={restStatus}
        refetchStatus={() => void statusQuery.refetch()}
      />
    </EditorialContainer>
  );
}
