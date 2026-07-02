"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { zodResolver } from "@hookform/resolvers/zod";
import { ChevronDown, ChevronUp, Loader2 } from "lucide-react";
import { useForm } from "react-hook-form";
import { toast } from "sonner";

import { stashRunIdea } from "@/lib/format/run-idea";
import { ApiError } from "@/lib/api/client";
import { createRun, getRunStatus } from "@/lib/api/runs";
import { parseApiDetail, RATE_LIMIT_MESSAGE } from "@/lib/api/types-helpers";
import { loadAdvancedSettings } from "@/lib/settings/advanced-settings";
import { cn } from "@/lib/utils";
import { Button } from "@/ui/button";
import { Input } from "@/ui/input";
import { Label } from "@/ui/label";
import { Textarea } from "@/ui/textarea";

import {
  IDEA_MAX_LENGTH,
  ideaFormDefaults,
  ideaFormSchema,
  type IdeaFormValues,
} from "./idea-form-schema";
import { toCreateRunRequest } from "./to-create-run-request";

function FieldError({ id, message }: { id?: string; message?: string }) {
  if (!message) return null;
  return (
    <p id={id} className="font-sans text-sm text-fail" role="alert">
      {message}
    </p>
  );
}

export function IdeaForm({ refineRunId }: { refineRunId?: string | null }) {
  const router = useRouter();
  const queryClient = useQueryClient();
  const [contextOpen, setContextOpen] = useState(false);
  const [refineDismissed, setRefineDismissed] = useState(false);

  const refineQuery = useQuery({
    queryKey: ["run", refineRunId, "refine"],
    queryFn: () => getRunStatus(refineRunId!),
    enabled: Boolean(refineRunId) && !refineDismissed,
    retry: 1,
  });

  const refineActive = Boolean(refineRunId) && !refineDismissed;
  const refining = refineActive && refineQuery.isSuccess;
  const refineLoading = refineActive && refineQuery.isLoading;
  const parentVersion = refineQuery.data?.version ?? 1;

  const {
    register,
    control,
    handleSubmit,
    watch,
    reset,
    formState: { errors, isSubmitting },
  } = useForm<IdeaFormValues>({
    resolver: zodResolver(ideaFormSchema),
    defaultValues: ideaFormDefaults,
    mode: "onBlur",
  });

  const ideaLength = watch("idea").trim().length;

  useEffect(() => {
    if (!refining || !refineQuery.data) return;
    reset({ ...ideaFormDefaults, idea: refineQuery.data.idea.trim() });
  }, [refining, refineQuery.data, reset]);

  const mutation = useMutation({
    mutationFn: createRun,
    onSuccess: ({ run_id }, variables) => {
      stashRunIdea(run_id, variables.idea);
      void queryClient.invalidateQueries({ queryKey: ["runs", "list"] });
      router.push(`/run/${run_id}`);
    },
    onError: (error: Error) => {
      if (error instanceof ApiError) {
        const detail = parseApiDetail(error.body);
        if (error.status === 429) {
          toast.error("Rate limited", {
            description: detail ?? RATE_LIMIT_MESSAGE,
          });
          return;
        }
        if (error.status === 422) {
          toast.error("Invalid submission", {
            description: detail ?? "Check your fields and try again.",
          });
          return;
        }
        toast.error("Could not start roast", {
          description: detail ?? `Server returned ${error.status}.`,
        });
        return;
      }
      toast.error("Network error", {
        description: "Could not reach the API. Is the backend running?",
      });
    },
  });

  const onSubmit = handleSubmit((values) => {
    if (refineActive && !refining) {
      toast.error("Still loading the prior version", {
        description: "Wait a moment, then roast again so this saves as the next version.",
      });
      return;
    }
    const request = toCreateRunRequest(values, loadAdvancedSettings());
    if (refining && refineRunId) {
      request.parent_run_id = refineRunId;
    }
    mutation.mutate(request);
  });

  const submitting = isSubmitting || mutation.isPending;
  const submitBlocked = submitting || refineLoading;

  return (
    <form onSubmit={onSubmit} className="mt-12 space-y-8" noValidate>
      {refineLoading && (
        <div className="rounded-md border border-rule-soft bg-paper-2 px-5 py-4">
          <p className="font-sans text-sm text-ink-muted">
            Loading your prior version…
          </p>
        </div>
      )}

      {refining && (
        <div className="rounded-md border border-rule-soft bg-paper-2 px-5 py-4">
          <p className="font-sans text-sm text-ink-muted">
            Refining this pitch — the next roast will save as{" "}
            <span className="font-semibold text-ink">v{parentVersion + 1}</span> linked to your
            prior version.
          </p>
          <button
            type="button"
            className="mt-3 font-sans text-sm font-semibold text-ink underline-offset-4 hover:underline"
            onClick={() => {
              setRefineDismissed(true);
              router.replace("/", { scroll: false });
            }}
          >
            Submit as a new standalone pitch instead
          </button>
        </div>
      )}

      {refineRunId && refineQuery.isError && !refineDismissed && (
        <p className="font-sans text-sm text-fail" role="alert">
          Could not load the prior run to refine. Submit as a new standalone pitch instead.
        </p>
      )}

      <div className="space-y-2">
        <div className="flex items-baseline justify-between gap-4">
          <Label htmlFor="idea">Your startup idea</Label>
          <span
            className={cn(
              "font-mono text-xs tabular-nums",
              ideaLength > IDEA_MAX_LENGTH ? "text-fail" : "text-ink-subtle",
            )}
            aria-live="polite"
          >
            {ideaLength} / {IDEA_MAX_LENGTH}
          </span>
        </div>
        <Textarea
          id="idea"
          rows={6}
          placeholder="Describe what you're building, who it's for, and why it matters…"
          aria-invalid={!!errors.idea}
          aria-describedby={errors.idea ? "idea-error" : undefined}
          disabled={submitting}
          {...register("idea")}
        />
        <FieldError id="idea-error" message={errors.idea?.message} />
      </div>

      <div>
        <button
          type="button"
          className="inline-flex min-h-11 items-center gap-2 font-sans text-sm font-semibold text-ink underline-offset-4 hover:underline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-cta"
          aria-expanded={contextOpen}
          onClick={() => setContextOpen((open) => !open)}
        >
          {contextOpen ? (
            <ChevronUp className="size-4" aria-hidden />
          ) : (
            <ChevronDown className="size-4" aria-hidden />
          )}
          Add context
          <span className="font-normal text-ink-muted">(optional)</span>
        </button>

        {contextOpen && (
          <div className="mt-6 space-y-6 border-l-2 border-rule-soft pl-6">
            <div className="space-y-2">
              <Label htmlFor="target_customer">Target customer</Label>
              <Input
                id="target_customer"
                placeholder="e.g. solo founders at pre-seed stage"
                disabled={submitting}
                {...register("target_customer")}
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="pricing">Pricing</Label>
              <Input
                id="pricing"
                placeholder="e.g. $29/mo per seat"
                disabled={submitting}
                {...register("pricing")}
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="traction">Traction</Label>
              <Input
                id="traction"
                placeholder="e.g. 200 waitlist signups, $2k MRR"
                disabled={submitting}
                {...register("traction")}
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="competitors">Competitors</Label>
              <Textarea
                id="competitors"
                rows={3}
                placeholder="One competitor per line"
                disabled={submitting}
                {...register("competitorsText")}
              />
            </div>
          </div>
        )}
      </div>

      <p className="font-sans text-sm text-ink-muted">
        Model, debate rounds, and web search live on{" "}
        <Link
          href="/settings"
          className="font-semibold text-ink underline-offset-4 hover:underline"
        >
          Advanced settings
        </Link>
        . Most founders can ignore them.
      </p>

      <Button type="submit" disabled={submitBlocked} className="w-full sm:w-auto">
        {submitting ? (
          <>
            <Loader2 className="size-4 animate-spin" aria-hidden />
            Sending to the judges…
          </>
        ) : refineLoading ? (
          <>
            <Loader2 className="size-4 animate-spin" aria-hidden />
            Loading prior version…
          </>
        ) : refining ? (
          `Roast v${parentVersion + 1}`
        ) : (
          "Roast it"
        )}
      </Button>
    </form>
  );
}
