"use client";

import { useEffect, useState, type ReactNode } from "react";
import Link from "next/link";

import {
  DEFAULT_RUN_FOLD_VARIANT,
  formatFoldSectionOrder,
  RUN_FOLD_VARIANTS,
  type RunFoldVariant,
} from "@/features/run/run-fold-layout";
import { SETTINGS_COPY } from "@/features/run/run-page-copy";
import {
  DEFAULT_ADVANCED_SETTINGS,
  loadAdvancedSettings,
  saveAdvancedSettings,
  type AdvancedSettings,
} from "@/lib/settings/advanced-settings";
import { cn } from "@/lib/utils";
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

function SettingsSection({
  title,
  description,
  children,
}: {
  title: string;
  description: string;
  children: ReactNode;
}) {
  return (
    <section className="border-t-2 border-rule-soft pt-10 first:border-t-0 first:pt-0">
      <h2 className="font-sans text-2xl font-semibold text-ink">{title}</h2>
      <p className="mt-2 max-w-prose font-sans text-sm text-ink-muted">{description}</p>
      <div className="mt-6 space-y-6">{children}</div>
    </section>
  );
}

export function AdvancedSettingsPanel() {
  const [settings, setSettings] = useState<AdvancedSettings>(DEFAULT_ADVANCED_SETTINGS);
  const [ready, setReady] = useState(false);

  useEffect(() => {
    setSettings(loadAdvancedSettings());
    setReady(true);
  }, []);

  const patch = (partial: Partial<AdvancedSettings>) => {
    const next = saveAdvancedSettings(partial);
    setSettings(next);
  };

  if (!ready) {
    return (
      <p className="font-sans text-sm text-ink-muted" aria-live="polite">
        Loading settings…
      </p>
    );
  }

  const foldOptions = Object.entries(RUN_FOLD_VARIANTS) as [
    RunFoldVariant,
    (typeof RUN_FOLD_VARIANTS)[RunFoldVariant],
  ][];

  return (
    <div className="space-y-10">
      <header>
        <p className="font-sans text-sm font-semibold uppercase tracking-widest text-cta">
          Maintainer
        </p>
        <h1 className="mt-2 font-sans text-title font-semibold text-ink md:text-display-md">
          Advanced settings
        </h1>
        <p className="mt-4 max-w-prose font-sans text-ink-muted">
          {SETTINGS_COPY.intro}{" "}
          <Link href="/" className="font-semibold text-ink underline-offset-4 hover:underline">
            home
          </Link>
          .
        </p>
      </header>

      <SettingsSection
        title={SETTINGS_COPY.newReviewDefaults}
        description={SETTINGS_COPY.newReviewDescription}
      >
        <div className="grid gap-8 md:grid-cols-2">
          <div className="space-y-2">
            <Label htmlFor="settings-model-runtime">Model runtime</Label>
            <Select
              value={settings.model_runtime}
              onValueChange={(value: "local" | "deepseek") =>
                patch({ model_runtime: value })
              }
            >
              <SelectTrigger id="settings-model-runtime">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="deepseek">DeepSeek (paid, faster)</SelectItem>
                <SelectItem value="local">Local (free, slower)</SelectItem>
              </SelectContent>
            </Select>
            <p className="font-sans text-xs text-ink-muted">
              Which LLM backend runs the judges. Local costs $0 but needs Ollama running.
            </p>
          </div>

          <div className="space-y-3">
            <div className="flex items-baseline justify-between gap-4">
              <Label htmlFor="settings-debate-rounds">Debate rounds</Label>
              <span className="font-mono text-sm font-medium tabular-nums text-ink">
                {settings.max_debate_rounds}
              </span>
            </div>
            <Slider
              id="settings-debate-rounds"
              min={1}
              max={5}
              step={1}
              value={[settings.max_debate_rounds]}
              onValueChange={([value]) => patch({ max_debate_rounds: value })}
              aria-label="Debate rounds"
            />
            <p className="font-sans text-xs text-ink-muted">
              How many back-and-forth debate rounds before the final synthesis (1–5).
            </p>
          </div>
        </div>

        <div className="flex items-center justify-between gap-4 border border-rule-soft bg-paper-2 px-4 py-4">
          <div className="space-y-1">
            <Label htmlFor="settings-web-search">Web search</Label>
            <p className="font-sans text-xs text-ink-muted">
              Let judges pull live research snippets into the roast (extra latency and cost when
              using DeepSeek).
            </p>
          </div>
          <Switch
            id="settings-web-search"
            checked={settings.enable_web_search}
            onCheckedChange={(checked) => patch({ enable_web_search: checked })}
            aria-label={SETTINGS_COPY.webSearchLabel}
          />
        </div>
      </SettingsSection>

      <SettingsSection
        title="Review page layout"
        description={SETTINGS_COPY.reviewLayoutDescription}
      >
        <fieldset aria-labelledby="fold-variant-legend">
          <legend
            id="fold-variant-legend"
            className="font-sans text-xs font-semibold uppercase tracking-widest text-ink-muted"
          >
            Section order
          </legend>
          <div className="mt-4 grid gap-4 lg:grid-cols-2">
            {foldOptions.map(([id, meta]) => {
              const active = settings.run_fold_variant === id;
              return (
                <label
                  key={id}
                  className={cn(
                    "block cursor-pointer rounded-ui border p-4 transition-colors duration-200",
                    active
                      ? "border-cta bg-card shadow-soft"
                      : "border-rule-soft bg-paper-2 hover:border-ink-muted",
                  )}
                >
                  <div className="flex items-start gap-3">
                    <input
                      type="radio"
                      name="run-fold-variant"
                      value={id}
                      checked={active}
                      onChange={() => patch({ run_fold_variant: id })}
                      className="mt-1 size-4 accent-cta"
                    />
                    <div className="min-w-0 flex-1">
                      <p className="font-sans text-sm font-semibold text-ink">
                        {meta.label}
                        {id === DEFAULT_RUN_FOLD_VARIANT && (
                          <span className="ml-2 font-normal text-ink-subtle">(recommended)</span>
                        )}
                      </p>
                      <p className="mt-1 font-sans text-sm leading-relaxed text-ink-muted">
                        {meta.summary}
                      </p>
                      <p className="mt-2 font-sans text-xs text-ink-subtle">{meta.bestFor}</p>
                      <ol className="mt-4 space-y-1 border-t border-rule-soft pt-3">
                        {formatFoldSectionOrder(id).map((step, index) => (
                          <li
                            key={step}
                            className="flex gap-2 font-sans text-xs leading-relaxed text-ink-muted"
                          >
                            <span className="w-4 shrink-0 font-mono text-ink-subtle">
                              {index + 1}.
                            </span>
                            <span>{step}</span>
                          </li>
                        ))}
                      </ol>
                    </div>
                  </div>
                </label>
              );
            })}
          </div>
        </fieldset>
        <p className="font-sans text-xs text-ink-subtle">
          URL override for side-by-side tests: add{" "}
          <span className="font-mono">?fold=a</span> (scores first) or{" "}
          <span className="font-mono">?fold=b</span> (progress first) to any run link. URL wins over
          this setting. Lens-quality maintainer badge: add{" "}
          <span className="font-mono">?debug=1</span> to a completed run.
        </p>
      </SettingsSection>
    </div>
  );
}
