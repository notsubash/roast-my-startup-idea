import Link from "next/link";

import { EditorialContainer } from "@/components/app-shell";
import { secondaryCtaClass } from "@/lib/cta-classes";

type RunPageProps = {
  params: Promise<{ runId: string }>;
};

export default async function RunPage({ params }: RunPageProps) {
  const { runId } = await params;

  return (
    <EditorialContainer className="py-12 md:py-16 lg:py-24">
      <div className="col-span-12 lg:col-span-10 lg:col-start-2">
        <p className="font-sans text-sm font-semibold uppercase tracking-widest text-heat-ink">
          Verdict sheet
        </p>
        <h1 className="mt-2 font-serif text-title font-semibold text-ink md:text-display-md">
          The judges are convening
        </h1>
        <p className="mt-4 max-w-prose font-sans text-ink-muted">
          Run <span className="font-mono text-sm text-ink">{runId}</span> was
          created. Live streaming, judge columns, and the debate transcript land in
          Phase 2 — this page is the landing spot after submit.
        </p>
        <Link href="/" className={`mt-8 ${secondaryCtaClass}`}>
          Roast another idea
        </Link>
      </div>
    </EditorialContainer>
  );
}
