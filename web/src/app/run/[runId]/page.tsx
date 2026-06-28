import { RunSheet } from "@/features/run/run-sheet";

type RunPageProps = {
  params: Promise<{ runId: string }>;
};

export default async function RunPage({ params }: RunPageProps) {
  const { runId } = await params;
  return <RunSheet runId={runId} />;
}
