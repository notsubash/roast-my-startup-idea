import Link from "next/link";

import { heatCtaClass } from "@/lib/cta-classes";

import { HealthStatus } from "./health-status";

export function SkipLink() {
  return (
    <a
      href="#main"
      className="sr-only focus:not-sr-only focus:fixed focus:left-4 focus:top-4 focus:z-50 focus:inline-flex focus:min-h-11 focus:items-center focus:rounded-ui focus:border focus:border-rule-soft focus:bg-card focus:px-4 focus:py-2 focus:font-sans focus:text-sm focus:font-semibold focus:text-ink focus:shadow-soft"
    >
      Skip to main content
    </a>
  );
}

export function AppHeader() {
  return (
    <header className="border-b border-rule-soft bg-card">
      <div className="mx-auto flex max-w-3xl flex-wrap items-center justify-between gap-x-4 gap-y-3 px-4 py-4 md:px-6">
        <Link
          href="/"
          className="font-sans text-lg font-semibold tracking-tight text-primary md:text-xl"
        >
          Roast My Startup
        </Link>
        <nav className="flex flex-wrap items-center gap-2 sm:gap-3" aria-label="Main">
          <Link
            href="/history"
            className="font-sans text-sm font-medium text-ink-muted underline-offset-4 transition-colors duration-200 hover:text-ink hover:underline"
          >
            History
          </Link>
          <Link
            href="/settings"
            className="font-sans text-sm font-medium text-ink-muted underline-offset-4 transition-colors duration-200 hover:text-ink hover:underline"
          >
            Settings
          </Link>
          <Link href="/" className={`${heatCtaClass} px-3 sm:px-4`}>
            <span className="sm:hidden">Review</span>
            <span className="hidden sm:inline">Review an idea</span>
          </Link>
        </nav>
      </div>
    </header>
  );
}

export function AppFooter() {
  return (
    <footer className="mt-auto border-t border-rule-soft bg-paper-2">
      <div className="mx-auto flex max-w-3xl flex-wrap items-center justify-between gap-4 px-4 py-6 font-sans text-xs text-ink-muted md:px-6">
        <p>Five judges. One verdict. Zero sugarcoating.</p>
        <HealthStatus />
      </div>
    </footer>
  );
}

/** Minimal single-column workflow container (product-realignment-plan §3). */
export function EditorialContainer({
  children,
  className = "",
}: {
  children: React.ReactNode;
  className?: string;
}) {
  return (
    <div className={`mx-auto w-full max-w-3xl px-4 md:px-6 ${className}`}>
      {children}
    </div>
  );
}
