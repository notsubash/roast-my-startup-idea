"use client";

import Link from "next/link";
import { Fragment, useCallback, useEffect, useMemo, useState, type ReactNode } from "react";
import { useQuery } from "@tanstack/react-query";
import { useSearchParams } from "next/navigation";
import { AlertTriangle, CheckCircle2, ChevronDown, XCircle } from "lucide-react";

import { EditorialContainer } from "@/components/app-shell";
import { resolveExportIdea } from "@/lib/format/run-idea";
import { appealBaselineVerdicts, findDuplicateEvidenceJudges } from "@/lib/appeal/coaching";
import { ApiError } from "@/lib/api/client";
import { getRunStatus } from "@/lib/api/runs";
import { heatCtaClass } from "@/lib/cta-classes";
import { JUDGE_ORDER } from "@/lib/sse/types";
import { useRunStream } from "@/lib/sse/use-run-stream";
import type { LensUniquenessAssessment } from "@/lib/lens/lens-quality";
import type { RunState, RunStatus, Verdict, AppealResult } from "@/lib/sse/types";
import { cn } from "@/lib/utils";
import { Skeleton } from "@/ui/skeleton";

import { DebateTranscript } from "./debate-transcript";
import { AppealSection } from "../appeal/appeal-section";
import { VersionBadge, VersionComparison } from "../iteration/version-comparison";
import { JudgeColumn, JudgeColumnSkeleton } from "./judge-column";
import { PhaseRail } from "./phase-rail";
import { RunControls } from "./run-controls";
import { collapsibleSummaryClass, RunContextGroup } from "./run-context-group";
import { NextActionsStrip } from "./next-actions-strip";
import { PanelQualityDebugBadge } from "./panel-quality-debug";
import { RUN_PAGE_COPY } from "./run-page-copy";
import { deriveWorkflowBrief } from "./structured-synthesis";
import { VerdictCard } from "./verdict-card";
import { WorkflowBrief } from "./workflow-brief";
import { RUN_FOLD_ORDERS, type RunFoldSection } from "./run-fold-layout";
import { useRunFoldVariant } from "./use-run-fold-variant";
import { assessRevoteOutputQuality, type RevoteOutputQuality } from "./verdict-quality";

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
  if (status === "completed") return RUN_PAGE_COPY.reviewComplete;
  if (status === "failed") return "Run failed";
  if (status === "cancelled") return "Run cancelled";
  if (phase === "debate") return "The judges are debating";
  if (phase === "synthesis") return "The moderator is summing up";
  if (phase === "roast") return RUN_PAGE_COPY.phaseReviewing;
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
            Five judges, a full debate, and a final synthesis — saved at this URL.
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
            {state.cancelMessage ?? RUN_PAGE_COPY.reviewCancelled}
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
  version,
  parentRunId,
  initialFold,
}: {
  runId: string;
  ideaPreview: string;
  idea: string;
  restStatus: RunStatus;
  refetchStatus: () => void;
  version: number;
  parentRunId?: string | null;
  initialFold?: string | null;
}) {
  const { variant } = useRunFoldVariant(initialFold);
  const searchParams = useSearchParams();
  const showQualityDebug = searchParams.get("debug") === "1";
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
  const revoteQuality = hasRevote
    ? assessRevoteOutputQuality(
        stream.revoteBaseline,
        revealedVerdicts,
      )
    : null;
  const showDecisionCard = Boolean(stream.synthesis || stream.structuredSynthesis);
  const liveDebate = status === "running" && stream.phase === "debate";
  const [appealResult, setAppealResult] = useState<AppealResult | null>(stream.appeal);
  const onAppealChange = useCallback((result: AppealResult) => {
    setAppealResult(result);
  }, []);

  useEffect(() => {
    if (stream.appeal) setAppealResult(stream.appeal);
  }, [stream.appeal]);

  const appealBaseline = useMemo(
    () => appealBaselineVerdicts(revealedVerdicts),
    [revealedVerdicts],
  );
  const duplicateEvidenceJudges = useMemo(
    () => findDuplicateEvidenceJudges(revealedVerdicts),
    [revealedVerdicts],
  );
  const workflowBrief = useMemo(
    () =>
      deriveWorkflowBrief(
        stream.synthesis,
        stream.structuredSynthesis,
        revealedVerdicts,
      ),
    [stream.synthesis, stream.structuredSynthesis, revealedVerdicts],
  );

  const evidenceLink = useMemo(() => {
    if (status !== "completed") return null;
    if (appealResult) {
      return { href: "#appeal-result-heading", label: RUN_PAGE_COPY.viewEvidenceResult };
    }
    if (appealBaseline.length > 0) {
      return { href: "#appeal-form-heading", label: RUN_PAGE_COPY.presentEvidence };
    }
    return null;
  }, [status, appealResult, appealBaseline.length]);

  const collapseJudgeDetail = status === "completed" && !showJudgeSkeletons;

  const judgeGrid = (
    <div className="mt-6 grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
      {showJudgeSkeletons
        ? JUDGE_ORDER.map((id) => <JudgeColumnSkeleton key={id} judgeId={id} />)
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
                evidenceAskCollides={duplicateEvidenceJudges.has(id)}
              />
            );
          })}
    </div>
  );

  const foldSections: Record<RunFoldSection, ReactNode> = {
    decision: showDecisionCard ? (
      <section className="mt-10" aria-labelledby="decision-heading">
        <h2 id="decision-heading" className="font-serif text-2xl font-semibold text-ink">
          {RUN_PAGE_COPY.overallDecision}
        </h2>
        <div className="mt-6">
          <VerdictCard
            synthesisProse={stream.synthesis}
            structuredSynthesis={stream.structuredSynthesis}
            verdicts={revealedVerdicts}
          />
          <WorkflowBrief
            synthesisProse={stream.synthesis}
            structuredSynthesis={stream.structuredSynthesis}
            verdicts={revealedVerdicts}
            completed={status === "completed"}
            evidenceLink={evidenceLink}
          />
          <NextActionsStrip
            runId={runId}
            experiment={workflowBrief.experiment}
            completed={status === "completed"}
          />
        </div>
      </section>
    ) : null,
    judges: collapseJudgeDetail ? (
      <details
        className="group mt-10 border-t-2 border-rule-soft pt-10"
        aria-labelledby="judge-panel-heading"
      >
        <summary className={collapsibleSummaryClass}>
          <ChevronDown
            className="size-5 shrink-0 transition-transform group-open:rotate-180"
            aria-hidden
          />
          <span id="judge-panel-heading">{RUN_PAGE_COPY.judgePanel}</span>
        </summary>
        <div className="mt-6">
          {judgeGrid}
          <JudgePanelFootnotes
            hasRevote={hasRevote}
            revoteQuality={revoteQuality}
            showQualityDebug={showQualityDebug && status === "completed"}
            panelQuality={stream.panelQuality}
            verdicts={revealedVerdicts}
          />
        </div>
      </details>
    ) : (
      <section className="mt-10" aria-labelledby="judge-panel-heading">
        <h2
          id="judge-panel-heading"
          className="font-serif text-2xl font-semibold text-ink"
        >
          {RUN_PAGE_COPY.judgePanel}
        </h2>
        {judgeGrid}
        <JudgePanelFootnotes
          hasRevote={hasRevote}
          revoteQuality={revoteQuality}
          showQualityDebug={showQualityDebug && status === "completed"}
          panelQuality={stream.panelQuality}
          verdicts={revealedVerdicts}
        />
      </section>
    ),
    version: (
      <VersionComparison
        version={version}
        parentRunId={parentRunId}
        currentVerdicts={revealedVerdicts}
        completed={status === "completed"}
      />
    ),
    appeal: (
      <AppealSection
        runId={runId}
        completed={status === "completed"}
        baselineVerdicts={revealedVerdicts}
        streamAppeal={stream.appeal}
        onAppealChange={onAppealChange}
      />
    ),
    transcript: (
      <details
        className="group mt-12 border-t-2 border-rule-soft pt-10"
        aria-labelledby="debate-transcript-heading"
        {...(liveDebate ? { open: true } : {})}
      >
        <summary className={collapsibleSummaryClass}>
          <ChevronDown
            className="size-5 shrink-0 transition-transform group-open:rotate-180"
            aria-hidden
          />
          <span id="debate-transcript-heading">{RUN_PAGE_COPY.debateTranscript}</span>
          {liveDebate && (
            <span className="font-sans text-sm font-normal text-heat-ink">(live)</span>
          )}
        </summary>
        <div className="mt-6">
          <DebateTranscript turns={stream.debateTurns} currentRound={stream.currentRound} />
        </div>
      </details>
    ),
    context: (
      <RunContextGroup
        runId={runId}
        researchFindings={stream.researchFindings}
        metrics={stream.metrics}
        status={status}
      />
    ),
  };

  return (
    <>
      <header className="col-span-12 lg:col-span-10 lg:col-start-2">
        <p className="font-sans text-sm font-semibold uppercase tracking-widest text-heat-ink">
          {RUN_PAGE_COPY.reviewEyebrow}
        </p>
        <h1 className="mt-2 font-serif text-title font-semibold text-ink md:text-display-md">
          {headlineForStatus(status, stream.phase)}
        </h1>
        <p className="mt-4 max-w-prose font-sans text-ink-muted">
          <span className="font-semibold text-ink">Idea:</span> {ideaPreview}
        </p>
        <p className="mt-2 font-mono text-xs text-ink-subtle">
          Run {runId}
          <VersionBadge version={version} parentRunId={parentRunId} className="ml-2" />
        </p>
        <div className="mt-6 flex flex-wrap gap-3">
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

        {RUN_FOLD_ORDERS[variant].map((section) => {
          const node = foldSections[section];
          if (!node) return null;
          return <Fragment key={section}>{node}</Fragment>;
        })}
      </div>
    </>
  );
}

function JudgePanelFootnotes({
  hasRevote,
  revoteQuality,
  showQualityDebug,
  panelQuality,
  verdicts,
}: {
  hasRevote: boolean;
  revoteQuality: RevoteOutputQuality | null;
  showQualityDebug: boolean;
  panelQuality: LensUniquenessAssessment | null;
  verdicts: Verdict[];
}) {
  return (
    <>
      {hasRevote && (
        <p className="mt-4 max-w-prose font-sans text-sm text-ink-muted">
          Delta badges compare each judge&apos;s current score to their initial verdict after the
          post-debate re-vote.
        </p>
      )}
      {revoteQuality?.convergenceNote && !revoteQuality.lowConfidence && (
        <p className="mt-3 max-w-prose rounded-md border border-rule-soft bg-paper-2 px-4 py-3 font-sans text-sm text-ink-muted">
          {revoteQuality.convergenceNote}
        </p>
      )}
      {revoteQuality?.lowConfidence && (
        <p className="mt-3 max-w-prose rounded-md border border-amber-200 bg-amber-50 px-4 py-3 font-sans text-sm text-amber-950">
          {revoteQuality.reasons.join(" ")}
        </p>
      )}
      {!revoteQuality?.scoresMoved && hasRevote && (
        <p className="mt-3 max-w-prose font-sans text-sm text-ink-muted">
          No judge changed their score after the debate.
        </p>
      )}
      {showQualityDebug && (
        <PanelQualityDebugBadge panelQuality={panelQuality} verdicts={verdicts} />
      )}
    </>
  );
}

export function RunSheet({
  runId,
  initialFold,
}: {
  runId: string;
  initialFold?: string | null;
}) {
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
            {notFound ? RUN_PAGE_COPY.reviewNotFound : "Check your connection and try refreshing."}
          </p>
          <Link href="/" className={cn("mt-8 inline-flex", heatCtaClass)}>
            {RUN_PAGE_COPY.submitIdea}
          </Link>
        </div>
      </EditorialContainer>
    );
  }

  if (!statusQuery.data) {
    return null;
  }

  const { idea_preview: ideaPreview, idea, status: restStatus, version = 1, parent_run_id: parentRunId } =
    statusQuery.data;

  return (
    <EditorialContainer className="py-12 md:py-16 lg:py-24">
      <RunSheetContent
        key={runId}
        runId={runId}
        ideaPreview={ideaPreview}
        idea={idea}
        restStatus={restStatus}
        refetchStatus={() => void statusQuery.refetch()}
        version={version}
        parentRunId={parentRunId}
        initialFold={initialFold}
      />
    </EditorialContainer>
  );
}
