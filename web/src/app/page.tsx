import { EditorialContainer } from "@/components/app-shell";
import { HOME_COPY } from "@/features/run/run-page-copy";
import { IdeaForm } from "@/features/submit/idea-form";

type HomeProps = {
  searchParams: Promise<{ refine?: string }>;
};

export default async function Home({ searchParams }: HomeProps) {
  const params = await searchParams;
  return (
    <EditorialContainer className="py-16 md:py-24 lg:py-32">
      <p className="font-sans text-sm font-semibold uppercase tracking-widest text-cta">
        {HOME_COPY.eyebrow}
      </p>
      <h1 className="mt-4 font-sans text-display-md font-semibold leading-[1.1] tracking-tight text-ink md:text-display-lg lg:text-display-xl">
        {HOME_COPY.headline}
      </h1>
      <p className="mt-8 max-w-prose font-sans text-lg leading-relaxed text-ink-muted">
        {HOME_COPY.lead}
      </p>
      <IdeaForm refineRunId={params.refine ?? null} />
    </EditorialContainer>
  );
}
