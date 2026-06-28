import Link from "next/link";

import { heatCtaClass } from "@/lib/cta-classes";

import { HealthStatus } from "./health-status";

export function SkipLink() {
  return (
    <a
      href="#main"
      className="sr-only focus:not-sr-only focus:fixed focus:left-4 focus:top-4 focus:z-50 focus:inline-flex focus:min-h-11 focus:items-center focus:border-2 focus:border-ink focus:bg-card focus:px-4 focus:py-2 focus:font-sans focus:text-sm focus:font-semibold focus:text-ink focus:shadow-hard"
    >
      Skip to main content
    </a>
  );
}

export function AppHeader() {
  return (
    <header className="border-b-2 border-ink bg-paper">
      <div className="mx-auto grid max-w-[1200px] grid-cols-12 items-center gap-x-4 px-4 py-4 md:px-6 lg:px-8">
        <div className="col-span-8 sm:col-span-9">
          <Link
            href="/"
            className="font-serif text-xl font-semibold tracking-tight text-ink md:text-2xl"
          >
            Roast My Startup
          </Link>
        </div>
        <div className="col-span-4 flex justify-end sm:col-span-3">
          <Link href="/" className={heatCtaClass}>
            Roast an idea
          </Link>
        </div>
      </div>
    </header>
  );
}

export function AppFooter() {
  return (
    <footer className="mt-auto border-t border-rule-soft bg-paper-2">
      <div className="mx-auto flex max-w-[1200px] flex-wrap items-center justify-between gap-4 px-4 py-6 font-sans text-xs text-ink-muted md:px-6 lg:px-8">
        <p>Five judges. One verdict. Zero sugarcoating.</p>
        <HealthStatus />
      </div>
    </footer>
  );
}

export function EditorialContainer({
  children,
  className = "",
}: {
  children: React.ReactNode;
  className?: string;
}) {
  return (
    <div
      className={`mx-auto grid max-w-[1200px] grid-cols-12 gap-x-4 px-4 md:px-6 lg:px-8 ${className}`}
    >
      {children}
    </div>
  );
}
