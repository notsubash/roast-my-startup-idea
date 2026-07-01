"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import { useMutation } from "@tanstack/react-query";
import { Loader2 } from "lucide-react";
import { useState } from "react";
import { useForm } from "react-hook-form";
import { toast } from "sonner";
import { z } from "zod";

import { ApiError } from "@/lib/api/client";
import { submitAppeal } from "@/lib/api/runs";
import type { AppealResponse } from "@/lib/api/types-helpers";
import { parseApiDetail, APPEAL_MAX_LENGTH, APPEAL_MIN_LENGTH } from "@/lib/api/types-helpers";
import type { JudgeId, Verdict } from "@/lib/sse/types";
import { Button } from "@/ui/button";
import { Label } from "@/ui/label";
import { Textarea } from "@/ui/textarea";

import { AppealCoaching } from "./appeal-coaching";
import { EVIDENCE_COPY } from "../run/run-page-copy";

const APPEAL_MIN = APPEAL_MIN_LENGTH;
const APPEAL_MAX = APPEAL_MAX_LENGTH;

const appealSchema = z.object({
  appeal_text: z
    .string()
    .trim()
    .min(APPEAL_MIN, EVIDENCE_COPY.minLengthError(APPEAL_MIN))
    .max(APPEAL_MAX, EVIDENCE_COPY.maxLengthError(APPEAL_MAX)),
});

type AppealFormValues = z.infer<typeof appealSchema>;

export function AppealForm({
  runId,
  baselineVerdicts,
  disabled,
  onSuccess,
}: {
  runId: string;
  baselineVerdicts: Verdict[];
  disabled?: boolean;
  onSuccess: (result: AppealResponse) => void;
}) {
  const [targetJudges, setTargetJudges] = useState<JudgeId[]>([]);
  const {
    register,
    handleSubmit,
    watch,
    formState: { errors, isSubmitting },
  } = useForm<AppealFormValues>({
    resolver: zodResolver(appealSchema),
    defaultValues: { appeal_text: "" },
    mode: "onBlur",
  });

  const length = watch("appeal_text").trim().length;

  const mutation = useMutation({
    mutationFn: (values: AppealFormValues) =>
      submitAppeal(runId, {
        appeal_text: values.appeal_text,
        target_judges: targetJudges.length > 0 ? targetJudges : undefined,
      }),
    onSuccess,
    onError: (error: Error) => {
      if (error instanceof ApiError) {
        const detail = parseApiDetail(error.body);
        toast.error(EVIDENCE_COPY.submitFailed, {
          description: detail ?? EVIDENCE_COPY.submitFailedDetail,
        });
        return;
      }
      toast.error(EVIDENCE_COPY.submitFailed, { description: "Check your connection and try again." });
    },
  });

  return (
    <form
      className="border-2 border-ink bg-card p-6 shadow-hard"
      onSubmit={handleSubmit((values) => mutation.mutate(values))}
      aria-labelledby="appeal-form-heading"
      aria-busy={mutation.isPending || isSubmitting}
    >
      <h2 id="appeal-form-heading" className="scroll-mt-28 font-serif text-2xl font-semibold text-ink">
        {EVIDENCE_COPY.formTitle}
      </h2>
      <p className="mt-2 max-w-prose font-sans text-sm text-ink-muted">
        {EVIDENCE_COPY.formLead}
      </p>

      <AppealCoaching
        baselineVerdicts={baselineVerdicts}
        targetJudges={targetJudges}
        onTargetChange={setTargetJudges}
        disabled={disabled || isSubmitting || mutation.isPending}
      />

      <div className="mt-6 space-y-2">
        <Label htmlFor="appeal_text" className="font-sans text-sm font-semibold text-ink">
          {EVIDENCE_COPY.evidenceLabel}
        </Label>
        <Textarea
          id="appeal_text"
          rows={5}
          placeholder={EVIDENCE_COPY.evidencePlaceholder}
          aria-invalid={Boolean(errors.appeal_text)}
          aria-describedby={errors.appeal_text ? "appeal_text-error" : "appeal_text-count"}
          disabled={disabled || isSubmitting || mutation.isPending}
          {...register("appeal_text")}
        />
        <div className="flex items-start justify-between gap-4">
          {errors.appeal_text ? (
            <p id="appeal_text-error" className="font-sans text-sm text-fail" role="alert">
              {errors.appeal_text.message}
            </p>
          ) : (
            <span className="sr-only" id="appeal_text-count">
              {length} of {APPEAL_MAX} characters
            </span>
          )}
          <p className="ml-auto shrink-0 font-mono text-xs text-ink-subtle" aria-hidden>
            {length}/{APPEAL_MAX}
          </p>
        </div>
      </div>

      <Button
        type="submit"
        className="mt-6"
        disabled={disabled || isSubmitting || mutation.isPending}
      >
        {(isSubmitting || mutation.isPending) && (
          <Loader2 className="size-4 animate-spin" aria-hidden />
        )}
        {EVIDENCE_COPY.submit}
      </Button>
      {(mutation.isPending || isSubmitting) && (
        <p className="sr-only" aria-live="polite">
          {EVIDENCE_COPY.submitting}
        </p>
      )}
    </form>
  );
}
