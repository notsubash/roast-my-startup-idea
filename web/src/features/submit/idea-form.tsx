"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { zodResolver } from "@hookform/resolvers/zod";
import { useMutation } from "@tanstack/react-query";
import { ChevronDown, ChevronUp, Loader2 } from "lucide-react";
import { Controller, useForm } from "react-hook-form";
import { toast } from "sonner";

import { stashRunIdea } from "@/lib/format/run-idea";
import { ApiError } from "@/lib/api/client";
import { createRun } from "@/lib/api/runs";
import { parseApiDetail, RATE_LIMIT_MESSAGE } from "@/lib/api/types-helpers";
import { cn } from "@/lib/utils";
import { Button } from "@/ui/button";
import { Input } from "@/ui/input";
import { Label } from "@/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/ui/select";
import { Slider } from "@/ui/slider";
import { Switch } from "@/ui/switch";
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

export function IdeaForm() {
  const router = useRouter();
  const [contextOpen, setContextOpen] = useState(false);

  const {
    register,
    control,
    handleSubmit,
    watch,
    formState: { errors, isSubmitting },
  } = useForm<IdeaFormValues>({
    resolver: zodResolver(ideaFormSchema),
    defaultValues: ideaFormDefaults,
    mode: "onBlur",
  });

  const ideaLength = watch("idea").trim().length;
  const debateRounds = watch("max_debate_rounds");

  const mutation = useMutation({
    mutationFn: createRun,
    onSuccess: ({ run_id }, variables) => {
      stashRunIdea(run_id, variables.idea);
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
    mutation.mutate(toCreateRunRequest(values));
  });

  const submitting = isSubmitting || mutation.isPending;

  return (
    <form onSubmit={onSubmit} className="mt-12 space-y-8" noValidate>
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
          className="inline-flex min-h-11 items-center gap-2 font-sans text-sm font-semibold text-ink underline-offset-4 hover:underline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-heat"
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

      <div className="grid gap-8 md:grid-cols-2">
        <div className="space-y-2">
          <Label htmlFor="model_runtime">Model runtime</Label>
          <Controller
            name="model_runtime"
            control={control}
            render={({ field }) => (
              <Select
                value={field.value}
                onValueChange={field.onChange}
                disabled={submitting}
              >
                <SelectTrigger id="model_runtime">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="deepseek">DeepSeek (paid, faster)</SelectItem>
                  <SelectItem value="local">Local (free, slower)</SelectItem>
                </SelectContent>
              </Select>
            )}
          />
          <p className="font-sans text-xs text-ink-muted">
            Local = free, slower; DeepSeek = paid, faster.
          </p>
        </div>

        <div className="space-y-3">
          <div className="flex items-baseline justify-between gap-4">
            <Label htmlFor="max_debate_rounds">Debate rounds</Label>
            <span className="font-mono text-sm font-medium tabular-nums text-ink">
              {debateRounds}
            </span>
          </div>
          <Controller
            name="max_debate_rounds"
            control={control}
            render={({ field }) => (
              <Slider
                id="max_debate_rounds"
                min={1}
                max={5}
                step={1}
                value={[field.value]}
                onValueChange={([value]) => field.onChange(value)}
                disabled={submitting}
                aria-label="Debate rounds"
              />
            )}
          />
          <FieldError message={errors.max_debate_rounds?.message} />
        </div>
      </div>

      <div className="flex items-center justify-between gap-4 border-t border-rule-soft pt-6">
        <div className="space-y-1">
          <Label htmlFor="enable_web_search">Web search</Label>
          <p className="font-sans text-xs text-ink-muted">
            Ground roasts in live research (when enabled on the backend).
          </p>
        </div>
        <Controller
          name="enable_web_search"
          control={control}
          render={({ field }) => (
            <Switch
              id="enable_web_search"
              checked={field.value}
              onCheckedChange={field.onChange}
              disabled={submitting}
              aria-label="Enable web search"
            />
          )}
        />
      </div>

      <Button type="submit" disabled={submitting} className="w-full sm:w-auto">
        {submitting ? (
          <>
            <Loader2 className="size-4 animate-spin" aria-hidden />
            Sending to the judges…
          </>
        ) : (
          "Roast it"
        )}
      </Button>
    </form>
  );
}
