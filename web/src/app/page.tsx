import { EditorialContainer } from "@/components/app-shell";
import { IdeaForm } from "@/features/submit/idea-form";

type HomeProps = {
  searchParams: Promise<{ refine?: string }>;
};

export default async function Home({ searchParams }: HomeProps) {
  const params = await searchParams;
  return (
    <EditorialContainer className="py-16 md:py-24 lg:py-32">
      <div className="col-span-12 lg:col-span-10 lg:col-start-2">
        <p className="font-sans text-sm font-semibold uppercase tracking-widest text-heat-ink">
          Editorial verdict
        </p>
        <h1 className="mt-4 font-serif text-display-md font-semibold leading-[1.05] tracking-tight text-ink md:text-display-lg lg:text-display-xl">
          Five AI judges roast your startup idea, debate it, and hand down a{" "}
          <span className="text-heat">verdict</span>.
        </h1>
        <p className="mt-8 max-w-prose font-sans text-lg leading-relaxed text-ink-muted">
          Submit your pitch. Watch five distinct critics score, roast, and argue in
          real time.
        </p>
        <IdeaForm refineRunId={params.refine ?? null} />
      </div>
    </EditorialContainer>
  );
}
