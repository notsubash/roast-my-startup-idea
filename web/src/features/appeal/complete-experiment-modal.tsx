"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import { useMutation } from "@tanstack/react-query";
import { Loader2, Paperclip } from "lucide-react";
import { useMemo } from "react";
import { useForm } from "react-hook-form";
import { toast } from "sonner";
import { z } from "zod";

import { ApiError } from "@/lib/api/client";
import { submitAppeal } from "@/lib/api/runs";
import type { AppealResponse } from "@/lib/api/types-helpers";
import { parseApiDetail, APPEAL_MAX_LENGTH, APPEAL_MIN_LENGTH } from "@/lib/api/types-helpers";
import { appealCoachingHint } from "@/lib/appeal/coaching";
import { JUDGE_META } from "@/lib/sse/judges";
import type { JudgeId, Verdict } from "@/lib/sse/types";
import { Button } from "@/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/ui/dialog";
import { Label } from "@/ui/label";
import { Textarea } from "@/ui/textarea";

import { EVIDENCE_COPY } from "../run/run-page-copy";

const APPEAL_MIN = APPEAL_MIN_LENGTH;
const APPEAL_MAX = APPEAL_MAX_LENGTH;

const experimentSchema = z.object({
  appeal_text: z
    .string()
    .trim()
    .min(APPEAL_MIN, EVIDENCE_COPY.minLengthError(APPEAL_MIN))
    .max(APPEAL_MAX, EVIDENCE_COPY.maxLengthError(APPEAL_MAX)),
});

type ExperimentFormValues = z.infer<typeof experimentSchema>;

export function CompleteExperimentModal({
  runId,
  open,
  onOpenChange,
  targetJudges,
  baselineVerdicts,
  experiment,
  onSuccess,
}: {
  runId: string;
  open: boolean;
  onOpenChange: (open: boolean) => void;
  targetJudges: JudgeId[];
  baselineVerdicts: Verdict[];
  experiment: string;
  onSuccess: (result: AppealResponse) => void;
}) {
  const {
    register,
    handleSubmit,
    watch,
    reset,
    formState: { errors, isSubmitting },
  } = useForm<ExperimentFormValues>({
    resolver: zodResolver(experimentSchema),
    defaultValues: { appeal_text: "" },
    mode: "onBlur",
  });

  const length = watch("appeal_text").trim().length;
  const verdictByJudge = useMemo(
    () => new Map(baselineVerdicts.map((verdict) => [verdict.judge, verdict])),
    [baselineVerdicts],
  );

  const mutation = useMutation({
    mutationFn: (values: ExperimentFormValues) =>
      submitAppeal(runId, {
        appeal_text: values.appeal_text,
        target_judges: targetJudges.length > 0 ? targetJudges : undefined,
      }),
    onSuccess: (result) => {
      reset();
      onOpenChange(false);
      onSuccess(result);
    },
    onError: (error: Error) => {
      if (error instanceof ApiError) {
        const detail = parseApiDetail(error.body);
        toast.error(EVIDENCE_COPY.submitFailed, {
          description: detail ?? EVIDENCE_COPY.submitFailedDetail,
        });
        return;
      }
      toast.error(EVIDENCE_COPY.submitFailed, {
        description: "Check your connection and try again.",
      });
    },
  });

  const busy = isSubmitting || mutation.isPending;

  function handleOpenChange(next: boolean) {
    if (busy) return;
    if (!next) reset();
    onOpenChange(next);
  }

  return (
    <Dialog open={open} onOpenChange={handleOpenChange}>
      <DialogContent aria-describedby="complete-experiment-description">
        <DialogHeader>
          <DialogTitle>{EVIDENCE_COPY.modalTitle}</DialogTitle>
          <DialogDescription id="complete-experiment-description">
            {EVIDENCE_COPY.modalLead}
          </DialogDescription>
        </DialogHeader>

        <p className="rounded-md border border-rule-soft bg-paper-2 px-4 py-3 font-sans text-sm text-ink-muted">
          <span className="font-semibold text-ink">{EVIDENCE_COPY.experimentFocus}</span>{" "}
          {experiment}
        </p>

        {targetJudges.length > 0 && (
          <div>
            <p className="font-sans text-xs font-semibold uppercase tracking-widest text-ink-muted">
              {EVIDENCE_COPY.autoTargetJudges}
            </p>
            <ul className="mt-2 space-y-3" aria-label="Judges auto-selected for this evidence">
              {targetJudges.map((judgeId) => {
                const verdict = verdictByJudge.get(judgeId);
                const hint = verdict ? appealCoachingHint(verdict) : null;
                return (
                  <li
                    key={judgeId}
                    className="border border-rule-soft bg-paper-2 px-4 py-3"
                  >
                    <p className="font-sans text-sm font-semibold text-ink">
                      {JUDGE_META[judgeId].name}
                    </p>
                    {hint && (
                      <p className="mt-1 font-sans text-sm text-ink-muted">
                        <span className="font-semibold text-ink">{EVIDENCE_COPY.evidenceAsk}</span>{" "}
                        {hint}
                      </p>
                    )}
                  </li>
                );
              })}
            </ul>
          </div>
        )}

        <form
          className="space-y-4"
          onSubmit={handleSubmit((values) => mutation.mutate(values))}
          aria-busy={busy}
        >
          <div className="space-y-2">
            <Label htmlFor="experiment-evidence-text" className="font-sans text-sm font-semibold text-ink">
              {EVIDENCE_COPY.evidenceLabel}
            </Label>
            <Textarea
              id="experiment-evidence-text"
              rows={5}
              placeholder={EVIDENCE_COPY.evidencePlaceholder}
              aria-invalid={Boolean(errors.appeal_text)}
              aria-describedby={
                errors.appeal_text ? "experiment-evidence-text-error" : "experiment-evidence-text-count"
              }
              disabled={busy}
              {...register("appeal_text")}
            />
            <div className="flex items-start justify-between gap-4">
              {errors.appeal_text ? (
                <p id="experiment-evidence-text-error" className="font-sans text-sm text-fail" role="alert">
                  {errors.appeal_text.message}
                </p>
              ) : (
                <span className="sr-only" id="experiment-evidence-text-count">
                  {length} of {APPEAL_MAX} characters
                </span>
              )}
              <p className="ml-auto shrink-0 font-mono text-xs text-ink-subtle" aria-hidden>
                {length}/{APPEAL_MAX}
              </p>
            </div>
          </div>

          <div className="space-y-2">
            <Label className="font-sans text-sm font-semibold text-ink">
              {EVIDENCE_COPY.attachmentsLabel}
            </Label>
            <div
              className="flex items-center gap-3 border border-dashed border-rule-soft bg-paper-2 px-4 py-6 font-sans text-sm text-ink-muted"
              aria-disabled="true"
            >
              <Paperclip className="size-4 shrink-0" aria-hidden />
              {EVIDENCE_COPY.attachmentsPlaceholder}
            </div>
          </div>

          <DialogFooter>
            <Button type="button" variant="outline" disabled={busy} onClick={() => handleOpenChange(false)}>
              Cancel
            </Button>
            <Button type="submit" disabled={busy}>
              {busy && <Loader2 className="size-4 animate-spin" aria-hidden />}
              {EVIDENCE_COPY.modalSubmit}
            </Button>
          </DialogFooter>
          {busy && (
            <p className="sr-only" aria-live="polite">
              {EVIDENCE_COPY.submitting}
            </p>
          )}
        </form>
      </DialogContent>
    </Dialog>
  );
}
