"use client";

import { heatCtaClass } from "@/lib/cta-classes";

export default function Error({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  return (
    <div role="alert" className="mx-auto max-w-[1200px] px-4 py-16 md:px-6 lg:px-8">
      <h1 className="font-serif text-title font-semibold text-ink">
        Something went wrong
      </h1>
      <p className="mt-4 max-w-prose text-ink-muted">
        {error.message || "An unexpected error occurred."}
      </p>
      <button type="button" onClick={reset} className={`mt-8 ${heatCtaClass} px-6`}>
        Try again
      </button>
    </div>
  );
}
