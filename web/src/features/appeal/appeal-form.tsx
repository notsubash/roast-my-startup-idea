"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import { useMutation } from "@tanstack/react-query";
import { Loader2 } from "lucide-react";
import { useForm } from "react-hook-form";
import { toast } from "sonner";
import { z } from "zod";

import { ApiError } from "@/lib/api/client";
import { submitAppeal } from "@/lib/api/runs";
import type { AppealResponse } from "@/lib/api/types-helpers";
import { parseApiDetail, APPEAL_MAX_LENGTH, APPEAL_MIN_LENGTH } from "@/lib/api/types-helpers";
import { Button } from "@/ui/button";
import { Label } from "@/ui/label";
import { Textarea } from "@/ui/textarea";

const APPEAL_MIN = APPEAL_MIN_LENGTH;
const APPEAL_MAX = APPEAL_MAX_LENGTH;

const appealSchema = z.object({
  appeal_text: z
    .string()
    .trim()
    .min(APPEAL_MIN, `Rebuttal must be at least ${APPEAL_MIN} characters.`)
    .max(APPEAL_MAX, `Rebuttal must be at most ${APPEAL_MAX} characters.`),
});

type AppealFormValues = z.infer<typeof appealSchema>;

export function AppealForm({
  runId,
  disabled,
  onSuccess,
}: {
  runId: string;
  disabled?: boolean;
  onSuccess: (result: AppealResponse) => void;
}) {
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
    mutationFn: (values: AppealFormValues) => submitAppeal(runId, values),
    onSuccess,
    onError: (error: Error) => {
      if (error instanceof ApiError) {
        const detail = parseApiDetail(error.body);
        toast.error("Appeal failed", { description: detail ?? "Could not submit appeal." });
        return;
      }
      toast.error("Appeal failed", { description: "Check your connection and try again." });
    },
  });

  return (
    <form
      className="border-2 border-ink bg-card p-6 shadow-hard"
      onSubmit={handleSubmit((values) => mutation.mutate(values))}
      aria-labelledby="appeal-form-heading"
      aria-busy={mutation.isPending || isSubmitting}
    >
      <h2 id="appeal-form-heading" className="font-serif text-2xl font-semibold text-ink">
        Appeal the verdict
      </h2>
      <p className="mt-2 max-w-prose font-sans text-sm text-ink-muted">
        Push back with new evidence or context. Each judge will revise their score and the
        moderator will issue an updated synthesis.
      </p>

      <div className="mt-6 space-y-2">
        <Label htmlFor="appeal_text" className="font-sans text-sm font-semibold text-ink">
          Your rebuttal
        </Label>
        <Textarea
          id="appeal_text"
          rows={5}
          placeholder="We completed two validation studies, signed LOIs with pilot customers, and filed a provisional patent…"
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
        Submit appeal
      </Button>
      {(mutation.isPending || isSubmitting) && (
        <p className="sr-only" aria-live="polite">
          Submitting appeal — the panel is revising their verdicts.
        </p>
      )}
    </form>
  );
}
