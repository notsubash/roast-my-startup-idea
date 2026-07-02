"use client";

import { heatCtaClass } from "@/lib/cta-classes";

import "./globals.css";

export default function GlobalError({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  return (
    <html lang="en">
      <body className="min-h-full bg-paper text-ink antialiased">
        <div role="alert" className="mx-auto w-full max-w-3xl px-4 py-16 md:px-6">
          <h1 className="font-sans text-title font-semibold">Something went wrong</h1>
          <p className="mt-4 max-w-prose text-ink-muted">
            {error.message || "An unexpected error occurred."}
          </p>
          <button type="button" onClick={reset} className={`mt-8 ${heatCtaClass} px-6`}>
            Try again
          </button>
        </div>
      </body>
    </html>
  );
}
