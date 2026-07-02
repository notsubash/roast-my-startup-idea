import type { VerdictLabel } from "@/lib/sse/types";
import { cn } from "@/lib/utils";

import { VerdictStamp } from "./verdict-stamp";
import { parseAppealSynthesis, parseSynthesis, splitInlineMarkdown } from "./synthesis-format";

function SynthesisFallback({ content, className }: { content: string; className?: string }) {
  return (
    <blockquote
      className={cn(
        "border border-rule-soft bg-paper-2 p-6 font-sans text-base leading-relaxed text-ink shadow-soft whitespace-pre-wrap md:text-lg",
        className,
      )}
    >
      {content}
    </blockquote>
  );
}

function SynthesisHeader({
  verdict,
  score,
}: {
  verdict: VerdictLabel | null;
  score: string | null;
}) {
  if (!verdict && !score) return null;

  return (
    <header className="flex flex-wrap items-end gap-8 border-b border-rule-soft px-6 py-5">
      {verdict && (
        <div>
          <p className="font-sans text-xs font-semibold uppercase tracking-widest text-ink-muted">
            Overall verdict
          </p>
          <div className="mt-2">
            <VerdictStamp verdict={verdict} />
          </div>
        </div>
      )}
      {score && (
        <div>
          <p className="font-sans text-xs font-semibold uppercase tracking-widest text-ink-muted">
            Final score
          </p>
          <p className="mt-1 font-mono text-3xl font-bold tabular-nums text-ink md:text-4xl">
            {score}
            <span className="text-lg font-normal text-ink-muted">/10</span>
          </p>
        </div>
      )}
    </header>
  );
}

function FormattedInline({ text }: { text: string }) {
  return (
    <>
      {splitInlineMarkdown(text).map((part, i) => {
        if (part.kind === "bold") {
          return (
            <strong key={i} className="font-semibold text-ink">
              {part.value}
            </strong>
          );
        }
        if (part.kind === "italic") {
          return <em key={i}>{part.value}</em>;
        }
        return part.value;
      })}
    </>
  );
}

function SynthesisSection({
  title,
  bullets,
  richText = false,
}: {
  title: string;
  bullets: string[];
  richText?: boolean;
}) {
  const renderBullet = (bullet: string) =>
    richText ? <FormattedInline text={bullet} /> : bullet;

  return (
    <section>
      <h3 className="font-sans text-xl font-semibold text-ink">{title}</h3>
      {bullets.length === 1 && !bullets[0].includes("\n") ? (
        <p className="mt-3 font-sans text-base leading-relaxed text-ink-muted">
          {renderBullet(bullets[0])}
        </p>
      ) : (
        <ul className="mt-3 space-y-2 border-l-2 border-rule-soft pl-4">
          {bullets.map((bullet, i) => (
            <li
              key={i}
              className="font-sans text-base leading-relaxed text-ink-muted"
            >
              {renderBullet(bullet)}
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}

export function SynthesisBlock({
  content,
  className,
  variant = "debate",
}: {
  content: string | null;
  className?: string;
  /** Appeal synthesis uses free-form markdown sections instead of numbered moderator shape. */
  variant?: "debate" | "appeal";
}) {
  if (!content) {
    return (
      <p className={cn("font-sans text-sm text-ink-subtle", className)}>
        The moderator&apos;s final synthesis will land here after the debate.
      </p>
    );
  }

  const parsed =
    variant === "appeal"
      ? parseAppealSynthesis(content) ?? parseSynthesis(content)
      : parseSynthesis(content);
  if (!parsed) {
    return <SynthesisFallback content={content} className={className} />;
  }

  const richText = variant === "appeal";

  return (
    <article
      className={cn(
        "border border-rule-soft bg-card shadow-soft",
        className,
      )}
    >
      <SynthesisHeader verdict={parsed.verdict} score={parsed.score} />
      {parsed.sections.length > 0 && (
        <div className="space-y-8 px-6 py-6">
          {parsed.sections.map((section) => (
            <SynthesisSection
              key={section.title}
              title={section.title}
              bullets={section.bullets}
              richText={richText}
            />
          ))}
        </div>
      )}
    </article>
  );
}
