"use client";

import { useState } from "react";
import Link from "next/link";
import { toast } from "sonner";

import { RunControls } from "@/features/run/run-controls";
import { RunMetricsBar } from "@/features/run/run-metrics-bar";
import { ScoreLollipopStrip } from "@/features/run/score-lollipop-strip";
import { ScoreRadar, scoreRadarData } from "@/features/run/score-radar";
import { VerdictTallyBar } from "@/features/run/verdict-tally";
import { VerdictStamp } from "@/features/run/verdict-stamp";
import { secondaryCtaClass } from "@/lib/cta-classes";
import { initialRunState } from "@/lib/sse/run-reducer";
import { Badge } from "@/ui/badge";
import { Button } from "@/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardFooter,
  CardHeader,
  CardTitle,
} from "@/ui/card";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/ui/dialog";
import { Input } from "@/ui/input";
import { Label } from "@/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/ui/select";
import { Skeleton } from "@/ui/skeleton";
import { Slider } from "@/ui/slider";
import { Switch } from "@/ui/switch";
import { Textarea } from "@/ui/textarea";
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "@/ui/tooltip";

function Section({
  title,
  children,
}: {
  title: string;
  children: React.ReactNode;
}) {
  return (
    <section className="col-span-12 border-t-2 border-ink pt-12 first:border-t-0 first:pt-0">
      <h2 className="font-serif text-2xl font-semibold text-ink">{title}</h2>
      <div className="mt-6 flex flex-wrap items-start gap-4">{children}</div>
    </section>
  );
}

export function DevGallery() {
  const [sliderValue, setSliderValue] = useState([3]);
  const [switchOn, setSwitchOn] = useState(false);
  const [selectValue, setSelectValue] = useState("deepseek");

  const partialRadarState = initialRunState();
  partialRadarState.judges.vc = {
    status: "revealed",
    verdict: { judge: "vc", verdict: "FAIL", score: 4, roast: "x", key_concern: "y" },
  };
  partialRadarState.judges.engineer = {
    status: "revealed",
    verdict: { judge: "engineer", verdict: "CONDITIONAL", score: 6, roast: "x", key_concern: "y" },
  };

  const sampleMetrics = {
    roast_seconds: 4.2,
    debate_seconds: 11.8,
    total_seconds: 16,
    input_tokens: 2100,
    output_tokens: 980,
    total_tokens: 3080,
    estimated_cost_usd: 0.004,
    model_runtime: "deepseek" as const,
    judge_calls: [
      { label: "vc", phase: "roast" as const, seconds: 1.2, input_tokens: 400, output_tokens: 120, total_tokens: 520 },
      { label: "engineer", phase: "roast" as const, seconds: 1.1, input_tokens: 380, output_tokens: 110, total_tokens: 490 },
    ],
    debate_calls: [
      { label: "round-1-vc", phase: "debate" as const, seconds: 2.4, input_tokens: 600, output_tokens: 200, total_tokens: 800 },
    ],
  };

  return (
    <TooltipProvider>
      <div className="col-span-12 space-y-4">
        <p className="font-sans text-sm font-semibold uppercase tracking-widest text-heat-ink">
          Phase 3
        </p>
        <h1 className="font-serif text-title font-semibold text-ink md:text-display-md">
          Component gallery
        </h1>
        <p className="max-w-prose font-sans text-ink-muted">
          Every primitive and signature component in loading, empty, error, and
          success states.
        </p>
        <Link href="/" className={`mt-4 inline-flex ${secondaryCtaClass}`}>
          Back home
        </Link>
      </div>

      <Section title="Button">
        <Button>Default (Roast it)</Button>
        <Button variant="secondary">Secondary</Button>
        <Button variant="outline">Outline</Button>
        <Button variant="ghost">Ghost</Button>
        <Button disabled>Disabled</Button>
        <Button disabled>
          <span className="inline-block size-4 animate-spin rounded-full border-2 border-ink border-t-transparent" />
          Submitting…
        </Button>
      </Section>

      <Section title="Input & Textarea">
        <div className="w-full max-w-sm space-y-4">
          <Input placeholder="Empty" aria-label="Empty input" />
          <Input defaultValue="Filled value" aria-label="Filled input" />
          <Input disabled defaultValue="Disabled" aria-label="Disabled input" />
          <Input
            aria-invalid
            defaultValue="Bad input"
            aria-label="Error input"
            className="border-fail"
          />
          <Textarea placeholder="Empty textarea" aria-label="Empty textarea" />
        </div>
      </Section>

      <Section title="Select">
        <div className="w-full max-w-xs">
          <Select value={selectValue} onValueChange={setSelectValue}>
            <SelectTrigger aria-label="Model runtime">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="deepseek">DeepSeek</SelectItem>
              <SelectItem value="local">Local</SelectItem>
            </SelectContent>
          </Select>
        </div>
        <Select disabled>
          <SelectTrigger className="w-48" aria-label="Disabled select">
            <SelectValue placeholder="Disabled" />
          </SelectTrigger>
        </Select>
      </Section>

      <Section title="Slider & Switch">
        <div className="w-full max-w-xs space-y-2">
          <Label>Rounds: {sliderValue[0]}</Label>
          <Slider
            min={1}
            max={5}
            step={1}
            value={sliderValue}
            onValueChange={setSliderValue}
            aria-label="Debate rounds demo"
          />
        </div>
        <div className="flex items-center gap-3">
          <Switch
            checked={switchOn}
            onCheckedChange={setSwitchOn}
            aria-label="Web search demo"
          />
          <span className="font-sans text-sm text-ink-muted">
            {switchOn ? "On" : "Off"}
          </span>
        </div>
        <Switch disabled aria-label="Disabled switch" />
      </Section>

      <Section title="Card & Badge">
        <Card className="w-full max-w-sm">
          <CardHeader>
            <CardTitle>Judge card</CardTitle>
            <CardDescription>Idle state placeholder</CardDescription>
          </CardHeader>
          <CardContent>
            <p className="font-sans text-sm text-ink-muted">Waiting for verdict…</p>
          </CardContent>
          <CardFooter>
            <Badge variant="heat">Streaming</Badge>
          </CardFooter>
        </Card>
        <Badge>Default</Badge>
        <Badge variant="pass">Pass</Badge>
        <Badge variant="fail">Fail</Badge>
        <Badge variant="conditional">Conditional</Badge>
      </Section>

      <Section title="Skeleton">
        <Skeleton className="h-24 w-full max-w-sm" />
        <Skeleton className="size-12" />
      </Section>

      <Section title="Dialog">
        <Dialog>
          <DialogTrigger asChild>
            <Button variant="secondary">Open dialog</Button>
          </DialogTrigger>
          <DialogContent>
            <DialogHeader>
              <DialogTitle>Stop this roast?</DialogTitle>
              <DialogDescription>
                The judges will pack up. You can always submit a new idea.
              </DialogDescription>
            </DialogHeader>
            <DialogFooter>
              <Button variant="secondary">Keep going</Button>
              <Button variant="destructive">Stop</Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>
      </Section>

      <Section title="Tooltip">
        <Tooltip>
          <TooltipTrigger asChild>
            <Button variant="outline">Hover me</Button>
          </TooltipTrigger>
          <TooltipContent>Five judges, zero mercy.</TooltipContent>
        </Tooltip>
      </Section>

      <Section title="Sonner toast">
        <Button
          variant="secondary"
          onClick={() =>
            toast.error("Rate limited", {
              description: "Too many run requests. Please try again shortly.",
            })
          }
        >
          Show rate-limit toast
        </Button>
        <Button
          variant="secondary"
          onClick={() =>
            toast.error("Network error", {
              description: "Could not reach the API. Is the backend running?",
            })
          }
        >
          Show network toast
        </Button>
      </Section>

      <Section title="VerdictStamp">
        <VerdictStamp verdict="PASS" />
        <VerdictStamp verdict="FAIL" />
        <VerdictStamp verdict="CONDITIONAL" />
        <VerdictStamp verdict="PASS" animate />
        <VerdictStamp verdict="FAIL" animate />
        <VerdictStamp verdict="CONDITIONAL" animate />
      </Section>

      <Section title="VerdictTallyBar">
        <div className="w-full max-w-xl space-y-6">
          <VerdictTallyBar judges={initialRunState().judges} />
          <VerdictTallyBar judges={partialRadarState.judges} />
        </div>
      </Section>

      <Section title="ScoreLollipopStrip">
        <div className="w-full max-w-xl">
          <ScoreLollipopStrip judges={partialRadarState.judges} />
        </div>
      </Section>

      <Section title="ScoreRadar">
        <div className="w-full max-w-3xl">
          <p className="mb-3 w-full font-sans text-xs uppercase tracking-widest text-ink-muted">Empty</p>
          <ScoreRadar judges={initialRunState().judges} />
        </div>
        <div className="w-full max-w-3xl">
          <p className="mb-3 w-full font-sans text-xs uppercase tracking-widest text-ink-muted">Partial</p>
          <ScoreRadar judges={partialRadarState.judges} />
          <p className="mt-2 font-mono text-xs text-ink-subtle">
            {scoreRadarData(partialRadarState.judges)
              .filter((d) => d.score !== null)
              .map((d) => `${d.judge}: ${d.score}`)
              .join(" · ")}
          </p>
        </div>
      </Section>

      <Section title="RunControls">
        <div className="w-full space-y-6">
          <div>
            <p className="mb-3 w-full font-sans text-xs uppercase tracking-widest text-ink-muted">
              Running
            </p>
            <RunControls runId="demo-running" status="running" />
          </div>
          <div>
            <p className="mb-3 w-full font-sans text-xs uppercase tracking-widest text-ink-muted">
              Completed with export
            </p>
            <RunControls
              runId="demo-complete"
              status="completed"
              exportInput={{
                idea: "An AI journal that summarizes your day and ships weekly founder updates.",
                runId: "demo-complete",
                judges: partialRadarState.judges,
                debateTurns: [
                  {
                    speaker: "vc",
                    round: 1,
                    content: "Crowded category.",
                    streaming: false,
                    thinking: false,
                  },
                ],
                synthesis: "Needs sharper positioning.",
                metrics: sampleMetrics,
              }}
            />
          </div>
          <div>
            <p className="mb-3 w-full font-sans text-xs uppercase tracking-widest text-ink-muted">
              Failed without export
            </p>
            <RunControls runId="demo-failed" status="failed" exportInput={null} />
          </div>
        </div>
      </Section>

      <Section title="RunMetricsBar">
        <div className="w-full max-w-3xl space-y-8">
          <RunMetricsBar metrics={null} status="running" />
          <RunMetricsBar metrics={null} status="failed" />
          <RunMetricsBar metrics={sampleMetrics} status="completed" />
          <RunMetricsBar metrics={{ ...sampleMetrics, estimated_cost_usd: 0, model_runtime: "local" }} status="completed" />
        </div>
      </Section>
    </TooltipProvider>
  );
}
