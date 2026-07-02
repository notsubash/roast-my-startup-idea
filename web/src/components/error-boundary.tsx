"use client";

import Link from "next/link";
import { Component, type ErrorInfo, type ReactNode } from "react";

import { heatCtaClass } from "@/lib/cta-classes";

type Props = {
  children: ReactNode;
  fallback?: ReactNode;
};

type State = {
  hasError: boolean;
};

export class ErrorBoundary extends Component<Props, State> {
  state: State = { hasError: false };

  static getDerivedStateFromError(): State {
    return { hasError: true };
  }

  componentDidCatch(error: Error, info: ErrorInfo) {
    console.error("ErrorBoundary caught:", error, info.componentStack);
  }

  render() {
    if (this.state.hasError) {
      return (
        this.props.fallback ?? (
          <div
            role="alert"
            className="mx-auto w-full max-w-3xl px-4 py-16 md:px-6"
          >
            <h1 className="font-sans text-title font-semibold leading-tight text-ink">
              Something went wrong
            </h1>
            <p className="mt-4 max-w-prose text-ink-muted">
              The page hit an unexpected error. Refresh to try again, or head back home.
            </p>
            <Link href="/" className={`mt-8 ${heatCtaClass} px-6`}>
              Back home
            </Link>
          </div>
        )
      );
    }

    return this.props.children;
  }
}
