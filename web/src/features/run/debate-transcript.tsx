import { speakerMeta } from "@/lib/sse/judges";
import type { DebateTurnView } from "@/lib/sse/types";
import { cn } from "@/lib/utils";

export function DebateTurn({ turn }: { turn: DebateTurnView }) {
  const meta = speakerMeta(turn.speaker);
  const accentText = meta.accentClass.split(" ")[0];

  return (
    <article
      className="border-l-2 border-primary py-3 pl-4"
      aria-label={`${meta.name}, round ${turn.round}`}
    >
      <header className="flex flex-wrap items-baseline gap-x-2 gap-y-1">
        <span className={cn("font-sans text-sm font-bold", accentText)}>{meta.name}</span>
        <span className="font-mono text-xs text-ink-subtle">Round {turn.round}</span>
        {turn.thinking && (
          <span className="font-sans text-xs text-ink-muted">Thinking…</span>
        )}
      </header>
      {turn.content ? (
        <p className="mt-2 whitespace-pre-wrap font-mono text-sm leading-relaxed text-ink">
          {turn.content}
          {turn.streaming && (
            <span className="ml-0.5 inline-block h-4 w-0.5 animate-pulse bg-cta" aria-hidden />
          )}
        </p>
      ) : turn.thinking ? (
        <p className="mt-2 animate-pulse font-sans text-sm text-ink-muted">Preparing response…</p>
      ) : null}
    </article>
  );
}

export function DebateTranscript({
  turns,
  currentRound,
}: {
  turns: DebateTurnView[];
  currentRound: number | null;
}) {
  if (turns.length === 0 && currentRound === null) {
    return (
      <p className="font-sans text-sm text-ink-subtle">
        The debate transcript will appear here once the judges start arguing.
      </p>
    );
  }

  const rounds = [...new Set(turns.map((t) => t.round))].sort((a, b) => a - b);
  if (currentRound !== null && !rounds.includes(currentRound)) {
    rounds.push(currentRound);
    rounds.sort((a, b) => a - b);
  }

  return (
    <div className="space-y-8">
      {rounds.map((round) => {
        const roundTurns = turns.filter((t) => t.round === round);
        return (
          <section
            key={round}
            aria-labelledby={`debate-round-${round}`}
            className="animate-round-enter"
          >
            <h3
              id={`debate-round-${round}`}
              className="font-sans text-xs font-semibold uppercase tracking-widest text-ink-muted"
            >
              Round {round}
            </h3>
            <div className="mt-3 space-y-2">
              {roundTurns.length > 0 ? (
                roundTurns.map((turn) => (
                  <DebateTurn key={`${turn.round}-${turn.speaker}`} turn={turn} />
                ))
              ) : (
                <p className="font-sans text-sm text-ink-subtle">Round starting…</p>
              )}
            </div>
          </section>
        );
      })}
    </div>
  );
}
